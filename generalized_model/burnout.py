"""
Burnout risk scoring.

Burnout is a derived metric, not a learned model — there's no ground-truth
"this employee is burnt out" label in any HR dataset. So we score it
heuristically using signals that correlate with elevated burnout risk in
HR research:

1. **Low recent leave usage** — employees who haven't taken leave in a long
   time are more likely to be running on fumes.
2. **Long stretches without breaks** — consecutive working days without any
   leave (incl. weekends-only).
3. **Leave-balance accumulation** — high unused balance signals not taking
   what's owed.
4. **Recent intensity** — a recent SPIKE of unplanned/sick leave can also
   indicate strain (so we score this two-sidedly: too few AND too many
   unplanned leaves both raise risk).

Each signal is min-max normalized within the population, weighted, and
combined into a 0–100 risk score. We expose the component scores too so
HR can see WHY a given employee is flagged.

Public API:
    compute_burnout_scores(raw_df, employee_daily, as_of_date=None) -> pd.DataFrame
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class BurnoutConfig:
    weights: dict[str, float] = None  # populated in __post_init__
    risk_band_lo: float = 33.0
    risk_band_hi: float = 66.0

    def __post_init__(self):
        if self.weights is None:
            self.weights = {
                "low_recent_usage": 0.25,
                "long_streak_no_leave": 0.30,
                "high_balance": 0.15,
                "unplanned_spike": 0.20,
                "tenure_factor": 0.10,
            }


def _normalize(s: pd.Series) -> pd.Series:
    s = pd.to_numeric(s, errors="coerce").fillna(0)
    lo, hi = s.min(), s.max()
    if hi - lo < 1e-9:
        return pd.Series(np.zeros(len(s)), index=s.index)
    return (s - lo) / (hi - lo)


def compute_burnout_scores(
    raw_df: pd.DataFrame,
    employee_daily: pd.DataFrame,
    as_of_date: pd.Timestamp | None = None,
    config: BurnoutConfig | None = None,
) -> pd.DataFrame:
    """One row per active employee with burnout score + component breakdown."""
    cfg = config or BurnoutConfig()
    if employee_daily is None or employee_daily.empty:
        return pd.DataFrame(columns=["EmpNo", "Burnout_Score", "Risk_Band"])

    panel = employee_daily.copy()
    panel["Date"] = pd.to_datetime(panel["Date"])
    if as_of_date is not None:
        panel = panel[panel["Date"] <= pd.Timestamp(as_of_date)]
    if panel.empty:
        return pd.DataFrame(columns=["EmpNo", "Burnout_Score", "Risk_Band"])

    # Latest snapshot per employee
    latest = panel.sort_values("Date").groupby("EmpNo").tail(1).reset_index(drop=True)

    # Compute "unplanned_spike" from raw_df if `Type` column is present
    df = raw_df.copy()
    df.columns = df.columns.str.strip()
    df["From Date"] = pd.to_datetime(df.get("From Date"), errors="coerce", dayfirst=True)
    if as_of_date is not None:
        df = df[df["From Date"] <= pd.Timestamp(as_of_date)]
    type_col = "Type" if "Type" in df.columns else None
    if type_col is not None:
        recent_window = pd.Timestamp(as_of_date or df["From Date"].max()) - pd.Timedelta(days=60)
        recent = df[df["From Date"] >= recent_window]
        unplanned = (
            recent[recent[type_col].astype(str).str.lower().str.contains("unplan", na=False)]
            .groupby("EmpNo").size().rename("Unplanned_Last60")
        )
        latest = latest.merge(unplanned, on="EmpNo", how="left")
    latest["Unplanned_Last60"] = latest.get("Unplanned_Last60", 0)
    latest["Unplanned_Last60"] = pd.to_numeric(latest["Unplanned_Last60"], errors="coerce").fillna(0)

    # Component scores (each 0..1, higher = more risk)
    days_since_col = "Days_Since_Last_Leave" if "Days_Since_Last_Leave" in latest.columns else None
    leaves_30 = "Leaves_Last_30d" if "Leaves_Last_30d" in latest.columns else None
    leaves_90 = "Leaves_Last_90d" if "Leaves_Last_90d" in latest.columns else None
    balance_col = "Total_Leave_Balance" if "Total_Leave_Balance" in latest.columns else None
    tenure_col = "Tenure_Days" if "Tenure_Days" in latest.columns else None

    # 1. Low recent usage — invert recent count so higher = more at risk.
    if leaves_30 is not None:
        c1 = 1.0 - _normalize(latest[leaves_30])
    else:
        c1 = pd.Series(np.zeros(len(latest)))
    # 2. Long streak without any leave
    if days_since_col is not None:
        c2 = _normalize(latest[days_since_col].clip(upper=180))
    else:
        c2 = pd.Series(np.zeros(len(latest)))
    # 3. High accumulated balance
    if balance_col is not None:
        c3 = _normalize(latest[balance_col].clip(lower=0))
    else:
        c3 = pd.Series(np.zeros(len(latest)))
    # 4. Unplanned spike — scaled non-linearly (a couple of unplanned is normal,
    # 5+ is the meaningful tail)
    spike = (latest["Unplanned_Last60"].clip(upper=10) / 10.0)
    c4 = spike
    # 5. Tenure — long-tenure employees in same role have higher burnout base rate
    if tenure_col is not None:
        c5 = _normalize(latest[tenure_col].clip(upper=365 * 5))
    else:
        c5 = pd.Series(np.zeros(len(latest)))

    components = pd.DataFrame({
        "low_recent_usage": c1.values,
        "long_streak_no_leave": c2.values,
        "high_balance": c3.values,
        "unplanned_spike": c4.values,
        "tenure_factor": c5.values,
    })
    w = cfg.weights
    score = sum(components[k] * w[k] for k in components.columns)
    score = (score / sum(w.values())) * 100.0  # 0..100
    score = score.clip(0, 100)

    out = latest[["EmpNo"]].copy()
    out["Burnout_Score"] = score.round(1).values
    out["Risk_Band"] = pd.cut(
        out["Burnout_Score"],
        bins=[-1, cfg.risk_band_lo, cfg.risk_band_hi, 101],
        labels=["Low", "Medium", "High"],
    ).astype(str)
    for col in components.columns:
        out[f"comp_{col}"] = (components[col] * 100).round(1).values
    if days_since_col:
        out["Days_Since_Last_Leave"] = latest[days_since_col].values
    if balance_col:
        out["Total_Leave_Balance"] = latest[balance_col].values
    if leaves_30:
        out["Leaves_Last_30d"] = latest[leaves_30].values
    out["Unplanned_Last60"] = latest["Unplanned_Last60"].values

    return out.sort_values("Burnout_Score", ascending=False).reset_index(drop=True)
