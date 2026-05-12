"""
Workforce Analytics Dashboard.

Single Streamlit app that surfaces:
- Daily leave forecasting + actual-vs-predicted
- Per-employee leave probability classifier
- Anomaly detection on historical days
- Burnout risk leaderboard
- SHAP global importance
- Drift status vs prior run
- Model card / metadata viewer

Loads artifacts produced by `pipeline.py` from `./artifacts/`.
"""
from __future__ import annotations

import warnings
from datetime import date, timedelta
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

warnings.filterwarnings("ignore")

# ──────────────────────────── Imports ────────────────────────────
try:
    from gen_training import (
        TrainingConfig, train_model, save_model, load_model,
        clean_leave_data, build_feature_dataset,
    )
except ImportError:
    st.error("gen_training.py not importable.")
    st.stop()

try:
    from data_enrichment import enrich_dataset, EnrichmentConfig
except ImportError:
    enrich_dataset = None  # type: ignore
    EnrichmentConfig = None  # type: ignore
try:
    from classification import (
        train_classifier, save_classifier, load_classifier,
        predict_employee_day, ClassifierConfig,
    )
except ImportError:
    train_classifier = None  # type: ignore
try:
    from anomaly import detect_anomalies
except ImportError:
    detect_anomalies = None  # type: ignore
try:
    from burnout import compute_burnout_scores
except ImportError:
    compute_burnout_scores = None  # type: ignore
try:
    from drift import compute_drift, promotion_decision
except ImportError:
    compute_drift = None  # type: ignore
try:
    from explainability import explain_global, explain_local
except ImportError:
    explain_global = None  # type: ignore

ARTIFACTS_DIR = Path(__file__).resolve().parent / "artifacts"
st.set_page_config(page_title="Workforce Analytics Platform", layout="wide", page_icon="📊")
st.title("Workforce Analytics Platform")
st.caption("Forecasting · Per-employee probability · Anomalies · Burnout · Explainability · Drift")


# ──────────────────────── Sidebar: data + train ────────────────────────
with st.sidebar:
    st.header("Data")
    uploaded_file = st.file_uploader("Leave CSV", type=["csv"])
    st.divider()
    st.header("Training")
    forecast_horizon = st.number_input("Forecast horizon (days)", 7, 90, 30, 7)
    use_gpu = st.checkbox("Use GPU (CUDA) for XGBoost", value=False)
    as_of_str = st.text_input("As-of date (YYYY-MM-DD)", value="",
                              help="Trim trailing sparse / forward-dated rows.")
    enable_classifier = st.checkbox("Train per-employee classifier", value=True)
    enable_anomaly = st.checkbox("Run anomaly detection", value=True)
    enable_burnout = st.checkbox("Compute burnout scores", value=True)
    enable_shap = st.checkbox("Compute SHAP global importance", value=True)
    train_btn = st.button("Train full pipeline", type="primary", use_container_width=True)
    st.divider()
    load_btn = (ARTIFACTS_DIR / "model.pkl").exists() and st.button("Load saved artifacts", use_container_width=True)


# ──────────────────────── Session state ────────────────────────
for k, v in {
    "raw_df": None, "trained": None, "enriched": None,
    "classifier_bundle": None, "anomaly_df": None, "burnout_df": None,
    "shap_global": None, "drift_report": None,
    "employee_daily": None, "daily_extras": None,
}.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ──────────────────────── Data loading ────────────────────────
if uploaded_file is not None:
    try:
        st.session_state["raw_df"] = pd.read_csv(uploaded_file, low_memory=False)
        st.sidebar.success(f"Loaded {len(st.session_state['raw_df'])} rows.")
    except Exception as e:
        st.error(f"Read CSV failed: {e}")


