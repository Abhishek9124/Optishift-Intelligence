# OptiShift Intelligence — Comprehensive Derived Data Dictionary

## Purpose
This document comprehensively documents **every derived field, calculation, and data transformation** performed across the OptiShift Intelligence Streamlit application. It explains the exact formulas, source fields, and business logic for all values displayed in the dashboard.

## How to use this guide
- **For a specific metric**: Search by metric name (e.g., "WAPE", "Coverage Gap")
- **For a specific CSV field**: Search by field name (e.g., "EmpNo", "Leave Type")
- **For a specific tab**: Jump to the section labeled "# X. TabName Tab"
- **For calculation logic**: Look for **Formula:** or **Calculation:** sections

---

# 1. Feature Engineering — Core Data Transformations

This section explains how raw leave and employee data is transformed into model-ready features.

## 1.1 Leave Record Expansion

**Function:** `expand_leave_records()` and `expand_leave_records_full()`

**Purpose:** Convert period-based leave records (From Date → To Date) into daily rows for aggregation.

**Process:**
1. Input: Leave records with `From Date` and `To Date`
2. Calculation: `day_count = (To_Date - From_Date).days + 1` (inclusive of both ends)
3. Output: Repeat each leave record once per day in the period
4. Each expanded row represents one employee on one day

**Example:**
```
Input:  EmpNo=101, From Date=2026-04-15, To Date=2026-04-17, Leave Type="Casual"
Output: Three rows:
  - 2026-04-15, EmpNo=101, Leave Type="Casual"
  - 2026-04-16, EmpNo=101, Leave Type="Casual"
  - 2026-04-17, EmpNo=101, Leave Type="Casual"
```

**CSV fields used:**
- `From Date`, `To Date`, `EmpNo`, `Leave Type`, `Department`, `Location`, `Cost Centre`

## 1.2 Daily Leave Count Aggregation

**Function:** `build_feature_dataset()` — daily aggregation

**Calculation:**
```
Leave_Count = nunique(EmpNo) for each Date
  (Count of unique employees on leave that day)

Leave_Events = count(rows) for each Date
  (Total leave-day records; differs from Leave_Count if employees take multiple leave types)
```

**Example:**
```
On 2026-04-16:
  - Employee 101 on Casual Leave
  - Employee 105 on Sick Leave
  - Employee 203 on Casual Leave
Result: Leave_Count = 3, Leave_Events = 3
```

**Importance:** `Leave_Count` is the **target variable** for the ML model. It represents the daily unique headcount on leave, independent of leave type.

## 1.3 Calendar Features

**Function:** `add_calendar_features()`

**All calendar features extracted directly from the Date column:**

| Feature | Calculation | Business Logic | Example |
|---------|-------------|------------------|---------|
| `day_of_week` | `Date.dt.dayofweek` | 0=Monday, 6=Sunday | Friday=4 |
| `day_name` | `Date.dt.day_name()` | Full day name | "Friday" |
| `month` | `Date.dt.month` | Month number 1-12 | April=4 |
| `day_of_month` | `Date.dt.day` | Day within month | 15 |
| `week_of_year` | `Date.dt.isocalendar().week` | ISO week number | Week 16 |
| `quarter` | `Date.dt.quarter` | Quarter number 1-4 | Q2 |
| `is_weekend` | `day_of_week.isin([5, 6])` | 1 if Saturday/Sunday | 1 for Sat/Sun, 0 otherwise |
| `is_month_start` | `Date.dt.is_month_start` | 1 if first day of month | 1 for April 1 |
| `is_month_end` | `Date.dt.is_month_end` | 1 if last day of month | 1 for April 30 |
| `is_quarter_start` | `Date.dt.is_quarter_start` | 1 if first day of quarter | 1 for April 1 |
| `is_quarter_end` | `Date.dt.is_quarter_end` | 1 if last day of quarter | 1 for June 30 |

**Circular Encoding (Handles month/week/quarter seasonality):**

For cyclical features where Dec→Jan should be close:

| Feature | Formula |
|---------|---------|
| `month_sin` | `sin(2π × month / 12)` |
| `month_cos` | `cos(2π × month / 12)` |
| `week_sin` | `sin(2π × week_of_year / 52)` |
| `week_cos` | `cos(2π × week_of_year / 52)` |
| `day_sin` | `sin(2π × day_of_week / 7)` |
| `day_cos` | `cos(2π × day_of_week / 7)` |
| `quarter_sin` | `sin(2π × quarter / 4)` |
| `quarter_cos` | `cos(2π × quarter / 4)` |

**Why circular encoding?** In raw form, December (12) is far from January (1), but seasonally they're adjacent. Circular encoding preserves this mathematical relationship.

## 1.4 Holiday Features

**Function:** `add_calendar_features()` + `build_holiday_calendar()`

**Holiday Detection:**
```python
holiday_calendar = holidays.India(years=list(range(start_year, end_year + 1)))
holiday_name = holiday_calendar.get(date, "No Holiday")
```

**Derived holiday features:**

| Feature | Calculation | Purpose |
|---------|-------------|---------|
| `is_holiday` | 1 if `holiday_name != "No Holiday"` else 0 | Flag for any public holiday |
| `holiday_name` | Direct lookup from holiday calendar | Official holiday name (e.g., "Republic Day") |
| `festival_name` | `bucket_holiday_name(holiday_name)` | Grouped category (Diwali, Holi, Eid, Christmas, etc.) |
| `is_long_weekend` | 1 if holiday + adjacent day is weekend else 0 | Flag for 3+ day break |
| `is_post_holiday` | 1 if previous day was holiday else 0 | Flag for day after holiday (often high leave) |
| `is_monday` | 1 if day_of_week == 0 else 0 | Monday flag (often high leave for absconding) |
| `is_friday` | 1 if day_of_week == 4 else 0 | Friday flag (common for extensions) |

**Festival Bucketing** (`bucket_holiday_name()`):
```
"Diwali" ← ["diwali", "deepavali"]
"Holi" ← ["holi"]
"Eid" ← ["eid", "id-ul", "bakrid"]
"Christmas" ← ["christmas"]
"Republic Day" ← ["republic"]
"Independence Day" ← ["independence"]
"Other Public Holiday" ← anything else
```

**Interaction Features:**
```
weekend_holiday_interaction = is_weekend × is_holiday
  (High value if holiday falls on weekend)

month_end_holiday_interaction = is_month_end × is_holiday
  (High value if holiday at end of month → longer absence)

long_weekend_holiday_interaction = is_long_weekend × is_holiday
  (Emphasizes multi-day breaks)
```

## 1.5 Historical Leave Features (Lag & Rolling Window)

**Function:** `add_history_features()`

**Purpose:** Capture temporal dependencies and trend information.

### Lag Features
```python
leave_lag_1 = Leave_Count shifted by 1 day (yesterday's leave count)
leave_lag_2 = Leave_Count shifted by 2 days
leave_lag_3 = Leave_Count shifted by 3 days
leave_lag_5 = Leave_Count shifted by 5 days
leave_lag_7 = Leave_Count shifted by 7 days (same day last week)
leave_lag_14 = Leave_Count shifted by 14 days (2 weeks ago)
leave_lag_21 = Leave_Count shifted by 21 days (3 weeks ago)
leave_lag_30 = Leave_Count shifted by 30 days (last month same date)
leave_lag_45 = Leave_Count shifted by 45 days
leave_lag_60 = Leave_Count shifted by 60 days (2 months ago)
```

**Usage:** Model learns patterns like "high leave on Mondays repeats weekly" by seeing lag-7.

### Rolling Window Features (Mean, Std, Min, Max)
```python
rolling_mean_3 = mean(Leave_Count) over last 3 days (shifted by 1)
rolling_mean_7 = mean(Leave_Count) over last 7 days (shifted by 1)
rolling_mean_14, rolling_mean_21, rolling_mean_30, rolling_mean_45, rolling_mean_60

rolling_std_3 = std(Leave_Count) over last 3 days (shifted by 1)
rolling_std_7, rolling_std_14, ... rolling_std_60

rolling_min_3 = min(Leave_Count) over last 3 days
rolling_max_3 = max(Leave_Count) over last 3 days
```

### Expanding Window (Cumulative)
```python
expanding_mean = cumulative mean of Leave_Count up to yesterday
  (Overall average, useful for detecting shifts)

expanding_std = cumulative std of Leave_Count up to yesterday
  (Overall volatility, signals unusual days)
```

### Exponential Weighted Moving Average (EWM)
```python
ewm_mean_7 = exponential weighted mean with span=7
  (Recent days weighted more heavily than older days)

ewm_mean_30 = exponential weighted mean with span=30
  (Longer-term trend, dampens noise)
```

**Why shift by 1?** Prevents leakage—yesterday's data predicts today, not today predicting today.

## 1.6 Department-Level Features

**Function:** `build_feature_dataset()` — department aggregation

**Calculation:**
```python
department_daily = groupby(Date, Department).agg(
  Department_Leave_Count = nunique(EmpNo)
)

department_avg_leave = mean(Department_Leave_Count) grouped by Date
  (Average leave per department for that day)

department_leave_frequency = nunique(Department) grouped by Date
  (How many different departments had leave that day)
```

**Top 5 Department Encoding:** For each of the top 5 departments by frequency:
```
dept_{slugified_name} = sum(Department_Leave_Count) for that department
```

**Example:**
```
dept_sales = Leave count from Sales department that day = 12
dept_operations = Leave count from Operations that day = 8
```

## 1.7 Leave Type Features

**Function:** `build_feature_dataset()` — leave type aggregation

