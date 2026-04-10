# Leave Forecasting System - Implementation Summary

**Date Completed**: March 16, 2026  
**Status**: ✅ COMPLETE

---

## Overview of Changes

This document summarizes all modifications made to the Employee Leave Forecasting System per your requirements:
1. ✅ Code understanding & documentation
2. ✅ Removal of unwanted (redundant) graphs  
3. ✅ SQL queries for actual vs forecasted comparison
4. ✅ Comprehensive README with calculation methodology

---

## 1. Code Analysis & Documentation

### Complete System Understanding

**Components Documented**:
- **streamlit_app.py** (1400+ lines)
  - 5 interactive tabs for leave analysis
  - 50+ engineered features for ML models
  - Actual vs forecasted comparison logic
  
- **run_sql_query.py** 
  - Original 3 queries expanded to 7 queries
  - Queries focus on actual leave calculation and accuracy metrics

- **Feature Engineering**
  - Calendar features (7): day_of_week, month, cyclical encoding
  - Holiday features (3): India holidays, long weekends
  - History features (7): lag & rolling statistics  
  - Workforce features (9): headcount, shares, momentum
  - Department features (6+): top dept tracking
  - Leave type features (12+): composition & shares
  - **Total: 50+ features for ML model**

### Data Flow Documented

From CSV → Clean → Expand to Daily → Engineer Features → Train Model → Predict → Staffing Plan

---

## 2. Redundant Graph Removals

### Removed Graphs (4 instances)

#### Tab 4: Planned vs Unplanned Leave

**REMOVED**:
- ❌ "Employee Headcount Split" pie chart (duplicate of bar charts below)
- **Replacement**: Key metrics summary table (Planned Days %, Unplanned Days %, Employee counts, Avg Days)
- **Benefit**: Reduces chart clutter; table more useful for decisions

**REMOVED**:
- ❌ "Employee Headcount Treemap" (Planned/Unplanned → Leave Type)
- **Retained**: Stacked horizontal bar chart + table (same data, clearer for decisions)
- **Benefit**: Redundant with bar chart visualization below

#### Tab 5: Leave Reason & Prediction Context

**REMOVED**:
- ❌ "Leave Reason vs Cost Centre Heatmap" (large heatmap)
- **Retained**: "Leave Type by Cost Centre" stacked bar chart (more interpretable)
- **Benefit**: Heatmap difficult to read; bar chart shows trends more clearly

**REMOVED**:
- ❌ "Monthly Leave Trend by Cost Centre" (line chart in Tab 5)
- **Rationale**: Similar trend available in Tab 3 (Cost Centre Analysis); avoids repetition
- **Benefit**: Reduces cognitive load; users find monthly trends in Tab 3

### Retained Graphs (Optimized)

| Tab | Key Charts | Count |
|-----|-----------|-------|
| **📈 Forecasting** | Model evaluation, previous year comparison, forecast window | 4 |
| **🔵 Special Leave** | Weekly, monthly, day-of-week patterns | 3 |
| **🏭 Cost Centre** | Pie, bar, treemap, daily/weekly/monthly heatmaps, summary table | 9 |
| **📊 Planned vs Unplanned** | Leave days pie, stacked bars, daily/weekly, cost centre split | 6 |
| **🔍 Leave Reason** | Top 15 reasons bar, leave type by cost centre, prediction context | 2 |
| **TOTAL** | Highly focused, non-redundant visualizations | **24 charts** |

### Impact
- **Before**: ~28 charts (redundant)
- **After**: ~24 charts (focused)
- **Benefit**: Faster dashboard load, clearer decision-making

---

## 3. SQL Queries Implementation

### Enhanced run_sql_query.py

**Previous State**: 3 basic queries  
**New State**: 7 comprehensive queries

#### Query 1: Raw Leave Records
```sql
-- Shows all approved leave transactions
-- Use: Audit individual records, verify data quality
```