# ──────────────────────── Load saved artifacts ────────────────────────
if load_btn:
    try:
        bundle = load_model(ARTIFACTS_DIR)
        st.session_state["trained"] = bundle
        if (ARTIFACTS_DIR / "anomalies.csv").exists():
            adf = pd.read_csv(ARTIFACTS_DIR / "anomalies.csv")
            adf["Date"] = pd.to_datetime(adf["Date"])
            st.session_state["anomaly_df"] = adf
        if (ARTIFACTS_DIR / "burnout.csv").exists():
            st.session_state["burnout_df"] = pd.read_csv(ARTIFACTS_DIR / "burnout.csv")
        if (ARTIFACTS_DIR / "shap_global.pkl").exists():
            st.session_state["shap_global"] = joblib.load(ARTIFACTS_DIR / "shap_global.pkl")
        if (ARTIFACTS_DIR / "classifier.pkl").exists() and 'load_classifier' in dir():
            st.session_state["classifier_bundle"] = load_classifier(ARTIFACTS_DIR)
        if (ARTIFACTS_DIR / "drift_report.pkl").exists():
            st.session_state["drift_report"] = joblib.load(ARTIFACTS_DIR / "drift_report.pkl")
        if (ARTIFACTS_DIR / "employee_daily.parquet").exists():
            try:
                st.session_state["employee_daily"] = pd.read_parquet(ARTIFACTS_DIR / "employee_daily.parquet")
            except Exception:
                pass
        elif (ARTIFACTS_DIR / "employee_daily.csv").exists():
            ed = pd.read_csv(ARTIFACTS_DIR / "employee_daily.csv")
            ed["Date"] = pd.to_datetime(ed["Date"])
            st.session_state["employee_daily"] = ed
        if (ARTIFACTS_DIR / "daily_extras.csv").exists():
            de = pd.read_csv(ARTIFACTS_DIR / "daily_extras.csv")
            de["Date"] = pd.to_datetime(de["Date"])
            st.session_state["daily_extras"] = de
        st.sidebar.success("Artifacts loaded.")
    except Exception as e:
        st.sidebar.error(f"Load failed: {e}")


# ──────────────────────── Train pipeline ────────────────────────
def _run_full_pipeline(raw_df, forecast_horizon, as_of_date, use_gpu,
                       enable_classifier, enable_anomaly, enable_burnout, enable_shap):
    progress = st.progress(0.0, text="Stage 1/6: data enrichment")
    enr = enrich_dataset(raw_df) if enrich_dataset else {"daily_extras": pd.DataFrame(), "employee_daily": pd.DataFrame()}
    st.session_state["enriched"] = enr
    st.session_state["employee_daily"] = enr["employee_daily"]
    st.session_state["daily_extras"] = enr["daily_extras"]
    progress.progress(0.15, text="Stage 2/6: training daily forecaster")
    cfg = TrainingConfig(seed=42, forecast_horizon=int(forecast_horizon), use_gpu=bool(use_gpu))
    fc_result = train_model(
        raw_df, as_of_date=as_of_date, forecast_horizon=int(forecast_horizon),
        config=cfg, daily_extras=enr["daily_extras"],
    )
    save_model(fc_result, ARTIFACTS_DIR)
    if not enr["daily_extras"].empty:
        enr["daily_extras"].to_csv(ARTIFACTS_DIR / "daily_extras.csv", index=False)
    if not enr["employee_daily"].empty:
        try:
            enr["employee_daily"].to_parquet(ARTIFACTS_DIR / "employee_daily.parquet", index=False)
        except Exception:
            enr["employee_daily"].to_csv(ARTIFACTS_DIR / "employee_daily.csv", index=False)
    progress.progress(0.45)

    if enable_anomaly and detect_anomalies is not None:
        progress.progress(0.55, text="Stage 3/6: anomaly detection")
        feat_df = fc_result["bundle"]["feature_df"]
        cols = ["Date", "Leave_Count"] + [c for c in
            ("Leave_Rate_Lag1", "Headcount_90d", "Dept_Stddev_Lag1", "Top_Dept_Share_Lag1")
            if c in feat_df.columns]
        adf = detect_anomalies(feat_df[cols])
        adf.to_csv(ARTIFACTS_DIR / "anomalies.csv", index=False)
        st.session_state["anomaly_df"] = adf

    if enable_classifier and train_classifier is not None and not enr["employee_daily"].empty:
        progress.progress(0.65, text="Stage 4/6: per-employee classifier")
        try:
            clf_result = train_classifier(
                raw_df, enr["employee_daily"], daily_extras=enr["daily_extras"],
                config=ClassifierConfig(use_gpu=bool(use_gpu)),
            )
            save_classifier(clf_result, ARTIFACTS_DIR)
            st.session_state["classifier_bundle"] = {
                "model": clf_result["model"], "metadata": clf_result["metadata"],
            }
        except Exception as e:
            st.warning(f"Classifier training failed: {e}")

    if enable_shap and explain_global is not None:
        progress.progress(0.78, text="Stage 5/6: SHAP global importance")
        try:
            X = fc_result["bundle"]["model_df"][fc_result["metadata"]["feature_columns"]].fillna(0).values
            sg = explain_global(fc_result["model"], X, fc_result["metadata"]["feature_columns"])
            joblib.dump(sg, ARTIFACTS_DIR / "shap_global.pkl")
            st.session_state["shap_global"] = sg
        except Exception as e:
            st.warning(f"SHAP failed: {e}")

    if enable_burnout and compute_burnout_scores is not None and not enr["employee_daily"].empty:
        progress.progress(0.88, text="Stage 6/6: burnout scoring")
        try:
            bdf = compute_burnout_scores(
                raw_df, enr["employee_daily"],
                as_of_date=pd.Timestamp(as_of_date) if as_of_date else None,
            )
            bdf.to_csv(ARTIFACTS_DIR / "burnout.csv", index=False)
            st.session_state["burnout_df"] = bdf
        except Exception as e:
            st.warning(f"Burnout scoring failed: {e}")

    progress.progress(1.0, text="Done.")
    progress.empty()
    return fc_result


