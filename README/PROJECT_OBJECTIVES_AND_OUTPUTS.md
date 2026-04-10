# Employee Leave Forecasting System
## Project Objectives & Outputs

---

## 📋 PROJECT OBJECTIVES

### Primary Goals

1. **Predict Daily Leave Demand**
   - Use machine learning (XGBoost & TensorFlow) to forecast the number of employees who will be on leave
   - Provide forecasts 7-60 days into the future
   - Enable proactive workforce planning

2. **Track Actual Leave Behavior**
   - Aggregate and analyze approved leave records from the organization
   - Identify daily, weekly, and monthly leave patterns
   - Understand leave trends by cost centre, department, and leave type

3. **Support Workforce Planning**
   - Identify staffing gaps (predicted absence vs available workforce)
   - Distinguish critical leave types (ON-Duty vs Special Leave)
   - Help managers plan for resource allocation

4. **Analyze Leave Patterns**
   - Break down leaves by:
     - **Leave Type**: Casual, Sick, Comp-Off, Special Leave, etc.
     - **Planned vs Unplanned**: Forecastable vs unforecastable absence
     - **Cost Centre/Department**: Identify high-impact areas
     - **Time Dimensions**: Daily, weekly, monthly, seasonal trends
   
5. **Maintain Model Accuracy**
   - Track forecast accuracy using multiple metrics (MAE, RMSE, MAPE, R², WAPE, SMAPE)
   - Compare predicted vs actual leave counts
   - Identify seasonal patterns and anomalies

---

## 📊 KEY OUTPUTS REQUIRED

### 1. Dashboard Outputs (Streamlit Applications)

#### **streamlit_app.py** — Main Forecasting Dashboard
Comprehensive interactive dashboard with 6 tabs:

| Tab | Purpose | Key Outputs |
|-----|---------|-----------|
| **📈 Forecasting** | ML model predictions & accuracy | Forecast chart, accuracy metrics, model comparison (XGBoost vs TensorFlow) |
| **🔵 Special Leave** | Comp-Off & special leave analysis | Weekly/monthly patterns, day-of-week distribution, cost centre breakdown |
| **🏭 Cost Centre** | Department-level analysis | Leave days by cost centre, heatmaps, daily/weekly/monthly trends |
| **📊 Planned vs Unplanned** | Leave predictability | Pie charts, stacked bars, cost centre split, employee counts |
| **🔍 Leave Reason** | Leave type & reason analysis | Top 15 leave reasons, leave type by cost centre, prediction context |
| **⚙️ Settings** | Configuration & data exploration | Model selection, date range selection, raw data viewing |

**Key Metrics Shown**:
- Actual Leave Count (number of employees)
- Predicted Leave Count (model forecast)
- Planned % vs Unplanned %
- Leave days by type and cost centre
- Model accuracy (RMSE, MAE, MAPE, R²)
- Staffing gaps

#### **streamlit_sql_visualization.py** (NEW) — SQL Query Visualization
Interactive visualization dashboard with 5 tabs:

| Tab | Purpose | Key Outputs |
|-----|---------|-----------|
| **📈 Daily Totals** | Daily leave overview | Total leave days, employee count, peak day, line charts |
| **🏢 By Cost Centre** | Cost centre analysis | Top 15 cost centres by leave days & employee count, bar charts |
| **⚖️ Planned vs Unplanned** | ON-Duty vs Special Leave | Stacked bar charts, pie distribution, breakdown by type |
| **📋 Leave Type Summary** | Leave type distribution | Days and employees by leave type, detailed summary |
| **📊 Raw Data** | Query results download | All query results viewable and downloadable as CSV |

**Date Filters**: Dynamic date range selector to filter all visualizations

---

### 2. SQL Query Outputs (run_sql_query.py)

#### **Query 1: Raw Leave Records**
- **Purpose**: Detailed audit of individual leave transactions
- **Output Columns**: EmpNo, Name, Cost Centre, Department, Leave Type, Days, Plan Type, Status
- **Use Case**: Data validation, employee verification, detailed record lookup

#### **Query 2: Summary by Date/Cost Centre/Leave Type** ⭐
- **Purpose**: Multi-dimensional aggregation of leave
- **Output Format**:
  ```
  Leave_Date | Cost_Centre | Leave_Type | Employees_On_Leave | Total_Leave_Days | Planned_Count | Unplanned_Count
  ```
- **Key Metrics**:
  - Total leave days per combination
  - Employee count (unique)
  - Planned vs Unplanned event counts