**Daily Leave Type Features:**
```python
leave_type_daily_{slugified_leave_type} = count(rows) for that leave type per day
  (Daily count of each leave type)
```

**Monthly Leave Type Features (Share):**
```python
monthly_total = total leave-days in that month

Leave_Type_Monthly_Share = Leave_Type_Count / monthly_total
  (What percentage of month's leaves were this type?)
```

**Example:**
```
leave_type_share_sick_leave = 0.45 
  (45% of April's leaves were Sick Leave)

leave_type_daily_casual_leave = 8
  (8 leave-days of Casual Leave on this date)
```

## 1.8 Workforce Features (from Employee Master)

**Function:** `build_active_headcount_series()` and master workforce features

**Active Headcount Calculation:**

For each date, calculate cumulative headcount based on hire/exit dates:
```python
employees_active_on_date = count of employees where:
  Date_of_Joining <= current_date AND
  (Date_of_Leaving IS NULL OR Date_of_Leaving >= current_date)
```

**Key workforce features:**

| Feature | Calculation |
|---------|-------------|
| `active_employee_count` | Total active employees on date |
| `active_team_member_count` | Active employees with "Team Member" in designation |
| `active_indirect_count` | Active employees in Indirect roles |
| `active_local_count` | Active employees with "Local" status |
| `indirect_workforce_share` | `active_indirect_count / active_employee_count` |
| `local_workforce_share` | `active_local_count / active_employee_count` |
| `join_count_30d` | Sum of hires in last 30 days (rolling) |
| `exit_count_30d` | Sum of exits in last 30 days (rolling) |
| `workforce_growth_30d` | `active_employee_count.diff(30)` (headcount change over 30 days) |
| `active_master_headcount_{department}` | Active count for each top 3 department |

**Example:**
```
2026-04-16:
  active_employee_count = 845
  join_count_30d = 12 (12 people joined in last month)
  exit_count_30d = 3 (3 people left)
  indirect_workforce_share = 0.35 (35% indirect)
```

---

# 2. Feature Alignment & Model Readiness

**Function:** `align_feature_columns()` and `ensure_model_ready_features()`

**Process:**

1. **Requested columns:** Get list of feature columns model was trained on (from metadata)
2. **Fill missing:** If a feature not in current data, add it with value 0.0
3. **Clean inf values:** Replace `inf` and `-inf` with `NaN`, then `NaN` with 0.0
4. **Sort:** Ensure features are in same order as training
5. **Select:** Return only requested feature columns

**Purpose:** Ensures the model always receives a consistent, properly-shaped feature matrix, even if new features weren't present in training data or are missing in new prediction periods.

---

# 7. Forecasting Tab
Displays model performance, historical accuracy, and operational staffing planning.

## 7.1 Model Performance Metrics

**Function:** `evaluate_saved_model()` and metric functions

**Source:** Holdout test set, comparing model predictions vs. actual vs. naive baseline

**Test Set Selection:**
```python
if test_start_date and test_end_date (from metadata):
    test_df = model_df[(Date >= test_start_date) & (Date <= test_end_date)]
else:
    holdout_size = max(30, int(len(model_ready_df) * 0.15))  # minimum 30 days or 15%
    test_df = model_ready_df.iloc[-holdout_size:]  # last N days
```

### 7.1.1 Mean Absolute Error (MAE)

**Formula:**
$$\text{MAE} = \frac{1}{n} \sum_{i=1}^{n} |y_{\text{actual},i} - y_{\text{pred},i}|$$

**Interpretation:** Average daily error in number of employees. If MAE=5, predictions are off by 5 employees/day on average.

**Calculation in code:**
```python
MAE = mean_absolute_error(y_test, model_predictions)
```

**Example:** If actual leave on 5 days: [10, 15, 12, 18, 11], predicted: [9, 16, 14, 17, 10]
- Errors: [1, 1, 2, 1, 1]
- MAE = (1+1+2+1+1)/5 = 1.2 employees/day

### 7.1.2 Root Mean Squared Error (RMSE)

**Formula:**
$$\text{RMSE} = \sqrt{\frac{1}{n} \sum_{i=1}^{n} (y_{\text{actual},i} - y_{\text{pred},i})^2}$$

**Interpretation:** Penalizes large errors heavily. RMSE >> MAE means occasional large errors.

**Calculation in code:**
```python
RMSE = sqrt(mean_squared_error(y_test, model_predictions))
```

**Why square then sqrt?** Large errors get squared (making them bigger), so RMSE emphasizes avoiding big misses.

### 7.1.3 Mean Absolute Percentage Error (MAPE)

**Formula:**
$$\text{MAPE} = \frac{1}{n} \sum_{i=1}^{n} \left| \frac{y_{\text{actual},i} - y_{\text{pred},i}}{y_{\text{actual},i}} \right| \times 100\%$$

**Interpretation:** Percentage error. Only computed for days with non-zero actual leave.

**Calculation in code:**
```python
def mean_absolute_percentage_error_safe(y_true, y_pred):
    non_zero_mask = y_true != 0
    if not non_zero_mask.any():
        return 0.0
    return mean(abs((y_true[non_zero_mask] - y_pred[non_zero_mask]) / y_true[non_zero_mask])) * 100
```

**Why exclude zero days?** On days with 0 leave, any prediction divides by zero. So MAPE focuses on "real" leave days.

**Example:** Actual=[10, 15, 0], Predicted=[9, 18, 5]
- Non-zero mask: [True, True, False]
- Errors: [|10-9|/10, |15-18|/15] = [0.10, 0.20]
- MAPE = (0.10 + 0.20) / 2 × 100% = 15%

### 7.1.4 Weighted Absolute Percentage Error (WAPE)

**Formula:**
$$\text{WAPE} = \frac{\sum_{i=1}^{n} |y_{\text{actual},i} - y_{\text{pred},i}|}{\sum_{i=1}^{n} |y_{\text{actual},i}|} \times 100\%$$

**Interpretation:** This is the PRIMARY metric. It weights errors by actual leave magnitude, so high-leave days are penalized more. Days with 100 employees on leave matter more than days with 10.

**Calculation in code:**
```python
def weighted_absolute_percentage_error(y_true, y_pred):
    denominator = np.abs(y_true).sum()
    if denominator == 0:
        return 0.0
    return (np.abs(y_true - y_pred).sum() / denominator) * 100
```

**Example:**
- Day 1: Actual=100, Predicted=95 → Error=5
- Day 2: Actual=10, Predicted=12 → Error=2
- Total Actual=110, Total Errors=7
- WAPE = 7/110 × 100% = 6.36%

Day 1 error is weighted 100/110 = 91%, Day 2 only 10/110 = 9%. Why? Because on high-leave days, staffing gaps are critical.

### 7.1.5 Symmetric Mean Absolute Percentage Error (SMAPE)

**Formula:**
$$\text{SMAPE} = \frac{1}{n} \sum_{i=1}^{n} \frac{2|y_{\text{actual},i} - y_{\text{pred},i}|}{|y_{\text{actual},i}| + |y_{\text{pred},i}|} \times 100\%$$

**Interpretation:** Fair metric that treats overprediction and underprediction symmetrically, and works for both high and low values.

**Calculation in code:**
```python
def symmetric_mean_absolute_percentage_error(y_true, y_pred):
    denominator = np.abs(y_true) + np.abs(y_pred)
    non_zero_mask = denominator != 0
    if not non_zero_mask.any():
        return 0.0
    return mean(2 * abs(y_true[non_zero_mask] - y_pred[non_zero_mask]) / denominator[non_zero_mask]) * 100
```

**Bounds:** SMAPE ranges 0-200% (vs. MAPE which can exceed 100%).

### 7.1.6 R² Score (Coefficient of Determination)

**Formula:**
$$R^2 = 1 - \frac{\sum_{i=1}^{n} (y_{\text{actual},i} - y_{\text{pred},i})^2}{\sum_{i=1}^{n} (y_{\text{actual},i} - \bar{y})^2}$$

**Interpretation:** Percentage of variance explained by model. Range: 0 to 1 (or negative for terrible models).
- R² = 0.95 means model explains 95% of variation
- R² = 0.70+ is considered "good"
- R² < 0 means model performs worse than predicting the average

**Calculation in code:**
```python
R2 = r2_score(y_test, model_predictions)
```

**Why this matters for staffing?** R² tells if the model captures the essential variation in leave. R²=0.75 means 75% of leave patterns are predictable.

### 7.1.7 Naive Baseline Comparison

