# OptiShift Intelligence — Derived Values & Calculation Reference

> **Purpose:** This document explains every metric, KPI, and chart in the dashboard — what data source it uses, how it is calculated, and where the code lives.

---

## 📁 Data Sources

| Source File | Used For |
|-------------|----------|
| `Data/Combined_All_Leave_Data.csv` | All leave analytics, model training, forecasting |
| `Employee Master - Feb 2026 Team Member.xlsx` (sheets: *Live*, *Left*) | Headcount series, workforce features, live employee count |
| `artifacts/leave_forecasting_model.pkl` | Saved XGBoost/RF/GBR model used for predictions |
| `artifacts/leave_forecasting_metadata.pkl` | Feature list, training dates, prediction interval bounds |
| `indian_calendar.py` (module) | Festival calendar — 429 festivals, 2020-2030, 7 religions |

---

## 🔄 Data Pipeline (How raw data becomes analytics)

```
Combined_All_Leave_Data.csv
        │
        ▼  clean_leave_data()
   Filter Status == "Approved"
   Parse date columns (dayfirst=True)
   Drop duplicates (EmpNo + Leave Type + From Date + To Date)
   Fill missing text columns → "Unknown"
        │
        ▼  expand_leave_records_full()
   Each leave record expanded to ONE ROW PER CALENDAR DAY
   (if From=Jan 1, To=Jan 3 → 3 rows: Jan 1, Jan 2, Jan 3)
   Columns retained: Date, EmpNo, Department, Location,
                     Leave Type, Cost Centre, Type, Leave Reason
        │
        ▼  full_expanded_frame  ← used by ALL analytics tabs
```

---

## 📈 Tab 1 — Forecasting

### Model Evaluation Metrics

| Metric | Formula | Interpretation |
|--------|---------|----------------|
| **MAE** | `mean(|actual - predicted|)` | Avg employees mis-forecast per day |
| **RMSE** | `sqrt(mean((actual - predicted)²))` | Penalises large errors more |
| **MAPE** | `mean(|actual - predicted| / actual)` where actual ≠ 0 | % error on non-zero days |
| **R²** | `1 - SS_res / SS_tot` | Variance explained; 1.0 = perfect |
| **WAPE** | `sum(|actual - predicted|) / sum(|actual|)` | Primary metric; weighted by volume |
| **SMAPE** | `mean(2|actual - predicted| / (|actual| + |predicted|))` | Symmetric percentage error |

> **Code:** `weighted_absolute_percentage_error()`, `symmetric_mean_absolute_percentage_error()` in `streamlit_app.py`  
> **Test window:** Defined in `metadata["test_start_date"]` → `metadata["test_end_date"]` (last 15% of history)

### Forecast Generation

```
Feature row for target date
      │
      ▼  model.predict(features)
Predicted_Leave_Count  (clipped to ≥ 0)
      │
      ▼  apply_prediction_interval()
Lower_Bound = prediction + residual_p05
Upper_Bound = prediction + residual_p95
(residuals from holdout evaluation stored in metadata)
```

### Workforce Planner Derived Columns

| Column | Formula |
|--------|---------|
| `Total_Expected_Absent` | `Predicted_Leave_Count + Known_Absent_Employees` |
| `Projected_Available` | `max(Total_Workforce - Total_Expected_Absent, 0)` |
| `Coverage_Gap` | `max(Required_Present - Projected_Available, 0)` |
| `Total_Staff_Needed` | `Required_Present + Total_Expected_Absent` |
| `Additional_Headcount_Needed` | `max(Total_Staff_Needed - Total_Workforce, 0)` |

> **Inputs:** Sidebar sliders — *Current total workforce*, *Required present workforce*, *Known planned absences*

---

## 🧭 Tab 2 — Executive Intelligence

### `prepare_leave_intelligence()` → `build_leave_intelligence_dataset()`

Each row of `full_expanded_frame` is enriched daily:

| Column | Derivation |
|--------|-----------|
| `Employees_On_Leave` | `nunique(EmpNo)` per Date |
| `Staffing_Relevant_Employees` | Employees on leave **excluding** Special Leave & Comp-Off |
| `Unplanned_Days` | Rows where `Type == "Un-Planned"` |
| `Unplanned_Share` | `Unplanned_Days / Employees_On_Leave` |
| `Special_Leave_Share` | Rows where `Leave Type` ∈ {"Special Leave [Not Call ON Duty]", "Comp-Off"} |
| `Cost_Centres_Affected` | `nunique(Cost Centre)` per Date |
| `Departments_Affected` | `nunique(Department)` per Date |
| `Sick_Leave` | Count where Leave Type contains "Sick" |
| `Casual_Leave` | Count where Leave Type contains "Casual" |
| `Others` | Leave days not classified as Sick or Casual |

### Forecast Extension

When the date exceeds the last historical date, the Executive Intelligence chart appends forecast rows from `metadata["next_30_days_forecast"]`. These rows show `Employees_On_Leave = Predicted_Leave_Count` and all other columns default to 0 (no breakdown available for future dates).

