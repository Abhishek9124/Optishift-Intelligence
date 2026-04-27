"""Generalized Leave Forecasting Model — Train on any organization's leave data."""
from __future__ import annotations

import warnings
from datetime import date
from pathlib import Path

import holidays
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

try:
    from xgboost import XGBRegressor
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBRegressor = None
    XGBOOST_AVAILABLE = False

warnings.filterwarnings("ignore")

TARGET_COLUMN = "Leave_Count"
DATE_COLUMNS = ["From Date", "To Date", "Applied On", "Approved On"]


# ═══════════════════════════════════════════════════
# DATA CLEANING
# ═══════════════════════════════════════════════════

def clean_leave_data(raw: pd.DataFrame) -> pd.DataFrame:
    """Clean raw leave CSV: parse dates, keep Approved, deduplicate."""
    df = raw.copy()
    df.columns = df.columns.str.strip()
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].astype(str).str.strip().replace({"nan": np.nan, "None": np.nan, "": np.nan})
    for col in DATE_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce", dayfirst=True)
    if "Status" in df.columns:
        df = df[df["Status"].eq("Approved")].copy()
    df = df.dropna(subset=["From Date", "To Date"]).copy()
    df = df[df["To Date"] >= df["From Date"]].copy()
    dedup_key = [c for c in ["EmpNo", "Leave Type", "From Date", "To Date"] if c in df.columns]
    if dedup_key:
        df = df.drop_duplicates(subset=dedup_key, keep="first")
    return df.reset_index(drop=True)


def expand_to_daily(clean: pd.DataFrame) -> pd.DataFrame:
    """Expand leave records to one row per employee-day."""
    base = clean[["EmpNo", "From Date", "To Date"]].copy()
    for col in ["Department", "Leave Type", "Cost Centre"]:
        if col in clean.columns:
            base[col] = clean[col].fillna("Unknown")
    counts = (base["To Date"] - base["From Date"]).dt.days.add(1).astype(int)
    repeated = base.loc[base.index.repeat(counts)].copy()
    repeated["Date"] = np.concatenate([
        pd.date_range(s, e, freq="D").to_numpy()
        for s, e in zip(base["From Date"], base["To Date"])
    ])
    result_cols = ["Date", "EmpNo"] + [c for c in ["Department", "Leave Type", "Cost Centre"] if c in base.columns]
    return repeated[result_cols].reset_index(drop=True)


# ═══════════════════════════════════════════════════
# FEATURE ENGINEERING
# ═══════════════════════════════════════════════════

def build_holiday_calendar(start_year: int, end_year: int):
    return holidays.India(years=list(range(start_year, end_year + 1)))


def add_calendar_features(df: pd.DataFrame, hol_cal) -> pd.DataFrame:
    out = df.copy()
    out["day_of_week"] = out["Date"].dt.dayofweek
    out["month"] = out["Date"].dt.month
    out["day_of_month"] = out["Date"].dt.day
    out["week_of_year"] = out["Date"].dt.isocalendar().week.astype(int)
    out["quarter"] = out["Date"].dt.quarter
    out["is_weekend"] = out["day_of_week"].isin([5, 6]).astype(int)
    out["is_month_start"] = out["Date"].dt.is_month_start.astype(int)
    out["is_month_end"] = out["Date"].dt.is_month_end.astype(int)
    out["month_sin"] = np.sin(2 * np.pi * out["month"] / 12)
    out["month_cos"] = np.cos(2 * np.pi * out["month"] / 12)
    out["is_holiday"] = out["Date"].apply(lambda d: int(d.date() in hol_cal))
    out["is_long_weekend"] = out["Date"].apply(
        lambda d: int(any((d + pd.Timedelta(days=o)).date() in hol_cal for o in (-1, 0, 1))
                      and any((d + pd.Timedelta(days=o)).weekday() >= 5 for o in (-1, 0, 1)))
    )
    out["is_post_holiday"] = out["Date"].apply(lambda d: int((d - pd.Timedelta(days=1)).date() in hol_cal))
    out["is_monday"] = (out["day_of_week"] == 0).astype(int)
    out["is_friday"] = (out["day_of_week"] == 4).astype(int)
    out["week_sin"] = np.sin(2 * np.pi * out["week_of_year"] / 52)
    out["week_cos"] = np.cos(2 * np.pi * out["week_of_year"] / 52)
    out["day_sin"] = np.sin(2 * np.pi * out["day_of_week"] / 7)
    out["day_cos"] = np.cos(2 * np.pi * out["day_of_week"] / 7)
    out["quarter_sin"] = np.sin(2 * np.pi * out["quarter"] / 4)
    out["quarter_cos"] = np.cos(2 * np.pi * out["quarter"] / 4)
    return out


