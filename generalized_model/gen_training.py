"""
Generalized Leave Forecasting — production-ready training pipeline.

Foundation module for the workforce-analytics platform.

Public API:
    train_model(raw_df, ...) -> dict
    save_model(result, output_dir)
    load_model(output_dir) -> dict

Core design choices:
- Walk-forward (TimeSeriesSplit with gap) cross-validation — no leakage.
- Three-way time-ordered split: train / val (early-stopping + conformal calibration) / test.
- Multiple model families: XGBoost (CUDA-capable), LightGBM, CatBoost, RandomForest, GradientBoosting.
- Hyperparameter sweep over regularization knobs; selection by CV WAPE with gap tie-break.
- Early stopping kept ACTIVE in the final fit (key overfitting guard).
- Split-conformal prediction intervals from validation residuals; widen with horizon.
- Underfitting check vs seasonal-naive baseline (lag-7).
- Reproducibility: seed + env + data fingerprint in metadata.
- Atomic artifact saves; JSON + pkl + model card.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import platform
import sys
import tempfile
import warnings
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

import holidays
import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import TimeSeriesSplit

# Optional gradient boosters
try:
    import xgboost
    from xgboost import XGBRegressor
    XGBOOST_AVAILABLE = True
    XGBOOST_VERSION = xgboost.__version__
except ImportError:
    XGBRegressor = None  # type: ignore
    XGBOOST_AVAILABLE = False
    XGBOOST_VERSION = None

try:
    import lightgbm
    from lightgbm import LGBMRegressor
    LIGHTGBM_AVAILABLE = True
    LIGHTGBM_VERSION = lightgbm.__version__
except ImportError:
    LGBMRegressor = None  # type: ignore
    LIGHTGBM_AVAILABLE = False
    LIGHTGBM_VERSION = None

try:
    import catboost
    from catboost import CatBoostRegressor
    CATBOOST_AVAILABLE = True
    CATBOOST_VERSION = catboost.__version__
except ImportError:
    CatBoostRegressor = None  # type: ignore
    CATBOOST_AVAILABLE = False
    CATBOOST_VERSION = None

warnings.filterwarnings("ignore")

# ───────────────────────── Constants ─────────────────────────
TARGET_COLUMN = "Leave_Count"
DATE_COLUMNS = ["From Date", "To Date", "Applied On", "Approved On"]
REQUIRED_COLUMNS = ["EmpNo", "From Date", "To Date"]
RICH_CATEGORICAL_COLUMNS = [
    "Department", "Sub Department 1", "Sub Department 2", "Sub Department 3",
    "Cost Centre", "Business Area", "Location", "Work Contract External",
    "Sub Group Category", "Leave Type", "Leave Reason", "Type", "SourceApp",
]
RICH_NUMERIC_COLUMNS = ["Days", "Delay"]
MIN_TRAINING_DAYS = 90

LOG = logging.getLogger("gen_training")
if not LOG.handlers:
    _h = logging.StreamHandler(sys.stdout)
    _h.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s | %(message)s", "%H:%M:%S"))
    LOG.addHandler(_h)
LOG.setLevel(logging.INFO)


# ═════════════════════════════════════════════════════════════
# Configuration
# ═════════════════════════════════════════════════════════════

@dataclass
class TrainingConfig:
    seed: int = 42
    forecast_horizon: int = 30
    test_fraction: float = 0.15
    val_fraction: float = 0.15
    cv_splits: int = 5
    cv_gap: int = 7
    min_train_rows_for_cv: int = 60
    conformal_alpha: float = 0.10
    overfit_warn_ratio: float = 1.5
    horizon_uncertainty_growth: float = 0.02
    n_jobs: int = 1
    enable_xgb: bool = True
    enable_rf: bool = True
    enable_gbr: bool = True
    enable_lgbm: bool = True
    enable_catboost: bool = True
    use_gpu: bool = False
    gpu_device: str = "cuda"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ═════════════════════════════════════════════════════════════
# Validation
# ═════════════════════════════════════════════════════════════

def validate_raw_input(raw: pd.DataFrame) -> None:
    if raw is None or raw.empty:
        raise ValueError("Input dataframe is empty.")
    cols = {c.strip() for c in raw.columns}
    missing = [c for c in REQUIRED_COLUMNS if c not in cols]
    if missing:
        raise ValueError(
            f"Missing required columns: {missing}. "
            f"Expected at least: {REQUIRED_COLUMNS}."
        )


# ═════════════════════════════════════════════════════════════
# Cleaning & expansion
# ═════════════════════════════════════════════════════════════

def clean_leave_data(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy()
    df.columns = df.columns.str.strip()
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].astype(str).str.strip().replace(
            {"nan": np.nan, "None": np.nan, "": np.nan, "NaT": np.nan}
        )
    for col in DATE_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce", dayfirst=True)
    for col in RICH_NUMERIC_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if {"Applied On", "From Date"}.issubset(df.columns):
        df["Application_Lead_Days"] = (df["From Date"] - df["Applied On"]).dt.total_seconds() / 86400
    if {"Approved On", "Applied On"}.issubset(df.columns):
        df["Approval_Turnaround_Days"] = (df["Approved On"] - df["Applied On"]).dt.total_seconds() / 86400
    if "Status" in df.columns:
        df = df[df["Status"].astype(str).str.lower().eq("approved")].copy()
    df = df.dropna(subset=["From Date", "To Date"]).copy()
    df = df[df["To Date"] >= df["From Date"]].copy()
    dedup_key = [c for c in ["EmpNo", "Leave Type", "From Date", "To Date"] if c in df.columns]
    if dedup_key:
        df = df.drop_duplicates(subset=dedup_key, keep="first")
    return df.reset_index(drop=True)


def expand_to_daily(clean: pd.DataFrame) -> pd.DataFrame:
    base = clean[["EmpNo", "From Date", "To Date"]].copy()
    for col in RICH_CATEGORICAL_COLUMNS:
        if col in clean.columns:
            base[col] = clean[col].fillna("Unknown")
    for col in [*RICH_NUMERIC_COLUMNS, "Application_Lead_Days", "Approval_Turnaround_Days"]:
        if col in clean.columns:
            base[col] = clean[col]
    counts = (base["To Date"] - base["From Date"]).dt.days.add(1).astype(int)
    if counts.sum() == 0:
        return pd.DataFrame(columns=["Date", "EmpNo"])
    repeated = base.loc[base.index.repeat(counts)].copy()
    repeated["Date"] = np.concatenate([
        pd.date_range(s, e, freq="D").to_numpy()
        for s, e in zip(base["From Date"], base["To Date"])
    ])
    keep = ["Date", "EmpNo"] + [c for c in base.columns if c not in ("From Date", "To Date", "Date", "EmpNo")]
    return repeated[keep].reset_index(drop=True)


# ═════════════════════════════════════════════════════════════
# Feature engineering
# ═════════════════════════════════════════════════════════════

def build_holiday_calendar(start_year: int, end_year: int):
    return holidays.India(years=list(range(start_year, end_year + 1)))


def add_calendar_features(df: pd.DataFrame, hol_cal) -> pd.DataFrame:
    out = df.copy()
    d = out["Date"]
    out["day_of_week"] = d.dt.dayofweek
    out["month"] = d.dt.month
    out["day_of_month"] = d.dt.day
    out["week_of_year"] = d.dt.isocalendar().week.astype(int)
    out["quarter"] = d.dt.quarter
    out["year"] = d.dt.year
    out["is_weekend"] = out["day_of_week"].isin([5, 6]).astype(int)
    out["is_month_start"] = d.dt.is_month_start.astype(int)
    out["is_month_end"] = d.dt.is_month_end.astype(int)
    out["is_quarter_start"] = d.dt.is_quarter_start.astype(int)
    out["is_quarter_end"] = d.dt.is_quarter_end.astype(int)
    out["is_year_start"] = d.dt.is_year_start.astype(int)
    out["is_year_end"] = d.dt.is_year_end.astype(int)
    out["month_sin"] = np.sin(2 * np.pi * out["month"] / 12)
    out["month_cos"] = np.cos(2 * np.pi * out["month"] / 12)
    out["week_sin"] = np.sin(2 * np.pi * out["week_of_year"] / 52)
    out["week_cos"] = np.cos(2 * np.pi * out["week_of_year"] / 52)
    out["day_sin"] = np.sin(2 * np.pi * out["day_of_week"] / 7)
    out["day_cos"] = np.cos(2 * np.pi * out["day_of_week"] / 7)
    out["quarter_sin"] = np.sin(2 * np.pi * out["quarter"] / 4)
    out["quarter_cos"] = np.cos(2 * np.pi * out["quarter"] / 4)
    out["is_monday"] = (out["day_of_week"] == 0).astype(int)
    out["is_friday"] = (out["day_of_week"] == 4).astype(int)

    hol_dates = pd.to_datetime(sorted({pd.Timestamp(d) for d in hol_cal.keys()}))
    if len(hol_dates):
        d_norm = d.dt.normalize()
        idx = np.searchsorted(hol_dates.values, d_norm.values)
        idx_clip_next = np.clip(idx, 0, len(hol_dates) - 1)
        idx_clip_prev = np.clip(idx - 1, 0, len(hol_dates) - 1)
        next_h = pd.to_datetime(hol_dates.values[idx_clip_next])
        prev_h = pd.to_datetime(hol_dates.values[idx_clip_prev])
        one_day = np.timedelta64(1, "D")
        diff_next = (next_h.values - d_norm.values) / one_day
        diff_prev = (d_norm.values - prev_h.values) / one_day
        out["days_to_next_holiday"] = pd.Series(diff_next, index=out.index).fillna(0).astype(int).clip(0, 60)
        out["days_since_last_holiday"] = pd.Series(diff_prev, index=out.index).fillna(0).astype(int).clip(0, 60)
        out["is_holiday"] = (out["days_to_next_holiday"] == 0).astype(int)
        out["is_pre_holiday"] = (out["days_to_next_holiday"] == 1).astype(int)
        out["is_post_holiday"] = (out["days_since_last_holiday"] == 1).astype(int)
        adj_holiday = (
            (out["days_to_next_holiday"] <= 1) | (out["days_since_last_holiday"] <= 1)
        ).astype(int)
        out["is_long_weekend"] = (
            (adj_holiday & out["is_weekend"]).astype(int)
            | ((out["is_friday"] | out["is_monday"]) & adj_holiday).astype(int)
        )
    else:
        for col in ["days_to_next_holiday", "days_since_last_holiday",
                    "is_holiday", "is_pre_holiday", "is_post_holiday", "is_long_weekend"]:
            out[col] = 0
    return out


def add_lag_features(df: pd.DataFrame, target: str = TARGET_COLUMN) -> pd.DataFrame:
    out = df.copy()
    shifted = out[target].shift(1)
    for lag in [1, 2, 3, 5, 7, 14, 21, 28, 30, 45, 60, 91, 182, 364]:
        out[f"leave_lag_{lag}"] = out[target].shift(lag)
    for k in [1, 2, 4, 8, 13, 26, 52]:
        out[f"leave_dow_lag_{k}w"] = out[target].shift(7 * k)
    for win in [3, 7, 14, 21, 30, 45, 60]:
        out[f"rolling_mean_{win}"] = shifted.rolling(window=win, min_periods=max(2, win // 3)).mean()
        out[f"rolling_std_{win}"] = shifted.rolling(window=win, min_periods=max(2, win // 3)).std()
        out[f"rolling_max_{win}"] = shifted.rolling(window=win, min_periods=max(2, win // 3)).max()
        out[f"rolling_min_{win}"] = shifted.rolling(window=win, min_periods=max(2, win // 3)).min()
    out["expanding_mean"] = shifted.expanding(min_periods=7).mean()
    out["ewm_mean_7"] = shifted.ewm(span=7, adjust=False, min_periods=2).mean()
    out["ewm_mean_30"] = shifted.ewm(span=30, adjust=False, min_periods=2).mean()
    return out


def build_feature_dataset(
    raw: pd.DataFrame,
    as_of_date=None,
    daily_extras: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """Build the feature dataset from raw leave CSV.

    `daily_extras` (optional) is a DataFrame with a `Date` column and additional
    daily features (e.g. headcount, leave-balance summaries) produced by the
    data_enrichment module. They are merged in by date.
    """
    clean = clean_leave_data(raw)
    if as_of_date is not None:
        cutoff = pd.Timestamp(as_of_date).normalize()
        clean = clean[clean["From Date"] <= cutoff].copy()
        clean["To Date"] = clean["To Date"].clip(upper=cutoff)
        clean = clean[clean["To Date"] >= clean["From Date"]].copy()

    expanded = expand_to_daily(clean)
    if expanded.empty:
        return {
            "feature_df": pd.DataFrame(), "model_df": pd.DataFrame(),
            "feature_columns": [], "holiday_calendar": None, "expanded": expanded,
        }

    daily = (
        expanded.groupby("Date")
        .agg(Leave_Count=("EmpNo", "nunique"), Leave_Events=("EmpNo", "size"))
        .reset_index().sort_values("Date").reset_index(drop=True)
    )
    full_cal = pd.DataFrame({"Date": pd.date_range(daily["Date"].min(), daily["Date"].max(), freq="D")})
    daily = full_cal.merge(daily, on="Date", how="left")
    daily[["Leave_Count", "Leave_Events"]] = daily[["Leave_Count", "Leave_Events"]].fillna(0).astype(int)

    if daily_extras is not None and not daily_extras.empty:
        extras = daily_extras.copy()
        extras["Date"] = pd.to_datetime(extras["Date"])
        daily = daily.merge(extras, on="Date", how="left")

    hol_cal = build_holiday_calendar(int(daily["Date"].dt.year.min()), int(daily["Date"].dt.year.max()) + 2)
    feature_df = add_calendar_features(daily, hol_cal)
    feature_df = add_lag_features(feature_df)
    feature_df = feature_df.replace([np.inf, -np.inf], np.nan)

    exclude = {"Date", TARGET_COLUMN, "Leave_Events"}
    feature_columns = [
        c for c in feature_df.columns
        if c not in exclude and np.issubdtype(feature_df[c].dtype, np.number)
    ]

    max_safe_lag = 60
    model_df = feature_df.iloc[max_safe_lag:].copy()
    for c in feature_columns:
        if model_df[c].isna().any():
            med = model_df[c].median()
            if pd.isna(med):
                med = 0.0
            model_df[c] = model_df[c].fillna(med)
    model_df = model_df.reset_index(drop=True)

    return {
        "feature_df": feature_df,
        "model_df": model_df,
        "feature_columns": feature_columns,
        "holiday_calendar": hol_cal,
        "expanded": expanded,
    }


# ═════════════════════════════════════════════════════════════
# Metrics
# ═════════════════════════════════════════════════════════════

def wape(y_true, y_pred) -> float:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    denom = np.abs(y_true).sum()
    return float(np.abs(y_true - y_pred).sum() / denom) if denom else 0.0


def smape(y_true, y_pred) -> float:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    denom = np.abs(y_true) + np.abs(y_pred)
    mask = denom != 0
    return float(np.mean(2 * np.abs(y_true[mask] - y_pred[mask]) / denom[mask])) if mask.any() else 0.0


def mape_safe(y_true, y_pred) -> float:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    return float(np.mean(np.abs(y_true - y_pred) / (np.abs(y_true) + 1.0)))


def evaluate(y_true, y_pred) -> dict[str, float]:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    return {
        "MAE": float(mean_absolute_error(y_true, y_pred)),
        "RMSE": float(mean_squared_error(y_true, y_pred) ** 0.5),
        "MAPE": mape_safe(y_true, y_pred),
        "R2": float(r2_score(y_true, y_pred)) if len(np.unique(y_true)) > 1 else 0.0,
        "WAPE": wape(y_true, y_pred),
        "SMAPE": smape(y_true, y_pred),
    }


# ═════════════════════════════════════════════════════════════
# Candidate models
# ═════════════════════════════════════════════════════════════

def _xgb_grid(seed: int) -> list[dict]:
    return [
        dict(max_depth=3, learning_rate=0.04, min_child_weight=4, reg_alpha=1.0, reg_lambda=4.0,
             subsample=0.8, colsample_bytree=0.8),
        dict(max_depth=4, learning_rate=0.04, min_child_weight=3, reg_alpha=0.5, reg_lambda=3.0,
             subsample=0.85, colsample_bytree=0.8),
        dict(max_depth=5, learning_rate=0.05, min_child_weight=2, reg_alpha=0.3, reg_lambda=2.0,
             subsample=0.85, colsample_bytree=0.85),
        dict(max_depth=6, learning_rate=0.03, min_child_weight=2, reg_alpha=0.2, reg_lambda=1.5,
             subsample=0.9, colsample_bytree=0.9),
    ]


def _lgbm_grid() -> list[dict]:
    return [
        dict(num_leaves=15, learning_rate=0.04, min_child_samples=10, reg_alpha=1.0, reg_lambda=4.0,
             subsample=0.8, colsample_bytree=0.8),
        dict(num_leaves=31, learning_rate=0.04, min_child_samples=8, reg_alpha=0.5, reg_lambda=2.0,
             subsample=0.85, colsample_bytree=0.85),
        dict(num_leaves=63, learning_rate=0.03, min_child_samples=5, reg_alpha=0.2, reg_lambda=1.0,
             subsample=0.9, colsample_bytree=0.9),
    ]


def make_xgb(params: dict, seed: int, n_jobs: int = 1, early_stopping: int | None = 50,
             use_gpu: bool = False, gpu_device: str = "cuda") -> "XGBRegressor":
    kw = dict(n_estimators=2000, random_state=seed, n_jobs=n_jobs, eval_metric="rmse", tree_method="hist")
    if use_gpu:
        kw["device"] = gpu_device
    kw.update(params)
    if early_stopping is not None:
        kw["early_stopping_rounds"] = early_stopping
    return XGBRegressor(**kw)


def make_lgbm(params: dict, seed: int, n_jobs: int = 1, use_gpu: bool = False) -> "LGBMRegressor":
    kw = dict(n_estimators=2000, random_state=seed, n_jobs=n_jobs, verbose=-1, objective="regression")
    if use_gpu:
        kw["device"] = "gpu"
    kw.update(params)
    return LGBMRegressor(**kw)


def make_catboost(seed: int, use_gpu: bool = False) -> "CatBoostRegressor":
    # subsample requires bootstrap_type != Bayesian (the default).
    kw = dict(
        iterations=1500, depth=5, learning_rate=0.04,
        l2_leaf_reg=4.0,
        bootstrap_type="Bernoulli", subsample=0.85,
        random_seed=seed, verbose=False, allow_writing_files=False,
    )
    if use_gpu:
        kw["task_type"] = "GPU"
        kw["devices"] = "0"
    return CatBoostRegressor(**kw)


def make_rf(seed: int, n_jobs: int = 1) -> RandomForestRegressor:
    return RandomForestRegressor(
        n_estimators=400, max_depth=12, min_samples_leaf=4,
        max_features="sqrt", random_state=seed, n_jobs=n_jobs,
    )


def make_gbr(seed: int) -> GradientBoostingRegressor:
    return GradientBoostingRegressor(
        n_estimators=400, max_depth=3, learning_rate=0.04, subsample=0.85, random_state=seed,
    )


# ═════════════════════════════════════════════════════════════
# Baseline (for underfitting check)
# ═════════════════════════════════════════════════════════════

def _seasonal_naive_val_wape(train_df: pd.DataFrame, val_df: pd.DataFrame, period: int = 7) -> float:
    series = pd.concat([train_df, val_df], ignore_index=True)[TARGET_COLUMN].values
    n_train = len(train_df)
    if n_train < period:
        return float("inf")
    y_true = series[n_train:]
    y_pred = series[n_train - period: n_train - period + len(y_true)]
    return wape(y_true, y_pred)


# ═════════════════════════════════════════════════════════════
# Splits
# ═════════════════════════════════════════════════════════════

def _three_way_split(model_df: pd.DataFrame, cfg: TrainingConfig):
    n = len(model_df)
    n_test = max(30, int(n * cfg.test_fraction))
    n_val = max(30, int(n * cfg.val_fraction))
    if n - n_test - n_val < cfg.min_train_rows_for_cv:
        n_val = max(14, (n - cfg.min_train_rows_for_cv) // 3)
        n_test = max(14, (n - cfg.min_train_rows_for_cv) // 3)
    train = model_df.iloc[: n - n_val - n_test].copy()
    val = model_df.iloc[n - n_val - n_test: n - n_test].copy()
    test = model_df.iloc[n - n_test:].copy()
    return train, val, test


# ═════════════════════════════════════════════════════════════
# CV scoring
# ═════════════════════════════════════════════════════════════

def _cv_score(make_fn, model_df: pd.DataFrame, feature_cols: list[str], cfg: TrainingConfig,
              uses_eval_set: bool = False) -> tuple[float, float]:
    tss = TimeSeriesSplit(n_splits=cfg.cv_splits, gap=cfg.cv_gap)
    val_w, train_w = [], []
    X_all = model_df[feature_cols].values
    y_all = model_df[TARGET_COLUMN].values
    for tr_idx, va_idx in tss.split(X_all):
        if len(tr_idx) < cfg.min_train_rows_for_cv or len(va_idx) < 7:
            continue
        X_tr, y_tr = X_all[tr_idx], y_all[tr_idx]
        X_va, y_va = X_all[va_idx], y_all[va_idx]
        m = make_fn()
        if uses_eval_set:
            try:
                m.fit(X_tr, y_tr, eval_set=[(X_va, y_va)], verbose=False)
            except TypeError:
                m.fit(X_tr, y_tr)
        else:
            m.fit(X_tr, y_tr)
        val_w.append(wape(y_va, np.clip(m.predict(X_va), 0, None)))
        train_w.append(wape(y_tr, np.clip(m.predict(X_tr), 0, None)))
    if not val_w:
        return float("inf"), float("inf")
    return float(np.mean(val_w)), float(np.mean(train_w))


def _select_grid(grid: list[dict], make_fn, model_df: pd.DataFrame, feature_cols: list[str],
                 cfg: TrainingConfig, label: str, uses_eval_set: bool = True) -> dict:
    results = []
    for i, params in enumerate(grid):
        v, t = _cv_score(lambda p=params: make_fn(p), model_df, feature_cols, cfg, uses_eval_set)
        gap = max(0.0, v - t)
        LOG.info(f"  {label} candidate {i+1}/{len(grid)}: val WAPE={v:.4f} train WAPE={t:.4f} gap={gap:.4f}")
        results.append((v, gap, params, t))
    results.sort(key=lambda r: (r[0], r[1]))
    best = results[0]
    return {"params": best[2], "cv_wape": best[0], "cv_gap": best[1], "cv_train_wape": best[3]}


# ═════════════════════════════════════════════════════════════
# CUDA probe
# ═════════════════════════════════════════════════════════════

def _probe_cuda() -> tuple[bool, str]:
    if not XGBOOST_AVAILABLE:
        return False, "xgboost not installed"
    try:
        import xgboost as _x
        dm = _x.DMatrix([[1.0, 2.0], [3.0, 4.0]], label=[0.0, 1.0])
        _x.train({"device": "cuda", "tree_method": "hist", "objective": "reg:squarederror"}, dm, num_boost_round=1)
        return True, "CUDA OK"
    except Exception as e:
        return False, f"{e.__class__.__name__}: {str(e)[:120]}"


# ═════════════════════════════════════════════════════════════
# Main pipeline
# ═════════════════════════════════════════════════════════════

def train_model(
    raw_df: pd.DataFrame,
    as_of_date=None,
    forecast_horizon: int = 30,
    seed: int = 42,
    config: TrainingConfig | None = None,
    daily_extras: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """Train the best forecasting model. See module docstring for design."""
    cfg = config or TrainingConfig(seed=seed, forecast_horizon=forecast_horizon)
    LOG.info(f"Training started (seed={cfg.seed}, horizon={cfg.forecast_horizon})")

    if cfg.use_gpu and cfg.enable_xgb and XGBOOST_AVAILABLE:
        ok, msg = _probe_cuda()
        if ok:
            LOG.info(f"GPU enabled: device={cfg.gpu_device} ({msg})")
        else:
            LOG.warning(f"use_gpu=True but {msg}. Falling back to CPU for XGBoost.")
            cfg.use_gpu = False

    validate_raw_input(raw_df)

    bundle = build_feature_dataset(raw_df, as_of_date=as_of_date, daily_extras=daily_extras)
    model_df: pd.DataFrame = bundle["model_df"].sort_values("Date").reset_index(drop=True)
    feature_cols: list[str] = bundle["feature_columns"]
    if len(model_df) < MIN_TRAINING_DAYS:
        raise ValueError(f"Need >= {MIN_TRAINING_DAYS} model rows; got {len(model_df)}.")
    LOG.info(f"Feature set: {len(model_df)} rows, {len(feature_cols)} features")

    train_df, val_df, test_df = _three_way_split(model_df, cfg)
    trainval_df = pd.concat([train_df, val_df], ignore_index=True)
    LOG.info(f"Split: train={len(train_df)}, val={len(val_df)}, test={len(test_df)}")

    X_train, y_train = train_df[feature_cols].values, train_df[TARGET_COLUMN].values
    X_val, y_val = val_df[feature_cols].values, val_df[TARGET_COLUMN].values
    X_test, y_test = test_df[feature_cols].values, test_df[TARGET_COLUMN].values

    candidates: dict[str, dict[str, Any]] = {}

    if cfg.enable_xgb and XGBOOST_AVAILABLE:
        LOG.info("Tuning XGBoost via walk-forward CV...")
        sel = _select_grid(
            _xgb_grid(cfg.seed),
            lambda p: make_xgb(p, cfg.seed, cfg.n_jobs, 50, cfg.use_gpu, cfg.gpu_device),
            trainval_df, feature_cols, cfg, "XGB", uses_eval_set=True,
        )
        candidates["XGBoost"] = sel
        LOG.info(f"  XGB selected: WAPE={sel['cv_wape']:.4f} params={sel['params']}")

    if cfg.enable_lgbm and LIGHTGBM_AVAILABLE:
        LOG.info("Tuning LightGBM via walk-forward CV...")
        sel = _select_grid(
            _lgbm_grid(),
            lambda p: make_lgbm(p, cfg.seed, cfg.n_jobs, use_gpu=False),  # LGBM GPU build needs separate install
            trainval_df, feature_cols, cfg, "LGBM", uses_eval_set=False,
        )
        candidates["LightGBM"] = sel
        LOG.info(f"  LGBM selected: WAPE={sel['cv_wape']:.4f} params={sel['params']}")

    if cfg.enable_catboost and CATBOOST_AVAILABLE:
        LOG.info("Scoring CatBoost via walk-forward CV...")
        v, t = _cv_score(lambda: make_catboost(cfg.seed, cfg.use_gpu),
                         trainval_df, feature_cols, cfg, uses_eval_set=False)
        candidates["CatBoost"] = {"params": {}, "cv_wape": v, "cv_gap": max(0.0, v - t), "cv_train_wape": t}
        LOG.info(f"  CatBoost: WAPE={v:.4f}")

    if cfg.enable_rf:
        LOG.info("Scoring RandomForest via walk-forward CV...")
        v, t = _cv_score(lambda: make_rf(cfg.seed, cfg.n_jobs), trainval_df, feature_cols, cfg)
        candidates["RandomForest"] = {"params": {}, "cv_wape": v, "cv_gap": max(0.0, v - t), "cv_train_wape": t}
        LOG.info(f"  RF: WAPE={v:.4f}")

    if cfg.enable_gbr:
        LOG.info("Scoring GradientBoosting via walk-forward CV...")
        v, t = _cv_score(lambda: make_gbr(cfg.seed), trainval_df, feature_cols, cfg)
        candidates["GradientBoosting"] = {"params": {}, "cv_wape": v, "cv_gap": max(0.0, v - t), "cv_train_wape": t}
        LOG.info(f"  GBR: WAPE={v:.4f}")

    if not candidates:
        raise RuntimeError("No candidate models available. Install at least one of xgboost/lightgbm/catboost.")

    best_name = min(candidates.keys(), key=lambda k: candidates[k]["cv_wape"])
    LOG.info(f"Best family: {best_name} (CV WAPE={candidates[best_name]['cv_wape']:.4f})")

    # Final fit
    if best_name == "XGBoost":
        params = candidates["XGBoost"]["params"]
        final_model = make_xgb(params, cfg.seed, cfg.n_jobs, 50, cfg.use_gpu, cfg.gpu_device)
        final_model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)
    elif best_name == "LightGBM":
        params = candidates["LightGBM"]["params"]
        final_model = make_lgbm(params, cfg.seed, cfg.n_jobs)
        final_model.fit(np.vstack([X_train, X_val]), np.concatenate([y_train, y_val]))
    elif best_name == "CatBoost":
        final_model = make_catboost(cfg.seed, cfg.use_gpu)
        final_model.fit(np.vstack([X_train, X_val]), np.concatenate([y_train, y_val]))
    elif best_name == "RandomForest":
        final_model = make_rf(cfg.seed, cfg.n_jobs)
        final_model.fit(np.vstack([X_train, X_val]), np.concatenate([y_train, y_val]))
    else:
        final_model = make_gbr(cfg.seed)
        final_model.fit(np.vstack([X_train, X_val]), np.concatenate([y_train, y_val]))

    pred_train = np.clip(final_model.predict(X_train), 0, None)
    pred_val = np.clip(final_model.predict(X_val), 0, None)
    pred_test = np.clip(final_model.predict(X_test), 0, None)

    train_metrics = evaluate(y_train, pred_train)
    val_metrics = evaluate(y_val, pred_val)
    test_metrics = evaluate(y_test, pred_test)
    LOG.info(f"Train WAPE={train_metrics['WAPE']:.4f} | Val WAPE={val_metrics['WAPE']:.4f} | Test WAPE={test_metrics['WAPE']:.4f}")

    # Diagnostics
    diagnostics: dict[str, Any] = {"warnings": []}
    if train_metrics["WAPE"] > 0:
        gap_ratio = val_metrics["WAPE"] / max(train_metrics["WAPE"], 1e-9)
        diagnostics["val_train_wape_ratio"] = gap_ratio
        if gap_ratio > cfg.overfit_warn_ratio:
            msg = (f"Possible overfitting: val WAPE is {gap_ratio:.2f}x train WAPE "
                   f"({val_metrics['WAPE']:.4f} vs {train_metrics['WAPE']:.4f}).")
            LOG.warning(msg)
            diagnostics["warnings"].append(msg)

    val_naive_wape = _seasonal_naive_val_wape(train_df, val_df)
    diagnostics["seasonal_naive_val_wape"] = val_naive_wape
    diagnostics["model_vs_naive_lift"] = (
        (val_naive_wape - val_metrics["WAPE"]) / max(val_naive_wape, 1e-9)
        if val_naive_wape > 0 else 0.0
    )
    if val_naive_wape > 0 and val_metrics["WAPE"] >= 0.95 * val_naive_wape:
        msg = (f"Possible underfitting: model val WAPE ({val_metrics['WAPE']:.4f}) "
               f"barely beats seasonal-naive baseline ({val_naive_wape:.4f}).")
        LOG.warning(msg)
        diagnostics["warnings"].append(msg)
    else:
        LOG.info(f"Model beats seasonal-naive baseline: "
                 f"{val_metrics['WAPE']:.4f} vs {val_naive_wape:.4f} "
                 f"(lift {diagnostics['model_vs_naive_lift']:.1%})")

    # Conformal interval
    val_residuals = y_val - pred_val
    abs_val_residuals = np.abs(val_residuals)
    n_cal = len(abs_val_residuals)
    if n_cal >= 5:
        q_level = min(1.0, np.ceil((n_cal + 1) * (1 - cfg.conformal_alpha)) / n_cal)
        conformal_radius = float(np.quantile(abs_val_residuals, q_level))
    else:
        conformal_radius = float(np.percentile(np.abs(y_test - pred_test), 90)) if len(y_test) else 1.0
    LOG.info(f"Conformal radius (alpha={cfg.conformal_alpha}): +/-{conformal_radius:.2f}")

    # Forecast
    forecast_df = _recursive_forecast(
        bundle=bundle, feature_cols=feature_cols, model=final_model,
        horizon=cfg.forecast_horizon, conformal_radius=conformal_radius,
        horizon_growth=cfg.horizon_uncertainty_growth,
    )

    # Feature importance
    feature_importance = []
    if hasattr(final_model, "feature_importances_"):
        importances = final_model.feature_importances_
        order = np.argsort(importances)[::-1][:25]
        feature_importance = [
            {"feature": feature_cols[i], "importance": float(importances[i])} for i in order
        ]

    # Capture actual vs predicted for the test period (used by reporting)
    actual_vs_pred = pd.DataFrame({
        "Date": test_df["Date"].values,
        "Actual": y_test, "Predicted": pred_test,
        "Residual": y_test - pred_test,
        "Lower_Bound": np.maximum(0.0, pred_test - conformal_radius),
        "Upper_Bound": pred_test + conformal_radius,
    })

    metadata: dict[str, Any] = {
        "best_model_name": best_name,
        "config": cfg.to_dict(),
        "feature_columns": feature_cols,
        "n_features": len(feature_cols),
        "n_train": len(train_df), "n_val": len(val_df), "n_test": len(test_df),
        "training_end_date": str(model_df["Date"].max().date()),
        "test_start_date": str(test_df["Date"].min().date()),
        "test_end_date": str(test_df["Date"].max().date()),
        "forecast_horizon": cfg.forecast_horizon,
        "train_metrics": train_metrics, "val_metrics": val_metrics, "test_metrics": test_metrics,
        "candidate_scores": candidates,
        "conformal_radius": conformal_radius, "conformal_alpha": cfg.conformal_alpha,
        "diagnostics": diagnostics,
        "feature_importance": feature_importance,
        "trained_at": datetime.now().isoformat(timespec="seconds"),
        "data_fingerprint": _fingerprint_data(raw_df),
        "env": {
            "python": platform.python_version(),
            "sklearn": sklearn.__version__,
            "xgboost": XGBOOST_VERSION,
            "lightgbm": LIGHTGBM_VERSION,
            "catboost": CATBOOST_VERSION,
            "pandas": pd.__version__,
            "numpy": np.__version__,
        },
        "forecast": forecast_df.assign(Date=lambda f: f["Date"].dt.strftime("%Y-%m-%d")).to_dict(orient="records"),
    }

    LOG.info("Training complete.")
    return {
        "model": final_model, "metadata": metadata, "bundle": bundle,
        "forecast_df": forecast_df, "test_metrics_df": pd.DataFrame([test_metrics]),
        "actual_vs_pred": actual_vs_pred,
        "val_metrics": val_metrics, "train_metrics": train_metrics,
    }


# ═════════════════════════════════════════════════════════════
# Recursive forecasting
# ═════════════════════════════════════════════════════════════

def _recursive_forecast(bundle, feature_cols, model, horizon, conformal_radius, horizon_growth):
    history = bundle["feature_df"][["Date", TARGET_COLUMN]].copy().sort_values("Date").reset_index(drop=True)
    hol_cal = bundle["holiday_calendar"]
    rows = []
    # Carry over any extras present in feature_df (headcount etc) by repeating last known
    extras_cols = [c for c in bundle["feature_df"].columns
                   if c not in {"Date", TARGET_COLUMN, "Leave_Events"}
                   and c not in feature_cols]  # raw extras get re-derived; nothing here
    for h in range(1, horizon + 1):
        next_date = history["Date"].max() + pd.Timedelta(days=1)
        prov = pd.concat([history, pd.DataFrame({"Date": [next_date], TARGET_COLUMN: [np.nan]})], ignore_index=True)
        prov = add_calendar_features(prov, hol_cal)
        prov = add_lag_features(prov)
        prov = prov.replace([np.inf, -np.inf], np.nan)
        for c in feature_cols:
            if c not in prov.columns:
                prov[c] = 0.0
            elif prov[c].isna().any():
                med = prov[c].median()
                if pd.isna(med):
                    med = 0.0
                prov[c] = prov[c].fillna(med)
        row_feats = prov.iloc[[-1]][feature_cols].values
        pred = float(np.clip(model.predict(row_feats)[0], 0, None))
        history = pd.concat([history, pd.DataFrame({"Date": [next_date], TARGET_COLUMN: [pred]})], ignore_index=True)
        radius_h = conformal_radius * (1.0 + h * horizon_growth)
        rows.append({
            "Date": next_date,
            "Predicted_Leave_Count": int(round(pred)),
            "Lower_Bound": int(round(max(0.0, pred - radius_h))),
            "Upper_Bound": int(round(pred + radius_h)),
            "Day_of_Week": next_date.day_name(),
        })
    return pd.DataFrame(rows)


# ═════════════════════════════════════════════════════════════
# Persistence
# ═════════════════════════════════════════════════════════════

def _fingerprint_data(raw: pd.DataFrame) -> str:
    try:
        h = hashlib.sha256()
        h.update(str(raw.shape).encode())
        h.update(",".join(map(str, raw.columns)).encode())
        sample = pd.concat([raw.head(50), raw.tail(50)], ignore_index=True)
        h.update(pd.util.hash_pandas_object(sample, index=False).values.tobytes())
        return h.hexdigest()[:16]
    except Exception:
        return "unknown"


def _atomic_dump(obj, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    os.close(fd)
    try:
        joblib.dump(obj, tmp)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def save_model(result: dict, output_dir) -> Path:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    _atomic_dump(result["model"], out / "model.pkl")
    _atomic_dump(result["metadata"], out / "metadata.pkl")
    meta_for_json = {k: v for k, v in result["metadata"].items() if k != "forecast"}
    with open(out / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(meta_for_json, f, indent=2, default=str)
    result["forecast_df"].to_csv(out / "forecast.csv", index=False)
    if "actual_vs_pred" in result:
        result["actual_vs_pred"].to_csv(out / "actual_vs_predicted.csv", index=False)
    _write_model_card(result, out / "MODEL_CARD.md")
    LOG.info(f"Artifacts saved to {out}")
    return out


def load_model(output_dir) -> dict:
    p = Path(output_dir)
    model = joblib.load(p / "model.pkl")
    metadata = joblib.load(p / "metadata.pkl")
    forecast_df = pd.read_csv(p / "forecast.csv")
    if "Date" in forecast_df.columns:
        forecast_df["Date"] = pd.to_datetime(forecast_df["Date"])
    bundle = {
        "model": model, "metadata": metadata, "forecast_df": forecast_df,
        "test_metrics_df": pd.DataFrame([metadata.get("test_metrics", {})]),
    }
    avp_path = p / "actual_vs_predicted.csv"
    if avp_path.exists():
        avp = pd.read_csv(avp_path)
        if "Date" in avp.columns:
            avp["Date"] = pd.to_datetime(avp["Date"])
        bundle["actual_vs_pred"] = avp
    return bundle


def _write_model_card(result: dict, path: Path) -> None:
    md = result["metadata"]
    lines = [
        "# Leave Forecasting Model Card", "",
        f"- **Model family**: `{md['best_model_name']}`",
        f"- **Trained at**: {md['trained_at']}",
        f"- **Training end date**: {md['training_end_date']}",
        f"- **Test window**: {md['test_start_date']} -> {md['test_end_date']}",
        f"- **Forecast horizon**: {md['forecast_horizon']} days",
        f"- **Features**: {md['n_features']}",
        f"- **Splits**: train={md['n_train']}, val={md['n_val']}, test={md['n_test']}",
        f"- **Data fingerprint**: `{md['data_fingerprint']}`",
        "", "## Metrics", "",
        "| Split | MAE | RMSE | R2 | WAPE | SMAPE |",
        "|-------|-----|------|----|------|-------|",
    ]
    for split, m in [("Train", md["train_metrics"]), ("Val", md["val_metrics"]), ("Test", md["test_metrics"])]:
        lines.append(f"| {split} | {m['MAE']:.2f} | {m['RMSE']:.2f} | {m['R2']:.3f} | "
                     f"{m['WAPE']:.4f} | {m['SMAPE']:.4f} |")
    lines += ["", f"- **Conformal interval**: +/-{md['conformal_radius']:.2f} (alpha={md['conformal_alpha']})", "",
              "## Diagnostics", ""]
    diag = md.get("diagnostics", {})
    if diag.get("warnings"):
        for w in diag["warnings"]:
            lines.append(f"- WARNING: {w}")
    else:
        lines.append("- No over/underfitting warnings.")
    lines += ["", "## Top features", ""]
    for fi in md.get("feature_importance", [])[:15]:
        lines.append(f"- `{fi['feature']}` -- {fi['importance']:.4f}")
    lines += ["", "## Environment", ""]
    for k, v in md.get("env", {}).items():
        lines.append(f"- {k}: `{v}`")
    path.write_text("\n".join(lines), encoding="utf-8")


# ═════════════════════════════════════════════════════════════
# CLI
# ═════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Train production leave forecasting model.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--output", default="artifacts")
    parser.add_argument("--forecast-horizon", type=int, default=30)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--as-of-date", default=None)
    parser.add_argument("--gpu", action="store_true")
    parser.add_argument("--gpu-device", default="cuda")
    args = parser.parse_args()

    raw = pd.read_csv(args.data, low_memory=False)
    cfg = TrainingConfig(seed=args.seed, forecast_horizon=args.forecast_horizon,
                         use_gpu=args.gpu, gpu_device=args.gpu_device)
    result = train_model(raw, as_of_date=args.as_of_date,
                         forecast_horizon=args.forecast_horizon, seed=args.seed, config=cfg)
    save_model(result, Path(args.output))
    md = result["metadata"]
    print("\n=== Test Metrics ===")
    print(pd.DataFrame([md["test_metrics"]]).to_string(index=False))
    print(f"\nBest Model: {md['best_model_name']}")
    if md["diagnostics"].get("warnings"):
        print("\nWarnings:")
        for w in md["diagnostics"]["warnings"]:
            print(f"  - {w}")