---

## 🔵 Tab 3 — Special Leave & Comp-Off

**Filter:** `Leave Type` ∈ `{"Special Leave [Not Call ON Duty]", "Comp-Off"}`  
**Source:** `full_expanded_frame`

| Metric | Derivation |
|--------|-----------|
| Total Special Leave Days | `shape[0]` of filtered frame |
| Employees Affected | `nunique(EmpNo)` |
| By Department | `groupby(Department).size()` |
| Monthly Trend | `groupby(Date.to_period("M")).nunique(EmpNo)` |

---

## 🏭 Tab 4 — Cost Centre Analysis

**Source:** `full_expanded_frame` filtered by `Cost Centre`

| Chart | Calculation |
|-------|-------------|
| Leave by Cost Centre | `groupby([Period, Cost Centre]).nunique(EmpNo)` |
| Risk Score | `(Unplanned_Days / Total_Days) × 100` per Cost Centre |
| Top Employees by CC | `groupby([Cost Centre, EmpNo]).size()` sorted descending |

---

## 📊 Tab 5 — Planned vs Unplanned

**Source:** `full_expanded_frame`, column `Type` (values: "Planned", "Un-Planned")

| Metric | Derivation |
|--------|-----------|
| Planned Days | `count(Type == "Planned")` |
| Unplanned Days | `count(Type == "Un-Planned")` |
| Unplanned % | `Unplanned_Days / (Planned + Unplanned) × 100` |
| Monthly trend | `groupby([Month, Type]).nunique(EmpNo)` |
| Department split | `groupby([Department, Type]).size()` |

---

## 🔍 Tab 6 — Leave Reason & Prediction

**Source:** `full_expanded_frame`, column `Leave Reason`

| Chart | Calculation |
|-------|-------------|
| Top Leave Reasons | `value_counts(Leave Reason).head(N)` |
| Reason by Month | `groupby([Month, Leave Reason]).size()` |
| SHAP Explainability | `shap.TreeExplainer(model).shap_values(feature_row)` — shows each feature's contribution to the prediction for a selected date |

---

## 📈 Tab 7 — Daily CC Leave

**Source:** `full_expanded_frame`  
**Slicers:** From/To dates, Year, Granularity, Leave Type, Cost Centre, **Department** (new), Planned/Unplanned, YoY toggle

### Aggregation

```
full_expanded_frame
  → filter by all slicers
  → assign _Period:
      Daily   = Date.normalize()
      Weekly  = Date.to_period("W").start_time
      Monthly = Date.to_period("M").start_time
  → groupby([_Period, Cost Centre]).nunique(EmpNo)
  → → "Employees on Leave" per period per CC
```

### KPIs

| KPI | Formula |
|-----|---------|
| Total Leave Days | `filtered_df.shape[0]` (one row per employee-day) |
| Cost Centres | `nunique(Cost Centre)` |
| Employees on Leave | `nunique(EmpNo)` |
| Avg Days / Employee | `Total Leave Days / Employees on Leave` |

### Planned vs Unplanned Bifurcation

| KPI | Formula |
|-----|---------|
| Planned Days | `count(Type == "Planned")` after title-casing |
| Unplanned Days | `count(Type == "Un-Planned")` |
| Unplanned % | `Unplanned_Days / total × 100` |
| Planned Emp | `nunique(EmpNo where Type == "Planned")` |
| Unplanned Emp | `nunique(EmpNo where Type == "Un-Planned")` |

### Year-over-Year Comparison (toggle)

```
Current period: Date range [_dcc_start, _dcc_end]
Prior period:   Date range [_dcc_start - 1 year, _dcc_end - 1 year]

Both filtered with identical slicer values.

Prior year dates are shifted +1 year for visual overlay.

KPI delta = Current - Prior (red if increase, green if decrease,
            since higher leave = worse for staffing)

Department YoY table = outer join of:
  current_year.groupby(Department).nunique(EmpNo)
  prior_year.groupby(Department).nunique(EmpNo)
  → Change = Current Year Emp - Prior Year Emp
```

---

## 🗓️ Tab 8 — Indian Festival Calendar

**Source:** `indian_calendar.py` module (no CSV — dates are hard-coded from authoritative Indian calendar sources for 2020-2030)

| Column | Description |
|--------|-------------|
| `Date` | Exact date of the festival |
| `Festival` | Name of the festival |
| `Religion` | Hindu / Muslim / Christian / Sikh / Jain / Buddhist / National |
| `Is_Gazetted` | True if it is a Central Government Gazette public holiday |
| `Day_Name` | Day of week |
| `Month` / `Month_Name` | Numeric and text month |
| `Year` | Calendar year |

### Leave Correlation

```
For each festival date in the filtered list:
  → Look up actual Employees_On_Leave on that date from full_expanded_frame
  → groupby(Festival).mean(Employees_On_Leave)
  → Compare vs overall org average (mean across all dates)
```