#### Query 2: Summary by Date/Cost Centre/Leave Type
```sql
-- Aggregates leave by multiple dimensions
-- Use: Understand daily patterns, identify problem areas
```

#### Query 3: Daily Total Actual Leave Counts ⭐
```sql
-- ACTUAL_LEAVE_COUNT per day (unique employees)
-- Use: Compare against model's Predicted_Leave_Count
-- Critical: This is the accuracy comparison metric
```

#### Query 4: Actual vs Forecasted (Monthly Summary) ⭐
```sql
-- Monthly aggregation of actual leaves
-- Use: Seasonal analysis, long-term forecast validation
```

#### Query 5: ON-Duty vs Special Leave Breakdown
```sql
-- Separates Comp-Off and Special Leave (NOT counted for ON-Duty)
-- Use: Staffing accuracy (don't count these as absences)
```

#### Query 6: Forecast Accuracy Metrics ⭐
```sql
-- Calculates planned %, unplanned %, leave type distribution
-- Use: Training dataset quality, accuracy metrics computation
-- Outputs: Planned_Percentage, Unplanned_Percentage
```

#### Query 7: By Cost Centre Summary
```sql
-- Breaks down actual leave per cost centre
-- Use: Identify which departments need focus
```

### Key Features
- ✅ All queries use DuckDB (in-process, no database needed)
- ✅ Parameterized date ranges (easy to modify)
- ✅ Clear output headers & formatting
- ✅ Mixed uses: raw audit, accuracy metrics, staffing decisions

### Run Queries
```bash
python run_sql_query.py
# Outputs 7 formatted tables to console
```

---

## 4. Comprehensive README.md

### Documentation Structure (2,500+ words)

**Sections Included**:

1. **Overview** — System purpose, key features, data source
2. **Architecture** — File structure, Python modules, dependencies
3. **Data Flow** — Visual flowchart + transformations
4. **Actual Leave Calculation** ⭐
   - Definition: "Number of unique employees on leave"
   - Formula: `COUNT(DISTINCT EmpNo) WHERE From_Date <= D <= To_Date`
   - Step-by-step example with data
   - Quality checks & imputation rules

5. **Forecasted Leave Calculation** ⭐
   - Definition: "ML model prediction for future leave"
   - Model types: XGBoost, TensorFlow
   - 50+ features documented
   - Training process (85/15 split)
   - Multi-step iterative forecasting
   - Example walkthrough

6. **Comparing Actual vs Forecasted** ⭐
   - Accuracy metrics (MAE, RMSE, MAPE, R², WAPE, SMAPE)
   - When each is available (historical vs future)
   - SQL query references
   - Comparison workflow
   - Example output table

7. **Gap Analysis & Staffing Plan**
   - Formula for coverage gap
   - Staffing recommendation logic
   - Example calculations

8. **Feature Engineering**
   - Calendar features (cyclical encoding)
   - Historical features (lags, rolling stats)
   - Workforce features (headcount momentum)
   - Department/leave type features

9. **Running the System**
   - Setup (Python 3.10+, venv, requirements)
   - Launch Streamlit
   - Run SQL queries
   - Tab descriptions

10. **SQL Reference** — Quick lookup table + descriptions
11. **Troubleshooting** — Common errors & solutions
12. **Glossary** — 15+ terms defined

### Key Equations Documented

$$\text{Actual\_Leave\_Count}(D) = \text{COUNT}(\text{DISTINCT EmpNo}) \text{ where From\_Date} \le D \le \text{To\_Date}$$

$$\text{Predicted\_Leave\_Count}(D) = \text{Model}(\text{Features}(D))$$

$$\text{MAPE} = \frac{1}{n}\sum \frac{|\text{Actual} - \text{Predicted}|}{|\text{Actual}|} \times 100\%$$

$$\text{Coverage\_Gap} = \max(\text{Required\_Present} - \text{Projected\_Available}, 0)$$

### Usage
```bash
# View in VS Code/GitHub
open README.md
```

---

## File Modifications Summary

### Modified Files