if train_btn:
    raw_df = st.session_state.get("raw_df")
    if raw_df is None:
        st.error("Upload a CSV first.")
    else:
        with st.spinner("Training pipeline... 1–4 minutes typical."):
            try:
                fc_result = _run_full_pipeline(
                    raw_df, forecast_horizon, as_of_str.strip() or None, use_gpu,
                    enable_classifier, enable_anomaly, enable_burnout, enable_shap,
                )
                st.session_state["trained"] = {
                    "model": fc_result["model"],
                    "metadata": fc_result["metadata"],
                    "forecast_df": fc_result["forecast_df"],
                    "test_metrics_df": fc_result["test_metrics_df"],
                    "actual_vs_pred": fc_result.get("actual_vs_pred"),
                }
                st.sidebar.success(f"Trained {fc_result['metadata']['best_model_name']}!")
            except Exception as e:
                st.error(f"Training failed: {e}")


# ──────────────────────── Main UI ────────────────────────
trained = st.session_state.get("trained")
if trained is None:
    st.info("← Upload a CSV and click **Train full pipeline**, or **Load saved artifacts**.")
    st.markdown("""
    ### Required CSV columns
    `EmpNo`, `From Date`, `To Date` (and ideally `Status`, `Leave Type`, `Department`, `Cost Centre`, `Type`)
    """)
    st.stop()

md = trained["metadata"]
forecast_df = trained.get("forecast_df", pd.DataFrame())
avp = trained.get("actual_vs_pred")
clf_bundle = st.session_state.get("classifier_bundle")
anomaly_df = st.session_state.get("anomaly_df")
burnout_df = st.session_state.get("burnout_df")
shap_global = st.session_state.get("shap_global")
drift_report = st.session_state.get("drift_report")

tab_overview, tab_forecast, tab_avp, tab_classifier, tab_explain, tab_anomaly, tab_burnout, tab_drift, tab_meta = st.tabs([
    "Overview", "Forecast", "Actual vs Predicted", "Per-Employee", "Explainability",
    "Anomalies", "Burnout", "Drift", "Metadata",
])


