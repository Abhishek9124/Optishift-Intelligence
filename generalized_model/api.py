"""
FastAPI prediction service for the leave forecasting platform.

Endpoints:
    GET  /                           — service banner
    GET  /health                     — liveness + loaded artifact info
    GET  /forecast?days=30           — daily aggregate forecast for next N days
    POST /predict/employee           — per-employee leave probability for a date
    GET  /anomalies                  — anomaly-flagged historical days (latest run)
    GET  /burnout                    — burnout risk scores (latest run)
    GET  /metadata                   — full training metadata
    GET  /explain/global?top=15      — global SHAP feature importance (cached)

Run:
    uvicorn api:app --host 0.0.0.0 --port 8000

Notes:
- Loads artifacts from `ARTIFACTS_DIR` (env var or ./artifacts).
- Endpoints are read-only — retraining is intentionally not exposed via HTTP.
- For production, put this behind your reverse proxy with TLS + auth.
"""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

ARTIFACTS_DIR = Path(os.environ.get("ARTIFACTS_DIR", str(Path(__file__).resolve().parent / "artifacts")))

try:
    from fastapi import FastAPI, HTTPException, Query
    from pydantic import BaseModel, Field
    FASTAPI_OK = True
except ImportError:
    FASTAPI_OK = False
    FastAPI = None  # type: ignore
    BaseModel = object  # type: ignore

