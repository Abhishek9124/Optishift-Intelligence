"""Generalized Leave Forecasting Dashboard — Upload any leave CSV to train & forecast."""
from __future__ import annotations

import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

warnings.filterwarnings("ignore")

try:
    from train_model import (
        build_feature_dataset, clean_leave_data, expand_to_daily,
        train_model, save_model, wape, smape, TARGET_COLUMN,
        add_calendar_features, add_lag_features, build_holiday_calendar,
    )
except ImportError:
    st.error("train_model.py must be in the same directory.")
    st.stop()

try:
    from indian_calendar import get_indian_festival_calendar
except ImportError:
    get_indian_festival_calendar = None


# ═══════════════════════════════════════════════════════════
# Helper: switchable chart type
# ═══════════════════════════════════════════════════════════
CHART_TYPES = ["Bar", "Line", "Area", "Scatter"]
CHART_TYPES_WITH_PIE = ["Bar", "Line", "Area", "Scatter", "Pie / Donut"]


def switchable_chart(
    df: pd.DataFrame,
    x: str,
    y: str,
    title: str,
    key: str,
    color: str | None = None,
    barmode: str = "stack",
    height: int = 420,
    default: str = "Bar",
    orientation: str = "v",
    show_pie: bool = False,
    color_scale: str | None = None,
    range_slider: bool = False,
    markers: bool = True,
):
    """Render a chart with a radio button to switch between Bar / Line / Area / Scatter / Pie."""
    options = CHART_TYPES_WITH_PIE if show_pie else CHART_TYPES
    default_idx = options.index(default) if default in options else 0

    chart_type = st.radio(
        "Chart Type",
        options=options,
        index=default_idx,
        horizontal=True,
        key=f"chart_switch_{key}",
    )

    common = dict(template="plotly_white", height=height, color_discrete_sequence=px.colors.qualitative.Set2)
    color_kw = {"color": color} if color else {}
    scale_kw = {"color_continuous_scale": color_scale} if color_scale and not color else {}

    if chart_type == "Bar":
        if orientation == "h":
            fig = px.bar(df, x=y, y=x, orientation="h", title=title, barmode=barmode, **color_kw, **scale_kw)
        else:
            fig = px.bar(df, x=x, y=y, title=title, barmode=barmode, **color_kw, **scale_kw)
    elif chart_type == "Line":
        fig = px.line(df, x=x, y=y, title=title, markers=markers, **color_kw)
    elif chart_type == "Area":
        fig = px.area(df, x=x, y=y, title=title, **color_kw)
    elif chart_type == "Scatter":
        fig = px.scatter(df, x=x, y=y, title=title, **color_kw)
    elif chart_type == "Pie / Donut" and show_pie:
        name_col = color if color else x
        fig = px.pie(df, names=name_col, values=y, title=title, hole=0.4)
        fig.update_traces(textposition="outside", textinfo="label+value+percent")
        fig.update_layout(height=height, showlegend=True, template="plotly_white")
        st.plotly_chart(fig, width="stretch")
        return

    fig.update_layout(**common)
    if range_slider:
        fig.update_layout(xaxis=dict(rangeslider=dict(visible=True, thickness=0.05)))
    st.plotly_chart(fig, width="stretch")


st.set_page_config(page_title="Generalized Leave Forecaster", layout="wide")
st.title("🚀 Generalized Leave Forecasting System")
st.caption("Upload any organization's leave data → Auto-train → Forecast → Analyse")

ARTIFACTS_DIR = Path(__file__).resolve().parent / "artifacts"