- **Use Case**: Understand daily patterns by department and leave type

#### **Query 3: Daily Total Actual Leave Counts** ⭐⭐
- **Purpose**: Daily aggregation across entire organization
- **Output Format**:
  ```
  Leave_Date | Actual_Employees_On_Leave | Actual_Total_Leave_Days | Planned_Count | Unplanned_Count | Planned_Employees | Unplanned_Employees
  ```
- **Calculation**: 
  - `Actual_Employees_On_Leave = COUNT(DISTINCT EmpNo)`
  - `Actual_Total_Leave_Days = SUM(Days)`
- **Use Case**: **CRITICAL** — Compare against model's Predicted_Leave_Count for accuracy evaluation
- **Output Example**:
  ```
  2026-02-01 | 15 employees | 45 days | 10 planned events | 5 unplanned events
  2026-02-02 | 18 employees | 52 days | 12 planned events | 6 unplanned events
  ```

#### **Query 4: Actual vs Forecasted (Monthly Summary)** ⭐
- **Purpose**: Monthly aggregation for seasonal analysis
- **Output Format**:
  ```
  Year_Month | Actual_Unique_Employees_On_Leave | Actual_Total_Leave_Days | Actual_Planned_Employees | Actual_Unplanned_Employees | Cost_Centres_Affected | Leave_Types_Used
  ```
- **Use Case**: Long-term forecast validation, seasonal pattern identification

#### **Query 5: ON-Duty vs Special Leave Breakdown** ⭐
- **Purpose**: Separate leaves that require staffing replacement from those that don't
- **Output Format**:
  ```
  Leave_Date | ON_Duty_Absence_Count | Special_Leave_Count | ON_Duty_Leave_Days | Special_Leave_Days
  ```
- **Special Leave Types** (NOT counted for staffing):
  - Comp-Off
  - Special Leave [Not Call ON Duty]
- **Use Case**: **Staffing accuracy** — only count ON_Duty_Leave_Days for workforce planning
- **Output Example**:
  ```
  2026-02-01 | 12 employees | 3 employees | 35 days | 10 days
  (Means: 12 employees need replacement, 3 don't; 35 days of actual absence vs 10 days of special leave)
  ```

#### **Query 6: Forecast Accuracy Metrics** ⭐
- **Purpose**: Calculate planned/unplanned percentages for model training and validation
- **Output Format**:
  ```
  Leave_Date | Actual_Leave_Count | Avg_Leave_Duration_Days | Planned_Leave_Events | Unplanned_Leave_Events | Planned_Percentage | Unplanned_Percentage
  ```
- **Calculation**:
  - `Planned_Percentage = (Planned_Events / Total_Events) × 100`
  - `Unplanned_Percentage = (Unplanned_Events / Total_Events) × 100`
- **Use Case**: Training data quality, accuracy metric computation
- **Output Example**:
  ```
  2026-02-01 | 15 | 3.0 days | 10 | 5 | 66.67% | 33.33%
  (Means: 15 employees, 66.67% took planned leave, 33.33% unplanned)
  ```

#### **Query 7: Actual Leave by Cost Centre** ⭐
- **Purpose**: Cost centre-level leave analysis
- **Output Format**:
  ```
  Cost_Centre | Unique_Employees_On_Leave | Total_Leave_Days | Avg_Days_Per_Employee | Planned_Events | Unplanned_Events
  ```
- **Calculation**:
  - `Avg_Days_Per_Employee = Total_Leave_Days / Unique_Employees`
- **Use Case**: Identify high-impact cost centres, departmental comparisons
- **Output Example** (sorted by highest leave days):
  ```
  IT001       | 25 | 120 | 4.8 | 60 | 28
  SALES005    | 18 | 95  | 5.3 | 48 | 20
  HR003       | 12 | 58  | 4.8 | 30 | 10
  ```

---

### 3. Documentation Outputs

#### **SQL.md** ✅
- Complete guide to SQL query calculations
- Explains how Total Leave Days are calculated
- Breaks down Planned vs Unplanned formulas
- Provides calculation examples with concrete numbers
- Reference table for all metrics

#### **README.md** ✅
- System architecture and data flow
- Feature engineering methodology (50+ features)
- Actual vs Forecasted calculation explanations
- Gap analysis and staffing plan logic
- Model training and prediction process

#### **IMPLEMENTATION_SUMMARY.md** ✅
- Complete implementation log
- Changes made to optimize system
- SQL query enhancements (3→7 queries)
- Graph optimization and removal of redundancy

---

## 🎯 SPECIFIC CALCULATIONS & OUTPUTS