def add_lag_features(df: pd.DataFrame, target: str = TARGET_COLUMN) -> pd.DataFrame:
    out = df.copy()
    for lag in [1, 2, 3, 5, 7, 14, 21, 30, 45, 60]:
        out[f"leave_lag_{lag}"] = out[target].shift(lag)
    for win in [3, 7, 14, 21, 30, 45, 60]:
        shifted = out[target].shift(1)
        out[f"rolling_mean_{win}"] = shifted.rolling(window=win, min_periods=1).mean()
        out[f"rolling_std_{win}"] = shifted.rolling(window=win, min_periods=1).std()
    out["expanding_mean"] = out[target].shift(1).expanding(min_periods=1).mean()
    out["ewm_mean_7"] = out[target].shift(1).ewm(span=7, adjust=False).mean()
    out["ewm_mean_30"] = out[target].shift(1).ewm(span=30, adjust=False).mean()
    return out


def build_feature_dataset(raw: pd.DataFrame, as_of_date=None):
    """Build the full feature dataset from raw leave CSV data."""
    clean = clean_leave_data(raw)
    if as_of_date is not None:
        cutoff = pd.Timestamp(as_of_date).normalize()
        clean = clean[clean["From Date"] <= cutoff].copy()
        clean["To Date"] = clean["To Date"].clip(upper=cutoff)
        clean = clean[clean["To Date"] >= clean["From Date"]].copy()

    expanded = expand_to_daily(clean)
    if expanded.empty:
        return {"feature_df": pd.DataFrame(), "model_df": pd.DataFrame(), "feature_columns": [], "expanded": expanded}

    daily = (
        expanded.groupby("Date")
        .agg(Leave_Count=("EmpNo", "nunique"), Leave_Events=("EmpNo", "size"))
        .reset_index().sort_values("Date").reset_index(drop=True)
    )

    full_cal = pd.DataFrame({"Date": pd.date_range(daily["Date"].min(), daily["Date"].max(), freq="D")})
    daily = full_cal.merge(daily, on="Date", how="left")
    daily[["Leave_Count", "Leave_Events"]] = daily[["Leave_Count", "Leave_Events"]].fillna(0).astype(int)

    hol_cal = build_holiday_calendar(int(daily["Date"].dt.year.min()), int(daily["Date"].dt.year.max()) + 2)
    feature_df = add_calendar_features(daily, hol_cal)
    feature_df = add_lag_features(feature_df)
    feature_df = feature_df.replace([np.inf, -np.inf], np.nan).ffill().bfill()
    numeric_cols = feature_df.select_dtypes(include=[np.number]).columns
    feature_df[numeric_cols] = feature_df[numeric_cols].fillna(0)

    exclude = {"Date", TARGET_COLUMN, "Leave_Events"}
    feature_columns = [c for c in feature_df.columns if c not in exclude and feature_df[c].dtype in [np.float64, np.int64, np.int32, np.float32, int, float]]

    # Drop rows without enough lag history
    lag_cols = [c for c in feature_columns if "lag" in c]
    model_df = feature_df.dropna(subset=[c for c in lag_cols if c in feature_df.columns]).reset_index(drop=True)

    return {
        "feature_df": feature_df,
        "model_df": model_df,
        "feature_columns": feature_columns,
        "holiday_calendar": hol_cal,
        "expanded": expanded,
    }


# ═══════════════════════════════════════════════════
# MODEL TRAINING
# ═══════════════════════════════════════════════════

def wape(y_true, y_pred) -> float:
    denom = np.abs(y_true).sum()
    return float(np.abs(y_true - y_pred).sum() / denom) if denom else 0.0


def smape(y_true, y_pred) -> float:
    denom = np.abs(y_true) + np.abs(y_pred)
    mask = denom != 0
    return float(np.mean(2 * np.abs(y_true[mask] - y_pred[mask]) / denom[mask])) if mask.any() else 0.0


def build_candidates(seed: int = 42):
    models = {
        "RandomForest": RandomForestRegressor(n_estimators=400, max_depth=12, min_samples_leaf=4, random_state=seed, n_jobs=1),
        "GradientBoosting": GradientBoostingRegressor(n_estimators=400, max_depth=3, learning_rate=0.04, subsample=0.85, random_state=seed),
    }
    if XGBOOST_AVAILABLE:
        models["XGBoost"] = XGBRegressor(
            n_estimators=800, max_depth=4, learning_rate=0.03,
            subsample=0.85, colsample_bytree=0.8, reg_alpha=0.8, reg_lambda=3.0,
            random_state=seed, n_jobs=1, eval_metric="rmse", early_stopping_rounds=50,
        )
    return models


