# Workforce Analytics Platform

Production-grade leave forecasting + workforce intelligence on top of any
organization's leave CSV. Walk-forward validation, conformal prediction
intervals, per-employee classification, anomaly detection, burnout scoring,
SHAP explainability, drift monitoring, FastAPI service, and Streamlit dashboard
— all from a single CSV.

---

## Architecture

```
                  ┌──────────────────┐
   raw leave CSV →│ data_enrichment  │── synthetic features
                  └────────┬─────────┘
                           │
        ┌──────────────────┼──────────────────────────┐
        ▼                  ▼                          ▼
┌──────────────┐   ┌────────────────┐        ┌──────────────┐
│ gen_training │   │ classification │        │ data_extras  │
│  (regress.)  │   │ (per-employee) │        │  (daily)     │
└──────┬───────┘   └───────┬────────┘        └──────┬───────┘
       │                   │                        │
       ▼                   ▼                        ▼
┌──────────────┐    ┌──────────────┐         ┌─────────────┐
│   anomaly    │    │   burnout    │         │explainability│
│ (Iso Forest) │    │ (risk score) │         │   (SHAP)    │
└──────┬───────┘    └──────┬───────┘         └──────┬──────┘
       └──────────┬────────┴─────────────────┬──────┘
                  ▼                          ▼
            ┌──────────┐              ┌────────────┐
            │  drift   │              │ reporting  │
            │ (PSI/Δ)  │              │ REPORT.md  │
            └──────────┘              └─────┬──────┘
                                            ▼
                                   ┌──────────────────┐
                                   │ streamlit_app.py │ ← interactive UI
                                   │     api.py       │ ← REST endpoints
                                   └──────────────────┘
```

## Modules

| File | Responsibility |
|---|---|
| `gen_training.py` | Walk-forward CV, hyperparameter sweep, conformal intervals, GPU XGBoost, LightGBM/CatBoost/RF/GBR candidates |
| `data_enrichment.py` | Synthetic features: headcount-90d, leave-rate, leave-balance, tenure, recent-leave-intensity, dept mix |
| `classification.py` | Per-employee daily leave probability with class-weight + Platt calibration |
| `anomaly.py` | Isolation Forest + per-DOW robust z-score for unusual leave days |
| `explainability.py` | SHAP global + local; auto-picks Tree vs Kernel explainer |
| `burnout.py` | Composite burnout score from low-recent-usage, long streak, balance, unplanned spike, tenure |
| `drift.py` | Population Stability Index + performance regression gating |
| `reporting.py` | `REPORT.md` + PNG plots: actual-vs-predicted, residuals, calibration, importance, anomalies |
| `pipeline.py` | One command runs every stage end-to-end |
| `api.py` | FastAPI: `/forecast`, `/predict/employee`, `/anomalies`, `/burnout`, `/explain/global` |
| `streamlit_app.py` | Dashboard with 9 tabs covering every output |

---

## Install

```powershell
# from project root with venv active
.venv\Scripts\activate
pip install -r generalized_model\requirements.txt
```

The pipeline gracefully degrades if optional packages are missing — only one
of xgboost/lightgbm/catboost is strictly required.

---

## Run end-to-end

```powershell
cd generalized_model
python pipeline.py `
    --data ..\Combined_All_Leave_Data.csv `
    --output artifacts `
    --as-of-date 2026-02-28 `
    --forecast-horizon 30 `
    --gpu
```

Outputs into `artifacts/`:

```
model.pkl                   classifier.pkl
metadata.pkl                classifier_metadata.pkl
metadata.json               classifier_test_panel.csv
forecast.csv                anomalies.csv
actual_vs_predicted.csv     burnout.csv
shap_global.pkl             drift_report.pkl
daily_extras.csv            employee_daily.parquet
enriched_dataset.csv        MODEL_CARD.md
REPORT.md                   plots/*.png
```

`REPORT.md` is the human-readable summary — open it first.

---

## Run the dashboard

```powershell
streamlit run generalized_model\streamlit_app.py
```

Tabs:
1. **Overview** — headline metrics, candidate-model comparison, generalization warnings
2. **Forecast** — next-N-days forecast with 90% confidence band
3. **Actual vs Predicted** — held-out test window with residual histogram
4. **Per-Employee** — pick employee + date → leave probability + calibration plot
5. **Explainability** — native + SHAP feature importance + beeswarm
6. **Anomalies** — Isolation Forest + robust-z flagged days
7. **Burnout** — risk leaderboard + score distribution
8. **Drift** — promotion gate (PSI + WAPE/RMSE regression)
9. **Metadata** — full model card / metadata JSON

---

## Run the API

```powershell
cd generalized_model
uvicorn api:app --host 0.0.0.0 --port 8000
```

Visit `http://localhost:8000/docs` for Swagger.

Sample calls:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/forecast?days=14
curl -X POST http://localhost:8000/predict/employee \
     -H "Content-Type: application/json" \
     -d '{"emp_no":"40051088","target_date":"2026-03-15"}'
curl http://localhost:8000/anomalies?limit=10
curl http://localhost:8000/burnout?risk=High
```

---

## Required CSV columns

| Column | Required | Notes |
|---|---|---|
| `EmpNo` | yes | Employee ID |
| `From Date` | yes | Leave start (any common format) |
| `To Date` | yes | Leave end |
| `Status` | optional | If present, only `Approved` rows are kept |
| `Leave Type` | optional | Used for balance synthesis + analytics |
| `Department` | optional | Used for cohort features |
| `Cost Centre` | optional | Used for analytics |
| `Type` | optional | Planned/Unplanned — used by burnout |
| `Days`, `Applied On`, `Approved On` | optional | Used as features when present |

Minimum **~150 days** of history (model needs ≥ 90 rows after lag features).

---

## What the system honestly does and does not do

**Does:**
- Predict daily leave totals with calibrated confidence intervals.
- Predict per-employee P(leave on day D) with calibration check.
- Flag unusual leave days using two complementary detectors.
- Score every employee for burnout risk with explainable components.
- Detect when input data or model performance has drifted between runs.
- Tell you HONESTLY when the model isn't beating a seasonal-naive baseline.

**Does not:**
- Replace HR judgment for individual approvals.
- Predict things the data doesn't carry (project deadlines, individual life
  events, undisclosed health issues).
- Achieve high R² on noisy daily series — see the diagnostics output for
  whether the model is picking up real signal vs. matching noise.

The synthetic features (headcount proxy, balance, etc.) are derived from the
leave events themselves — they are NOT a substitute for a real HRIS feed of
active employees, joining dates, and entitlements. When such feeds are
available, replace the synthetic columns with real ones for substantially
better accuracy.

---

## Reproducibility

Every training run captures:
- Random seed
- Library versions (sklearn, xgboost, lightgbm, catboost, pandas, numpy)
- Data fingerprint (sha256 of shape + cols + sampled rows)
- Train/val/test split sizes and date ranges
- Conformal radius and α
- All candidate model CV scores

…in `metadata.json` and `MODEL_CARD.md`.

---

## Drift gating

After the second training run, `drift_report.pkl` is written. The report
flags:
- Target distribution PSI (warn ≥0.10, alert ≥0.25)
- Test WAPE regression vs prior (default tolerance 1.10×)
- Test RMSE regression vs prior (default tolerance 1.15×)

A new model is `promotable: true` only if no warnings fire. Wire this into
your CI to block bad rollouts.

---

## License

Internal use. Adapt freely.