# ════════════════════════════════════════════════════════════════
# SIDEBAR — Upload & Train
# ════════════════════════════════════════════════════════════════
with st.sidebar:
    st.header("📂 Data Upload")
    uploaded_file = st.file_uploader(
        "Upload Leave CSV",
        type=["csv"],
        help="CSV must have columns: EmpNo, From Date, To Date, Status (Approved). Optional: Leave Type, Department, Cost Centre.",
    )
    st.divider()
    st.header("⚙️ Training Settings")
    forecast_horizon = st.number_input("Forecast Horizon (days)", min_value=7, max_value=90, value=30, step=7)

    train_btn = st.button("🚂 Train Model", type="primary", use_container_width=True)

    st.divider()
    st.header("📦 Load Saved Model")
    if (ARTIFACTS_DIR / "model.pkl").exists():
        load_saved = st.button("Load Saved Model", use_container_width=True)
    else:
        load_saved = False
        st.info("No saved model found. Upload data and train first.")


# ════════════════════════════════════════════════════════════════
# SESSION STATE
# ════════════════════════════════════════════════════════════════
if "trained_result" not in st.session_state:
    st.session_state["trained_result"] = None
if "raw_df" not in st.session_state:
    st.session_state["raw_df"] = None

# Load saved model
if load_saved and (ARTIFACTS_DIR / "model.pkl").exists():
    try:
        model = joblib.load(ARTIFACTS_DIR / "model.pkl")
        metadata = joblib.load(ARTIFACTS_DIR / "metadata.pkl")
        forecast_df = pd.read_csv(ARTIFACTS_DIR / "forecast.csv")
        forecast_df["Date"] = pd.to_datetime(forecast_df["Date"])
        st.session_state["trained_result"] = {
            "model": model, "metadata": metadata,
            "forecast_df": forecast_df,
            "test_metrics_df": pd.DataFrame([metadata.get("test_metrics", {})]),
        }
        st.sidebar.success("Saved model loaded!")
    except Exception as e:
        st.sidebar.error(f"Failed to load: {e}")

# Process uploaded file
if uploaded_file is not None:
    try:
        raw_df = pd.read_csv(uploaded_file, low_memory=False)
        st.session_state["raw_df"] = raw_df
    except Exception as e:
        st.error(f"Failed to read CSV: {e}")

# Train model
if train_btn:
    raw_df = st.session_state.get("raw_df")
    if raw_df is None:
        st.error("Please upload a CSV file first.")
    else:
        with st.spinner("Training model... This may take 1-3 minutes."):
            try:
                result = train_model(raw_df, forecast_horizon=int(forecast_horizon))
                save_model(result, ARTIFACTS_DIR)
                st.session_state["trained_result"] = result
                st.sidebar.success(f"✅ Trained {result['metadata']['best_model_name']} model!")
            except Exception as e:
                st.error(f"Training failed: {e}")


# ════════════════════════════════════════════════════════════════
# MAIN DASHBOARD
# ════════════════════════════════════════════════════════════════
result = st.session_state.get("trained_result")

if result is None:
    st.info("👈 Upload a CSV and click **Train Model** to get started, or load a saved model.")
    st.markdown("""
    ### Required CSV Columns
    | Column | Description |
    |--------|-------------|
    | `EmpNo` | Employee ID |
    | `From Date` | Leave start date |
    | `To Date` | Leave end date |
    | `Status` | Must contain "Approved" |

    ### Optional Columns
    `Leave Type`, `Department`, `Cost Centre`, `Leave Reason`, `Type` (Planned/Unplanned)
    """)
    st.stop()

metadata = result["metadata"]
forecast_df = result["forecast_df"]
test_metrics = result.get("test_metrics_df", pd.DataFrame())
raw_df = st.session_state.get("raw_df")

# Build expanded data for analytics if raw data available
full_exp = pd.DataFrame()
if raw_df is not None:
    try:
        clean = clean_leave_data(raw_df)
        full_exp = expand_to_daily(clean)
        full_exp["Date"] = pd.to_datetime(full_exp["Date"])
    except Exception:
        pass

tab_forecast, tab_data, tab_costcentre, tab_festival = st.tabs([
    "📈 Forecast", "📊 Data Explorer", "🏭 Cost Centre Analysis", "🗓️ Festival Calendar",
])


