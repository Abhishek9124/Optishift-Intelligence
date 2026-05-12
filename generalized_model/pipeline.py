"""
End-to-end pipeline orchestrator.

Runs every stage of the platform on a single CSV and writes all artifacts
plus the comprehensive REPORT.md.

Stages:
1. Data enrichment            — synthetic features (headcount, balances, panels)
2. Daily forecasting model    — train + select best of XGBoost/LGBM/CatBoost/RF/GBR
3. Anomaly detection          — Isolation Forest on enriched daily series
4. Per-employee classifier    — leave probability head with calibration
5. SHAP global explainability — for the daily regressor
6. Burnout risk scoring       — per-employee derived metric
7. Drift comparison           — vs prior run if metadata.pkl exists
8. Reporting                  — REPORT.md + plots

CLI:
    python pipeline.py --data <csv> --output <dir> [--gpu] [--as-of-date YYYY-MM-DD]
                       [--no-classifier] [--no-shap] [--no-anomaly] [--no-burnout]
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import joblib
import pandas as pd

LOG = logging.getLogger("pipeline")
if not LOG.handlers:
    _h = logging.StreamHandler(sys.stdout)
    _h.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s | %(message)s", "%H:%M:%S"))
    LOG.addHandler(_h)
LOG.setLevel(logging.INFO)


def main() -> int:
    p = argparse.ArgumentParser(description="End-to-end workforce analytics pipeline.")
    p.add_argument("--data", required=True, help="Path to leave CSV.")
    p.add_argument("--output", default="artifacts", help="Output directory.")
    p.add_argument("--forecast-horizon", type=int, default=30)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--as-of-date", default=None)
    p.add_argument("--gpu", action="store_true")
    p.add_argument("--no-classifier", action="store_true")
    p.add_argument("--no-shap", action="store_true")
    p.add_argument("--no-anomaly", action="store_true")
    p.add_argument("--no-burnout", action="store_true")
    args = p.parse_args()

    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)

    # Load prior metadata for drift comparison BEFORE we overwrite it
    prev_metadata = None
    if (out / "metadata.pkl").exists():
        try:
            prev_metadata = joblib.load(out / "metadata.pkl")
            LOG.info("Found prior model metadata for drift comparison.")
        except Exception:
            prev_metadata = None

    LOG.info(f"Loading {args.data}")
    raw = pd.read_csv(args.data, low_memory=False)
    LOG.info(f"  rows: {len(raw)}, cols: {len(raw.columns)}")

    # ─────────────────────── Stage 1: enrichment ────────────────────────
    from data_enrichment import enrich_dataset
    LOG.info("Stage 1: data enrichment (synthetic features)")
    enr = enrich_dataset(raw)
    daily_extras = enr["daily_extras"]
    employee_daily = enr["employee_daily"]
    enr["enriched_csv"].to_csv(out / "enriched_dataset.csv", index=False)
    daily_extras.to_csv(out / "daily_extras.csv", index=False)
    # Employee panel can be large; write parquet if pyarrow available
    try:
        employee_daily.to_parquet(out / "employee_daily.parquet", index=False)
    except Exception:
        employee_daily.to_csv(out / "employee_daily.csv", index=False)
    LOG.info(f"  daily_extras: {daily_extras.shape}, employee_daily: {employee_daily.shape}")

    # ─────────────────────── Stage 2: forecasting ───────────────────────
    from gen_training import TrainingConfig, train_model, save_model
    LOG.info("Stage 2: daily aggregate forecasting")
    cfg = TrainingConfig(
        seed=args.seed, forecast_horizon=args.forecast_horizon,
        use_gpu=args.gpu, gpu_device="cuda",
    )
    fc_result = train_model(
        raw, as_of_date=args.as_of_date,
        forecast_horizon=args.forecast_horizon, seed=args.seed,
        config=cfg, daily_extras=daily_extras,
    )
    save_model(fc_result, out)

    # ─────────────────────── Stage 3: anomaly ───────────────────────────
    anomaly_df = None
    if not args.no_anomaly:
        from anomaly import detect_anomalies
        LOG.info("Stage 3: anomaly detection")
        # The feature_df in the bundle has Leave_Count + the merged extras
        feat_df = fc_result["bundle"]["feature_df"]
        cols = ["Date", "Leave_Count"] + [c for c in
            ("Leave_Rate_Lag1", "Headcount_90d", "Dept_Stddev_Lag1", "Top_Dept_Share_Lag1")
            if c in feat_df.columns]
        anomaly_df = detect_anomalies(feat_df[cols])
        anomaly_df.to_csv(out / "anomalies.csv", index=False)
        LOG.info(f"  flagged: {int(anomaly_df['is_anomaly'].sum())} / {len(anomaly_df)}")

    # ─────────────────────── Stage 4: classifier ────────────────────────
    clf_result = None
    if not args.no_classifier:
        from classification import train_classifier, save_classifier, ClassifierConfig
        LOG.info("Stage 4: per-employee classifier")
        try:
            clf_result = train_classifier(
                raw, employee_daily, daily_extras=daily_extras,
                config=ClassifierConfig(seed=args.seed, use_gpu=args.gpu),
            )
            save_classifier(clf_result, out)
        except Exception as e:
            LOG.warning(f"Classifier failed: {e}")
            clf_result = None

    # ─────────────────────── Stage 5: SHAP ──────────────────────────────
    shap_global = None
    if not args.no_shap:
        try:
            from explainability import explain_global
            LOG.info("Stage 5: SHAP global importance for forecaster")
            X_test = fc_result["actual_vs_pred"][["Date"]].merge(
                fc_result["bundle"]["model_df"],  on="Date", how="left",
            )[fc_result["metadata"]["feature_columns"]].fillna(0).values
            shap_global = explain_global(
                fc_result["model"], X_test,
                fc_result["metadata"]["feature_columns"],
            )
            joblib.dump(shap_global, out / "shap_global.pkl")
        except Exception as e:
            LOG.warning(f"SHAP failed: {e}")
            shap_global = None

    # ─────────────────────── Stage 6: burnout ───────────────────────────
    burnout_df = None
    if not args.no_burnout:
        from burnout import compute_burnout_scores
        LOG.info("Stage 6: burnout risk scoring")
        try:
            burnout_df = compute_burnout_scores(
                raw, employee_daily,
                as_of_date=pd.Timestamp(args.as_of_date) if args.as_of_date else None,
            )
            burnout_df.to_csv(out / "burnout.csv", index=False)
            LOG.info(f"  scored: {len(burnout_df)} employees")
        except Exception as e:
            LOG.warning(f"Burnout failed: {e}")

    # ─────────────────────── Stage 7: drift ─────────────────────────────
    drift_report = None
    try:
        from drift import compute_drift, promotion_decision
        LOG.info("Stage 7: drift comparison")
        new_target = fc_result["bundle"]["model_df"]["Leave_Count"].values
        prev_target = None
        if prev_metadata is not None:
            # Use distribution stored in prev metadata if available; fall back to None
            prev_target = None  # we don't snapshot the series; relies on metric drift only
        drift_report = compute_drift(
            prev_metadata=prev_metadata,
            new_metadata=fc_result["metadata"],
            prev_target_series=prev_target,
            new_target_series=new_target,
        )
        decision = promotion_decision(drift_report)
        LOG.info(f"  promotion: {decision}")
        joblib.dump(drift_report, out / "drift_report.pkl")
    except Exception as e:
        LOG.warning(f"Drift comparison failed: {e}")

    # ─────────────────────── Stage 8: reporting ─────────────────────────
    from reporting import write_report
    LOG.info("Stage 8: writing comprehensive report")
    report_path = write_report(
        fc_result, out,
        classifier_result=clf_result,
        anomaly_df=anomaly_df,
        burnout_df=burnout_df,
        drift_report=drift_report,
        shap_global=shap_global,
    )

    LOG.info("=" * 60)
    LOG.info(f"DONE. Report: {report_path}")
    LOG.info(f"Best forecasting model: {fc_result['metadata']['best_model_name']} "
             f"(test WAPE={fc_result['metadata']['test_metrics']['WAPE']:.4f})")
    if clf_result:
        cm = clf_result["metadata"]["metrics"]
        LOG.info(f"Classifier: {clf_result['metadata']['family']} "
                 f"(AUC={cm['ROC_AUC']:.3f}, F1={cm['F1']:.3f})")
    LOG.info("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