### Total Leave Days Calculation
```
Formula: SUM(Days)
WHERE Status = 'Approved'

Example:
Employee A: 3 days leave
Employee B: 2 days leave (same date as A)
Employee C: 1 day leave

Total Leave Days = 3 + 2 + 1 = 6 days
```

### Planned vs Unplanned Leave Days
```
Planned Days:
  COUNT(events WHERE Type = 'Planned')
  or
  SUM(Days WHERE Type = 'Planned')

Unplanned Days:
  COUNT(events WHERE Type = 'Un-Planned')
  or
  SUM(Days WHERE Type = 'Un-Planned')

Example:
Date: 2026-02-01
  Planned Leave Records: 5 with 12 total days
  Unplanned Leave Records: 2 with 5 total days
  
  Planned_Percentage = (5 / 7) × 100 = 71.43%
  Unplanned_Percentage = (2 / 7) × 100 = 28.57%
```

---

## 📈 MODEL PREDICTION OUTPUTS

### Forecast Output Format
```
For each forecast date:
  - Predicted_Leave_Count (continuous: 0.0 to max employees)
  - Predicted_Employees_On_Leave (integer: discrete count)
  - Confidence Interval (lower bound, upper bound)
  - Model Used (XGBoost or TensorFlow)
  - Forecast Accuracy (if comparing to actual)
```

### Accuracy Metrics Output
```
- MAE (Mean Absolute Error): Average error in employee count
- RMSE (Root Mean Square Error): Penalizes large errors
- MAPE (Mean Absolute Percentage Error): Percentage error
- R² (R-squared): Model fit quality (0-1, higher = better)
- WAPE (Weighted Absolute Percentage Error): Weighted error
- SMAPE (Symmetric Mean Absolute Percentage Error): Symmetric error
```

### Staffing Gap Analysis Output
```
For each forecast date:
  Active_Workforce = employees available to work
  Forecasted_Leave = predicted employees on leave
  Staffing_Gap = Active_Workforce - Forecasted_Leave
  Gap_Percentage = (Forecasted_Leave / Active_Workforce) × 100
  
  Status:
    ✅ ADEQUATE: Gap ≥ minimum required staff
    ⚠️ WARNING: Gap < minimum but manageable
    🔴 CRITICAL: Gap below critical threshold
```

---

## 🔄 DATA FLOW SUMMARY

```
CSV Data
  ↓
Data Cleaning & Validation
  ↓
Expand to Daily Records
  ↓
├─→ SQL Queries (Actual Leave Analysis)
│   └─→ Dashboard Visualizations
│
└─→ Feature Engineering (50+ features)
    ↓
    ML Model Training (XGBoost/TensorFlow)
    ↓
    ├─→ Model Evaluation (Accuracy Metrics)
    │
    └─→ Forecasting (7-60 days ahead)
        ↓
        Staffing Gap Analysis
        ↓
        Dashboard Display & Export
```

---

## ✅ DELIVERABLES CHECKLIST

- ✅ **streamlit_app.py**: Main forecasting dashboard (6 tabs)
- ✅ **streamlit_sql_visualization.py**: SQL visualization dashboard (5 tabs)
- ✅ **run_sql_query.py**: 7 SQL queries for data analysis
- ✅ **SQL.md**: Comprehensive SQL documentation
- ✅ **README.md**: System architecture & calculations
- ✅ **IMPLEMENTATION_SUMMARY.md**: Implementation log
- ✅ **Model Artifacts**: Trained XGBoost & TensorFlow models
- ✅ **Feature Engineering**: 50+ features for predictions
- ✅ **Data Validation**: clean_leave_data() function
- ✅ **Accuracy Tracking**: Multi-metric evaluation system

---

## 🚀 HOW TO RUN

### Main Dashboard
```bash
streamlit run streamlit_app.py
```

### SQL Visualization Dashboard
```bash
streamlit run streamlit_sql_visualization.py
```

### Run SQL Queries (Console)
```bash
python run_sql_query.py
```

---

## 📌 KEY TAKEAWAYS

1. **Objectives**: Predict leave demand, track patterns, support workforce planning
2. **Core Output**: Daily Actual vs Predicted leave count comparison
3. **Critical Query**: Query 3 (Daily Total Actual Leave Counts) for accuracy measurement
4. **Special Logic**: ON-Duty vs Special Leave distinction for staffing decisions
5. **Dashboard**: Interactive visualizations for decision-making support
6. **Documentation**: Complete SQL.md and README.md for reference