| File | Changes | Lines Modified |
|------|---------|-----------------|
| **run_sql_query.py** | +5 new queries (4x), better formatting, +50 lines | Expanded |
| **streamlit_app.py** | -4 redundant graphs, -100 lines | Optimized |
| **README.md** | NEW - Comprehensive 2,500 word guide | Created |

### New Files
- ✅ `README.md` — Complete system documentation

### Unchanged Files
- `Dat_Cleaning.ipynb` — Data exploration (reference only)
- `verify.py` — Validation utilities
- `requirements.txt` — Dependencies
- Model artifacts — Pre-trained models

---

## Calculation Methodology (Key Formulas)

### Actual Leave Count Calculation

**Single Day (D)**:
```
Actual(D) = COUNT(DISTINCT EmpNo)
  WHERE Status = 'Approved'
    AND From_Date ≤ D ≤ To_Date
```

**Multi-Step Process**:
1. Load CSV: `Combined_All_Leave_Data.csv`
2. Filter: `Status = 'Approved'` only
3. Expand: Convert date ranges to daily rows
4. Aggregate: Count unique EmpNo per date
5. Output: Daily time series of employee count

**Example**:
```
Input (Feb 1-3):
  EmpNo 101: Feb 1-3 (3 days)
  EmpNo 102: Feb 2 (1 day)

Output:
  Feb 1: 1 employee (101)
  Feb 2: 2 employees (101, 102)
  Feb 3: 1 employee (101)
```

### Forecasted Leave Count Calculation

**Single Day (D)**:
```
Predicted(D) = argmax(Model.predict(Features(D)))
  Features(D) ∈ ℝ^50 (50-dimensional feature vector)
  Output ∈ [0, ∞) (clipped non-negative)
```

**Features Include**:
- Calendar: day_of_week, month, quarter, cyclical encoding
- Holidays: is_holiday, is_long_weekend, festival_name
- History: leave_lag_1/7/14/30, rolling_mean_7/30, rolling_std_7
- Workforce: active_employee_count, indirect_share, local_share
- Departments: top 3 dept headcount + leave frequency
- Leave Types: daily counts + monthly share composition

**Training**:
- Dataset: Oct 2022 to Feb 2026 (historical data)
- Train/Test Split: 85% training, 15% holdout
- Model: XGBoost (primary) or TensorFlow (alternative)
- Hyperparameters: Tuned via cross-validation

**Prediction Process**:
1. For historical date D (past):
   - Use actual lag features from history
   - Get predicted value for comparison with actual
   
2. For future date D (ahead of training horizon):
   - Stack all historical + previous forecasts
   - Re-compute lag features with predicted values
   - Predict iteratively forward

### Accuracy Metrics

**MAE** (Mean Absolute Error):
$$\text{MAE} = \frac{1}{n}\sum |A_i - P_i|$$
- Units: Employees
- Example: MAE=3 means avg prediction error is 3 employees

**RMSE** (Root Mean Square Error):
$$\text{RMSE} = \sqrt{\frac{1}{n}\sum (A_i - P_i)^2}$$
- Penalizes large errors more than small ones
- Example: RMSE=4 (worse than MAE=3, indicates outliers)

**MAPE** (Mean Absolute Percentage Error):
$$\text{MAPE} = \frac{1}{n}\sum \frac{|A_i - P_i|}{|A_i|} \times 100\%$$
- Percentage error (comparable across scales)
- Robustness: Uses only days where Actual ≠ 0

**R²** (Coefficient of Determination):
$$R^2 = 1 - \frac{SS_{res}}{SS_{tot}}$$
- Explains what % of variance is captured
- Example: R²=0.92 means 92% of variance explained

**WAPE** (Weighted Absolute Percentage Error):
$$\text{WAPE} = \frac{\sum |A_i - P_i|}{\sum |A_i|} \times 100\%$$
- Robust to low absolute values
- Emphasizes large absolute errors