if FASTAPI_OK:
    app = FastAPI(
        title="Workforce Analytics API",
        description="Leave forecasting, per-employee probability, anomalies, burnout.",
        version="1.0.0",
    )

    # ─── In-memory cache of loaded artifacts ──────────────────────────────
    _STATE: dict[str, Any] = {
        "model": None, "metadata": None, "forecast_df": None,
        "classifier": None, "classifier_meta": None,
        "anomaly_df": None, "burnout_df": None,
        "shap_global": None,
        "employee_daily": None, "daily_extras": None,
    }

    def _load_state(force: bool = False) -> None:
        if _STATE["model"] is not None and not force:
            return
        if not ARTIFACTS_DIR.exists():
            raise RuntimeError(f"Artifacts dir not found: {ARTIFACTS_DIR}")
        _STATE["model"] = joblib.load(ARTIFACTS_DIR / "model.pkl")
        _STATE["metadata"] = joblib.load(ARTIFACTS_DIR / "metadata.pkl")
        if (ARTIFACTS_DIR / "forecast.csv").exists():
            fc = pd.read_csv(ARTIFACTS_DIR / "forecast.csv")
            if "Date" in fc.columns:
                fc["Date"] = pd.to_datetime(fc["Date"])
            _STATE["forecast_df"] = fc
        if (ARTIFACTS_DIR / "classifier.pkl").exists():
            _STATE["classifier"] = joblib.load(ARTIFACTS_DIR / "classifier.pkl")
            _STATE["classifier_meta"] = joblib.load(ARTIFACTS_DIR / "classifier_metadata.pkl")
        if (ARTIFACTS_DIR / "anomalies.csv").exists():
            adf = pd.read_csv(ARTIFACTS_DIR / "anomalies.csv")
            if "Date" in adf.columns:
                adf["Date"] = pd.to_datetime(adf["Date"])
            _STATE["anomaly_df"] = adf
        if (ARTIFACTS_DIR / "burnout.csv").exists():
            _STATE["burnout_df"] = pd.read_csv(ARTIFACTS_DIR / "burnout.csv")
        if (ARTIFACTS_DIR / "shap_global.pkl").exists():
            _STATE["shap_global"] = joblib.load(ARTIFACTS_DIR / "shap_global.pkl")
        if (ARTIFACTS_DIR / "employee_daily.parquet").exists():
            _STATE["employee_daily"] = pd.read_parquet(ARTIFACTS_DIR / "employee_daily.parquet")
        elif (ARTIFACTS_DIR / "employee_daily.csv").exists():
            ed = pd.read_csv(ARTIFACTS_DIR / "employee_daily.csv")
            ed["Date"] = pd.to_datetime(ed["Date"])
            _STATE["employee_daily"] = ed
        if (ARTIFACTS_DIR / "daily_extras.csv").exists():
            de = pd.read_csv(ARTIFACTS_DIR / "daily_extras.csv")
            de["Date"] = pd.to_datetime(de["Date"])
            _STATE["daily_extras"] = de

    # ─── Schemas ──────────────────────────────────────────────────────────
    class EmployeePredictRequest(BaseModel):
        emp_no: str = Field(..., description="Employee number / ID")
        target_date: date = Field(..., description="Date to predict for (YYYY-MM-DD)")

    class EmployeePredictResponse(BaseModel):
        emp_no: str
        target_date: str
        leave_probability: float
        predicted_label: int

    # ─── Routes ───────────────────────────────────────────────────────────
    @app.get("/")
    def root():
        return {
            "service": "Workforce Analytics API",
            "version": "1.0.0",
            "docs": "/docs",
            "endpoints": ["/health", "/forecast", "/predict/employee", "/anomalies",
                          "/burnout", "/metadata", "/explain/global"],
        }

    @app.get("/health")
    def health():
        try:
            _load_state()
            md = _STATE["metadata"]
            return {
                "status": "ok",
                "best_model": md.get("best_model_name"),
                "trained_at": md.get("trained_at"),
                "training_end_date": md.get("training_end_date"),
                "data_fingerprint": md.get("data_fingerprint"),
                "has_classifier": _STATE["classifier"] is not None,
                "has_anomalies": _STATE["anomaly_df"] is not None,
                "has_burnout": _STATE["burnout_df"] is not None,
            }
        except Exception as e:
            raise HTTPException(503, f"Service not ready: {e}")

    @app.get("/forecast")
    def forecast(days: int = Query(30, ge=1, le=90)):
        _load_state()
        fc = _STATE.get("forecast_df")
        if fc is None or fc.empty:
            raise HTTPException(404, "No forecast available. Train the model first.")
        return {
            "horizon": int(min(days, len(fc))),
            "forecast": fc.head(days).assign(Date=lambda d: d["Date"].dt.strftime("%Y-%m-%d")).to_dict(orient="records"),
        }

    @app.post("/predict/employee", response_model=EmployeePredictResponse)
    def predict_employee(req: EmployeePredictRequest):
        _load_state()
        clf = _STATE.get("classifier")
        meta = _STATE.get("classifier_meta")
        ed = _STATE.get("employee_daily")
        de = _STATE.get("daily_extras")
        if clf is None or meta is None:
            raise HTTPException(404, "Classifier not trained. Run pipeline.py with --enable-classifier.")
        if ed is None:
            raise HTTPException(503, "Employee panel not available. Re-run pipeline.py.")

        from classification import predict_employee_day
        bundle = {"model": clf, "metadata": meta}
        result = predict_employee_day(bundle, req.emp_no, req.target_date, ed, de)
        return EmployeePredictResponse(
            emp_no=result["EmpNo"],
            target_date=result["Date"],
            leave_probability=result["leave_probability"],
            predicted_label=result["predicted_label"],
        )

    @app.get("/anomalies")
    def anomalies(limit: int = Query(50, ge=1, le=500), only_flagged: bool = True):
        _load_state()
        adf = _STATE.get("anomaly_df")
        if adf is None or adf.empty:
            raise HTTPException(404, "No anomaly results. Run pipeline.py with anomaly enabled.")
        if only_flagged:
            adf = adf[adf["is_anomaly"] == True]  # noqa: E712
        return {
            "n": int(len(adf)),
            "anomalies": adf.head(limit).assign(
                Date=lambda d: d["Date"].dt.strftime("%Y-%m-%d") if pd.api.types.is_datetime64_any_dtype(d["Date"]) else d["Date"]
            ).to_dict(orient="records"),
        }

    @app.get("/burnout")
    def burnout(limit: int = Query(50, ge=1, le=500), risk: str | None = None):
        _load_state()
        bdf = _STATE.get("burnout_df")
        if bdf is None or bdf.empty:
            raise HTTPException(404, "No burnout results. Run pipeline.py first.")
        if risk:
            bdf = bdf[bdf["Risk_Band"].astype(str).str.lower() == risk.lower()]
        return {"n": int(len(bdf)), "rows": bdf.head(limit).to_dict(orient="records")}

    @app.get("/metadata")
    def metadata():
        _load_state()
        md = dict(_STATE["metadata"])
        # Drop bulky forecast list — already exposed by /forecast
        md.pop("forecast", None)
        return md

    @app.get("/explain/global")
    def explain_global(top: int = Query(15, ge=1, le=50)):
        _load_state()
        sg = _STATE.get("shap_global")
        if sg is None or not sg.get("available"):
            # Fallback to native importance from metadata
            md = _STATE["metadata"]
            return {"available": False, "fallback_native": md.get("feature_importance", [])[:top]}
        return {
            "available": True,
            "n_samples_used": sg.get("n_samples_used"),
            "mean_abs_shap": sg["mean_abs_shap"][:top],
        }

else:
    # Stub so importing this module doesn't crash if FastAPI isn't installed.
    app = None