# ──────────────── Overview ────────────────
with tab_overview:
    st.subheader("Headline metrics")
    cols = st.columns(5)
    tm = md.get("test_metrics", {})
    cols[0].metric("Best model", md.get("best_model_name", "?"))
    cols[1].metric("Test MAE", f"{tm.get('MAE', 0):.2f}")
    cols[2].metric("Test RMSE", f"{tm.get('RMSE', 0):.2f}")
    cols[3].metric("Test WAPE", f"{tm.get('WAPE', 0):.2%}")
    cols[4].metric("Test R²", f"{tm.get('R2', 0):.3f}")

    diag = md.get("diagnostics", {})
    if diag.get("warnings"):
        for w in diag["warnings"]:
            st.warning(w)
    else:
        st.success("No over/underfitting warnings — generalization is healthy.")
    if diag.get("model_vs_naive_lift") is not None:
        st.info(f"Lift over seasonal-naive baseline: **{diag['model_vs_naive_lift']:+.1%}** "
                f"(baseline WAPE {diag.get('seasonal_naive_val_wape', 0):.4f})")

    train_m = md.get("train_metrics") or {}
    val_m = md.get("val_metrics") or {}
    cmp_df = pd.DataFrame({
        "Split": ["Train", "Validation", "Test"],
        "MAE": [train_m.get("MAE", np.nan), val_m.get("MAE", np.nan), tm.get("MAE", np.nan)],
        "RMSE": [train_m.get("RMSE", np.nan), val_m.get("RMSE", np.nan), tm.get("RMSE", np.nan)],
        "WAPE": [train_m.get("WAPE", np.nan), val_m.get("WAPE", np.nan), tm.get("WAPE", np.nan)],
        "R2": [train_m.get("R2", np.nan), val_m.get("R2", np.nan), tm.get("R2", np.nan)],
    })
    st.dataframe(cmp_df, hide_index=True, width="stretch")

    st.markdown("#### Candidate model comparison")
    cands = md.get("candidate_scores", {})
    if cands:
        crows = [{"Model": n, "CV WAPE": s.get("cv_wape", float("nan")),
                  "CV gap": s.get("cv_gap", 0)} for n, s in cands.items()]
        cdf = pd.DataFrame(crows).sort_values("CV WAPE")
        fig = px.bar(cdf, x="Model", y="CV WAPE", color="CV WAPE",
                     color_continuous_scale="Tealgrn_r", template="plotly_white",
                     title="Walk-forward CV WAPE (lower is better)")
        st.plotly_chart(fig, width="stretch")
        st.dataframe(cdf, hide_index=True, width="stretch")