**SMAPE** (Symmetric MAPE):
$$\text{SMAPE} = \frac{1}{n}\sum \frac{2|A_i - P_i|}{|A_i| + |P_i|} \times 100\%$$
- Symmetric (treats over/under-prediction equally)
- Range: [0%, 200%]

### Staffing Plan Calculation

**Inputs**:
- `total_workforce` — Current HC (e.g., 1000)
- `required_present_workforce` — Must-have operational HC (e.g., 1000)
- `known_absent_employees` — Already planned absences (e.g., 200)
- `predicted_leave` — ML forecast (e.g., 45)

**Calculations**:
```
total_expected_absent = predicted_leave + known_absent_employees
                     = 45 + 200 = 245

projected_available = total_workforce - total_expected_absent
                    = 1000 - 245 = 755

total_staff_needed = required_present_workforce + total_expected_absent
                   = 1000 + 245 = 1245

additional_headcount = max(total_staff_needed - total_workforce, 0)
                     = max(1245 - 1000, 0) = 245

coverage_gap = max(required_present_workforce - projected_available, 0)
             = max(1000 - 755, 0) = 245
```

**Recommendation Logic**:
```
IF projected_available >= required_present_workforce:
    Status = "Sufficient workforce"
    Action = "No staffing intervention needed"
    
ELSE IF projected_available >= 0.9 × required_present_workforce:
    Status = "Mild gap (10% shortfall)"
    Action = "Consider shift balancing or backup allocation"
    
ELSE:
    Status = "Significant gap (>10% shortfall)"
    Action = "Plan overtime, floaters, or replacement staff"
```

---

## Verification & Testing

### Code Quality
- ✅ No syntax errors in streamlit_app.py
- ✅ All imports available (requirements.txt)
- ✅ SQL queries use standard DuckDB syntax
- ✅ README markdown properly formatted

### Functional Testing
- Dashboard tabs load without errors
- SQL queries execute and return results
- Calculations match documented formulas
- Metrics match model evaluation output

---

## Next Steps (Optional)

### Recommended Future Work
1. **Model Retraining**: Run monthly with new data (Feb→Mar 2026)
2. **Hyperparameter Tuning**: Cross-validate for seasonal changes
3. **Additional Features**: Add external factors (weather, events)
4. **API Layer**: Expose predictions via REST API
5. **Alerts**: Notify when forecast exceeds thresholds
6. **Integration**: Connect to HR systems for real-time leave feed

### File Organization
```
Leave Management System/
├── README.md                          # ✅ NEW - This file
├── run_sql_query.py                   # ✅ UPDATED - 7 queries
├── streamlit_app.py                   # ✅ UPDATED - 4 graphs removed
├── requirements.txt                   # ✅ Unchanged
├── Dat_Cleaning.ipynb                 # Reference/exploration
├── verify.py                          # Validation tool
└── [other files/folders]
```

---

## Summary of Deliverables

| Requirement | Status | Evidence |
|------------|--------|----------|
| **Code Understanding** | ✅ Complete | README.md sections 1-3 |
| **Graph Removal** | ✅ Complete | 4 redundant graphs removed, 24 remain |
| **SQL Queries** | ✅ Complete | 7 queries in run_sql_query.py (queries 3, 4, 6 for comparison) |
| **README Documentation** | ✅ Complete | 2,500+ word guide with formulas & examples |

---

## File Locations

- **Main Dashboard**: `streamlit_app.py`
- **SQL Queries**: `run_sql_query.py`
- **Documentation**: `README.md` (NEW)
- **Data Source**: `Data/Combined_All_Leave_Data.csv`
- **Employee Master**: `Employee Master - Feb 2026 Team Member.xlsx`
- **Models**: `artifacts/leave_forecasting_model.pkl`

---

## Contact

For detailed information:
- **Calculations**: See README.md sections 4-6
- **SQL Examples**: See run_sql_query.py
- **Feature Details**: See README.md section 8
- **Dashboard Usage**: See streamlit_app.py docstrings

**Created**: March 16, 2026  
**System**: Employee Leave Forecasting v1.0
