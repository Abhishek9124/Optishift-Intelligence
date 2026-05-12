"""
Anomaly detection on daily leave counts.

Two complementary detectors:
1. Isolation Forest on multi-feature daily snapshots (count, leave-rate,
   day-of-week-adjusted residual, dept-stddev). Catches multivariate outliers.
2. Robust Z-score per day-of-week — flags days that deviate sharply from
   their typical day-of-week mean (median + MAD). Cheap and interpretable.

Returns a DataFrame with anomaly scores and a boolean is_anomaly flag.

Public API:
    detect_anomalies(daily_df, ...) -> pd.DataFrame
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest


@dataclass
class AnomalyConfig:
    seed: int = 42
    contamination: float = 0.04   # ~4% of days flagged as anomalies
    z_threshold: float = 3.5      # robust z-score (modified z) threshold
    iso_n_estimators: int = 200


def _modified_zscore(x: np.ndarray) -> np.ndarray:
    """Modified z-score using median absolute deviation (MAD).

    More robust to outliers than standard z-score.
    """
    if len(x) == 0:
        return x
    med = np.median(x)
    mad = np.median(np.abs(x - med))
    if mad == 0:
        return np.zeros_like(x, dtype=float)
    return 0.6745 * (x - med) / mad


def detect_anomalies(daily_df: pd.DataFrame,
                     count_col: str = "Leave_Count",
                     config: AnomalyConfig | None = None) -> pd.DataFrame:
    """Score each day for anomaly, combining IsolationForest + per-DOW robust z.

    Input:
        daily_df: DataFrame with at least 'Date' and `count_col` columns.
                  Optional: 'Leave_Rate', 'Headcount_90d', 'Dept_Stddev'.
    Returns:
        DataFrame with columns:
            Date, Leave_Count, IsoForest_Score, ModZ_DOW,
            Combined_Score, is_anomaly, anomaly_reason
    """
    cfg = config or AnomalyConfig()
    if daily_df is None or daily_df.empty:
        return pd.DataFrame(columns=["Date", count_col, "is_anomaly"])

    df = daily_df.copy()
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.sort_values("Date").reset_index(drop=True)

    # Build feature matrix for IsolationForest
    feats = [count_col]
    for opt in (
        "Leave_Rate", "Leave_Rate_Lag1",
        "Headcount_90d",
        "Dept_Stddev", "Dept_Stddev_Lag1",
        "Top_Dept_Share", "Top_Dept_Share_Lag1",
    ):
        if opt in df.columns:
            feats.append(opt)
    df["dow"] = df["Date"].dt.dayofweek
    df["month"] = df["Date"].dt.month

    # Day-of-week-adjusted residual (helps the IF separate weekly seasonality from anomalies)
    dow_means = df.groupby("dow")[count_col].transform("median")
    df["dow_residual"] = df[count_col] - dow_means
    feats.append("dow_residual")

    X = df[feats].fillna(0).values
    iso = IsolationForest(
        n_estimators=cfg.iso_n_estimators, contamination=cfg.contamination,
        random_state=cfg.seed, n_jobs=1,
    )
    iso.fit(X)
    iso_score = -iso.score_samples(X)  # higher = more anomalous
    iso_pred = iso.predict(X)  # -1 anomaly, 1 normal

    # Per-day-of-week robust z-score
    modz = np.zeros(len(df))
    for dow_val in range(7):
        mask = (df["dow"].values == dow_val)
        modz[mask] = _modified_zscore(df.loc[mask, count_col].values)

    df["IsoForest_Score"] = iso_score
    df["ModZ_DOW"] = modz
    df["Combined_Score"] = (iso_score - iso_score.min()) / max(iso_score.max() - iso_score.min(), 1e-9) \
                          + np.minimum(np.abs(modz) / cfg.z_threshold, 2.0) / 2.0

    iso_flag = iso_pred == -1
    z_flag = np.abs(modz) >= cfg.z_threshold
    df["is_anomaly"] = iso_flag | z_flag

    reasons = []
    for i in range(len(df)):
        bits = []
        if iso_flag[i]:
            bits.append("multivariate")
        if z_flag[i]:
            direction = "high" if modz[i] > 0 else "low"
            bits.append(f"{direction}-vs-DOW({modz[i]:+.1f}σ)")
        reasons.append("|".join(bits) if bits else "")
    df["anomaly_reason"] = reasons

    return df.drop(columns=["dow", "month"]).reset_index(drop=True)