**Formula:**
$$\text{Naive Prediction} = \text{Yesterday's Leave Count} = \text{leave\_lag\_1}$$

**Purpose:** Sanity check. Model should beat "just predict yesterday's value."

**Calculation:**
```python
naive_predictions = test_df["leave_lag_1"].to_numpy()
```

**Interpretation:** If Naive R² = 0.60 and Model R² = 0.72, the model adds 12 percentage points of explanatory power over a trivial baseline.

#### Root source fields used:
- **Leave CSV:** `EmpNo`, `From Date`, `To Date`
- **Feature lineage:** `Department`, `Leave Type`, calendar features, holiday features
- **Employee master:** Workforce features from `SAP Emp No`

## 7.2 Model Context Table
**Source:** `metadata` with fallbacks to loaded bundle

**Values shown:**

| Field | Calculation | Source |
|-------|-------------|--------|
| **Best model name** | `metadata["best_model_name"]` | Model metadata saved during training |
| **Training end date** | `metadata["training_end_date"]` | Last date model was trained on |
| **Feature count** | `len(metadata["feature_columns"])` | Number of model input features |
| **Default forecast horizon** | `metadata["forecast_horizon"]` (default 30) | Days ahead for next-30-day forecast |
| **Current live headcount** | `metadata["current_live_headcount_from_master"]` | Active employees from master data |

#### Source fields used:
- **Metadata fields:**
  - `best_model_name`
  - `training_end_date`
  - `feature_columns` (calendar, history, employee count, holiday features)
  - `forecast_horizon`
  - `current_live_headcount_from_master`

## 7.3 Prediction Intervals (Confidence Bands)

**Function:** `apply_prediction_interval()`

**Purpose:** Quantify uncertainty around point predictions. Show 90% confidence range.

**Data Source:** Residuals from historical test set
```python
residual_p05 = 5th percentile of (actual - predicted)
residual_p95 = 95th percentile of (actual - predicted)
absolute_error_p90 = 90th percentile of abs(actual - predicted)
```

**Bounds Calculation:**
```python
Prediction_Lower_Bound = Predicted_Leave_Count + residual_p05
  (Point forecast + lower residual = lower bound)

Prediction_Upper_Bound = Predicted_Leave_Count + residual_p95
  (Point forecast + upper residual = upper bound)

Prediction_Error_Band_P90 = absolute_error_p90
  (Raw error magnitude at p90, used for uncertainty visualization)
```

**Applied Clipping:**
```python
Lower_Bound = max(Lower_Bound, 0)  # Can't have negative employees
Upper_Bound = max(Upper_Bound, 0)
```

**Interpretation:**
```
Example: On 2026-04-20
  Predicted_Leave_Count = 45
  residual_p05 = -8 (model was sometimes 8 below)
  residual_p95 = +12 (model was sometimes 12 above)
  
Result:
  Lower_Bound = 45 + (-8) = 37
  Upper_Bound = 45 + 12 = 57
  
Message: "We predict 45 on leave, but 90% confident it's between 37-57"
```

**Stored in metadata:**
```python
metadata["prediction_interval"] = {
    "residual_p05": -8.5,
    "residual_p95": 12.3,
    "absolute_error_p90": 10.8
}
```

## 7.4 Iterative Forecast (30-Day Ahead)

**Function:** `iterative_forecast()`

**Purpose:** Generate multi-step ahead predictions. For each future day, predict based on updated history.

**Algorithm:**

```
Given: forecast_horizon (e.g., 30 days)
Process:
1. Start with historical feature data up to today
2. For each day 1 to horizon:
     a. Create features for next_date (calendar + workforce features already known)
     b. Predict Leave_Count using model + these features
     c. Add predicted value to history (for lag features in step 2a)
     d. Store prediction and features
3. Return DataFrame with all 30 predictions

Why update history each iteration?
  - Day 10 prediction uses Days 1-9 actual/predicted values as lag features
  - This captures compounding effects (e.g., weekend patterns building into week)
```

**Code Flow:**
```python
history = bundle["feature_df"][["Date", TARGET_COLUMN]].copy()

for day in range(1, forecast_horizon + 1):
    next_date = history["Date"].max() + timedelta(days=1)
    
    # Build features for next_date
    provisional = history + [next_date, NaN]
    provisional = add_calendar_features(provisional, holiday_calendar)
    provisional = merge with workforce features
    provisional = merge with department features
    provisional = add_history_features(provisional)  # Uses updated history for lags
    
    # Predict
    next_features = provisional.iloc[-1]  # Last row = next_date
    prediction = model.predict(next_features)
    
    # Update history
    history = history + [next_date, prediction]
    forecasts.append({Date: next_date, Predicted_Leave_Count: prediction})

return DataFrame(forecasts)
```

**Key Detail:** `add_history_features()` is called on `provisional` which includes predicted values from previous iterations. This allows the model to learn patterns like "Monday tends to be high after a high-leave Friday."

## 7.5 Next 30 Days Forecast (Stored in Metadata)

**Function:** Pre-computed by `retrain_model.py` and stored as `metadata["next_30_days_forecast"]`

**Displayed Fields:**
- `Date`: Calendar date
- `Day_of_Week`: Day name (Monday-Sunday)
- `Predicted_Leave_Count`: Point forecast for employees on leave
- `Lower_Bound`: 90% confidence lower bound (calculated via prediction interval)
- `Upper_Bound`: 90% confidence upper bound (calculated via prediction interval)

**Summary Statistics Cards:**
```python
Avg_Daily_Leave_30d = mean(Predicted_Leave_Count) for all 30 rows
  (Average daily predicted absence)

Peak_Leave_Day = row with max(Predicted_Leave_Count)
  (Date with highest predicted leave)

Peak_Delta = Peak_Leave_Count - Avg_Daily_Leave_30d
  (How much above average is the peak?)

Total_30Day_EmployeeDays = sum(Predicted_Leave_Count) for all 30 days
  (Total employee-days of predicted absence in next 30 days)
```

**Visualization:**
- Line chart with point forecast
- Shaded area between Upper and Lower bounds
- Color: Primary color for point, confidence band in light blue

## 7.6 Staffing Plan (Forecast + Planning)

**Function:** `forecast_for_specific_date()` → `derive_planning_columns()`

**User Inputs (from Sidebar):**
```
total_workforce: int (Current total headcount, e.g., 850)
required_present_workforce: int (Must-have headcount, e.g., 700)
known_absent_employees: int (Already-scheduled absences, e.g., 30)
```

**Step 1: Get Forecast for Selected Date**

```python
if selected_date <= historical_data.max():
    # Historical date: Use actual historical row
    predicted_leave = model.predict(features_for_date)
    actual_leave = historical_Leave_Count[date]
else:
    # Future date: Use iterative forecast
    forecasted_leave = iterative_forecast(days_ahead)[selected_date]
    actual_leave = NaN
```

**Step 2: Apply Prediction Interval**

```python
Prediction_Lower_Bound = predicted_leave + residual_p05
Prediction_Upper_Bound = predicted_leave + residual_p95
```

**Step 3: Calculate Staffing Derived Fields**

```python
Known_Absent_Employees = user_input

Total_Expected_Absent = round(Predicted_Leave_Count) + known_absent_employees

Projected_Available = max(total_workforce - Total_Expected_Absent, 0)
  (How many people can show up?)

Coverage_Gap = max(required_present_workforce - Projected_Available, 0)
  (Shortfall in required staffing)

Total_Staff_Needed = required_present_workforce + Total_Expected_Absent
  (Everyone required + everyone out = total needed)

Additional_Headcount_Needed = max(Total_Staff_Needed - total_workforce, 0)
  (Extra people to hire to meet gap)

# Conservative versions using upper bound
Conservative_Total_Expected_Absent = round(Prediction_Upper_Bound) + known_absent_employees
Conservative_Projected_Available = max(total_workforce - Conservative_Total_Expected_Absent, 0)
Conservative_Coverage_Gap = max(required_present_workforce - Conservative_Projected_Available, 0)
```

**Step 4: Generate Recommendation**

```python
if Coverage_Gap == 0:
    recommendation = "✅ Can meet required staffing levels"
    risk_color = "green"
elif Coverage_Gap <= required_present_workforce * 0.05:
    recommendation = "⚠️ Minimal gap — monitor closely"
    risk_color = "yellow"
else:
    recommendation = "🔴 Gap exists — may need contingency staffing"
    risk_color = "red"
```

**Example Scenario:**
```
User inputs:
  total_workforce = 850
  required_present_workforce = 750
  known_absent_employees = 30
  selected_date = 2026-04-20

Predictions:
  Predicted_Leave_Count = 45
  Lower_Bound = 37
  Upper_Bound = 57

Calculations:
  Total_Expected_Absent = 45 + 30 = 75
  Projected_Available = 850 - 75 = 775
  Coverage_Gap = 750 - 775 = 0 ✓ (No gap!)
  
  Conservative (using upper bound):
  Conservative_Total_Expected_Absent = 57 + 30 = 87
  Conservative_Projected_Available = 850 - 87 = 763
  Conservative_Coverage_Gap = 750 - 763 = 0 ✓ (Still OK even in worst case)
  
Recommendation: ✅ Can meet required staffing levels
```

## 7.7 Weekly Forecast Window

**Function:** `predict_date_range()` for all dates in [Start_Date, End_Date]

**Process:** Apply `iterative_forecast()` for all dates in range, then apply `derive_planning_columns()`.

**Columns Displayed:**
- Date
- Day_of_Week
- Predicted_Leave_Count (with trend color coding)
- Prediction_Lower_Bound
- Prediction_Upper_Bound
- Conservative_Projected_Available (using upper bound)
- Conservative_Coverage_Gap

**Trend Color Coding:**
```python
if Predicted_Leave_Count > week_average * 1.3:
    color = RED (High risk)
elif Predicted_Leave_Count > week_average:
    color = YELLOW (Medium risk)
else:
    color = GREEN (Low risk)
```

#### Source fields used:
- All feature columns for the date range
- Model predictions for each date
- Prediction intervals from metadata

---

# 8. Executive Intelligence Tab
Analyzes organizational leave patterns for operational decision-making.

**Data Preparation:**
- Full expanded leave fact table: `bundle["full_expanded_frame"]`
- Built from join of cleaned leave records + calendar features + employee master
- Includes all leave types but marks Special Leave & Comp-Off separately for exclusion

## 8.1 Leave Intelligence Dataset Flags

**Function:** `build_leave_intelligence_dataset()`

**Input:** `full_expanded_frame` — Daily leave records (one row per employee per day)

**Processing:**

```python
# Type normalization
def normalize_plan_type(raw_type):
    if pd.isna(raw_type):
        return "Unknown"
    normalized = raw_type.strip().upper()
    if normalized in ["PLANNED", "PLN", "P"]:
        return "Planned"
    if normalized in ["UN-PLANNED", "UNPLANNED", "UPL", "U"]:
        return "Unplanned"
    return "Unknown"

intelligence_df["Type_Normalized"] = raw_type.apply(normalize_plan_type)

# Staffing relevance flags
intelligence_df["Is_Special_Leave"] = intelligence_df["Leave Type"].isin(
    {"Special Leave [Not Call ON Duty]", "Comp-Off"}
).astype(int)

intelligence_df["Is_Staffing_Relevant"] = 1 - intelligence_df["Is_Special_Leave"]

# Binary plan type flags
intelligence_df["Is_Planned"] = (intelligence_df["Type_Normalized"] == "Planned").astype(int)
intelligence_df["Is_Unplanned"] = (intelligence_df["Type_Normalized"] == "Unplanned").astype(int)

# Helper column for aggregation
intelligence_df["Employee_Day"] = 1  # Count rows as employee-days

# Calendar breakdown
intelligence_df["Week_Start"] = intelligence_df["Date"].dt.to_period("W").dt.start_time
intelligence_df["Month_Label"] = intelligence_df["Date"].dt.strftime("%Y-%m")
intelligence_df["Day_Name"] = intelligence_df["Date"].dt.day_name()
```

**Output columns for aggregation:**
- `Type_Normalized` — "Planned", "Unplanned", or "Unknown"
- `Is_Special_Leave` — 1 if non-staffing-relevant, 0 otherwise
- `Is_Staffing_Relevant` — Inverse of Is_Special_Leave
- `Is_Planned`, `Is_Unplanned` — 1 if that type, 0 otherwise
- `Employee_Day` — Always 1 (used for summing employee-days)

## 8.2 Daily Leave Intelligence Summary

**Function:** `build_leave_intelligence_summary()`

**Input:** intelligence_df filtered by date range

**Aggregation:** Group by Date

**Calculated fields per date:**

```python
intelligence_summary = intelligence_df.groupby("Date").agg(
    # Basic counts
    Employees_On_Leave = ("EmpNo", "nunique"),       # Unique employees
    Employee_Days = ("Employee_Day", "sum"),         # Total rows (should = Employees if 1 employee-day each)
    
    # Staffing breakdown
    Staffing_Relevant_Days = ("Is_Staffing_Relevant", "sum"),
    Special_Leave_Days = ("Is_Special_Leave", "sum"),
    Planned_Days = ("Is_Planned", "sum"),
    Unplanned_Days = ("Is_Unplanned", "sum"),
    
    # Unique employee counts by type
    Staffing_Relevant_Employees = (row with Is_Staffing_Relevant=1, "nunique(EmpNo)"),
    Special_Leave_Employees = (row with Is_Special_Leave=1, "nunique(EmpNo)"),
    Planned_Employees = (row with Is_Planned=1, "nunique(EmpNo)"),
    Unplanned_Employees = (row with Is_Unplanned=1, "nunique(EmpNo)"),
    
    # Dimension counts
    Cost_Centres_Affected = ("Cost Centre", "nunique"),
    Departments_Affected = ("Department", "nunique"),
).reset_index()

# Calculated ratios
intelligence_summary["Unplanned_Share"] = (
    intelligence_summary["Unplanned_Days"] / 
    intelligence_summary["Employee_Days"]
).fillna(0)  # 0 if no data

intelligence_summary["Special_Leave_Share"] = (
    intelligence_summary["Special_Leave_Days"] / 
    intelligence_summary["Employee_Days"]
).fillna(0)

# Operational Risk Index (weighted combination)
intelligence_summary["Operational_Risk_Index"] = (
    (intelligence_summary["Staffing_Relevant_Employees"] * 0.55) +
    (intelligence_summary["Unplanned_Employees"] * 0.30) +
    (intelligence_summary["Cost_Centres_Affected"] * 0.15)
)
```

**Interpretation:**
- `Employees_On_Leave = 45` means 45 unique people on leave that day
- `Employee_Days = 45` (normally same as Employees if each has 1 day of leave)
- `Staffing_Relevant_Employees = 40` means 40 need backfill (5 are special leave)
- `Unplanned_Share = 0.67` means 67% of today's leave is unplanned
- `Operational_Risk_Index = 32.5` combines staffing (heaviest), unplanned (medium), and cost centre spread

## 8.3 Daily Leave Dashboard KPIs

**Function:** Filters intelligence summary + loads real-time data

```python
# Today's actual (from approved records with today's date)
todays_actual_leaves = get_todays_actual_leaves(data_path)
  # Returns: {
  #   total: nunique(EmpNo),
  #   breakdown: {Leave_Type: count},
  #   employee_details: DataFrame
  # }

# Week average
week_average = intelligence_summary[
    Date in last 7 days
]["Employees_On_Leave"].mean()

# Peak in next 7 days
peak_day_next_7 = intelligence_summary[
    Date in next 7 days
]["Employees_On_Leave"].max()

# Highest risk cost centre
highest_risk_cc = cost_centre_risk_summary.sort_values("Risk_Score", ascending=False).iloc[0]
```

**Metrics displayed:**

| Metric | Value | Source |
|--------|-------|--------|
| Today's Actual On Leave | 38 | `todays_actual_leaves["total"]` |
| Week Average Leave | 42 | `intelligence_summary[last 7 days]["Employees_On_Leave"].mean()` |
| Peak Day (Next 7) | 65 | `intelligence_summary[next 7 days]["Employees_On_Leave"].max()` |
| Highest Risk Centre | Sales | Top cost centre by `Risk_Score` from cost centre summary |

## 8.4 Cost Centre Risk Scoring

**Function:** `build_cost_centre_risk_summary()`

**Calculation per cost centre (from filtered period):**

```python
cost_centre_summary = intelligence_df.groupby("Cost Centre").agg(
    Employees_On_Leave = ("EmpNo", "nunique"),
    Employee_Days = ("Employee_Day", "sum"),
    Staffing_Relevant_Days = ("Is_Staffing_Relevant", "sum"),
    Special_Leave_Days = ("Is_Special_Leave", "sum"),
    Planned_Days = ("Is_Planned", "sum"),
    Unplanned_Days = ("Is_Unplanned", "sum"),
    Departments_Affected = ("Department", "nunique"),
    Staffing_Relevant_Employees = (EmpNo for Is_Staffing_Relevant=1, "nunique"),
).reset_index()

# Risk scoring formula (weights sum to 1.0)
cost_centre_summary["Risk_Score"] = (
    (cost_centre_summary["Staffing_Relevant_Employees"] * 0.50) +
    (cost_centre_summary["Unplanned_Days"] * 0.30) +
    (cost_centre_summary["Departments_Affected"] * 0.20)
)

# Sort by risk descending
cost_centre_summary = cost_centre_summary.sort_values("Risk_Score", ascending=False)
```

**Risk Score Interpretation:**
- **Weight 0.50 on Staffing_Relevant_Employees:** Number of people who need backfill is primary risk factor
- **Weight 0.30 on Unplanned_Days:** Unpredictable absences are harder to plan for
- **Weight 0.20 on Departments_Affected:** Spreading across many depts = coordinating complexity

**Example:**
```
Cost Centre = "Sales_Delhi"
  Staffing_Relevant_Employees = 12
  Unplanned_Days = 8
  Departments_Affected = 3
  
Risk_Score = (12 × 0.50) + (8 × 0.30) + (3 × 0.20)
           = 6.0 + 2.4 + 0.6
           = 9.0 (High risk)
```

## 8.5 Operational Risk Index (Daily)

**Formula:**

$$\text{Operational\_Risk\_Index} = (\text{Staffing\_Relevant\_Employees} \times 0.55) + (\text{Unplanned\_Employees} \times 0.30) + (\text{Cost\_Centres\_Affected} \times 0.15)$$

**Calculation:**
```python
Operational_Risk_Index = (
    (Staffing_Relevant_Employees * 0.55) +
    (Unplanned_Employees * 0.30) +
    (Cost_Centres_Affected * 0.15)
)
```

**Interpretation:**
- **0.55 weight on staffing-relevant employees:** Number of people = primary impact
- **0.30 weight on unplanned employees:** Unpredicted absence = secondary risk
- **0.15 weight on cost centres affected:** Spread across orgs = coordination cost

**Example:**
```
Date: 2026-04-16
  Staffing_Relevant_Employees = 50
  Unplanned_Employees = 35
  Cost_Centres_Affected = 8
  
Risk = (50 × 0.55) + (35 × 0.30) + (8 × 0.15)
     = 27.5 + 10.5 + 1.2
     = 39.2 (Moderate-High risk)
```

## 8.6 Daily Status Flagging

**Status calculation for daily summary table:**

```python
week_average = intelligence_summary["Employees_On_Leave"].mean()

def get_status(employees_on_leave, week_avg):
    if employees_on_leave > week_avg * 1.3:
        return "🔴 High"
    elif employees_on_leave > week_avg:
        return "🟡 Medium"
    else:
        return "🟢 Normal"

intelligence_summary["Status"] = intelligence_summary.apply(
    lambda row: get_status(row["Employees_On_Leave"], week_average),
    axis=1
)
```

**Threshold Logic:**
- **> 130% of weekly average:** High risk (unpredictable spike)
- **> 100% of weekly average:** Medium risk (above normal but manageable)
- **≤ 100% of weekly average:** Normal (as expected)

## 8.7 Forecast Extension to Intelligence Summary

**Function:** `extend_intelligence_summary_with_forecast()`

**Input:**
- Historical intelligence summary
- `metadata["next_30_days_forecast"]` (pre-computed 30-day forecast)

**Process:**

```python
# Filter forecast to future dates only (after last historical date)
last_actual = intelligence_summary["Date"].max()
forecast_df = metadata["next_30_days_forecast"][
    (Date > last_actual) & (Date <= forecast_window_end)
]

# Create synthesized intelligence rows for forecast period
future_rows = []
for _, row in forecast_df.iterrows():
    future_rows.append({
        "Date": row["Date"],
        "Employees_On_Leave": round(row["Predicted_Leave_Count"]),
        "Staffing_Relevant_Employees": round(row["Predicted_Leave_Count"]),
        "Employee_Days": round(row["Predicted_Leave_Count"]),
        "Unplanned_Days": 0,  # No unplanned info in forecast
        "Cost_Centres_Affected": 0,  # Not predicted
        "Departments_Affected": 0,  # Not predicted
        "Unplanned_Share": 0.0,
        "Special_Leave_Share": 0.0,
        "Data_Source": "Forecast"
    })

# Combine with historical data
extended_summary = pd.concat(
    [
        intelligence_summary.assign(Data_Source="Actual"),
        pd.DataFrame(future_rows)
    ],
    ignore_index=True,
    sort=False
)

extended_summary = extended_summary.sort_values("Date").reset_index(drop=True)
```

**Key Details:**
- Forecast rows use `Predicted_Leave_Count` as all staff-relevant (conservative)
- Cost Centre / Department breakdowns set to 0 (not predicted)
- These rows are marked `Data_Source="Forecast"` for UI styling

---

---

# 9. Model Feature Contribution & Explainability

**Function:** `explain_forecast_reason()`

**Purpose:** Understand which features pushed forecast up or down (SHAP values or feature importance).

## 9.1 SHAP-Based Explanation (If available)

**Algorithm:** Tree SHAP explainer

```python
if shap is not None:
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(feature_row)  # Get feature contributions
    
    explanation = pd.DataFrame({
        "feature": feature_columns,
        "feature_value": feature_row.values,
        "contribution": shap_values,  # How much each feature shifted prediction
    })
else:
    # Fallback to feature importance × deviation from mean
    importance = model.feature_importances_
    centered_values = feature_row - feature_row.mean()
    contribution = importance * centered_values
```

**Output Columns:**

| Column | Example | Meaning |
|--------|---------|---------|
| `feature` | "is_monday" | Feature name |
| `feature_value` | 1 | Actual value for this prediction |
| `contribution` | +5.2 | How much this feature increased forecast |
| `abs_contribution` | 5.2 | Magnitude (used for sorting) |
| `direction` | "Pushes forecast up" | Sign interpretation |

**Interpretation:**

```
Feature: is_monday = 1, contribution = +5.2
  Message: "Being a Monday added 5.2 employees to the forecast"

Feature: rolling_mean_7 = 18, contribution = -3.1
  Message: "7-day trend was lower than average, reduced forecast by 3.1"
```

**Top N Features:** Display top 8 features by absolute contribution to show which factors mattered most for this specific day.

## 9.2 Historical Feature Importance

**Source:** `load_feature_importance_from_metadata()`

**Path:** `{versioned_model_path}_feature_importance.csv` saved during model training

**Columns:**
- `feature` — Feature name
- `importance` — Average contribution magnitude across all test set predictions

**Calculation (from training):**
```python
# For tree models
feature_importance = model.feature_importances_
# Shows which features the model relied on most overall

# Normalized
feature_importance_pct = importance / importance.sum() * 100
```

**Usage:** Shows long-term patterns (e.g., "holiday features are 8% of total importance") vs. daily SHAP (which is specific to one date).

---

# 10. Planned vs Unplanned Analytics

**Data:** `full_expanded_frame` filtered by Type (Planned / Un-Planned / Unknown)

## 10.1 Leave Day Counts

**Calculation:**

```python
planned_days = sum(rows where Type == "Planned")
unplanned_days = sum(rows where Type == "Un-Planned")
unknown_days = sum(rows where Type is null or unknown)

total_leave_days = planned_days + unplanned_days + unknown_days

unplanned_pct = (unplanned_days / total_leave_days) * 100
```

**Example:**
```
Planned_Days = 320
Unplanned_Days = 2930
Total_Days = 3250
Unplanned_Pct = (2930 / 3250) × 100 = 90.1%
```

**Interpretation:** 90.1% of leave taken is unplanned/unexpected, indicating high operational uncertainty.

## 10.2 Employee Count by Plan Type

**Calculation:**

```python
planned_employees = nunique(EmpNo where Type == "Planned")
  (Unique employees who took >= 1 planned leave day)

unplanned_employees = nunique(EmpNo where Type == "Un-Planned")
  (Unique employees who took >= 1 unplanned leave day)

unknown_employees = nunique(EmpNo where Type is null/unknown)

total_employees = nunique(EmpNo)  # All employees regardless of type
```

**Key difference from days:**
- Employee count answers: "How many people took this type?"
- Day count answers: "How many days of this type were taken?"

**Example:**
```
Employees with Planned = 526
Employees with Unplanned = 1873
Total Unique Employees = 1874

Note: Total > sum(Planned + Unplanned) because some employees took both types!
```

## 10.3 Average Days per Employee

**Calculation:**

```python
Avg_Days_Per_Employee = Total_Leave_Days / Total_Unique_Employees
```

**Example:**
```
Total_Days = 3250
Total_Employees = 1874
Avg_Days = 3250 / 1874 = 1.73 days/employee
```

**Interpretation:** On average, each employee took 1.73 days of leave during the period.

## 10.4 Planned vs Unplanned Time-Series

**Aggregation:**

```python
# Daily breakdown
daily_breakdown = full_exp.groupby(["Date", "Type"]).agg(
    Employees = ("EmpNo", "nunique"),
    Leave_Days = ("Employee_Day", "sum")
)

# Weekly breakdown
weekly_breakdown = full_exp.assign(
    Week = Date.to_period("W").start_time
).groupby(["Week", "Type"]).agg(...)

# Monthly breakdown
monthly_breakdown = full_exp.assign(
    Month = Date.to_period("M").start_time
).groupby(["Month", "Type"]).agg(...)
```

**Visualization:** Stacked area or bar chart showing ratio of Planned vs Unplanned over time.

---

# 11. Leave Reason Analytics

**Data:** `full_expanded_frame` where `Leave Reason` is not null

## 11.1 Top Leave Reasons

**Calculation:**

```python
reason_summary = full_exp.groupby("Leave Reason").agg(
    Employee_Days = ("Employee_Day", "sum"),
    Unique_Employees = ("EmpNo", "nunique"),
    Occurrences = (size,)
).sort_values("Employee_Days", ascending=False)
```

**Top 6 by employee-days:**

```
Leave Reason               Employee_Days  Unique_Employees
Personal                   1240           580
Medical / Illness          890            310
Family Emergency           340            120
Maternity / Paternity      120            15
Special Occasion           90             45
Other                      80             30
```

**Interpretation:**
- "Personal" reasons account for largest share
- Medical has high frequency (could indicate health issues)
- Maternity is low frequency but concentrated (whole weeks off)

## 11.2 Leave Reason by Leave Type

**Calculation:**

```python
reason_by_type = full_exp.groupby(["Leave Reason", "Leave Type"]).agg(
    Employee_Days = ("Employee_Day", "sum")
).pivot_table(
    index="Leave Reason",
    columns="Leave Type",
    values="Employee_Days",
    fill_value=0
)
```

**Result (Heatmap):**
```
Leave Reason          Sick Leave   Casual  Earned  Medical
Personal              20           800     400     20
Medical / Illness     800          50      30      10
Family Emergency      50           280     10      0
```

**Usage:** Identify leave type patterns (e.g., "Medical always used for illness").

---

# 12. Cost Centre & Department Analytics

**Data:** `full_expanded_frame` with Cost Centre and Department fields

## 12.1 Cost Centre Leave Distribution

**Calculation:**

```python
cc_summary = full_exp.groupby("Cost Centre").agg(
    Employees_On_Leave = ("EmpNo", "nunique"),
    Leave_Days = ("Employee_Day", "sum"),
    Avg_Days_Per_Employee = lambda x: x.sum() / x["EmpNo"].nunique()
).sort_values("Employees_On_Leave", ascending=False)

cc_summary["Pct_of_Total"] = cc_summary["Employees_On_Leave"] / cc_summary["Employees_On_Leave"].sum() * 100
```

**Example output:**
```
Cost Centre      Employees  %     Days    Avg/Emp
Sales_Delhi      245        22.3  385     1.57
Operations_Mum   198        18.0  310     1.57
Finance_Bng      157        14.3  250     1.59
IT_Hyderabad     145        13.2  220     1.52
```

**Visualization:**
- **Donut chart:** Size = employee count by cost centre
- **Bar chart:** Horizontal, sorted by employee count

## 12.2 Cost Centre Risk Score

(See Section 8.6 for calculation)

**Risk_Score per CC** = (Staffing_Relevant_Employees × 0.50) + (Unplanned_Days × 0.30) + (Departments_Affected × 0.20)

Top 5 highest-risk cost centres highlight operational challenges.

---

# 13. Department & Organizational Analytics

**Data:** `full_expanded_frame` with Department field

## 13.1 Department Leave Aggregation

**Calculation:**

```python
dept_summary = full_exp.groupby("Department").agg(
    Employees_On_Leave = ("EmpNo", "nunique"),
    Leave_Days = ("Employee_Day", "sum"),
    Unique_Leave_Types = ("Leave Type", "nunique"),
    Avg_Days_Per_Employee = lambda x: x.sum() / x["EmpNo"].nunique()
).sort_values("Employees_On_Leave", ascending=False)
```

## 13.2 Department × Leave Type Cross-Tab

**Calculation:**

```python
dept_ltype_cross = full_exp.groupby(["Department", "Leave Type"]).agg(
    Employees = ("EmpNo", "nunique")
).pivot_table(
    index="Department",
    columns="Leave Type",
    values="Employees",
    fill_value=0
)
```

**Heatmap/Treemap:** Shows which departments use which leave types most.

---

# 14. Forecast vs Historical Accuracy Analysis

**Data:** `model_df` (feature matrix with actual + predictions)

## 14.1 Historical Period Forecast Accuracy

**Calculation:** Evaluate model on historical date range

```python
if test_period is specified:
    historical_test_df = model_df[
        (Date >= test_start_date) & (Date <= test_end_date)
    ]
else:
    historical_test_df = model_df.iloc[-90:]  # Last 90 days

# Predictions (could be actual model.predict or cached in bundle)
y_actual = historical_test_df[TARGET_COLUMN]
y_pred = model.predict(historical_test_df[feature_columns])

# Metrics per date
comparison_df = pd.DataFrame({
    "Date": historical_test_df["Date"],
    "Actual_Leave": y_actual,
    "Predicted_Leave": y_pred,
    "Error": y_actual - y_pred,
    "Abs_Error": abs(y_actual - y_pred),
    "Pct_Error": abs(y_actual - y_pred) / y_actual * 100  # Safe division
})
```

## 14.2 Monthly Accuracy Summary

**Calculation:**

```python
comparison_df["Year_Month"] = comparison_df["Date"].dt.strftime("%Y-%m")

monthly_accuracy = comparison_df.groupby("Year_Month").agg(
    Actual_Total = ("Actual_Leave", "sum"),
    Predicted_Total = ("Predicted_Leave", "sum"),
    Days = ("Date", "count"),
    Avg_Abs_Error = ("Abs_Error", "mean"),
    WAPE = (weighted_absolute_percentage_error on month)
)

monthly_accuracy["Monthly_Error"] = (
    monthly_accuracy["Actual_Total"] - monthly_accuracy["Predicted_Total"]
).abs()
```

**Example:**
```
Year_Month  Actual  Predicted  Error  Days  Avg_Error  WAPE
2026-03     1250    1310       60     31    7.2        4.8%
2026-02     1180    1165       15     28    6.1        3.2%
2026-01     1390    1420       30     31    8.5        5.1%
```

**Trend Insight:** "Model slightly overpredicts in high-leave months (Mar), underpredicts in low-leave months (Feb)."

---

# 15. Festival Impact & Calendar Analysis

**Data:** Indian festival calendar from `indian_calendar.py`

## 15.1 Festival Date Features

**Source:** `cached_festival_calendar(2020, 2030)`

**Fields:**
```python
festival_df = {
    "Date": datetime,           # Festival date
    "Festival": str,            # Festival name
    "Religion": str,            # Hindu / Muslim / Christian / Sikh / etc.
    "Is_Gazetted": bool,        # Official public holiday?
    "Day_Name": str,            # "Monday", "Friday", etc.
    "Month_Name": str,          # "January", "March", etc.
    "Month_Num": int,           # 1-12
}
```

## 15.2 Festival Density Analysis

**Calculation:**

```python
festivals_per_month = festival_df.groupby("Month_Name").agg(
    Festival_Count = ("Festival", "count"),
    Gazetted_Count = ("Is_Gazetted", "sum"),
    Religions = ("Religion", "nunique")
)

festivals_per_religion = festival_df.groupby("Religion").agg(
    Festival_Count = ("Festival", "count"),
    Gazetted_Count = ("Is_Gazetted", "sum")
).sort_values("Festival_Count", ascending=False)
```

**Example:**
```
Month        Festivals  Gazetted  (High density = spike season)
March        8          3
April        6          2
...
October      7          2         (Diwali season high activity)
November     5          1
December     6          3         (Christmas, New Year)
```

## 15.3 Festival-Leave Spike Analysis

**Function:** `compute_spike_analysis_vectorized()`

**Algorithm:**

For each festival:
1. Identify festival date from calendar
2. Look at leave records ±3 days around festival (7-day window)
3. Aggregate employees on leave for each day offset
4. Detect if leave clusters before/on/after festival

**Offsets analyzed:**
```
Before: Day-3, Day-2, Day-1
Festival Day: Day 0
After: Day+1, Day+2, Day+3
```

**Calculation:**

```python
for festival_date in festival_calendar:
    window_start = festival_date - 3 days
    window_end = festival_date + 3 days
    
    window_leaves = full_exp[
        (Date >= window_start) & (Date <= window_end)
    ]
    
    for offset in [-3, -2, -1, 0, 1, 2, 3]:
        target_date = festival_date + offset days
        employees_on_offset = nunique(EmpNo) for target_date
        
    spike_pattern[festival] = [emp_count for each offset]
```

**Output:**

```
Festival: "Diwali" (2026-10-29)
Offset  Day           Employees_On_Leave
-3      2026-10-26    120
-2      2026-10-27    180   ← Started clustering 2 days before
-1      2026-10-28    320   ← Day before is peak
0       2026-10-29    315   ← Festival day still high
+1      2026-10-30    250   ← Post-festival decline
+2      2026-10-31    140
+3      2026-11-01    95    ← Back to normal
```

**Interpretation:** Leave clusters heavily 1-2 days before festival (preparing to travel), remains high on festival day, then returns to normal.

---

# 9. Special Leave & Comp-Off Tab
Analyzes non-operational leave types that don't require backfill.

**Important:** Special Leave [Not Call ON Duty] and Comp-Off are **NOT counted as ON Duty absence** and are excluded from staffing forecasts.

**Filter:** `full_exp` where `Leave Type in SPECIAL_LEAVE_TYPES`
- `SPECIAL_LEAVE_TYPES = {"Special Leave [Not Call ON Duty]", "Comp-Off"}`

### 9.1 KPI Summary
- **Total Special Leave Days** = `count(Leave Type == "Special Leave [Not Call ON Duty]")`
- **Total Comp-Off Days** = `count(Leave Type == "Comp-Off")`
- **Unique Employees** = `nunique(EmpNo)`

#### CSV fields used:
- `Leave Type`, `EmpNo`, `From Date`, `To Date`

### 9.2 Charts
All counts represent **leave-days** (row count), not unique employees.

**Weekly Chart:**
- Rows grouped by: `Date.to_period("W")` and `Leave Type`
- Y-axis: `count(rows)` (days)
- Bars: Side-by-side by Leave Type (blue=Special, red=Comp-Off)

**Monthly Trend:**
- Rows grouped by: `Date.to_period("M")` and `Leave Type`
- Y-axis: `count(rows)` (days)
- Shows month-over-month pattern

**Day-of-Week Pattern:**
- Rows grouped by: `day_of_week` and `Leave Type`
- Y-axis: `count(rows)`
- Reveals if certain weekdays (Mon/Fri) have higher special leave

#### CSV fields used by charts:
- `Leave Type`, `Date`, `EmpNo`, `From Date`, `To Date`

---

# 10. Cost Centre Analysis Tab
Analyzes leave distribution and operational impact by department.

**Filter:** `full_exp` restricted by date range and optional `Leave Type` filter

### 10.1 KPI Summary
- **Total Leave Days** = `_cc_df.shape[0]` (row count)
- **Cost Centres** = `nunique(Cost Centre)`
- **Employees on Leave** = `nunique(EmpNo)`
- **Avg Days per Employee** = `shape[0] / nunique(EmpNo)`

#### CSV fields used:
- `Cost Centre`, `EmpNo`, `Leave Type`, `From Date`, `To Date`

### 10.2 Employee Count Segregation by Cost Centre
**Purpose:** "If 10 employees are on leave, how many come from each Cost Centre?"

#### Fields:
- **Employees on Leave** = `nunique(EmpNo)` grouped by `Cost Centre`
- **% of Total** = `Employees on Leave / total_employees_on_leave * 100`

#### Visualizations:
- Donut chart: Size = employee count, label = Cost Centre name
- Bar chart: Horizontal, sorted by employee count

#### CSV fields used:
- `Cost Centre`, `EmpNo`, `From Date`, `To Date`

### 10.3 Treemap (Cost Centre → Leave Type)
**Purpose:** Drill down leave distribution by cost centre and leave type

#### Fields:
- **Size (color)** = `nunique(EmpNo)` grouped by (`Cost Centre`, `Leave Type`)

Hierarchy: Cost Centre → Leave Type

#### CSV fields used:
- `Cost Centre`, `Leave Type`, `EmpNo`, `From Date`, `To Date`

### 10.4 Single-Day Employee Breakdown
**Source:** `full_exp[Date == selected_date]`

**Purpose:** "For a selected date, which cost centres are affected and by how much?"

#### Fields:
- **Date** = Selected date
- **_cc_day_total** = `nunique(EmpNo)` for the day (all cost centres)
- Per Cost Centre:
  - **Employees on Leave** = `nunique(EmpNo)`
  - **% of Total** = `Employees on Leave / _cc_day_total * 100`
- Per (Cost Centre, Leave Type):
  - **Employees** = `nunique(EmpNo)`

Shown only for actual dates, not forecast dates.

#### CSV fields used:
- `Date`, `Cost Centre`, `Leave Type`, `EmpNo`, `From Date`, `To Date`

### 10.5 Period Trend Chart
**Purpose:** Daily/Weekly/Monthly trend of employees on leave by cost centre

#### Aggregation:
- X-axis: Time period (day/week/month based on granularity)
- Y-axis: `nunique(EmpNo)` by period and `Cost Centre`
- Lines/Bars: One per cost centre

#### CSV fields used:
- `Date`, `Cost Centre`, `EmpNo`, `From Date`, `To Date`

---

# 11. Planned vs Unplanned Tab
Analyzes the split between pre-planned and unplanned leave.

**Filter:** `full_exp` restricted by date range, optional cost centre, optional leave type
- Requires non-null `Type` column

> **Note:** This tab uses raw `Type` values from expanded leave facts. The intelligence tab separately uses `normalize_plan_type()` for consistency.

### 11.1 KPI Summary
- **Planned Days** = `count(Type == "Planned")`
- **Unplanned Days** = `count(Type == "Un-Planned")`
- **Total Leave Days** = `Planned Days + Unplanned Days`
- **Unplanned %** = `Unplanned Days / Total Leave Days * 100`
- **Employees — Planned** = `nunique(EmpNo where Type == "Planned")`
- **Employees — Unplanned** = `nunique(EmpNo where Type == "Un-Planned")`
- **Total Employees on Leave** = `nunique(EmpNo)`
- **Unplanned Emp %** = `Employees_Unplanned / Total_Employees * 100`
- **Avg Days/Employee** = `Total Leave Days / Total Employees on Leave`

#### CSV fields used:
- `Type`, `EmpNo`, `Leave Type`, `Cost Centre`, `Date`, `From Date`, `To Date`

### 11.2 Charts
All visualizations available in different aggregations:

**By Leave Type and Type:**
- Grouped by `Leave Type` and `Type`
- Y-axis: `nunique(EmpNo)` (employee count)

**Daily Employee Headcount:**
- X-axis: `Date`
- Y-axis: `nunique(EmpNo)` by `Type`
- Lines: Planned vs Unplanned

**Daily Leave Days:**
- X-axis: `Date`
- Y-axis: `count(rows)` by `Type`

**Weekly Employee Headcount:**
- X-axis: `Date.to_period("W")`
- Y-axis: `nunique(EmpNo)` by `Type`

**Weekly Leave Days:**
- X-axis: `Date.to_period("W")`
- Y-axis: `count(rows)` by `Type`

**Cost Centre Breakdown:**
- X-axis: `Cost Centre`
- Y-axis: `nunique(EmpNo)` by `Type`

**Day-of-Week Pattern:**
- X-axis: `day_of_week` (0=Mon, 6=Sun)
- Y-axis: `nunique(EmpNo)` by `Type`

**Monthly Trend:**
- X-axis: `Date.to_period("M")`
- Y-axis: `nunique(EmpNo)` by `Type`

#### CSV fields used across all charts:
- `Type`, `Leave Type`, `Cost Centre`, `EmpNo`, `Date`, `From Date`, `To Date`

---

# 12. Leave Reason & Prediction Context Tab
Analyzes leave reasons and provides prediction context for selected dates.

**Filter:** `full_exp` restricted by date range, optional cost centre, optional leave type

### 12.1 Top Leave Reasons
**Source:** If `Leave Reason` column exists

#### Aggregation:
- Grouped by `Leave Reason`
- Y-axis: `count(rows)` (leave days)
- Chart type: Horizontal bar chart, sorted descending

#### CSV fields used:
- `Leave Reason`, `Date`, `From Date`, `To Date`

### 12.2 Leave Type by Cost Centre
**Purpose:** Cross-tabulation of leave types and departments

#### Aggregation:
- Grouped by (`Cost Centre`, `Leave Type`)
- Value: `count(rows)` (leave days)
- Visualization: Heatmap or stacked bar

#### CSV fields used:
- `Cost Centre`, `Leave Type`, `Date`, `From Date`, `To Date`

### 12.3 Prediction Context
**Purpose:** Historical context for the selected prediction date

#### Selection:
User selects a date for context. System filters historical leave records by:
1. Same calendar month as selected date
2. Same day-of-week as selected date

#### Context Outputs:
For rows matching both month AND weekday:
- **Top 6 Cost Centres**: `nunique(EmpNo)` or `count(rows)`, sorted descending
- **Top 6 Leave Reasons**: `count(rows)`, sorted descending

#### Interpretation:
"On similar Mondays in March, these cost centres and reasons were common."

#### CSV fields used:
- `Date`, `Cost Centre`, `Leave Reason`, `From Date`, `To Date`

---

# 13. Daily CC Leave Tab
Analyzes daily employee count on leave by cost centre with full filtering capabilities.

**Source:** `full_exp` (full expanded leave fact table)

### 13.1 Filters & Slicers
**Row 1:**
- Date range: From → To (all historical dates)
- Leave Type: Multiselect (default: all)

**Row 2:**
- Year: Multiselect (default: current year)
- Granularity: Radio (Daily / Weekly / Monthly)
- Cost Centre: Multiselect (default: first 6 or all if <6)

**Row 3:**
- Department: Cascading multiselect (filtered by selected cost centres)
- Planned / Unplanned (Type): Multiselect (default: all)
- YoY Toggle: "Compare vs Last Year" (boolean)

### 13.2 KPI Summary
- **Total Leave Days** = `count(rows)`
- **Cost Centres** = `nunique(Cost Centre)`
- **Employees on Leave** = `nunique(EmpNo)`
- **Avg Days / Employee** = `count(rows) / nunique(EmpNo)`

#### CSV fields used:
- `EmpNo`, `Cost Centre`, `Leave Type`, `Type`, `Department`, `Date`

### 13.3 Time-Series Aggregation
**Time Bucket Column** (`_Period`):
- **Daily**: `Date.normalize()`
- **Weekly**: `Date.to_period("W").start_time`
- **Monthly**: `Date.to_period("M").start_time`

#### Metric per Period & Cost Centre:
- **Employees on Leave** = `nunique(EmpNo)` grouped by (`_Period`, `Cost Centre`)

#### Visualization:
- X-axis: Time period
- Y-axis: Employee count
- Lines/Bars: One per selected cost centre

#### Optional Year-over-Year:
If YoY toggle enabled:
- Filter current period: `year == selected_year`
- Filter prior period: `year == selected_year - 1` (same month/period)
- Overlay both on same chart for comparison

#### CSV fields used:
- `Date`, `Cost Centre`, `EmpNo`, `Leave Type`, `Type`, `Department`, `From Date`, `To Date`

---

# 14. Indian Festival Calendar Tab
Displays comprehensive multi-religion Indian festival calendar with spike analysis.

**Source:** `cached_festival_calendar(2020, 2030)` from `indian_calendar.py`

### 14.1 Festival Calendar Filters
**Row 1:**
- Year: Multiselect (default: current year)
- Religion / Category: Multiselect (default: all)
- Gazetted Only: Toggle (default: false)
- Search: Text input (e.g., "Diwali", "Eid")

### 14.2 KPI Summary
- **Festivals Found**: `count(rows)` matching filters
- **Gazetted Holidays**: `sum(Is_Gazetted)` among filtered rows
- **Religions Covered**: `nunique(Religion)` among filtered rows
- **Date Range**: `min(Date).strftime('%b %Y')` to `max(Date).strftime('%b %Y')`

#### Festival table columns:
- `Date` (YYYY-MM-DD)
- `Festival` name
- `Religion` / category
- `Is_Gazetted` (yes/no)
- `Day_Name` (Monday-Sunday)
- `Month_Name` (January-December)

#### CSV fields used:
- `Date`, `Festival`, `Religion`, `Is_Gazetted`, `Day_Name`, `Month_Name`

### 14.3 Monthly Festival Density
**Aggregation:**
- Grouped by `Month_Name` (and sort by month number)
- Y-axis: `count(rows)` (festivals per month)
- Chart type: Bar chart, color intensity = festival count

#### Purpose:
Identify which months have most festivals (spike seasons).

#### CSV fields used:
- `Month_Name`, `Month`, `Festival`

### 14.4 Religion Distribution
**Aggregation:**
- `Religion`: `count(rows)` (festivals per religion)
- Sorted descending

#### Visualizations:
- **Pie/Donut chart** (hole=0.4): Shows % of festivals by religion
- **Table**: Religion name, festival count

#### CSV fields used:
- `Religion`, `Festival`

### 14.5 Festival Timeline
**Visualization:**
- X-axis: `DateTS` (date as timestamp)
- Y-axis: `Religion` (category)
- Scatter points: One per festival
- Color: By `Religion`
- Hover: `Festival`, `Day_Name`, `Is_Gazetted`

**Purpose:** See chronological distribution of festivals by religion throughout the year.

#### CSV fields used:
- `Date`, `Religion`, `Festival`, `Day_Name`, `Is_Gazetted`

### 14.6 Festival Spike Analysis (if integrated with leave data)
**Function:** `compute_spike_analysis_vectorized()`

For each festival:
- Analyze leave behavior on Festival Day, and ±3 days around it
- Offsets: Before (-3d, -2d, -1d), Festival Day (0), After (+1d, +2d, +3d)
- Metric: `nunique(EmpNo)` or `sum(Employee_Days)` for each offset

#### Output Columns:
- `Festival` name
- `Offset` label ("Before (-1d)", "Festival Day", "After (+1d)", etc.)
- `Employees_On_Leave` (null/filled for each offset window)

#### Chart:
- X-axis: Offset (Before → Festival Day → After)
- Y-axis: Employee count
- Lines: One per festival
- Pattern recognition: Shows if leave "clusters" around festivals

#### CSV fields used:
- Festival data: `Date`, `Festival`, `Religion`
- Leave data: `Date`, `EmpNo`, `Leave Type`, `From Date`, `To Date`

*These are historical analog patterns, not model features directly displayed to the model.*

---

---

# 15. Employee Headcount on Leave Dashboard Metrics
**Dashboard Location:** Planned vs Unplanned Tab → "Employee Headcount on Leave" KPI Row

This section documents the exact calculations for the four key metrics displayed on the dashboard showing employee headcount breakdown by planned vs unplanned status.

### 15.1 Dashboard Display

The "Employee Headcount on Leave" section displays these four metrics:

| Metric | Example Value | Formula |
|--------|---------------|---------|
| **Total Employees on Leave** | 1874 | `nunique(EmpNo)` across all filtered leave records |
| **Employees — Planned** | 526 | `nunique(EmpNo where Type == "Planned")` |
| **Employees — Unplanned** | 1873 | `nunique(EmpNo where Type == "Un-Planned")` |
| **Unplanned Emp %** | 99.9% | `(Unplanned_Count / Total_Count) * 100` |

### 15.2 Data Source & Filters

**Source:** `full_exp` (full expanded leave fact table)
- Built from: `Combined_All_Leave_Data.csv` + calendar join + employee master join

**Filters Applied (user-selectable):**
1. **Date Range**: From → To (selected on dashboard)
2. **Cost Centre** (optional): Multiselect filter
3. **Leave Type** (optional): Multiselect filter

**Requirement:** `Type` column must be non-null (contains "Planned" or "Un-Planned" values)

#### CSV Fields Used:
- `EmpNo` — Unique employee identifier (primary key for deduplication)
- `Type` — Leave classification ("Planned", "Un-Planned", or variations)
- `Date` — Calendar date of leave (derived from From_Date + To_Date expansion)
- `Cost Centre` (optional filter) — Department cost center
- `Leave Type` (optional filter) — Category of leave

### 15.3 Calculation Logic

#### Step 1: Filter the leave records
```
_pu_df = full_exp[
    (full_exp["Date"] >= start_date) AND 
    (full_exp["Date"] <= end_date)
]

// Apply optional cost centre filter
if cost_centres_selected:
    _pu_df = _pu_df[_pu_df["Cost Centre"].isin(cost_centres)]

// Apply optional leave type filter
if leave_types_selected:
    _pu_df = _pu_df[_pu_df["Leave Type"].isin(leave_types)]

// Remove rows where Type is null or unknown
_pu_df = _pu_df[_pu_df["Type"].notna()]

// Normalize Type values to "Planned" and "Un-Planned"
_pu_df["Type"] = _pu_df["Type"].str.strip().str.title()
```

#### Step 2: Calculate Planned employee count
```
_planned_emp = int(_pu_df[_pu_df["Type"] == "Planned"]["EmpNo"].nunique())
```
**Interpretation:** Count of unique employee IDs who took **any planned leave** during the filtered date range.

**CSV Mechanics:**
- Filter rows where `Type` column contains "Planned" (case-insensitive after normalization)
- Apply `nunique()` to `EmpNo` column
- This counts each employee **once**, regardless of how many planned leave days they took
- Returns as integer

#### Step 3: Calculate Unplanned employee count
```
_unplanned_emp = int(_pu_df[_pu_df["Type"] == "Un-Planned"]["EmpNo"].nunique())
```
**Interpretation:** Count of unique employee IDs who took **any unplanned leave** during the filtered date range.

**CSV Mechanics:**
- Filter rows where `Type` column contains "Un-Planned" (case-insensitive)
- Apply `nunique()` to `EmpNo` column
- Counts each employee **once**, regardless of unplanned leave day count
- Returns as integer

#### Step 4: Calculate Total employee count
```
_total_emp = int(_pu_df["EmpNo"].nunique())
```
**Interpretation:** Count of all unique employee IDs who took **any leave** (planned, unplanned, or unknown type) during the filtered date range.

**CSV Mechanics:**
- Apply `nunique()` to entire filtered `EmpNo` column (no Type filter)
- Returns count of distinct employee IDs
- Returns as integer

**Important Note on Overlaps:**
- An employee can appear in both Planned and Unplanned counts if they took **both** types of leave during the period
- Example: Employee #123 took 2 days planned leave on Jan 5-6, and 1 day unplanned on Jan 10
  - They are counted in `_planned_emp` (1 employee)
  - They are counted in `_unplanned_emp` (1 employee)
  - They are counted in `_total_emp` (1 employee)
  - So: 1 + 1 ≠ 1 total (overlap exists)

#### Step 5: Calculate Leave Days counts
```
_planned_count = int((_pu_df["Type"] == "Planned").sum())
_unplanned_count = int((_pu_df["Type"] == "Un-Planned").sum())
_total = _planned_count + _unplanned_count
```
**Interpretation:** Count of **leave-day rows** (not unique employees).

**CSV Mechanics:**
- Each row in the expanded leave table represents one employee-day of leave
- Boolean filter sums to row count matching the condition
- Does NOT use `nunique()` — counts all rows

### 15.4 Percentage Calculation

#### Formula:
```
Unplanned_Emp_% = (_unplanned_emp / _total_emp) * 100
```

**Interpretation:** Percentage of total employees who took unplanned leave.

**Example:**
- Total Employees on Leave: 1874
- Employees — Unplanned: 1873
- Unplanned Emp %: (1873 / 1874) * 100 = 99.9%

**CSV Source:**
- Numerator: `nunique(EmpNo where Type == "Un-Planned")`
- Denominator: `nunique(EmpNo)` (all types)
- Computed in Python: `f"{value:.1f}%"` format

### 15.5 Display KPI Row

The dashboard displays all four metrics in a single row:

```
┌────────────────────────────┬────────────────────┬────────────────────┬──────────────────┐
│ Total Employees on Leave   │ Employees — Planned│ Employees —Unplanned│ Unplanned Emp %  │
│        1874                │        526         │        1873        │      99.9%       │
└────────────────────────────┴────────────────────┴────────────────────┴──────────────────┘
```

### 15.6 Related KPI Row: Leave Days (above Employee Headcount)

The same dashboard section displays leave-day metrics in an upper row:

```
┌──────────────────────┬────────────────────┬──────────────────────┬─────────────────┐
│ Total Leave Days     │ Planned Days       │ Unplanned Days       │ Unplanned %     │
│      3250            │       320          │      2930            │    90.1%        │
└──────────────────────┴────────────────────┴──────────────────────┴─────────────────┘
```

**Calculation:** Uses `.sum()` on boolean masks (counts rows), not `.nunique()` on EmpNo.

---

## 13. Field meaning cheat sheet
- **Employees_On_Leave:** unique employees for a date
- **Employee_Days** or **Leave Days:** expanded row count
- **Staffing_Relevant_***: excludes `Special Leave [Not Call ON Duty]` and `Comp-Off`
- **Special_Leave_***: only those excluded leave types
- **Planned_***: based on leave `Type` saying planned
- **Unplanned_***: based on leave `Type` saying unplanned
- **Predicted_Leave_Count:** model output for daily unique employees on leave
- **Actual_Leave_Count:** actual daily unique employees on leave
- **Coverage_Gap:** shortfall against required present workforce
- **Additional_Headcount_Needed:** extra people needed beyond current total workforce

### 13.1 Major displayed values and their exact CSV field lineage
This is the shortest answer to "which CSV field is used for this value?"

- **Any count of employees on leave:**
  - root CSV fields: `EmpNo`, `From Date`, `To Date`
- **Any split by department:**
  - root CSV fields: `EmpNo`, `Department`, `From Date`, `To Date`
- **Any split by leave type:**
  - root CSV fields: `EmpNo`, `Leave Type`, `From Date`, `To Date`
- **Any split by cost centre:**
  - root CSV fields: `EmpNo`, `Cost Centre`, `From Date`, `To Date`
- **Any planned vs unplanned number:**
  - root CSV fields: `EmpNo`, `Type`, `From Date`, `To Date`
- **Any leave-reason number:**
  - root CSV fields: `Leave Reason`, `From Date`, `To Date`, often also `EmpNo`
- **Any leave-days number:**
  - root CSV fields: `From Date`, `To Date`, plus the grouping field
- **Any workforce/headcount composition number:**
  - root employee master fields: `SAP Emp No`, `D.O.J`, `D.O.L`, plus org attributes
- **Any forecast number:**
  - root source is the historical leave counts built from `EmpNo` + `From Date` + `To Date`
  - enriched with department/leave-type patterns from `Department` and `Leave Type`
  - enriched with workforce features from employee master
- **Any interval, model quality, or saved horizon number:**
  - root source is metadata, not CSV directly

---

## 14. Caveats and implementation notes
- Many analytics tabs use expanded daily leave rows, so counts often represent **employee-days**, not leave applications.
- Forecast rows injected into Executive Intelligence do not have true future cost-centre or leave-type splits; those fields are set to zeros or generic placeholders.
- `Special Leave` and `Comp-Off` are intentionally excluded from staffing-relevant counts.
- Prediction bounds come from saved residual quantiles in metadata, not from date-specific uncertainty estimation.
- Historical forecasts inside the app are still model predictions, even when actual values exist for comparison.