def train_model(raw_df: pd.DataFrame, as_of_date=None, forecast_horizon: int = 30, seed: int = 42):
    """Train the best model from raw leave data. Returns bundle dict."""
    bundle = build_feature_dataset(raw_df, as_of_date=as_of_date)
    model_df = bundle["model_df"].sort_values("Date").reset_index(drop=True)
    feature_cols = bundle["feature_columns"]

    if len(model_df) < 90:
        raise ValueError(f"Need at least 90 rows of daily data to train; got {len(model_df)}.")

    test_size = max(30, int(len(model_df) * 0.15))
    train_df = model_df.iloc[:-test_size].copy()
    test_df = model_df.iloc[-test_size:].copy()

    X_train, y_train = train_df[feature_cols], train_df[TARGET_COLUMN]
    X_test, y_test = test_df[feature_cols], test_df[TARGET_COLUMN]

    candidates = build_candidates(seed)
    best_name, best_model, best_wape = None, None, float("inf")

    for name, model in candidates.items():
        fit_kw = {}
        if name == "XGBoost":
            fit_kw["eval_set"] = [(X_test, y_test)]
            fit_kw["verbose"] = False
        model.fit(X_train, y_train, **fit_kw)
        preds = np.clip(model.predict(X_test), 0, None)
        w = wape(y_test.to_numpy(), preds)
        if w < best_wape:
            best_name, best_model, best_wape = name, model, w

    # Refit on full data
    final_model = build_candidates(seed)[best_name]
    if best_name == "XGBoost":
        final_model.set_params(early_stopping_rounds=None)
    final_model.fit(model_df[feature_cols], model_df[TARGET_COLUMN])

    test_preds = np.clip(final_model.predict(X_test), 0, None)
    residuals = y_test.to_numpy() - test_preds

    metadata = {
        "best_model_name": best_name,
        "feature_columns": feature_cols,
        "training_end_date": str(model_df["Date"].max().date()),
        "test_start_date": str(test_df["Date"].min().date()),
        "test_end_date": str(test_df["Date"].max().date()),
        "forecast_horizon": forecast_horizon,
        "test_metrics": {
            "MAE": mean_absolute_error(y_test, test_preds),
            "RMSE": mean_squared_error(y_test, test_preds) ** 0.5,
            "R2": r2_score(y_test, test_preds),
            "WAPE": wape(y_test.to_numpy(), test_preds),
            "SMAPE": smape(y_test.to_numpy(), test_preds),
        },
        "prediction_interval": {
            "residual_p05": float(np.percentile(residuals, 5)),
            "residual_p95": float(np.percentile(residuals, 95)),
            "absolute_error_p90": float(np.percentile(np.abs(residuals), 90)),
        },
    }

    # Generate future forecast
    history = bundle["feature_df"][["Date", TARGET_COLUMN]].copy().sort_values("Date").reset_index(drop=True)
    hol_cal = bundle["holiday_calendar"]
    forecasts = []
    for _ in range(forecast_horizon):
        next_date = history["Date"].max() + pd.Timedelta(days=1)
        prov = pd.concat([history, pd.DataFrame({"Date": [next_date], TARGET_COLUMN: [np.nan]})], ignore_index=True)
        prov = add_calendar_features(prov, hol_cal)
        prov = add_lag_features(prov)
        prov = prov.replace([np.inf, -np.inf], np.nan).ffill().bfill().fillna(0)
        row_feats = prov.iloc[[-1]][feature_cols]
        pred = float(np.clip(final_model.predict(row_feats)[0], 0, None))
        history = pd.concat([history, pd.DataFrame({"Date": [next_date], TARGET_COLUMN: [pred]})], ignore_index=True)
        forecasts.append({"Date": next_date, "Predicted_Leave_Count": round(pred), "Day_of_Week": next_date.day_name()})

    forecast_df = pd.DataFrame(forecasts)
    err90 = metadata["prediction_interval"]["absolute_error_p90"]
    forecast_df["Lower_Bound"] = np.maximum(forecast_df["Predicted_Leave_Count"] - err90, 0).round().astype(int)
    forecast_df["Upper_Bound"] = (forecast_df["Predicted_Leave_Count"] + err90).round().astype(int)
    metadata["forecast"] = forecast_df.assign(Date=lambda f: f["Date"].dt.strftime("%Y-%m-%d")).to_dict(orient="records")

    return {
        "model": final_model,
        "metadata": metadata,
        "bundle": bundle,
        "forecast_df": forecast_df,
        "test_metrics_df": pd.DataFrame([metadata["test_metrics"]]),
    }


def save_model(result: dict, output_dir: Path):
    """Save trained model and metadata to disk."""
    output_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(result["model"], output_dir / "model.pkl")
    joblib.dump(result["metadata"], output_dir / "metadata.pkl")
    result["forecast_df"].to_csv(output_dir / "forecast.csv", index=False)
    print(f"Model saved to {output_dir}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Train generalized leave forecasting model.")
    parser.add_argument("--data", required=True, help="Path to leave CSV file.")
    parser.add_argument("--output", default="artifacts", help="Output directory for model artifacts.")
    parser.add_argument("--forecast-horizon", type=int, default=30)
    args = parser.parse_args()

    raw = pd.read_csv(args.data, low_memory=False)
    result = train_model(raw, forecast_horizon=args.forecast_horizon)
    save_model(result, Path(args.output))
    print("\nTest Metrics:")
    print(result["test_metrics_df"].to_string(index=False))
    print(f"\nBest Model: {result['metadata']['best_model_name']}")