# ──────────────── Forecast ────────────────
with tab_forecast:
    st.subheader(f"Next {md.get('forecast_horizon', 30)} days forecast")
    if not forecast_df.empty:
        forecast_df = forecast_df.copy()
        forecast_df["Date"] = pd.to_datetime(forecast_df["Date"])
        fig = go.Figure()
        if "Upper_Bound" in forecast_df:
            fig.add_trace(go.Scatter(x=forecast_df["Date"], y=forecast_df["Upper_Bound"],
                                     mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip"))
            fig.add_trace(go.Scatter(x=forecast_df["Date"], y=forecast_df["Lower_Bound"],
                                     mode="lines", line=dict(width=0), fill="tonexty",
                                     fillcolor="rgba(64,180,255,0.18)",
                                     name="90% Confidence", hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=forecast_df["Date"], y=forecast_df["Predicted_Leave_Count"],
                                 mode="lines+markers", name="Predicted",
                                 line=dict(color="#0f4c5c", width=3)))
        fig.update_layout(template="plotly_white", height=460, hovermode="x unified",
                          title="Daily Leave Forecast")
        st.plotly_chart(fig, width="stretch")
        c1, c2, c3 = st.columns(3)
        c1.metric("Avg/day", f"{forecast_df['Predicted_Leave_Count'].mean():.0f}")
        peak = forecast_df.loc[forecast_df['Predicted_Leave_Count'].idxmax()]
        c2.metric("Peak day", peak['Date'].strftime('%a, %d %b'))
        c3.metric("Total emp-days", int(forecast_df['Predicted_Leave_Count'].sum()))
        st.dataframe(forecast_df, hide_index=True, width="stretch")


# ──────────────── Actual vs Predicted ────────────────
with tab_avp:
    st.subheader("Actual vs Predicted (test window)")
    if avp is not None and not avp.empty:
        avp = avp.copy()
        avp["Date"] = pd.to_datetime(avp["Date"])
        fig = go.Figure()
        if "Upper_Bound" in avp:
            fig.add_trace(go.Scatter(x=avp["Date"], y=avp["Upper_Bound"], mode="lines",
                                     line=dict(width=0), showlegend=False, hoverinfo="skip"))
            fig.add_trace(go.Scatter(x=avp["Date"], y=avp["Lower_Bound"], mode="lines",
                                     line=dict(width=0), fill="tonexty",
                                     fillcolor="rgba(64,180,255,0.15)", name="90% CI", hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=avp["Date"], y=avp["Actual"], mode="lines",
                                 name="Actual", line=dict(color="#2c3e50", width=2.5)))
        fig.add_trace(go.Scatter(x=avp["Date"], y=avp["Predicted"], mode="lines",
                                 name="Predicted", line=dict(color="#e74c3c", width=2.5, dash="dash")))
        fig.update_layout(template="plotly_white", height=460, hovermode="x unified")
        st.plotly_chart(fig, width="stretch")

        st.markdown("#### Residuals")
        rfig = px.histogram(avp, x="Residual", nbins=30, template="plotly_white",
                            color_discrete_sequence=["#3498db"])
        rfig.update_layout(height=320, title=f"Mean={avp['Residual'].mean():.1f}, Sd={avp['Residual'].std():.1f}")
        st.plotly_chart(rfig, width="stretch")
        st.dataframe(avp.head(50), hide_index=True, width="stretch")
    else:
        st.info("Re-train to compute Actual vs Predicted.")


# ──────────────── Per-employee classifier ────────────────
with tab_classifier:
    st.subheader("Per-employee leave probability")
    if clf_bundle is None:
        st.info("Train with 'Per-employee classifier' enabled to use this tab.")
    else:
        cm = clf_bundle["metadata"]["metrics"]
        cols = st.columns(6)
        cols[0].metric("Family", clf_bundle["metadata"]["family"])
        cols[1].metric("Accuracy", f"{cm['Accuracy']:.3f}")
        cols[2].metric("F1", f"{cm['F1']:.3f}")
        cols[3].metric("ROC AUC", f"{cm['ROC_AUC']:.3f}")
        cols[4].metric("Brier", f"{cm['Brier']:.4f}")
        cols[5].metric("Pos. rate", f"{cm['Positive_Rate']:.3f}")

        ed = st.session_state.get("employee_daily")
        de = st.session_state.get("daily_extras")

        if ed is not None and not ed.empty:
            with st.form("predict_form"):
                emp_options = sorted(ed["EmpNo"].astype(str).unique().tolist())[:5000]
                emp = st.selectbox("Employee", emp_options)
                tgt = st.date_input("Target date", value=date.today() + timedelta(days=7))
                submit = st.form_submit_button("Predict", type="primary")
                if submit:
                    res = predict_employee_day(clf_bundle, emp, pd.Timestamp(tgt), ed, de)
                    st.success(f"P(leave) = {res['leave_probability']:.3f} → "
                               f"{'will likely take leave' if res['predicted_label'] else 'will likely work'}")

        cal = clf_bundle["metadata"].get("calibration_curve") or []
        if cal:
            cdf = pd.DataFrame(cal)
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode="lines",
                                     line=dict(color="#7f8c8d", dash="dash"), name="Perfect"))
            fig.add_trace(go.Scatter(x=cdf["mean_predicted"], y=cdf["empirical_positive_rate"],
                                     mode="markers+lines", name="Observed",
                                     marker=dict(size=10 + np.sqrt(cdf["n"]).clip(2, 20))))
            fig.update_layout(title="Calibration (reliability) diagram",
                              xaxis_title="Mean predicted probability",
                              yaxis_title="Empirical positive rate",
                              template="plotly_white", height=420)
            st.plotly_chart(fig, width="stretch")


