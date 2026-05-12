"""
Comprehensive evaluation report generator.

Produces:
- REPORT.md      — Markdown summary with all key metrics and findings
- plots/*.png    — PNG plots: actual-vs-predicted, residuals, calibration,
                   feature importance, model comparison

Plots use matplotlib (no plotly) to make them static / shareable.

Public API:
    write_report(result, output_dir, classifier_result=None,
                 anomaly_df=None, burnout_df=None, drift_report=None,
                 shap_global=None) -> Path
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

LOG = logging.getLogger("reporting")
if not LOG.handlers:
    import sys as _sys
    _h = logging.StreamHandler(_sys.stdout)
    _h.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s | %(message)s", "%H:%M:%S"))
    LOG.addHandler(_h)
LOG.setLevel(logging.INFO)


def _try_matplotlib():
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        return plt
    except Exception as e:
        LOG.warning(f"matplotlib unavailable: {e}")
        return None


def _plot_actual_vs_predicted(plt, avp: pd.DataFrame, out_path: Path) -> Path | None:
    if plt is None or avp is None or avp.empty:
        return None
    fig, ax = plt.subplots(2, 1, figsize=(11, 7), sharex=True,
                           gridspec_kw={"height_ratios": [3, 1]})
    ax[0].plot(avp["Date"], avp["Actual"], "-", color="#2c3e50", label="Actual", lw=1.6)
    ax[0].plot(avp["Date"], avp["Predicted"], "--", color="#e74c3c", label="Predicted", lw=1.6)
    if "Lower_Bound" in avp.columns and "Upper_Bound" in avp.columns:
        ax[0].fill_between(avp["Date"], avp["Lower_Bound"], avp["Upper_Bound"],
                           color="#3498db", alpha=0.15, label="90% Confidence")
    ax[0].set_ylabel("Daily Leave Count")
    ax[0].set_title("Actual vs Predicted (Test Period)")
    ax[0].legend(loc="upper right")
    ax[0].grid(alpha=0.25)
    ax[1].axhline(0, color="#7f8c8d", lw=1)
    ax[1].plot(avp["Date"], avp["Residual"], "-", color="#27ae60", lw=1.2)
    ax[1].fill_between(avp["Date"], 0, avp["Residual"], color="#27ae60", alpha=0.18)
    ax[1].set_ylabel("Residual")
    ax[1].set_xlabel("Date")
    ax[1].grid(alpha=0.25)
    fig.autofmt_xdate()
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    return out_path


def _plot_residual_histogram(plt, avp: pd.DataFrame, out_path: Path) -> Path | None:
    if plt is None or avp is None or avp.empty:
        return None
    fig, ax = plt.subplots(figsize=(8, 5))
    res = avp["Residual"].values
    ax.hist(res, bins=30, color="#3498db", edgecolor="white")
    ax.axvline(0, color="#2c3e50", lw=1.2)
    mu, sigma = np.mean(res), np.std(res)
    ax.set_title(f"Residual distribution (mean={mu:.1f}, sd={sigma:.1f})")
    ax.set_xlabel("Residual (Actual - Predicted)")
    ax.set_ylabel("Frequency")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    return out_path


def _plot_feature_importance(plt, fi: list[dict], out_path: Path, top: int = 20) -> Path | None:
    if plt is None or not fi:
        return None
    rows = fi[:top][::-1]
    feats = [r["feature"] for r in rows]
    vals = [r.get("importance", r.get("mean_abs_shap", 0)) for r in rows]
    fig, ax = plt.subplots(figsize=(8, max(4, 0.32 * len(feats))))
    ax.barh(feats, vals, color="#9b59b6")
    ax.set_xlabel("Importance")
    ax.set_title(f"Top {len(feats)} features")
    ax.grid(alpha=0.25, axis="x")
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    return out_path


def _plot_model_comparison(plt, candidates: dict, out_path: Path) -> Path | None:
    if plt is None or not candidates:
        return None
    names = list(candidates.keys())
    wapes = [candidates[n].get("cv_wape", float("nan")) for n in names]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    bars = ax.bar(names, wapes, color="#1abc9c")
    for bar, w in zip(bars, wapes):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                f"{w:.3f}", ha="center", va="bottom", fontsize=9)
    ax.set_ylabel("CV WAPE (lower is better)")
    ax.set_title("Candidate model comparison")
    ax.grid(alpha=0.25, axis="y")
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    return out_path


def _plot_calibration(plt, cal_curve: list[dict], out_path: Path) -> Path | None:
    if plt is None or not cal_curve:
        return None
    fig, ax = plt.subplots(figsize=(6, 6))
    xs = [c["mean_predicted"] for c in cal_curve]
    ys = [c["empirical_positive_rate"] for c in cal_curve]
    sizes = [max(20, c["n"] / 4) for c in cal_curve]
    ax.plot([0, 1], [0, 1], "--", color="#7f8c8d", label="Perfect calibration")
    ax.scatter(xs, ys, s=sizes, color="#e67e22", alpha=0.8, label="Observed")
    ax.set_xlabel("Mean predicted probability")
    ax.set_ylabel("Empirical positive rate")
    ax.set_title("Classifier calibration (reliability diagram)")
    ax.legend()
    ax.grid(alpha=0.25)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    return out_path


def _plot_anomalies(plt, anomaly_df: pd.DataFrame, out_path: Path) -> Path | None:
    if plt is None or anomaly_df is None or anomaly_df.empty:
        return None
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(anomaly_df["Date"], anomaly_df["Leave_Count"], "-", color="#34495e", lw=1.2, label="Daily leaves")
    flagged = anomaly_df[anomaly_df["is_anomaly"]]
    if not flagged.empty:
        ax.scatter(flagged["Date"], flagged["Leave_Count"], color="#e74c3c", s=40, zorder=5,
                   label=f"Anomalies ({len(flagged)})")
    ax.set_title("Anomaly detection on daily leave counts")
    ax.set_ylabel("Leave count")
    ax.legend()
    ax.grid(alpha=0.25)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    return out_path


def write_report(
    result: dict,
    output_dir,
    classifier_result: dict | None = None,
    anomaly_df: pd.DataFrame | None = None,
    burnout_df: pd.DataFrame | None = None,
    drift_report: dict | None = None,
    shap_global: dict | None = None,
) -> Path:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    plots_dir = out / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)
    plt = _try_matplotlib()

    md = result["metadata"]
    avp = result.get("actual_vs_pred")

    plot_paths = {
        "actual_vs_pred": _plot_actual_vs_predicted(plt, avp, plots_dir / "actual_vs_predicted.png"),
        "residual_hist": _plot_residual_histogram(plt, avp, plots_dir / "residual_histogram.png"),
        "feature_importance": _plot_feature_importance(plt, md.get("feature_importance", []),
                                                       plots_dir / "feature_importance.png"),
        "model_comparison": _plot_model_comparison(plt, md.get("candidate_scores", {}),
                                                   plots_dir / "model_comparison.png"),
    }
    if classifier_result:
        cmd = classifier_result["metadata"]
        plot_paths["calibration"] = _plot_calibration(plt, cmd.get("calibration_curve", []),
                                                      plots_dir / "calibration.png")
        plot_paths["clf_feature_importance"] = _plot_feature_importance(
            plt, cmd.get("feature_importance", []),
            plots_dir / "classifier_feature_importance.png",
        )
    if anomaly_df is not None and not anomaly_df.empty:
        plot_paths["anomalies"] = _plot_anomalies(plt, anomaly_df, plots_dir / "anomalies.png")

    # Build the markdown report
    L: list[str] = []
    L.append("# Workforce Analytics Evaluation Report")
    L.append("")
    L.append(f"_Generated: {md['trained_at']}_  ")
    L.append(f"_Data fingerprint: `{md['data_fingerprint']}`_")
    L.append("")
    L.append("## 1. Daily Leave Count Forecasting")
    L.append("")
    L.append(f"- Best model family: **{md['best_model_name']}**")
    L.append(f"- Forecast horizon: **{md['forecast_horizon']} days**")
    L.append(f"- Splits — train: {md['n_train']}, validation: {md['n_val']}, test: {md['n_test']}")
    L.append(f"- Test window: {md['test_start_date']} → {md['test_end_date']}")
    L.append("")
    L.append("### 1.1 Metrics")
    L.append("")
    L.append("| Split | MAE | RMSE | MAPE | R² | WAPE | SMAPE |")
    L.append("|-------|-----|------|------|-----|------|-------|")
    for split, m in [("Train", md["train_metrics"]), ("Validation", md["val_metrics"]), ("Test", md["test_metrics"])]:
        L.append(
            f"| {split} | {m['MAE']:.2f} | {m['RMSE']:.2f} | {m.get('MAPE', 0):.4f} | "
            f"{m['R2']:.3f} | {m['WAPE']:.4f} | {m['SMAPE']:.4f} |"
        )
    L.append("")
    L.append(f"- Conformal interval: **±{md['conformal_radius']:.2f}** at α={md['conformal_alpha']}")
    diag = md.get("diagnostics", {})
    if diag.get("model_vs_naive_lift") is not None:
        lift = diag["model_vs_naive_lift"] * 100
        L.append(f"- Lift over seasonal-naive baseline: **{lift:+.1f}%** "
                 f"(naive WAPE {diag.get('seasonal_naive_val_wape', 0):.4f})")
    if diag.get("warnings"):
        L.append("")
        L.append("**Diagnostic warnings:**")
        for w in diag["warnings"]:
            L.append(f"- ⚠️ {w}")
    L.append("")
    L.append("### 1.2 Candidate model comparison (cross-validated WAPE)")
    L.append("")
    L.append("| Model | CV WAPE | CV gap (val − train) |")
    L.append("|-------|---------|----------------------|")
    for name, sc in md.get("candidate_scores", {}).items():
        L.append(f"| {name} | {sc.get('cv_wape', float('nan')):.4f} | {sc.get('cv_gap', 0):.4f} |")
    L.append("")
    if plot_paths.get("model_comparison"):
        L.append(f"![Model comparison](plots/{plot_paths['model_comparison'].name})")
        L.append("")
    if plot_paths.get("actual_vs_pred"):
        L.append("### 1.3 Actual vs Predicted (Test Period)")
        L.append("")
        L.append(f"![Actual vs Predicted](plots/{plot_paths['actual_vs_pred'].name})")
        L.append("")
    if plot_paths.get("residual_hist"):
        L.append("### 1.4 Residual distribution")
        L.append("")
        L.append(f"![Residuals](plots/{plot_paths['residual_hist'].name})")
        L.append("")
    if plot_paths.get("feature_importance"):
        L.append("### 1.5 Feature importance (model-native)")
        L.append("")
        L.append(f"![Feature importance](plots/{plot_paths['feature_importance'].name})")
        L.append("")

    if shap_global and shap_global.get("available"):
        L.append("### 1.6 SHAP global importance")
        L.append("")
        L.append("| Feature | Mean \\|SHAP\\| |")
        L.append("|---------|----------------|")
        for fi in shap_global["mean_abs_shap"][:15]:
            L.append(f"| `{fi['feature']}` | {fi['mean_abs_shap']:.4f} |")
        L.append("")

    if classifier_result:
        cmd = classifier_result["metadata"]
        L.append("## 2. Per-Employee Leave Probability Classifier")
        L.append("")
        L.append(f"- Model family: **{cmd['family']}**")
        L.append(f"- Splits — train: {cmd['n_train']}, val: {cmd['n_val']}, test: {cmd['n_test']}")
        L.append(f"- Class balance correction (scale_pos_weight): {cmd['scale_pos_weight']:.2f}")
        L.append("")
        L.append("### 2.1 Metrics")
        L.append("")
        m = cmd["metrics"]
        L.append("| Metric | Value |")
        L.append("|--------|-------|")
        for k in ("Accuracy", "Precision", "Recall", "F1", "ROC_AUC", "Brier", "LogLoss", "Positive_Rate"):
            if k in m:
                L.append(f"| {k} | {m[k]:.4f} |")
        L.append("")
        if plot_paths.get("calibration"):
            L.append("### 2.2 Calibration (reliability diagram)")
            L.append("")
            L.append(f"![Calibration](plots/{plot_paths['calibration'].name})")
            L.append("")
        if plot_paths.get("clf_feature_importance"):
            L.append("### 2.3 Classifier feature importance")
            L.append("")
            L.append(f"![Classifier features](plots/{plot_paths['clf_feature_importance'].name})")
            L.append("")

    if anomaly_df is not None and not anomaly_df.empty:
        L.append("## 3. Anomaly Detection")
        L.append("")
        flagged = anomaly_df[anomaly_df["is_anomaly"]]
        L.append(f"- **{len(flagged)}** anomalous days flagged out of **{len(anomaly_df)}** total")
        L.append("")
        if plot_paths.get("anomalies"):
            L.append(f"![Anomalies](plots/{plot_paths['anomalies'].name})")
            L.append("")
        if not flagged.empty:
            L.append("### Top 15 anomalies by combined score")
            L.append("")
            L.append("| Date | Leave Count | Score | Reason |")
            L.append("|------|-------------|-------|--------|")
            top = flagged.nlargest(15, "Combined_Score")
            for _, r in top.iterrows():
                L.append(f"| {pd.Timestamp(r['Date']).date()} | {int(r['Leave_Count'])} | "
                         f"{r['Combined_Score']:.2f} | {r['anomaly_reason']} |")
            L.append("")

    if burnout_df is not None and not burnout_df.empty:
        L.append("## 4. Burnout Risk")
        L.append("")
        bands = burnout_df["Risk_Band"].value_counts().to_dict()
        L.append(f"- Low: {bands.get('Low', 0)}, Medium: {bands.get('Medium', 0)}, High: {bands.get('High', 0)}")
        L.append("")
        L.append("### Top 15 highest-risk employees")
        L.append("")
        L.append("| EmpNo | Score | Band | Days w/o leave | Balance | Recent (30d) |")
        L.append("|-------|-------|------|----------------|---------|--------------|")
        for _, r in burnout_df.head(15).iterrows():
            L.append(
                f"| {r['EmpNo']} | {r['Burnout_Score']:.0f} | {r['Risk_Band']} | "
                f"{int(r.get('Days_Since_Last_Leave', 0))} | "
                f"{r.get('Total_Leave_Balance', 0):.0f} | "
                f"{int(r.get('Leaves_Last_30d', 0))} |"
            )
        L.append("")

    if drift_report:
        L.append("## 5. Drift Monitoring")
        L.append("")
        if drift_report.get("data_drift"):
            for k, v in drift_report["data_drift"].items():
                L.append(f"- {k}: **{v:.4f}**")
        if drift_report.get("performance_drift"):
            for k, v in drift_report["performance_drift"].items():
                L.append(f"- {k}: **{v:.3f}**")
        if drift_report.get("warnings"):
            L.append("")
            L.append("**Drift warnings:**")
            for w in drift_report["warnings"]:
                L.append(f"- ⚠️ {w}")
        L.append(f"- **Promotable**: {drift_report.get('promotable', False)}")
        L.append("")

    L.append("## 6. Environment")
    L.append("")
    for k, v in md.get("env", {}).items():
        L.append(f"- {k}: `{v}`")
    L.append("")

    report_path = out / "REPORT.md"
    report_path.write_text("\n".join(L), encoding="utf-8")
    LOG.info(f"Report written: {report_path}")
    return report_path