# ════════════════════════════════════════════════════════════════
# TAB 1 — Forecast
# ════════════════════════════════════════════════════════════════
with tab_forecast:
    st.subheader("Model Performance & Forecast")

    # Metrics
    if not test_metrics.empty:
        st.markdown("### Test Metrics")
        metric_cols = st.columns(5)
        for i, (col_name, fmt) in enumerate([
            ("MAE", "{:.2f}"), ("RMSE", "{:.2f}"), ("R2", "{:.3f}"),
            ("WAPE", "{:.2%}"), ("SMAPE", "{:.2%}")
        ]):
            if col_name in test_metrics.columns:
                metric_cols[i].metric(col_name, fmt.format(float(test_metrics[col_name].iloc[0])))

    st.markdown(f"**Best Model**: {metadata.get('best_model_name', 'Unknown')}")
    st.markdown(f"**Training End Date**: {metadata.get('training_end_date', 'N/A')}")

    # Forecast chart — switchable
    st.markdown("---")
    st.markdown(f"### Next {metadata.get('forecast_horizon', 30)} Days Forecast")

    if not forecast_df.empty:
        forecast_df["Date"] = pd.to_datetime(forecast_df["Date"])

        _fc_chart_type = st.radio("Chart Type", ["Line + Confidence Band", "Bar", "Area", "Scatter"],
            index=0, horizontal=True, key="forecast_chart_type")

        if _fc_chart_type == "Line + Confidence Band":
            fig = go.Figure()
            if "Upper_Bound" in forecast_df.columns:
                fig.add_trace(go.Scatter(x=forecast_df["Date"], y=forecast_df["Upper_Bound"],
                    mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip"))
                fig.add_trace(go.Scatter(x=forecast_df["Date"], y=forecast_df["Lower_Bound"],
                    mode="lines", line=dict(width=0), fill="tonexty", fillcolor="rgba(100,180,255,0.2)",
                    name="90% Confidence", hoverinfo="skip"))
            fig.add_trace(go.Scatter(x=forecast_df["Date"], y=forecast_df["Predicted_Leave_Count"],
                mode="lines+markers", name="Predicted Leave", line=dict(color="#0f4c5c", width=3)))
            fig.update_layout(title="Daily Leave Forecast", template="plotly_white",
                hovermode="x unified", height=450)
        elif _fc_chart_type == "Bar":
            fig = px.bar(forecast_df, x="Date", y="Predicted_Leave_Count", title="Daily Leave Forecast",
                template="plotly_white")
            fig.update_layout(height=450)
        elif _fc_chart_type == "Area":
            fig = px.area(forecast_df, x="Date", y="Predicted_Leave_Count", title="Daily Leave Forecast",
                template="plotly_white")
            fig.update_layout(height=450)
        else:
            fig = px.scatter(forecast_df, x="Date", y="Predicted_Leave_Count", title="Daily Leave Forecast",
                template="plotly_white", size="Predicted_Leave_Count")
            fig.update_layout(height=450)

        st.plotly_chart(fig, width="stretch")

        # Stats
        s1, s2, s3 = st.columns(3)
        s1.metric("Avg Daily Leave", f"{forecast_df['Predicted_Leave_Count'].mean():.0f}")
        peak = forecast_df.loc[forecast_df["Predicted_Leave_Count"].idxmax()]
        s2.metric("Peak Day", f"{peak['Date'].strftime('%a, %d %b')}")
        s3.metric("Total Employee-Days", f"{int(forecast_df['Predicted_Leave_Count'].sum())}")

        st.dataframe(forecast_df, hide_index=True, width="stretch")
    else:
        st.info("No forecast data available.")


# ════════════════════════════════════════════════════════════════
# TAB 2 — Data Explorer
# ════════════════════════════════════════════════════════════════
with tab_data:
    st.subheader("📊 Leave Data Explorer")

    if full_exp.empty:
        st.info("Upload data and train model to explore leave patterns.")
    else:
        _de_date_min = full_exp["Date"].min().date()
        _de_date_max = full_exp["Date"].max().date()
        _de_c1, _de_c2 = st.columns(2)
        with _de_c1:
            _de_start = st.date_input("From", value=_de_date_min, min_value=_de_date_min, max_value=_de_date_max, key="de_start")
        with _de_c2:
            _de_end = st.date_input("To", value=_de_date_max, min_value=_de_date_min, max_value=_de_date_max, key="de_end")

        _de_df = full_exp[(full_exp["Date"] >= pd.Timestamp(_de_start)) & (full_exp["Date"] <= pd.Timestamp(_de_end))].copy()

        if _de_df.empty:
            st.warning("No data for selected range.")
        else:
            k1, k2, k3 = st.columns(3)
            k1.metric("Total Leave Days", int(_de_df.shape[0]))
            k2.metric("Employees", int(_de_df["EmpNo"].nunique()))
            k3.metric("Avg/Day", f"{_de_df.groupby('Date')['EmpNo'].nunique().mean():.1f}")

            # Daily trend — switchable
            daily_trend = _de_df.groupby("Date")["EmpNo"].nunique().reset_index(name="Employees")
            switchable_chart(
                daily_trend, x="Date", y="Employees",
                title="Daily Employees on Leave", key="de_daily",
                default="Line", range_slider=True, height=400,
            )

            # Leave type breakdown — switchable (with pie)
            if "Leave Type" in _de_df.columns:
                lt_dist = _de_df["Leave Type"].value_counts().reset_index()
                lt_dist.columns = ["Leave Type", "Days"]
                switchable_chart(
                    lt_dist, x="Leave Type", y="Days",
                    title="Leave Type Distribution", key="de_lt",
                    default="Pie / Donut", show_pie=True, height=400,
                )


# ════════════════════════════════════════════════════════════════
# TAB 3 — Cost Centre Analysis
# ════════════════════════════════════════════════════════════════
with tab_costcentre:
    st.subheader("🏭 Cost Centre Leave Analysis")

    if full_exp.empty or "Cost Centre" not in full_exp.columns:
        st.info("Cost Centre data not available. Ensure your CSV has a 'Cost Centre' column.")
    else:
        _gcc_all = sorted(full_exp["Cost Centre"].dropna().unique().tolist())
        _gcc_sel = st.multiselect("Filter Cost Centres", options=_gcc_all, default=_gcc_all[:6] if len(_gcc_all) >= 6 else _gcc_all, key="gcc_sel")
        _gcc_gran = st.radio("Granularity", ["Daily", "Weekly", "Monthly"], index=2, horizontal=True, key="gcc_gran")

        _gcc_df = full_exp.copy()
        if _gcc_sel:
            _gcc_df = _gcc_df[_gcc_df["Cost Centre"].isin(_gcc_sel)]

        if _gcc_df.empty:
            st.info("No data.")
        else:
            if _gcc_gran == "Daily":
                _gcc_df["_P"] = _gcc_df["Date"].dt.normalize()
            elif _gcc_gran == "Weekly":
                _gcc_df["_P"] = _gcc_df["Date"].dt.to_period("W").apply(lambda p: p.start_time)
            else:
                _gcc_df["_P"] = _gcc_df["Date"].dt.to_period("M").apply(lambda p: p.start_time)

            _gcc_agg = _gcc_df.groupby(["_P", "Cost Centre"])["EmpNo"].nunique().reset_index(name="Employees")

            # Switchable chart
            switchable_chart(
                _gcc_agg, x="_P", y="Employees",
                title=f"{_gcc_gran} Leave by Cost Centre", key="gcc_main",
                color="Cost Centre", barmode="stack", height=450,
                default="Bar", show_pie=True,
            )

            # Summary table
            _gcc_summary = (
                _gcc_df.groupby("Cost Centre")
                .agg(Total_Days=("EmpNo", "size"), Employees=("EmpNo", "nunique"))
                .reset_index().sort_values("Employees", ascending=False)
            )
            st.dataframe(_gcc_summary, hide_index=True, width="stretch")


# ════════════════════════════════════════════════════════════════
# TAB 4 — Festival Calendar
# ════════════════════════════════════════════════════════════════
with tab_festival:
    st.subheader("🗓️ Indian Festival Calendar")

    if get_indian_festival_calendar is None:
        st.error("indian_calendar.py not found. Place it in the same directory.")
    else:
        _fc = get_indian_festival_calendar(2020, 2030)
        if _fc.empty:
            st.warning("No festival data.")
        else:
            _fc_s1, _fc_s2, _fc_s3 = st.columns([1, 1.5, 1.5])
            with _fc_s1:
                _fc_years = st.multiselect("Year", sorted(_fc["Year"].unique().tolist()), default=[pd.Timestamp.now().year], key="fc_yr")
            with _fc_s2:
                _fc_rel = st.multiselect("Religion", sorted(_fc["Religion"].unique().tolist()), default=[], key="fc_rel", placeholder="All")
            with _fc_s3:
                _fc_search = st.text_input("Search", key="fc_search", placeholder="e.g. Diwali")

            _fc_f = _fc.copy()
            if _fc_years:
                _fc_f = _fc_f[_fc_f["Year"].isin(_fc_years)]
            if _fc_rel:
                _fc_f = _fc_f[_fc_f["Religion"].isin(_fc_rel)]
            if _fc_search.strip():
                _fc_f = _fc_f[_fc_f["Festival"].str.contains(_fc_search.strip(), case=False, na=False)]

            if _fc_f.empty:
                st.info("No festivals match filters.")
            else:
                st.metric("Festivals Found", len(_fc_f))
                _fc_disp = _fc_f[["Date", "Festival", "Religion", "Is_Gazetted", "Day_Name"]].copy()
                _fc_disp["Date"] = _fc_disp["Date"].dt.strftime("%Y-%m-%d")
                st.dataframe(_fc_disp.rename(columns={"Is_Gazetted": "Gazetted", "Day_Name": "Day"}),
                    hide_index=True, width="stretch", height=400)

                # Festival density — switchable
                _fc_dens = _fc_f.groupby(["Month_Name", "Month"]).size().reset_index(name="Count").sort_values("Month")
                switchable_chart(
                    _fc_dens, x="Month_Name", y="Count",
                    title="Festivals per Month", key="fc_density",
                    default="Bar", height=350, show_pie=True,
                    color_scale="Oranges",
                )

                # Leave correlation
                if not full_exp.empty:
                    st.markdown("---")
                    st.markdown("### Leave Correlation with Festivals")
                    _fc_daily = full_exp.groupby("Date")["EmpNo"].nunique().reset_index(name="Leave")
                    _fc_daily["Date"] = pd.to_datetime(_fc_daily["Date"])
                    _fc_merge = _fc_f[["Date", "Festival"]].copy()
                    _fc_merge["Date"] = pd.to_datetime(_fc_merge["Date"])
                    _fc_merge = _fc_merge.merge(_fc_daily, on="Date", how="left").fillna(0)
                    _fc_merge["Leave"] = _fc_merge["Leave"].astype(int)
                    avg_leave = _fc_daily["Leave"].mean()
                    _fc_avg = _fc_merge.groupby("Festival")["Leave"].mean().reset_index().sort_values("Leave", ascending=False).head(15)
                    if not _fc_avg.empty:
                        switchable_chart(
                            _fc_avg.sort_values("Leave"),
                            x="Festival", y="Leave",
                            title=f"Avg Employees on Leave per Festival (org avg: {avg_leave:.0f})",
                            key="fc_corr", default="Bar", orientation="h",
                            height=max(300, len(_fc_avg) * 28),
                            color_scale="Reds",
                        )