# ──────────────── Explainability ────────────────
with tab_explain:
    st.subheader("Feature importance")
    fi = md.get("feature_importance", [])
    if fi:
        fi_df = pd.DataFrame(fi).head(20)
        fig = px.bar(fi_df.iloc[::-1], x="importance", y="feature", orientation="h",
                     template="plotly_white", title="Native model feature importance",
                     color="importance", color_continuous_scale="Magma")
        fig.update_layout(height=520)
        st.plotly_chart(fig, width="stretch")
    if shap_global and shap_global.get("available"):
        st.subheader("SHAP global importance")
        sdf = pd.DataFrame(shap_global["mean_abs_shap"]).head(20)
        fig = px.bar(sdf.iloc[::-1], x="mean_abs_shap", y="feature", orientation="h",
                     template="plotly_white", color="mean_abs_shap",
                     color_continuous_scale="Tealgrn", title="SHAP |mean| values")
        fig.update_layout(height=520)
        st.plotly_chart(fig, width="stretch")
        if "beeswarm_data" in shap_global and shap_global["beeswarm_data"]:
            bdf = pd.DataFrame(shap_global["beeswarm_data"])
            fig = px.scatter(bdf, x="shap_value", y="feature", color="feature_value",
                             template="plotly_white", color_continuous_scale="RdBu",
                             title="SHAP beeswarm (top 15 features)")
            fig.update_layout(height=620, showlegend=False)
            st.plotly_chart(fig, width="stretch")
    else:
        st.info("SHAP not yet computed. Re-train with SHAP enabled.")


# ──────────────── Anomalies ────────────────
with tab_anomaly:
    st.subheader("Daily anomaly detection")
    if anomaly_df is not None and not anomaly_df.empty:
        adf = anomaly_df.copy()
        adf["Date"] = pd.to_datetime(adf["Date"])
        flagged = adf[adf["is_anomaly"]]
        c1, c2, c3 = st.columns(3)
        c1.metric("Days analyzed", len(adf))
        c2.metric("Flagged anomalies", len(flagged))
        c3.metric("Anomaly rate", f"{len(flagged) / max(len(adf), 1):.1%}")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=adf["Date"], y=adf["Leave_Count"], mode="lines",
                                 name="Daily leaves", line=dict(color="#34495e", width=1.5)))
        if not flagged.empty:
            fig.add_trace(go.Scatter(x=flagged["Date"], y=flagged["Leave_Count"], mode="markers",
                                     name="Anomalies", marker=dict(color="#e74c3c", size=10),
                                     text=flagged["anomaly_reason"], hovertemplate="%{x}<br>Leaves: %{y}<br>%{text}"))
        fig.update_layout(template="plotly_white", height=460, hovermode="x unified")
        st.plotly_chart(fig, width="stretch")
        st.dataframe(flagged.sort_values("Combined_Score", ascending=False).head(50),
                     hide_index=True, width="stretch")
    else:
        st.info("No anomalies computed. Re-train with anomaly detection enabled.")


# ──────────────── Burnout ────────────────
with tab_burnout:
    st.subheader("Burnout risk scoring")
    if burnout_df is not None and not burnout_df.empty:
        bdf = burnout_df.copy()
        c1, c2, c3 = st.columns(3)
        c1.metric("High risk", int((bdf["Risk_Band"] == "High").sum()))
        c2.metric("Medium risk", int((bdf["Risk_Band"] == "Medium").sum()))
        c3.metric("Low risk", int((bdf["Risk_Band"] == "Low").sum()))

        fig = px.histogram(bdf, x="Burnout_Score", color="Risk_Band", nbins=30,
                           template="plotly_white", color_discrete_map={
                               "Low": "#2ecc71", "Medium": "#f39c12", "High": "#e74c3c"
                           })
        fig.update_layout(height=380, title="Score distribution")
        st.plotly_chart(fig, width="stretch")

        st.markdown("#### Top 30 highest-risk employees")
        st.dataframe(bdf.head(30), hide_index=True, width="stretch")
    else:
        st.info("No burnout scores yet. Re-train with burnout enabled.")


# ──────────────── Drift ────────────────
with tab_drift:
    st.subheader("Drift status")
    if drift_report is None:
        st.info("Drift compares against the prior model run. Run the pipeline twice to populate this tab.")
    else:
        promotable = drift_report.get("promotable", False)
        if promotable:
            st.success("✓ All drift checks passed — model is promotable.")
        else:
            st.error("✗ Promotion blocked.")
            for w in drift_report.get("warnings", []):
                st.warning(w)
        st.json(drift_report, expanded=False)


# ──────────────── Metadata ────────────────
with tab_meta:
    st.subheader("Training metadata")
    md_clean = {k: v for k, v in md.items() if k != "forecast"}
    st.json(md_clean, expanded=False)
