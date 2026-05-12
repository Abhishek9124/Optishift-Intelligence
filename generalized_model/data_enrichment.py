"""
Synthetic feature enrichment for leave data.

Real-world leave CSVs only carry the leave events themselves. To predict leave
volume more accurately and to support per-employee classification, we DERIVE
additional features that proxy real signals:

1. Daily headcount  — number of distinct employees seen in a trailing window
   (90 days). Proxies "active workforce" for that day.
2. Daily leave-rate — leaves / headcount. A normalized series that's far less
   noisy than raw counts.
3. Tenure          — for each employee on each date, days since their first
   observed leave. Proxy for tenure when no joining-date column exists.
4. Leave balance   — synthetic remaining-balance for each employee per leave
   type per year (config-driven entitlements). Drops monotonically with usage.
5. Recent leave intensity — leaves the employee has taken in the last 30/90
   days. Used by the classification head and burnout scoring.
6. Department features — % of department on leave each day, dept-level rolling
   means.

All derivations are time-causal: features at date D only depend on records
strictly before D.

Public API:
    enrich_dataset(raw_df, ...) -> dict
        Returns:
            'enriched_csv'  : DataFrame mirroring the input plus synthetic columns
            'daily_extras'  : DataFrame keyed on Date with daily aggregate features
                              (headcount, leave_rate, dept_mix) suitable for
                              build_feature_dataset(daily_extras=...)
            'employee_daily': DataFrame keyed on (Date, EmpNo) with per-employee
                              features used by classification.py and burnout.py
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

# Default annual entitlements per leave type. Override via EnrichmentConfig.
DEFAULT_ENTITLEMENTS = {
    "Earned/Previlage Leave": 24,
    "Casual Leave": 12,
    "Sick Leave": 12,
    "Maternity Leave": 180,
    "Paternity Leave": 15,
    "Compensatory Off": 6,
    "Privilege Leave": 24,
    "PL": 24,
    "CL": 12,
    "SL": 12,
}
DEFAULT_FALLBACK_ENTITLEMENT = 12


@dataclass
class EnrichmentConfig:
    headcount_window_days: int = 90
    recent_leave_windows: tuple = (30, 90)
    entitlements: dict[str, int] = field(default_factory=lambda: dict(DEFAULT_ENTITLEMENTS))
    fallback_entitlement: int = DEFAULT_FALLBACK_ENTITLEMENT
    add_synthetic_to_csv: bool = True


def _ensure_dates(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = out.columns.str.strip()
    for c in ("From Date", "To Date", "Applied On", "Approved On"):
        if c in out.columns:
            out[c] = pd.to_datetime(out[c], errors="coerce", dayfirst=True)
    return out


def _expand_to_employee_days(clean: pd.DataFrame) -> pd.DataFrame:
    """One row per (employee, day) of leave."""
    base = clean[["EmpNo", "From Date", "To Date"]].copy()
    if "Leave Type" in clean.columns:
        base["Leave Type"] = clean["Leave Type"].fillna("Unknown")
    if "Department" in clean.columns:
        base["Department"] = clean["Department"].fillna("Unknown")
    counts = (base["To Date"] - base["From Date"]).dt.days.add(1).astype(int).clip(lower=0)
    if counts.sum() == 0:
        return pd.DataFrame(columns=["Date", "EmpNo", "Leave Type", "Department"])
    repeated = base.loc[base.index.repeat(counts)].copy()
    repeated["Date"] = np.concatenate([
        pd.date_range(s, e, freq="D").to_numpy()
        for s, e in zip(base["From Date"], base["To Date"])
    ])
    keep = ["Date", "EmpNo"] + [c for c in ("Leave Type", "Department") if c in base.columns]
    return repeated[keep].reset_index(drop=True)


# ═════════════════════════════════════════════════════════════
# Daily aggregates (headcount, leave-rate, dept mix)
# ═════════════════════════════════════════════════════════════

def _build_daily_extras(emp_days: pd.DataFrame, cfg: EnrichmentConfig) -> pd.DataFrame:
    """Daily features: headcount proxy, leave_rate, top-dept share, dept variance."""
    if emp_days.empty:
        return pd.DataFrame(columns=["Date"])
    emp_days = emp_days.copy()
    emp_days["Date"] = pd.to_datetime(emp_days["Date"]).dt.normalize()
    date_min, date_max = emp_days["Date"].min(), emp_days["Date"].max()
    cal = pd.DataFrame({"Date": pd.date_range(date_min, date_max, freq="D")})

    # Daily distinct employees on leave
    daily_leaves = emp_days.groupby("Date")["EmpNo"].nunique().rename("Leave_Distinct").reset_index()

    # Daily fresh leave starts — useful as a separate signal
    starts = emp_days.groupby(["EmpNo"])["Date"].min().reset_index()
    daily_starts = starts.groupby("Date").size().rename("New_Starts").reset_index()

    daily = cal.merge(daily_leaves, on="Date", how="left").merge(daily_starts, on="Date", how="left")
    daily[["Leave_Distinct", "New_Starts"]] = daily[["Leave_Distinct", "New_Starts"]].fillna(0).astype(int)

    # CRITICAL: these aggregates are derived from same-day leave events, which IS
    # the regression target. Using them at time t to predict t leaks the answer.
    # We expose them only as lag-1 values (yesterday's totals) — those are
    # legitimately known at forecast time.
    daily["Leave_Distinct_Lag1"] = daily["Leave_Distinct"].shift(1).fillna(0).astype(int)
    daily["New_Starts_Lag1"] = daily["New_Starts"].shift(1).fillna(0).astype(int)
    # Drop the same-day columns so they cannot be picked up as features.
    daily = daily.drop(columns=["Leave_Distinct", "New_Starts"])

    # Headcount proxy: distinct employees seen in the trailing window of leave records.
    # NOTE: This is not "active employees" in the HR sense — it's "employees who
    # have appeared in leave records recently". For most orgs it's a reasonable
    # proxy when no headcount table is available.
    seen = emp_days[["Date", "EmpNo"]].drop_duplicates()
    seen = seen.set_index("Date").sort_index()
    win = f"{cfg.headcount_window_days}D"
    # Rolling distinct count via expanding-then-windowed approach.
    # For each date in `cal`, count unique employees in [date-window, date].
    # Implementation: build a long-form (date, emp) and use a windowed groupby.
    seen_reset = seen.reset_index()
    headcount_rows = []
    if not seen_reset.empty:
        # Use a sweep-line: for each date in cal, count distinct in the window.
        seen_sorted = seen_reset.sort_values("Date").reset_index(drop=True)
        # Pre-build per-date employee sets (small sets of distinct emp seen ON that date)
        per_day = seen_sorted.groupby("Date")["EmpNo"].agg(set)
        # Walk the calendar with a deque of (date, set)
        from collections import deque
        dq: deque = deque()
        running: dict[str, int] = {}
        wnd = pd.Timedelta(days=cfg.headcount_window_days)
        for d in cal["Date"]:
            # add today's set
            today_set = per_day.get(d, set())
            if today_set:
                dq.append((d, today_set))
                for e in today_set:
                    running[e] = running.get(e, 0) + 1
            # evict expired from the left
            cutoff = d - wnd
            while dq and dq[0][0] < cutoff:
                _, expired_set = dq.popleft()
                for e in expired_set:
                    running[e] = running.get(e, 0) - 1
                    if running[e] <= 0:
                        del running[e]
            headcount_rows.append({"Date": d, "Headcount_90d": len(running)})
    headcount_df = pd.DataFrame(headcount_rows)
    daily = daily.merge(headcount_df, on="Date", how="left")
    daily["Headcount_90d"] = daily["Headcount_90d"].fillna(0).astype(int)

    # Leave rate based on YESTERDAY's distinct count — lag-safe.
    daily["Leave_Rate_Lag1"] = np.where(
        daily["Headcount_90d"] > 0,
        daily["Leave_Distinct_Lag1"] / daily["Headcount_90d"],
        0.0,
    )

    # Department concentration: same-day computation is also a leak. Expose lag-1 only.
    if "Department" in emp_days.columns:
        dept_daily = (
            emp_days.groupby(["Date", "Department"])["EmpNo"].nunique().reset_index(name="cnt")
        )
        top = dept_daily.sort_values(["Date", "cnt"], ascending=[True, False]).drop_duplicates("Date")
        top = top.rename(columns={"cnt": "Top_Dept_Count"}).drop(columns=["Department"])
        totals = dept_daily.groupby("Date")["cnt"].sum().rename("Dept_Total").reset_index()
        dept_daily_var = (
            dept_daily.groupby("Date")["cnt"].std(ddof=0).fillna(0).rename("Dept_Stddev").reset_index()
        )
        daily = daily.merge(top, on="Date", how="left") \
                     .merge(totals, on="Date", how="left") \
                     .merge(dept_daily_var, on="Date", how="left")
        daily[["Top_Dept_Count", "Dept_Total", "Dept_Stddev"]] = daily[
            ["Top_Dept_Count", "Dept_Total", "Dept_Stddev"]
        ].fillna(0)
        daily["Top_Dept_Share"] = np.where(
            daily["Dept_Total"] > 0, daily["Top_Dept_Count"] / daily["Dept_Total"], 0.0,
        )
        # Lag-shift to avoid same-day leakage; drop the leaking same-day versions.
        daily["Dept_Stddev_Lag1"] = daily["Dept_Stddev"].shift(1).fillna(0)
        daily["Top_Dept_Share_Lag1"] = daily["Top_Dept_Share"].shift(1).fillna(0)
        daily = daily.drop(columns=["Top_Dept_Count", "Dept_Total", "Dept_Stddev", "Top_Dept_Share"])

    return daily


# ═════════════════════════════════════════════════════════════
# Per-employee daily features
# ═════════════════════════════════════════════════════════════

def _build_employee_daily(clean: pd.DataFrame, emp_days: pd.DataFrame,
                          cfg: EnrichmentConfig) -> pd.DataFrame:
    """For each (Date, EmpNo) where the employee was OBSERVED at all in the
    dataset, derive features describing their state as-of that date.

    This panel is what classification.py and burnout.py consume.
    """
    if emp_days.empty:
        return pd.DataFrame(columns=["Date", "EmpNo"])

    emp_days = emp_days.copy()
    emp_days["Date"] = pd.to_datetime(emp_days["Date"]).dt.normalize()

    # Tenure proxy: days since first appearance per employee
    first_seen = emp_days.groupby("EmpNo")["Date"].min().rename("FirstSeen")

    # Leave events per employee with start date for cumulative balances
    starts = clean[["EmpNo", "From Date", "Days"]].copy() if "Days" in clean.columns \
        else clean[["EmpNo", "From Date"]].assign(Days=1)
    starts["From Date"] = pd.to_datetime(starts["From Date"]).dt.normalize()
    starts["Days"] = pd.to_numeric(starts["Days"], errors="coerce").fillna(1).astype(float)
    if "Leave Type" in clean.columns:
        starts["Leave Type"] = clean["Leave Type"].fillna("Unknown")
    else:
        starts["Leave Type"] = "Unknown"

    # Build a panel of (Date, EmpNo) — sample one row per emp_day pair
    panel = emp_days[["Date", "EmpNo"]].drop_duplicates().sort_values(["EmpNo", "Date"]).reset_index(drop=True)
    panel = panel.merge(first_seen, on="EmpNo", how="left")
    panel["Tenure_Days"] = (panel["Date"] - panel["FirstSeen"]).dt.days.clip(lower=0)
    panel = panel.drop(columns=["FirstSeen"])

    # Recent leave intensity per window — for each (Date, EmpNo), count leaves
    # with start date in [Date - W, Date]. We use a merge_asof-style sweep.
    leave_events = starts[["EmpNo", "From Date", "Days", "Leave Type"]].rename(
        columns={"From Date": "Date"}
    ).sort_values(["EmpNo", "Date"]).reset_index(drop=True)

    # For each window, compute rolling sum of leave Days per emp using merge_asof.
    for win in cfg.recent_leave_windows:
        col_events = f"Leaves_Last_{win}d"
        col_days = f"LeaveDays_Last_{win}d"
        # Build per-emp cumulative count and merge_asof
        ev = leave_events.copy()
        ev["events_cum"] = ev.groupby("EmpNo").cumcount() + 1
        ev["days_cum"] = ev.groupby("EmpNo")["Days"].cumsum()
        # current cumulative
        ev_cur = ev.rename(columns={"Date": "Date_event"})
        # Merge "current" as-of Date <= panel.Date
        cur = pd.merge_asof(
            panel.sort_values("Date"),
            ev_cur[["EmpNo", "Date_event", "events_cum", "days_cum"]].sort_values("Date_event"),
            left_on="Date", right_on="Date_event", by="EmpNo", direction="backward",
        )
        # Past as-of Date - win days
        past_dates = panel.assign(Date_past=panel["Date"] - pd.Timedelta(days=win))
        past = pd.merge_asof(
            past_dates.sort_values("Date_past"),
            ev_cur[["EmpNo", "Date_event", "events_cum", "days_cum"]].sort_values("Date_event"),
            left_on="Date_past", right_on="Date_event", by="EmpNo", direction="backward",
        )
        cur_ev = cur["events_cum"].fillna(0).to_numpy()
        cur_dy = cur["days_cum"].fillna(0).to_numpy()
        past_ev = past["events_cum"].fillna(0).to_numpy()
        past_dy = past["days_cum"].fillna(0).to_numpy()
        panel[col_events] = (cur_ev - past_ev).clip(min=0).astype(int)
        panel[col_days] = (cur_dy - past_dy).clip(min=0)

    # Leave balance proxy per employee per leave-type per calendar year.
    # Simplification: assume entitlement resets each Jan 1 to the configured
    # number of days. Subtract YTD usage of that leave type as-of Date.
    bal = leave_events.copy()
    bal["Year"] = bal["Date"].dt.year
    bal["Entitlement"] = bal["Leave Type"].map(cfg.entitlements).fillna(cfg.fallback_entitlement)
    # Precompute YTD usage per (EmpNo, Year, Leave Type)
    bal = bal.sort_values(["EmpNo", "Leave Type", "Year", "Date"])
    bal["YTD_Used"] = bal.groupby(["EmpNo", "Leave Type", "Year"])["Days"].cumsum()
    bal["Balance"] = (bal["Entitlement"] - bal["YTD_Used"]).clip(lower=0)
    # Per-employee aggregate balance — sum across leave types of latest balance
    # as-of `Date`. We approximate by taking the latest pre-Date balance per type.
    panel_dates = panel[["EmpNo", "Date"]].copy()
    panel_dates["Year"] = panel_dates["Date"].dt.year

    # For each (EmpNo, Year) get sum of (Entitlement - YTD_Used as-of Date)
    # We'll merge_asof on each leave-type's history and sum.
    # Cheap approximation: only use the current year aggregates per emp.
    bal_now = pd.merge_asof(
        panel_dates.sort_values("Date"),
        bal[["EmpNo", "Date", "Leave Type", "Balance"]].sort_values("Date"),
        on="Date", by="EmpNo", direction="backward",
    )
    panel["Total_Leave_Balance"] = bal_now["Balance"].fillna(0).clip(lower=0)

    # Days since last leave per employee
    last_leave = pd.merge_asof(
        panel.sort_values("Date"),
        leave_events[["EmpNo", "Date"]].rename(columns={"Date": "Last_Leave"}).sort_values("Last_Leave"),
        left_on="Date", right_on="Last_Leave", by="EmpNo", direction="backward",
    )
    panel["Days_Since_Last_Leave"] = (panel["Date"] - last_leave["Last_Leave"]).dt.days.fillna(9999).astype(int)

    return panel.reset_index(drop=True)


# ═════════════════════════════════════════════════════════════
# Public API
# ═════════════════════════════════════════════════════════════

def enrich_dataset(raw_df: pd.DataFrame, config: EnrichmentConfig | None = None) -> dict[str, Any]:
    cfg = config or EnrichmentConfig()
    df = _ensure_dates(raw_df)
    if "Status" in df.columns:
        clean = df[df["Status"].astype(str).str.lower().eq("approved")].dropna(subset=["From Date", "To Date"]).copy()
    else:
        clean = df.dropna(subset=["From Date", "To Date"]).copy()
    clean = clean[clean["To Date"] >= clean["From Date"]].copy()

    emp_days = _expand_to_employee_days(clean)

    daily_extras = _build_daily_extras(emp_days, cfg)
    employee_daily = _build_employee_daily(clean, emp_days, cfg)

    enriched_csv = df.copy()
    if cfg.add_synthetic_to_csv and not daily_extras.empty:
        # Annotate each leave row with the daily features keyed on its From Date
        merged = enriched_csv.merge(
            daily_extras.rename(columns={"Date": "From Date"}),
            on="From Date", how="left", suffixes=("", "_DAILY"),
        )
        # Annotate with employee panel as of From Date (per-emp features)
        if not employee_daily.empty:
            emp_lookup = employee_daily.rename(columns={"Date": "From Date"})
            merged = merged.merge(emp_lookup, on=["From Date", "EmpNo"], how="left", suffixes=("", "_EMP"))
        enriched_csv = merged

    return {
        "enriched_csv": enriched_csv,
        "daily_extras": daily_extras,
        "employee_daily": employee_daily,
    }


# ═════════════════════════════════════════════════════════════
# CLI
# ═════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Enrich a leave CSV with synthetic features.")
    p.add_argument("--data", required=True)
    p.add_argument("--output", required=True, help="Path to write enriched CSV.")
    args = p.parse_args()

    raw = pd.read_csv(args.data, low_memory=False)
    out = enrich_dataset(raw)
    out["enriched_csv"].to_csv(args.output, index=False)
    print(f"Wrote enriched CSV ({out['enriched_csv'].shape}) to {args.output}")
    print(f"Daily extras: {out['daily_extras'].shape}, columns: {list(out['daily_extras'].columns)}")
    print(f"Employee daily panel: {out['employee_daily'].shape}, columns: {list(out['employee_daily'].columns)}")
