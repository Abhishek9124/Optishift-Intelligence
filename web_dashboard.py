from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
import re

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from flask import Flask, render_template, request

app = Flask(__name__)
BASE_DIR = Path(__file__).resolve().parent
CSV_PATH = BASE_DIR / "Data" / "Combined_All_Leave_Data.csv"
ARTIFACT_DIR = BASE_DIR / "artifacts"


def fig_to_html(fig: go.Figure) -> str:
    return fig.to_html(full_html=False, include_plotlyjs="cdn", config={"displaylogo": False})


def empty_table_html(columns: list[str] | None = None) -> str:
    cols = columns or ["Info"]
    df = pd.DataFrame([{cols[0]: "No data available for the selected filters."}])
    return df.to_html(classes="table", index=False)


def load_clean_data() -> pd.DataFrame:
    df = pd.read_csv(CSV_PATH)
    df.columns = [c.strip() for c in df.columns]
    for col in ["From Date", "To Date", "Applied On", "Approved On"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce", dayfirst=True)
    if "Status" in df.columns:
        df = df[df["Status"].astype(str).str.strip().eq("Approved")].copy()
    if "Days" in df.columns:
        df["Days"] = pd.to_numeric(df["Days"], errors="coerce").fillna(1)
    for col in ["Type", "Leave Type", "Cost Centre", "Department", "Leave Reason"]:
        if col in df.columns:
            df[col] = df[col].fillna("Unknown").astype(str).str.strip()
    df = df[df["From Date"].notna() & df["To Date"].notna()].copy()
    df = df[df["To Date"] >= df["From Date"]].copy()
    return df


def expand_leave_records(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in df.iterrows():
        for dt in pd.date_range(row["From Date"], row["To Date"], freq="D"):
            out = row.to_dict()
            out["Date"] = dt
            rows.append(out)
    expanded = pd.DataFrame(rows)
    expanded["Date"] = pd.to_datetime(expanded["Date"])
    expanded["Week"] = expanded["Date"] - pd.to_timedelta(expanded["Date"].dt.dayofweek, unit="D")
    expanded["Month"] = expanded["Date"].dt.to_period("M").astype(str)
    expanded["Day_of_Week"] = expanded["Date"].dt.day_name()
    expanded["day_of_week"] = expanded["Date"].dt.dayofweek
    return expanded


def parse_artifact_ts(path: Path) -> int:
    match = re.search(r"(\d{12})", path.name)
    return int(match.group(1)) if match else 0


def latest_artifact(pattern: str) -> Path | None:
    matches = list(ARTIFACT_DIR.glob(pattern))
    if not matches:
        return None
    return sorted(matches, key=parse_artifact_ts)[-1]


def latest_common_artifact_ts() -> int:
    metric_files = list(ARTIFACT_DIR.glob("*_test_metrics.csv"))
    pred_files = list(ARTIFACT_DIR.glob("*_test_predictions.csv"))
    imp_files = list(ARTIFACT_DIR.glob("*_feature_importance.csv"))
    next_files = list(ARTIFACT_DIR.glob("leave_forecast_next_*days_*.csv"))
    if not metric_files or not pred_files or not imp_files or not next_files:
        return 0

    metric_ts = {parse_artifact_ts(p) for p in metric_files}
    pred_ts = {parse_artifact_ts(p) for p in pred_files}
    imp_ts = {parse_artifact_ts(p) for p in imp_files}
    next_ts = {parse_artifact_ts(p) for p in next_files}
    common = sorted(metric_ts & pred_ts & imp_ts & next_ts)
    return common[-1] if common else 0


def load_forecast_artifacts() -> dict[str, pd.DataFrame]:
    common_ts = latest_common_artifact_ts()
    files = {}
    if common_ts:
        files = {
            "metrics": latest_artifact(f"*{common_ts}_test_metrics.csv"),
            "predictions": latest_artifact(f"*{common_ts}_test_predictions.csv"),
            "importance": latest_artifact(f"*{common_ts}_feature_importance.csv"),
            "next30": latest_artifact(f"leave_forecast_next_*days_{common_ts}.csv"),
        }
    if not files or any(v is None for v in files.values()):
        files = {
            "metrics": latest_artifact("*_test_metrics.csv"),
            "predictions": latest_artifact("*_test_predictions.csv"),
            "importance": latest_artifact("*_feature_importance.csv"),
            "next30": latest_artifact("leave_forecast_next_*days_*.csv"),
        }
    out = {}
    for key, fp in files.items():
        if fp and fp.exists():
            out[key] = pd.read_csv(fp)
        else:
            out[key] = pd.DataFrame()
    out["run_ts"] = pd.DataFrame([{"timestamp": parse_artifact_ts(files.get("metrics")) if files.get("metrics") else 0}])
    for col in ["Date"]:
        for key in ["predictions", "next30"]:
            if col in out[key].columns:
                out[key][col] = pd.to_datetime(out[key][col], errors="coerce")
    return out


@app.route("/", methods=["GET"])
def dashboard():
    raw = load_clean_data()
    expanded = expand_leave_records(raw)
    if expanded.empty:
        today = date.today()
        cards = {"days_covered": 0, "avg_emp_per_day": 0, "total_leave_days": 0, "cost_centres": 0}
        tables = {
            "daily": empty_table_html(["Daily Summary"]),
            "cost": empty_table_html(["Cost Centre Summary"]),
            "forecast": empty_table_html(["Forecast Window"]),
            "ctx_cc": empty_table_html(["Top Cost Centres"]),
            "ctx_reason": empty_table_html(["Top Leave Reasons"]),
        }
        return render_template(
            "dashboard.html",
            min_date=today,
            max_date=today,
            start_date=today,
            end_date=today,
            context_date=today,
            cards=cards,
            forecast_charts=[],
            intelligence_charts=[],
            special_charts=[],
            cost_charts=[],
            planned_charts=[],
            reason_charts=[],
            tables=tables,
        )

    min_date = expanded["Date"].min().date()
    max_date = expanded["Date"].max().date()
    default_end = min(max_date, datetime.now().date())
    default_start = max(min_date, default_end - timedelta(days=29))

    start_date = request.args.get("start_date", str(default_start))
    end_date = request.args.get("end_date", str(default_end))
    context_date = request.args.get("context_date", str(default_end))

    try:
        start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
    except ValueError:
        start_date = default_start
    try:
        end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
    except ValueError:
        end_date = default_end
    try:
        context_date = datetime.strptime(context_date, "%Y-%m-%d").date()
    except ValueError:
        context_date = default_end

    start_date = max(min_date, start_date)
    end_date = min(max_date, end_date)
    if start_date > end_date:
        start_date, end_date = end_date, start_date

    filt = expanded[(expanded["Date"] >= pd.Timestamp(start_date)) & (expanded["Date"] <= pd.Timestamp(end_date))].copy()
    artifacts = load_forecast_artifacts()

    daily_emp = filt.groupby("Date")["EmpNo"].nunique().reset_index(name="Employees")

    # Forecast tab equivalents
    forecast_charts = []
    metrics_df = artifacts["metrics"]
    if not metrics_df.empty and "Model" in metrics_df.columns:
        mt = metrics_df.melt(id_vars=["Model"], var_name="Metric", value_name="Value")
        forecast_charts.append(fig_to_html(px.bar(mt, x="Metric", y="Value", color="Model", title="Model Evaluation")))

    importance_df = artifacts["importance"]
    if not importance_df.empty and {"importance", "feature"}.issubset(importance_df.columns):
        top_imp = importance_df.sort_values("importance", ascending=False).head(15)
        forecast_charts.append(fig_to_html(px.bar(top_imp, x="importance", y="feature", orientation="h", title="Top Forecast Drivers")))

    pred_df = artifacts["predictions"]
    if not pred_df.empty and {"Date", "Actual_Leave_Count", "Predicted_Leave_Count"}.issubset(pred_df.columns):
        prev = pred_df.copy().sort_values("Date")
        fig_prev = go.Figure()
        fig_prev.add_trace(go.Scatter(x=prev["Date"], y=prev["Actual_Leave_Count"], name="Actual"))
        fig_prev.add_trace(go.Scatter(x=prev["Date"], y=prev["Predicted_Leave_Count"], name="Predicted"))
        fig_prev.update_layout(title="Previous Year: Actual vs Predicted Leave Count")
        forecast_charts.append(fig_to_html(fig_prev))

    next30 = artifacts["next30"]
    if not next30.empty and {"Date", "Predicted_Leave_Count"}.issubset(next30.columns):
        fig_n = go.Figure()
        fig_n.add_trace(go.Scatter(x=next30["Date"], y=next30["Predicted_Leave_Count"], name="Predicted"))
        if {"Lower_Bound", "Upper_Bound"}.issubset(next30.columns):
            fig_n.add_trace(go.Scatter(x=next30["Date"], y=next30["Upper_Bound"], line=dict(width=0), showlegend=False))
            fig_n.add_trace(go.Scatter(x=next30["Date"], y=next30["Lower_Bound"], line=dict(width=0), fill="tonexty", name="Confidence Band"))
        fig_n.update_layout(title="Future Leave Forecast")
        forecast_charts.append(fig_to_html(fig_n))

    # Intelligence tab equivalents
    intelligence_charts = []
    if not daily_emp.empty:
        intelligence_charts.append(fig_to_html(px.line(daily_emp, x="Date", y="Employees", markers=True, title="Leave Intelligence Trend")))

    if "Cost Centre" in filt.columns:
        risk = filt.groupby("Cost Centre")["EmpNo"].nunique().reset_index(name="Employees on Leave").sort_values("Employees on Leave", ascending=False).head(12)
        intelligence_charts.append(fig_to_html(px.bar(risk, x="Cost Centre", y="Employees on Leave", title="Cost Centre Risk")))

    lt_pat = filt.groupby("Leave Type")["EmpNo"].nunique().reset_index(name="Employees").sort_values("Employees", ascending=False).head(12)
    if not lt_pat.empty:
        intelligence_charts.append(fig_to_html(px.bar(lt_pat, x="Leave Type", y="Employees", title="Leave Type Patterns")))

    # Special tab equivalents
    special_charts = []
    special = filt[filt["Leave Type"].isin(["Special Leave [Not Call ON Duty]", "Comp-Off"])].copy()
    if not special.empty:
        wk = special.groupby(["Week", "Leave Type"])["EmpNo"].nunique().reset_index(name="Employees")
        special_charts.append(fig_to_html(px.line(wk, x="Week", y="Employees", color="Leave Type", title="Special Leave Weekly Trend")))
        mo = special.groupby(["Month", "Leave Type"])["EmpNo"].nunique().reset_index(name="Employees")
        special_charts.append(fig_to_html(px.bar(mo, x="Month", y="Employees", color="Leave Type", barmode="group", title="Special Leave Monthly Distribution")))
        dow_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        dow = special.groupby(["Day_of_Week", "Leave Type"])["EmpNo"].nunique().reset_index(name="Employees")
        dow["Day_of_Week"] = pd.Categorical(dow["Day_of_Week"], categories=dow_order, ordered=True)
        dow = dow.sort_values("Day_of_Week")
        special_charts.append(fig_to_html(px.bar(dow, x="Day_of_Week", y="Employees", color="Leave Type", title="Special Leave Day-of-Week Pattern")))

    # Cost centre tab equivalents
    cost_charts = []
    cc = (
        filt.groupby("Cost Centre").agg(Leave_Days=("EmpNo", "count"), Unique_Employees=("EmpNo", "nunique")).reset_index()
        if "Cost Centre" in filt.columns
        else pd.DataFrame()
    )
    if not cc.empty:
        cc_top = cc.sort_values("Leave_Days", ascending=False).head(15)
        cost_charts.append(fig_to_html(px.pie(cc_top, names="Cost Centre", values="Leave_Days", title="Cost Centre Leave Distribution")))
        cost_charts.append(fig_to_html(px.bar(cc_top, x="Cost Centre", y="Unique_Employees", title="Unique Employees on Leave by Cost Centre")))
        cost_charts.append(fig_to_html(px.treemap(cc_top, path=["Cost Centre"], values="Leave_Days", title="Cost Centre Leave Treemap")))

    cc_daily = (
        filt.groupby(["Date", "Cost Centre"])["EmpNo"].nunique().reset_index(name="Employees")
        if "Cost Centre" in filt.columns
        else pd.DataFrame()
    )
    if not cc_daily.empty:
        top_cc = cc_daily.groupby("Cost Centre")["Employees"].sum().nlargest(6).index
        cc_daily_top = cc_daily[cc_daily["Cost Centre"].isin(top_cc)]
        cost_charts.append(fig_to_html(px.line(cc_daily_top, x="Date", y="Employees", color="Cost Centre", title="Daily Employees by Cost Centre")))

    # Planned/unplanned equivalents
    planned_charts = []
    pu = filt[filt["Type"].isin(["Planned", "Un-Planned"])].copy()
    if not pu.empty:
        pu_share = pu.groupby("Type").size().reset_index(name="Days")
        planned_charts.append(fig_to_html(px.pie(pu_share, names="Type", values="Days", title="Planned vs Unplanned Share")))

        pu_lt = pu.groupby(["Leave Type", "Type"])["EmpNo"].nunique().reset_index(name="Employees")
        planned_charts.append(fig_to_html(px.bar(pu_lt, x="Leave Type", y="Employees", color="Type", barmode="group", title="Leave Type Split by Planned/Unplanned")))

        pu_daily_emp = pu.groupby(["Date", "Type"])["EmpNo"].nunique().reset_index(name="Employees")
        planned_charts.append(fig_to_html(px.bar(pu_daily_emp, x="Date", y="Employees", color="Type", barmode="stack", title="Daily Planned vs Unplanned Employees")))

        pu_week = pu.groupby(["Week", "Type"])["EmpNo"].nunique().reset_index(name="Employees")
        planned_charts.append(fig_to_html(px.bar(pu_week, x="Week", y="Employees", color="Type", barmode="group", title="Weekly Planned vs Unplanned Employees")))

        pu_month = pu.groupby(["Month", "Type"])["EmpNo"].nunique().reset_index(name="Employees")
        planned_charts.append(fig_to_html(px.line(pu_month, x="Month", y="Employees", color="Type", markers=True, title="Monthly Planned vs Unplanned Trend")))

    # Reason tab equivalents
    reason_charts = []
    reason_tables = {}
    if "Leave Reason" in filt.columns:
        top_reason = filt.groupby("Leave Reason").size().reset_index(name="Days").sort_values("Days", ascending=False).head(15)
        reason_charts.append(fig_to_html(px.bar(top_reason, x="Days", y="Leave Reason", orientation="h", title="Top 15 Leave Reasons")))

    lr_cc = (
        filt.groupby(["Cost Centre", "Leave Type"]).size().reset_index(name="Days")
        if {"Cost Centre", "Leave Type"}.issubset(filt.columns)
        else pd.DataFrame()
    )
    if not lr_cc.empty:
        reason_charts.append(fig_to_html(px.bar(lr_cc, x="Cost Centre", y="Days", color="Leave Type", barmode="stack", title="Leave Type by Cost Centre")))

    ctx = expanded[(expanded["Date"].dt.month == context_date.month) & (expanded["Date"].dt.dayofweek == context_date.weekday())]
    reason_tables["ctx_cc"] = (
        ctx.groupby("Cost Centre").size().reset_index(name="Days").sort_values("Days", ascending=False).head(8)
        if (not ctx.empty and "Cost Centre" in ctx.columns)
        else pd.DataFrame()
    )
    reason_tables["ctx_reason"] = (
        ctx.groupby("Leave Reason").size().reset_index(name="Days").sort_values("Days", ascending=False).head(8)
        if (not ctx.empty and "Leave Reason" in ctx.columns) else pd.DataFrame()
    )

    cards = {
        "days_covered": int((end_date - start_date).days + 1),
        "avg_emp_per_day": round(float(daily_emp["Employees"].mean()), 2) if not daily_emp.empty else 0,
        "total_leave_days": int(len(filt)),
        "cost_centres": int(filt["Cost Centre"].nunique()) if "Cost Centre" in filt.columns else 0,
        "model_run_ts": int(artifacts["run_ts"]["timestamp"].iloc[0]) if not artifacts["run_ts"].empty else 0,
    }

    tables = {
        "daily": daily_emp.head(30).to_html(classes="table", index=False) if not daily_emp.empty else empty_table_html(["Daily Summary"]),
        "cost": cc.sort_values("Leave_Days", ascending=False).head(30).to_html(classes="table", index=False) if not cc.empty else empty_table_html(["Cost Centre Summary"]),
        "forecast": next30.head(30).to_html(classes="table", index=False) if not next30.empty else empty_table_html(["Forecast Window"]),
        "ctx_cc": reason_tables["ctx_cc"].to_html(classes="table", index=False) if not reason_tables["ctx_cc"].empty else empty_table_html(["Top Cost Centres"]),
        "ctx_reason": reason_tables["ctx_reason"].to_html(classes="table", index=False) if not reason_tables["ctx_reason"].empty else empty_table_html(["Top Leave Reasons"]),
    }

    return render_template(
        "dashboard.html",
        min_date=min_date,
        max_date=max_date,
        start_date=start_date,
        end_date=end_date,
        context_date=context_date,
        cards=cards,
        forecast_charts=forecast_charts,
        intelligence_charts=intelligence_charts,
        special_charts=special_charts,
        cost_charts=cost_charts,
        planned_charts=planned_charts,
        reason_charts=reason_charts,
        tables=tables,
    )


if __name__ == "__main__":
    app.run(debug=True)