### Spike Analysis (±3 days) — Vectorized

```
For each unique festival date:
  Generate 7 check_dates: [date-3, date-2, date-1, date, date+1, date+2, date+3]

Cross-join festivals × offsets (no Python loop — pandas merge)
  → merge with daily leave counts
  → groupby(Offset).mean(Employees)

Plotted as a bar chart showing avg employees on leave 
relative to festival dates.
```

---

## 🤖 Model Feature Engineering

All features are derived from `Combined_All_Leave_Data.csv` + `Employee Master`:

### Calendar Features
| Feature | Formula |
|---------|---------|
| `day_of_week` | `Date.dayofweek` (0=Mon, 6=Sun) |
| `month` | `Date.month` |
| `week_of_year` | `Date.isocalendar().week` |
| `is_weekend` | `day_of_week >= 5` |
| `is_holiday` | Date found in `holidays.India()` |
| `is_long_weekend` | Date within 1 day of both a holiday and a weekend |
| `is_post_holiday` | `(Date - 1 day)` is a holiday |
| `is_monday` | `day_of_week == 0` |
| `is_friday` | `day_of_week == 4` |
| `month_sin/cos` | `sin/cos(2π × month / 12)` — cyclical encoding |
| `week_sin/cos` | `sin/cos(2π × week / 52)` |
| `day_sin/cos` | `sin/cos(2π × day_of_week / 7)` |

### Lag & Rolling Features
| Feature | Formula |
|---------|---------|
| `leave_lag_N` | `Leave_Count` shifted by N days (N = 1,2,3,5,7,14,21,30,45,60) |
| `rolling_mean_N` | Rolling mean over N days with 1-day shift |
| `rolling_std_N` | Rolling std deviation |
| `rolling_min/max_N` | Rolling min/max |
| `expanding_mean` | Cumulative mean from series start |
| `ewm_mean_7/30` | Exponentially weighted mean (span 7 and 30) |

### Workforce Features (from Employee Master)
| Feature | Derivation |
|---------|-----------|
| `active_employee_count` | Cumulative join/exit deltas from DOJ/DOL per date |
| `active_team_member_count` | Filtered to designation containing "Team Member" |
| `active_indirect_count` | Filtered to Direct/Indirect == "Indirect" |
| `active_local_count` | Filtered to Local/Non-Local == "Local" |
| `indirect_workforce_share` | `active_indirect / active_employee_count` |
| `local_workforce_share` | `active_local / active_employee_count` |
| `join_count_30d` | Rolling 30-day sum of new joiners |
| `exit_count_30d` | Rolling 30-day sum of exits |
| `workforce_growth_30d` | `active_employee_count.diff(30)` |

### Department & Leave Type Features
| Feature | Derivation |
|---------|-----------|
| `department_avg_leave` | `mean(Leave_Count per Department)` per date |
| `department_leave_frequency` | `nunique(Departments)` per date |
| `dept_<name>` | Daily leave count for top 5 departments (one-hot style) |
| `leave_type_daily_<name>` | Daily count for top 5 leave types |
| `leave_type_share_<name>` | Monthly share of each leave type vs total |

---

## 🏗️ Generalized Model (`generalized_model/`)

| File | Purpose |
|------|---------|
| `train_model.py` | Standalone training pipeline — accepts any leave CSV |
| `streamlit_app.py` | Upload CSV → train → forecast dashboard |
| `indian_calendar.py` | Copy of festival calendar module |
| `requirements.txt` | Independent dependencies |

### Generalized Model — Required CSV Columns

| Column | Description |
|--------|-------------|
| `EmpNo` | Employee identifier |
| `From Date` | Leave start date |
| `To Date` | Leave end date |
| `Status` | Must contain "Approved" |

### Optional Columns
`Leave Type`, `Department`, `Cost Centre`, `Leave Reason`, `Type` (Planned/Un-Planned)

### Training Pipeline
```
Upload CSV
  → clean_leave_data() — same logic as main app
  → expand_to_daily() — one row per employee-day
  → build_feature_dataset() — calendar + lag + holiday features
  → Walk-forward cross-validation
  → Train: XGBoost (preferred), RandomForest, GradientBoosting
  → Select best by WAPE
  → save_model() → artifacts/model.pkl + metadata.pkl + forecast.csv
```

---

## 🔢 Performance Optimizations Implemented

| Optimization | Method |
|-------------|--------|
| Model + dataset loading | `@st.cache_resource` — loads once, never re-runs |
| Model evaluation | `@st.cache_data` — recomputed only if inputs change |
| Festival calendar | `@st.cache_data(cached_festival_calendar)` |
| Daily leave counts | `@st.cache_data(cached_daily_leave_counts)` |
| Festival spike analysis | Vectorized cross-join (no Python for-loop) |
| Leave intelligence prep | `@st.cache_data(prepare_leave_intelligence)` |
