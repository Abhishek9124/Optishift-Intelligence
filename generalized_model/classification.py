"""
Per-employee leave probability classification head.

Predicts: P(employee X takes leave on day D | features available before D).

This is structurally different from the daily-aggregate regression head:
- The training set is a panel of (Date, EmpNo) rows.
- Positive rows: the employee actually had an approved leave that day.
- Negative rows: the employee was "active" (seen in dataset within trailing
  90 days) but did NOT take leave that day.

We sub-sample negatives because the panel grows quadratically in employees x
days; for typical orgs negative-to-positive ratios are large enough that
careful sampling is required to keep training tractable and model calibrated.

Class imbalance is handled via:
- `scale_pos_weight` (tree models).
- Calibrated probabilities via Platt scaling on a held-out fold (sklearn's
  CalibratedClassifierCV with prefit) — classification probabilities should
  reflect actual frequencies, not just rank.

Public API:
    train_classifier(raw_df, employee_daily, ...) -> dict
    save_classifier(result, output_dir)
    load_classifier(output_dir) -> dict
    predict_employee_day(model_bundle, emp_no, target_date, ...) -> dict
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score, roc_auc_score,
    brier_score_loss, log_loss,
)
from sklearn.model_selection import TimeSeriesSplit

try:
    from xgboost import XGBClassifier
    XGB_OK = True
except ImportError:
    XGBClassifier = None  # type: ignore
    XGB_OK = False

try:
    from lightgbm import LGBMClassifier
    LGBM_OK = True
except ImportError:
    LGBMClassifier = None  # type: ignore
    LGBM_OK = False

LOG = logging.getLogger("classification")
if not LOG.handlers:
    import sys as _sys
    _h = logging.StreamHandler(_sys.stdout)
    _h.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s | %(message)s", "%H:%M:%S"))
    LOG.addHandler(_h)
LOG.setLevel(logging.INFO)


@dataclass
class ClassifierConfig:
    seed: int = 42
    test_fraction: float = 0.15
    val_fraction: float = 0.15
    negative_ratio: float = 5.0   # negatives per positive (in training only)
    min_active_window_days: int = 90  # employee considered active if seen within this window
    use_gpu: bool = False
    gpu_device: str = "cuda"
    n_jobs: int = 1


# ═════════════════════════════════════════════════════════════
# Panel construction
# ═════════════════════════════════════════════════════════════

def _build_positive_panel(clean: pd.DataFrame) -> pd.DataFrame:
    """Positives: each (Date, EmpNo) where the employee had an approved leave."""
    base = clean[["EmpNo", "From Date", "To Date"]].copy()
    counts = (base["To Date"] - base["From Date"]).dt.days.add(1).astype(int).clip(lower=0)
    if counts.sum() == 0:
        return pd.DataFrame(columns=["Date", "EmpNo"])
    repeated = base.loc[base.index.repeat(counts)].copy()
    repeated["Date"] = np.concatenate([
        pd.date_range(s, e, freq="D").to_numpy()
        for s, e in zip(base["From Date"], base["To Date"])
    ])
    return repeated[["Date", "EmpNo"]].drop_duplicates().reset_index(drop=True)


def _sample_negative_panel(positive_panel: pd.DataFrame, employee_daily: pd.DataFrame,
                           ratio: float, seed: int) -> pd.DataFrame:
    """Negatives: (Date, EmpNo) pairs from the active panel that are NOT positives."""
    rng = np.random.default_rng(seed)
    pos_keys = set(zip(positive_panel["Date"].astype("datetime64[ns]").astype("int64"),
                       positive_panel["EmpNo"].astype(str)))
    pool = employee_daily[["Date", "EmpNo"]].copy()
    pool["Date"] = pd.to_datetime(pool["Date"])
    pool_keys = list(zip(pool["Date"].astype("datetime64[ns]").astype("int64"),
                         pool["EmpNo"].astype(str)))
    neg_idx = [i for i, k in enumerate(pool_keys) if k not in pos_keys]
    n_neg = int(len(positive_panel) * ratio)
    if n_neg <= 0 or not neg_idx:
        return pool.iloc[0:0].copy()
    if len(neg_idx) > n_neg:
        sampled = rng.choice(neg_idx, size=n_neg, replace=False)
        return pool.iloc[sampled].reset_index(drop=True)
    return pool.iloc[neg_idx].reset_index(drop=True)


def _attach_features(panel: pd.DataFrame, employee_daily: pd.DataFrame,
                     daily_extras: pd.DataFrame | None) -> pd.DataFrame:
    """Merge per-employee and per-day features onto a (Date, EmpNo) panel."""
    panel = panel.copy()
    panel["Date"] = pd.to_datetime(panel["Date"])
    if not employee_daily.empty:
        ed = employee_daily.copy()
        ed["Date"] = pd.to_datetime(ed["Date"])
        panel = panel.merge(ed, on=["Date", "EmpNo"], how="left")
    if daily_extras is not None and not daily_extras.empty:
        de = daily_extras.copy()
        de["Date"] = pd.to_datetime(de["Date"])
        panel = panel.merge(de, on="Date", how="left")
    # Calendar features
    d = panel["Date"]
    panel["dow"] = d.dt.dayofweek
    panel["month"] = d.dt.month
    panel["is_weekend"] = d.dt.dayofweek.isin([5, 6]).astype(int)
    panel["dow_sin"] = np.sin(2 * np.pi * d.dt.dayofweek / 7)
    panel["dow_cos"] = np.cos(2 * np.pi * d.dt.dayofweek / 7)
    panel["month_sin"] = np.sin(2 * np.pi * d.dt.month / 12)
    panel["month_cos"] = np.cos(2 * np.pi * d.dt.month / 12)
    return panel


# ═════════════════════════════════════════════════════════════
# Training
# ═════════════════════════════════════════════════════════════

def train_classifier(
    raw_df: pd.DataFrame,
    employee_daily: pd.DataFrame,
    daily_extras: pd.DataFrame | None = None,
    config: ClassifierConfig | None = None,
) -> dict[str, Any]:
    """Train per-employee daily leave classifier."""
    cfg = config or ClassifierConfig()
    LOG.info(f"Classifier training started (negatives:positives = {cfg.negative_ratio}:1)")

    from gen_training import clean_leave_data
    clean = clean_leave_data(raw_df)
    if clean.empty or employee_daily.empty:
        raise ValueError("Empty input — cannot train classifier.")

    positives = _build_positive_panel(clean)
    if positives.empty:
        raise ValueError("No positive examples — no approved leaves found.")
    positives["Label"] = 1
    LOG.info(f"  positives: {len(positives)}")

    negatives = _sample_negative_panel(positives, employee_daily, cfg.negative_ratio, cfg.seed)
    negatives["Label"] = 0
    LOG.info(f"  negatives sampled: {len(negatives)}")

    panel = pd.concat([positives, negatives], ignore_index=True)
    panel = _attach_features(panel, employee_daily, daily_extras)
    panel = panel.sort_values("Date").reset_index(drop=True)

    feature_cols = [c for c in panel.columns
                    if c not in {"Date", "EmpNo", "Label"} and np.issubdtype(panel[c].dtype, np.number)]
    if not feature_cols:
        raise ValueError("No numeric features built. Did data_enrichment run?")

    X = panel[feature_cols].fillna(panel[feature_cols].median()).fillna(0).values
    y = panel["Label"].values

    n = len(panel)
    n_test = max(50, int(n * cfg.test_fraction))
    n_val = max(50, int(n * cfg.val_fraction))
    X_train, X_val, X_test = X[:n - n_val - n_test], X[n - n_val - n_test:n - n_test], X[n - n_test:]
    y_train, y_val, y_test = y[:n - n_val - n_test], y[n - n_val - n_test:n - n_test], y[n - n_test:]

    pos_w = max(1.0, (len(y_train) - y_train.sum()) / max(y_train.sum(), 1))
    LOG.info(f"  scale_pos_weight = {pos_w:.2f}")

    if XGB_OK:
        kw = dict(
            n_estimators=1500, max_depth=5, learning_rate=0.05,
            min_child_weight=3, reg_alpha=0.5, reg_lambda=2.0,
            subsample=0.85, colsample_bytree=0.8,
            scale_pos_weight=pos_w, eval_metric="logloss",
            tree_method="hist", random_state=cfg.seed, n_jobs=cfg.n_jobs,
            early_stopping_rounds=40,
        )
        if cfg.use_gpu:
            kw["device"] = cfg.gpu_device
        base = XGBClassifier(**kw)
        base.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)
        family = "XGBoost"
    elif LGBM_OK:
        base = LGBMClassifier(
            n_estimators=1000, num_leaves=31, learning_rate=0.05,
            min_child_samples=10, reg_alpha=0.5, reg_lambda=2.0,
            subsample=0.85, colsample_bytree=0.8,
            class_weight={0: 1.0, 1: pos_w},
            random_state=cfg.seed, n_jobs=cfg.n_jobs, verbose=-1,
        )
        base.fit(X_train, y_train)
        family = "LightGBM"
    else:
        from sklearn.ensemble import GradientBoostingClassifier
        base = GradientBoostingClassifier(
            n_estimators=400, max_depth=3, learning_rate=0.05, subsample=0.85, random_state=cfg.seed,
        )
        base.fit(X_train, y_train)
        family = "GradientBoosting"

    # Calibration on val → reliable probabilities
    calibrator = CalibratedClassifierCV(base, method="sigmoid", cv="prefit")
    calibrator.fit(X_val, y_val)

    # Evaluate on test
    y_proba = calibrator.predict_proba(X_test)[:, 1]
    y_pred = (y_proba >= 0.5).astype(int)

    metrics = {
        "Accuracy": float(accuracy_score(y_test, y_pred)),
        "Precision": float(precision_score(y_test, y_pred, zero_division=0)),
        "Recall": float(recall_score(y_test, y_pred, zero_division=0)),
        "F1": float(f1_score(y_test, y_pred, zero_division=0)),
        "ROC_AUC": float(roc_auc_score(y_test, y_proba)) if len(np.unique(y_test)) > 1 else 0.0,
        "Brier": float(brier_score_loss(y_test, y_proba)),
        "LogLoss": float(log_loss(y_test, np.clip(y_proba, 1e-7, 1 - 1e-7))),
        "Positive_Rate": float(y_test.mean()),
    }
    LOG.info(f"  Test: Acc={metrics['Accuracy']:.3f} F1={metrics['F1']:.3f} "
             f"AUC={metrics['ROC_AUC']:.3f} Brier={metrics['Brier']:.4f}")

    # Calibration curve points
    cal_curve = _calibration_points(y_test, y_proba)

    feature_importance = []
    if hasattr(base, "feature_importances_"):
        imps = base.feature_importances_
        order = np.argsort(imps)[::-1][:20]
        feature_importance = [{"feature": feature_cols[i], "importance": float(imps[i])} for i in order]

    return {
        "model": calibrator,
        "base_estimator": base,
        "metadata": {
            "family": family,
            "feature_columns": feature_cols,
            "metrics": metrics,
            "calibration_curve": cal_curve,
            "feature_importance": feature_importance,
            "n_train": len(X_train), "n_val": len(X_val), "n_test": len(X_test),
            "scale_pos_weight": pos_w,
        },
        "panel_test": panel.iloc[n - n_test:].reset_index(drop=True).assign(
            Predicted_Probability=y_proba,
            Predicted_Label=y_pred,
        ),
    }


def _calibration_points(y_true, y_proba, bins: int = 10) -> list[dict]:
    """Reliability-diagram points: predicted prob bin -> empirical positive rate."""
    out = []
    edges = np.linspace(0, 1, bins + 1)
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (y_proba >= lo) & (y_proba < hi if hi < 1 else y_proba <= hi)
        if not mask.any():
            continue
        out.append({
            "bin_lo": float(lo), "bin_hi": float(hi),
            "n": int(mask.sum()),
            "mean_predicted": float(y_proba[mask].mean()),
            "empirical_positive_rate": float(y_true[mask].mean()),
        })
    return out


# ═════════════════════════════════════════════════════════════
# Persistence & inference
# ═════════════════════════════════════════════════════════════

def save_classifier(result: dict, output_dir) -> Path:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    joblib.dump(result["model"], out / "classifier.pkl")
    joblib.dump(result["metadata"], out / "classifier_metadata.pkl")
    if "panel_test" in result and not result["panel_test"].empty:
        result["panel_test"].to_csv(out / "classifier_test_panel.csv", index=False)
    return out


def load_classifier(output_dir) -> dict:
    p = Path(output_dir)
    return {
        "model": joblib.load(p / "classifier.pkl"),
        "metadata": joblib.load(p / "classifier_metadata.pkl"),
    }


def predict_employee_day(bundle: dict, emp_no, target_date,
                         employee_daily: pd.DataFrame,
                         daily_extras: pd.DataFrame | None = None) -> dict[str, Any]:
    """Probability that `emp_no` takes leave on `target_date`."""
    target_date = pd.Timestamp(target_date)
    panel = pd.DataFrame({"Date": [target_date], "EmpNo": [emp_no]})
    panel = _attach_features(panel, employee_daily, daily_extras)
    feat_cols = bundle["metadata"]["feature_columns"]
    for c in feat_cols:
        if c not in panel.columns:
            panel[c] = 0.0
    X = panel[feat_cols].fillna(0).values
    proba = float(bundle["model"].predict_proba(X)[0, 1])
    return {
        "EmpNo": emp_no, "Date": str(target_date.date()),
        "leave_probability": proba,
        "predicted_label": int(proba >= 0.5),
    }
