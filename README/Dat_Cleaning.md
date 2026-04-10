# Employee Leave Forecasting System - Data Cleaning and Processing Documentation

## Table of Contents
1. [Overview](#overview)
2. [Setup and Configuration](#setup-and-configuration)
3. [Data Loading and Profiling](#data-loading-and-profiling)
4. [ETL and Data Cleaning](#etl-and-data-cleaning)
5. [Employee Master Data Integration](#employee-master-data-integration)
6. [Daily Expansion and Target Creation](#daily-expansion-and-target-creation)
7. [Feature Engineering](#feature-engineering)
8. [Exploratory Data Analysis](#exploratory-data-analysis)
9. [Feature Contribution Analysis](#feature-contribution-analysis)
10. [Machine Learning Models](#machine-learning-models)
11. [Deep Learning Benchmarks](#deep-learning-benchmarks)
12. [Prediction and Workforce Planning](#prediction-and-workforce-planning)
13. [Model Persistence](#model-persistence)
14. [Verification Process](#verification-process)

---

## Overview

This notebook builds an **end-to-end leave forecasting workflow** to estimate how many employees are likely to take leave on a given day. The system supports workforce availability planning with future leave forecasts.

**Business Objective:**
- Predict daily employee leave volume from historical HR leave records
- Support workforce availability planning with future leave forecasts
- Enable workforce scheduling and staffing optimization

**Key Deliverables:**
- Data cleaning and preprocessing pipeline
- Daily leave expansion and aggregation
- Comprehensive feature engineering
- Multiple machine learning models with evaluation
- 30-day leave forecasts
- Workforce planning recommendations
- Model persistence for production use

---

## Setup and Configuration

### Package Installation
The following packages are installed for the analysis:
```
pandas, numpy, matplotlib, seaborn, scikit-learn, xgboost, plotly, holidays, 
shap, tensorflow, joblib, streamlit, openpyxl
```

### Configuration Parameters

| Parameter | Value | Purpose |
|-----------|-------|---------|
| `TOTAL_EMPLOYEES` | 100 | Reference headcount for staffing calculations |
| `DEFAULT_REQUIRED_PRESENT` | 100 | Required employees to be present daily |
| `DEFAULT_KNOWN_ABSENT` | 0 | Pre-known absent employees (sick leave, etc.) |
| `FORECAST_HORIZON` | 30 | Days to forecast into the future |
| `MASTER_FORECAST_BUFFER_DAYS` | 730 | Extended date range for master employee features |
| `FUTURE_DATE` | 2026-11-12 | Example future date for prediction |
| `RANDOM_STATE` | 42 | Seed for reproducibility |

### Data Paths
- **Leave Data:** `Data/Combined_All_Leave_Data.csv`
- **Employee Master:** `Employee Master - Feb 2026 Team Member.xlsx`
- **Model Output:** `artifacts/` directory

### Pandas and TensorFlow Configuration
- Display all columns without truncation
- Format floats to 2 decimal places with thousands separator
- Set random seeds for reproducibility (numpy, TensorFlow)
- Use seaborn whitegrid theme for visualizations

---

## Data Loading and Profiling

### Raw Dataset Analysis

The raw leave dataset is loaded with the following characteristics:

**Dataset Shape:** Contains multiple columns capturing employee leave records

**Key Columns:**
- **Employee Information:** `EmpNo` (Employee Number), `Department`, `Location`
- **Leave Details:** `Leave Type`, `Leave Reason`
- **Date Information:** `From Date`, `To Date`, `Applied On`, `Approved On`
- **Workflow Data:** `Status`, `Approved By`, `Approver Comments`
- **Organization Hierarchy:** `Division`, `Business Area`, `Cost Centre`, `Sub Group Category`
- **Leave Duration:** `Days` (number of leave days)
- **Process Metrics:** `Delay` (approval delay in days)

### Data Quality Assessment

**Variable Types:**
- **Date Columns:** `From Date`, `To Date`, `Applied On`, `Approved On`
- **Numeric Columns:** `Days`, `Delay`
- **Categorical/Text Columns:** All remaining columns

**Missing Value Handling:**
- Columns with high missing percentages are identified
- Text columns are standardized (stripped whitespace, normalized)
- Date columns are parsed with flexible date formats
- Numeric columns are coerced to appropriate types

**Text Columns for Missing Value Imputation:**
```
Department, Location, Leave Type, Leave Reason, Approved By, Business Area,
Cost Centre, Work Contract External, Sub Group Category, Sub Department 1-3,
Type, SourceApp, Status
```

---

## ETL and Data Cleaning

### Data Cleaning Steps

#### 1. Column Name Standardization
- Strip leading/trailing whitespace from all column names
- Ensure consistent naming convention

#### 2. Text Data Cleaning
- Strip whitespace from all text columns
- Replace string representations of null values ("nan", "None", "") with actual NaN
- Apply to all object-type columns

#### 3. Date Parsing
- Convert `From Date`, `To Date`, `Applied On`, `Approved On` to datetime objects
- Use `dayfirst=True` for date parsing (handles DD-MM-YYYY format)
- Use `errors='coerce'` to mark unparseable dates as NaT

#### 4. Numeric Conversion
- Convert `Days` and `Delay` columns to numeric values
- Use `errors='coerce'` to handle invalid entries

#### 5. Status Filtering
- **Keep only "Approved" leaves** - removes pending, rejected, or cancelled records
- Removes leaves that are still in workflow

#### 6. Column Removal
- Remove comment columns: `Comments`, `Approver Comments`
- Remove user-defined columns (all columns starting with "userdefined")
- Reduces noise and focuses on standardized attributes

#### 7. Missing Value Imputation
- **Text columns:** Fill with "Unknown" to maintain records
- **Numeric columns (`Days`, `Delay`):** Fill with median value to preserve distribution

#### 8. Date Validation
- Remove records where `From Date` or `To Date` is missing
- Remove records where `To Date < From Date`
- Ensures data integrity for leave period expansion

#### 9. Deduplication
- Identify duplicate records using: `[EmpNo, Leave Type, From Date, To Date, Applied On]`
- Keep first occurrence of duplicates
- Maintains data quality without losing information

### ETL Summary Outputs

**Example ETL Metrics:**
- **Initial Raw Rows:** Full dataset size
- **Approved Rows:** Number of approved leaves only
- **Duplicates Removed:** Count of duplicate records
- **Final Rows:** Clean dataset size
- **Date Range:** Minimum to maximum dates in dataset

**Example Missing Value Summary:**
- Tracks remaining missing percentages across all columns
- Identifies columns to handle before analysis

---

## Employee Master Data Integration

### Master Data Loading

The employee master workbook contains two sheets:

#### Live Employees Sheet
- Current active employees
- Includes: Employee ID, Name, Department, Designation, DOJ, Age, Salary Band
- Multiple organizational hierarchy levels

#### Left Employees Sheet
- Employees who have separated from the organization
- Includes: Date of Leaving, Department at exit
- Historical context for workforce changes

### Employee Master Processing

**Required Columns Standardization:**
```
SAP Emp No → EmpNo
Name → Master_Name
Department → Master_Department
Division → Master_Division
Current Designation → Master_Designation
Business Area → Master_Business_Area
Direct / Indirect → Master_Direct_Indirect
State → Master_State
Local/Non Local → Master_Local_Non_Local
Category → Master_Category
Sex → Master_Sex
Marital Status → Master_Marital_Status
D.O.J → Date_of_Joining
D.O.L → Date_of_Leaving
Date of Retirement → Date_of_Retirement
Years of Service → Years_of_Service
Age → Employee_Age
```

**Data Type Conversions:**
- Employee IDs: Convert to Int64 (nullable integer)
- Dates: Parse to datetime objects
- Years of Service, Age: Convert to numeric
- Text fields: Strip whitespace, handle null representations

**Deduplication Strategy:**
- Prioritize LIVE employees over LEFT employees
- For duplicates, keep most recent date (latest DOJ or earliest DOL)
- Ensures accurate headcount at any point in time

### Workforce Timeline Fields
- `employment_start`: Normalized start date (midnight)
- `employment_end`: Normalized end date (midnight)
- Used for calculating active headcount over time

### Employee Master Summary Metrics

| Metric | Purpose |
|--------|---------|
| Live employee master rows | Current active workforce count |
| Left employee master rows | Historical employee count |
| Unique employees in unified master | Total unique IDs across live and left |
| Unique employees in leave data | Employees with leave records |
| Leave employees covered by master | Percentage of leave employees in master |
| Coverage percentage | Data quality indicator |
| Current live headcount | Baseline for staffing calculations |

---

## Daily Expansion and Target Creation

### Leave Record Expansion Process

**Objective:** Convert leave period records into daily employee-on-leave records

**Process:**
1. Extract leave date ranges from each leave record
2. Calculate number of days: `(To Date - From Date) + 1`
3. Repeat each record for the number of days in the leave period
4. Generate daily dates using `pd.date_range()`
5. Align all information (EmpNo, Department, Location, Leave Type) to daily level

**Example:**
- Input: Employee 101, Leave from 2026-03-01 to 2026-03-05 (5 days)
- Output: 5 rows, one for each day with same employee and leave information

**Expanded Dataset Columns:**
- `Date`: Daily date
- `EmpNo`: Employee number
- `Department`: Employee's department
- `Location`: Employee's work location
- `Leave Type`: Type of leave (Casual, Sick, Earned, etc.)

### Employee Master Join

**Purpose:** Enrich leave records with employee demographic and organizational attributes

**Join Type:** Left join on `EmpNo`
- Preserves all leave records
- Adds master employee attributes where available

**Master Attributes Added:**
```
Master_Department, Master_Division, Master_Designation, Master_Direct_Indirect,
Master_Local_Non_Local, Master_Category, Master_Sex, Years_of_Service,
Employee_Age, employment_status
```

**Coverage Metrics:**
- `master_record_found`: Binary indicator (1 = match, 0 = no match)
- Coverage percentage: % of expanded records with master match
- Typical coverage: 90-100% depending on data quality

### Daily Leave Count Target Creation

**Aggregation Level:** Daily (one row per date)

**Target Metric:** `Leave_Count`
- **Definition:** Number of UNIQUE employees on leave on a given date
- **Calculation:** `COUNT(DISTINCT EmpNo)` per date
- **Interpretation:** If 5 unique employees are on leave, Leave_Count = 5
- **Alternative:** `Leave_Events` counts total leave records (includes duplicates)

**Calendar Completion:**
- Create complete date range from minimum to maximum dates in data
- Fill missing dates with 0 leave count
- Enables time-series analysis without gaps
- Critical for lag and rolling feature calculations

### Target Dataset Example

| Date | Leave_Count | Leave_Events |
|------|-------------|--------------|
| 2022-10-01 | 5 | 7 |
| 2022-10-02 | 6 | 8 |
| 2022-10-03 | 0 | 0 |

---

## Feature Engineering

### Calendar Features

**Day-Level Features:**
- `day_of_week`: 0-6 (Monday to Sunday)
- `day_name`: Full weekday name (Monday, Tuesday, etc.)
- `day_of_month`: 1-31
- `month`: 1-12
- `week_of_year`: 1-53 (ISO week number)
- `quarter`: 1-4
- `is_weekend`: Binary (1 = Saturday or Sunday)
- `is_month_start`: Binary (1 = first day of month)
- `is_month_end`: Binary (1 = last day of month)

**Cyclical Encoding for Seasonality:**
- `month_sin`: `sin(2π * month / 12)` - Captures cyclical month pattern
- `month_cos`: `cos(2π * month / 12)` - Complements sine for continuity
- Prevents January (month 1) and December (month 12) being treated as distant

### Holiday and Festival Detection

**Process:**
1. Generate India holiday calendar for forecast year range
2. Check if each date is a public holiday
3. Bucket holidays into categories for better patterns

**Holiday Features:**
- `holiday_name`: Exact holiday name from calendar
- `is_holiday`: Binary indicator (1 = public holiday)
- `festival_name`: Bucketed holiday category

**Festival Categories:**
- Diwali / Deepavali
- Holi
- Eid / Bakrid
- Christmas
- Republic Day
- Independence Day
- Other Public Holiday
- None (not a holiday)

### Long Weekend Detection

**Definition:** A date is part of a long weekend if:
- It is adjacent (±1 day) to both a weekend AND a public holiday
- Creates extended holiday breaks

**Calculation:**
```
is_long_weekend = (has_holiday_nearby) AND (has_weekend_nearby)
```

**Business Use:** Employees often extend leaves around long weekends

### Organizational Structure Features

**Department-Level Analysis:**
1. **Daily Department Leave Counts:**
   - Count employees on leave per department per day
   - Identify which departments contribute most leaves

2. **Department Average:**
   - `department_avg_leave`: Mean daily leave per department
   - `department_leave_frequency`: Number of unique departments with leaves per day

3. **Department Encoding (Top 5 Departments):**
   - Create binary columns for each top department
   - `dept_<department_name>`: Count of leaves from that department on the day
   - Captures department-specific leave patterns

**Example:**
```
dept_engineering, dept_sales, dept_hr, dept_finance, dept_operations
```

### Leave Type Analysis

**Daily Leave Type Features:**
- `leave_type_daily_<type>`: Daily count of each leave type
- Top 5 leave types: Casual, Earned, Sick, Earned Compensatory, etc.

**Monthly Leave Type Shares:**
- `leave_type_share_<type>`: Proportion of total monthly leaves
- Formula: `Monthly_Leaves_of_Type / Total_Monthly_Leaves`
- Captures changing patterns across months

**Example Monthly Shares:**
| Month | casual_share | sick_share | earned_share |
|-------|--------------|-----------|--------------|
| Jan | 0.40 | 0.25 | 0.35 |
| Feb | 0.35 | 0.30 | 0.35 |

### Workforce Composition Features

**Active Headcount Series:**
Built for extended calendar (including forecast buffer) using employment dates

**Headcount Features:**
- `active_employee_count`: Total active employees on date
- `active_team_member_count`: Employees with "Team Member" designation
- `active_indirect_count`: Indirect employees
- `active_local_count`: Local (non-expatriate) employees

**Workforce Flow Features (30-Day Rolling):**
- `join_count_30d`: Cumulative employee joins in past 30 days
- `exit_count_30d`: Cumulative employee exits in past 30 days
- `workforce_growth_30d`: Net workforce change YoY 30-day difference

**Workforce Composition Ratios:**
- `indirect_workforce_share`: Proportion of indirect employees
- `local_workforce_share`: Proportion of local employees

**Department-Specific Headcount:**
- `active_master_headcount_<department>`: Active count per department (top 3)
- Captures team size changes over time

### Historical and Lag Features

**Lag Features (Days Back):**
- `leave_lag_1`: Leave count from 1 day ago
- `leave_lag_7`: Leave count from 7 days (1 week) ago
- `leave_lag_14`: Leave count from 14 days (2 weeks) ago
- `leave_lag_30`: Leave count from 30 days (1 month) ago

**Rolling Window Features:**
- `rolling_mean_7`: 7-day rolling average of previous leaves
- `rolling_std_7`: 7-day rolling standard deviation
- `rolling_mean_30`: 30-day rolling average

**Use Case:** Capture recent trends and seasonal patterns

### Period Feature

- `year_month`: Period as "YYYY-MM" string
- Links to monthly share features

### Feature Summary by Category

| Category | Feature Count | Purpose |
|----------|---------------|---------|
| Calendar | 10 | Day, week, month, season patterns |
| Seasonality | 2 | Cyclical encode month |
| Holidays | 3 | Festival and long weekend patterns |
| Workforce | 10+ | Organizational structure and team changes |
| Department | 8+ | Department-level leave patterns |
| Leave Type | 10+ | Leave type distribution and shares |
| History/Lag | 7 | Recent trends and autocorrelation |
| **Total** | **50+** | Comprehensive feature set |

### Feature Missing Value Handling

- Text-based features: Forward fill, backward fill, then fill with 0
- Month-level features: Aligned with daily data using left merge
- All feature columns filled to 0 for missing values after alignment

---

## Exploratory Data Analysis

### Time Series Trends

**Purpose:** Understand leave patterns across time

**Analyses:**
1. **Daily Leave Trend:** Line plot of Leave_Count over entire historical period
   - Shows seasonality and overall trends
   - Identifies long-term patterns

2. **Monthly Leave Distribution:** Bar plot of monthly aggregates
   - Reveals which months have higher leave propensity
   - Useful for capacity planning

### Temporal Patterns

**Weekday Analysis:**
- Average leave count by day of week
- Identifies weekly seasonality
- Common pattern: Higher leaves on Mondays/Fridays (day offs)

**Day of Month Pattern:**
- Leaves at start vs. end of month
- Salary/benefits timing effects

### Categorical Patterns

**Department Contributions:**
- Top 10 departments with most leave days
- Identifies departments with high leave frequency
- Useful for resource allocation

**Leave Type Distribution:**
- Frequency of each leave type
- Top 5 leave types account for majority
- Insights into leave utilization

### Festival and Holiday Impact

**Festival Spikes:**
- Average leave count around public holidays
- Identifies which festivals trigger leaves
- Helps set expectations during holiday periods

**Long Weekend Impact:**
- Elevated leaves around long weekends
- Data-driven capacity planning

### Interactive Visualizations

- **Interactive Daily Trend:** Plotly line chart for exploration
- **Monthly Leave Type Frequency:** Colored line chart by leave type
- Enables drill-down analysis

### EDA Insights Summary

Retrieved metrics:
- Average daily leave count
- Maximum daily leave count recorded
- Most leave-heavy weekday
- Top leave department
- Most common leave type
- Average number of departments with leaves per day

---

## Feature Contribution Analysis

### Feature Correlation Analysis

**Purpose:** Understand feature relationships and redundancy

**Method:** Pearson correlation matrix
- Identifies highly correlated features
- Detects multicollinearity issues
- Visualized using seaborn heatmap with diverging colormap

**Typical Patterns:**
- Lag features positively correlated with target
- Holiday/weekend features show seasonal correlation
- Workforce features show structural relationships

### Feature Importance Evaluation

**Method:** Tree-based feature importance (from Random Forest or tuned XGBoost)
- Measures relative contribution to predictions
- Ranked from most to least important
- Top 15 features visualized as bar chart

**Interpretation:**
- High importance = strong signal for predictions
- Low importance = potentially removable features
- Domain validation = compare to business logic

### SHAP Explainability Analysis

**Purpose:** Explain individual and aggregate model decisions

**TreeExplainer Method:**
- Computes Shapley values
- Shows how features push prediction up/down
- Summary plot (bar) shows average absolute impact

**Insights:**
- Which features drive high vs. low predictions
- Positive vs. negative feature impacts
- Feature interaction effects

---

## Machine Learning Models

### Model Training Setup

**Train-Test Split:**
- **Holdout Size:** MAX(30 days, 15% of data)
- **Strategy:** Chronological split (not random)
- Ensures temporal validity - test on future unseen data
- Critical for time series

**Cross-Validation:**
- **Method:** TimeSeriesSplit with 5 splits
- Maintains temporal order in CV folds
- Prevents data leakage from future to past

### Baseline Model: Naive Lag-1

**Definition:** Use previous day's leave count as prediction

**Purpose:**
- Simple benchmark to beat
- Validates model improvement
- Common baseline in forecasting

**Prediction:** `y_pred = leave_lag_1`

### Regression Models

#### 1. Random Forest

**Hyperparameters:**
- `n_estimators: 300` - Number of trees
- `max_depth: 8` - Tree depth limit
- `min_samples_leaf: 2` - Minimum samples per leaf
- `n_jobs: -1` - Parallel processing on all cores

**Characteristics:**
- Handles non-linear relationships
- Feature importance available
- Robust to outliers
- No assumption of linearity

#### 2. Gradient Boosting

**Hyperparameters:** Default scikit-learn settings
- Sequential tree building
- Learns from previous errors
- Generally strong baseline

#### 3. XGBoost (Multiple Tuning Variants)

**Tuning Strategy:** Grid search over 4 parameter sets

**Example Variant Parameters:**
```
n_estimators: 500-900
learning_rate: 0.02-0.03
max_depth: 4-6
min_child_weight: 2-3
subsample: 0.85-0.95
colsample_bytree: 0.85-0.95
gamma: 0.0-0.2
reg_alpha: 0.0-0.1
reg_lambda: 1.2-2.0
```

**Selection Logic:**
- Regularization (gamma, alpha, lambda) prevents overfitting
- Subsample/colsample balance bias-variance
- Learning rate controls convergence speed
- Max depth controls tree complexity

### Deep Learning Model: Tabular DNN

**Architecture:**
```
Dense(256, activation='relu', input_shape=(n_features,))
Dropout(0.25)
Dense(128, activation='relu')
Dropout(0.20)
Dense(64, activation='relu')
Dense(1, activation='linear')  # Regression output
```

**Compilation:** Adam optimizer, MSE loss

**Training:**
- Epochs: 250 (with early stopping)
- Batch size: 32
- Validation split: 20%
- Early stopping: patience=20 (stop if val_loss doesn't improve)

**Preprocessing:**
- StandardScaler normalization of input features
- Critical for neural network convergence

**Output:** Clipped to [0, ∞) to prevent negative leave count predictions

### Evaluation Metrics

#### Cross-Validation Metrics (on training data)

| Metric | Formula | Interpretation |
|--------|---------|----------------|
| MAE | Mean \| y - ŷ \| | Average absolute error in employees |
| RMSE | √(Mean((y - ŷ)²)) | Penalizes large errors more |
| MAPE | Mean(\|y - ŷ\| / \|y\|) | Percentage error (excludes zero values) |
| R² | 1 - (SS_res / SS_tot) | Variance explained (0-1 scale) |
| WAPE | Sum(\|y - ŷ\|) / Sum(\|y\|) | Weighted average percentage error |

#### Test Metrics (on holdout data)

Same metrics as CV, but on unseen future data

#### Additional Test Metrics

| Metric | Formula | Use |
|--------|---------|-----|
| SMAPE | 2 * Mean(\|y - ŷ\| / (\|y\| + \|ŷ\|)) | Symmetric MAPE, bounds to [0, 200%] |

### Model Selection Criteria

1. **Primary:** Lowest Test RMSE
2. **Secondary:** Lowest Test MAE
3. **Tertiary:** Best MAPE (handles scale)
4. **Constraint:** Must beat naive lag-1 baseline on all metrics

### Feature Used in Models

**Total Features:** 50+

**Feature Groups:**
1. Calendar features (10)
2. Seasonality cyclical (2)
3. Workspace composition (10)
4. Department patterns (8)
5. Leave type patterns (10)
6. Historical/Lag (7)

---

## Deep Learning Benchmarks

### Sequence Models: LSTM and GRU

**Purpose:** Benchmark deep sequence learning alternatives

**Data Preparation:**
1. **Sequence Generation:**
   - Create sequences of fixed length (30 days)
   - Target is the next day's leave count
   - Overlapping sequences for maximum data utilization

2. **Scaling:**
   - MinMaxScaler normalizes leave counts to [0, 1]
   - Important for gradient-based optimization

3. **Train-Test Split:**
   - 80-20 chronological split of sequences
   - Maintains temporal integrity

### LSTM Model

**Architecture:**
```
LSTM(64, activation='tanh', return_sequences=True, input_shape=(sequence_length, 1))
Dropout(0.2)
LSTM(32, activation='tanh')
Dense(1)
```

**LSTM Characteristics:**
- Processes sequences with memory
- Captures long-term dependencies
- Better for long sequences

### GRU Model

**Architecture:**
```
GRU(64, activation='tanh', return_sequences=True, input_shape=(sequence_length, 1))
Dropout(0.2)
GRU(32, activation='tanh')
Dense(1)
```

**GRU Characteristics:**
- Simpler than LSTM (fewer parameters)
- Often comparable performance
- Faster training

### Sequence Model Training

**Configuration:**
- Epochs: 80
- Batch size: 16
- Validation split: 20%
- Early stopping: patience=12
- Optimizer: Adam
- Loss: MSE

**Post-Processing:**
- Reverse MinMaxScaler to get actual leave counts
- Clip predictions to [0, ∞)

### Benchmark Comparison

Results table compares:
- LSTM vs GRU with same architecture
- Against tree-based and tabular DNN models
- Metric: Test RMSE, MAE, MAPE, R²

---

## Prediction and Workforce Planning

### Future Date Prediction

**Function:** `predict_leave_for_date(target_date, ...)`

**Process:**
1. Check if target date is historical or future
2. If historical: Use actual features with imputed lags
3. If future: Iteratively forecast to target date

**Inputs:**
- Target date (YYYY-MM-DD)
- Total workforce size
- Required present workforce
- Known absent employees (other reasons)

**Output:** Detailed prediction with staffing plan

### Iterative Future Forecast

**For Dates Beyond Training Data:**

1. Start with last observed leave count
2. For each future day:
   a. Create new row with date
   b. Calculate all calendar features for new date
   c. Copy forward workforce features (no future changes assumed)
   d. Copy forward department and leave type features
   e. Calculate new lag features from previous prediction
   f. Make prediction using trained model
   g. Add predicted value to history
   h. Move to next day

**Assumptions:**
- Workforce composition stable (uses last known values)
- Department and leave type patterns stable
- Calendar already defined (holidays are known)

### Workforce Planning Calculation

**Given:**
- Predicted leave count (from model)
- Total workforce size
- Required present workforce
- Known absent employees (other reasons)

**Calculations:**

| Calculation | Formula |
|-------------|---------|
| Total Expected Absent | Predicted_Leave + Known_Absent |
| Projected Available | Total_Workforce - Total_Expected_Absent |
| Total Staff Needed | Required_Present + Total_Expected_Absent |
| Additional Headcount Needed | MAX(0, Total_Staff_Needed - Total_Workforce) |
| Coverage Gap | MAX(0, Required_Present - Projected_Available) |

**Recommendation Logic:**
- If Projected_Available ≥ Required_Present: "Sufficient workforce"
- If Projected_Available ≥ 90% Required_Present: "Mild gap, consider balancing"
- If Projected_Available < 90% Required_Present: "Significant gap, plan overtime/floaters"

### 30-Day Forecast

**Function:** `predict_date_range(start_date, periods=30, ...)`

**Process:**
1. For dates in training data: Use actual features + predictions
2. For dates beyond training: Use iterative forecast
3. Combine both into single forecast window
4. Apply staffing plan calculations to each day

**Output Table Columns:**
```
Date, Predicted_Leave_Count, Actual_Leave_Count (if historical),
Known_Absent_Employees, Total_Expected_Absent, Projected_Available,
Required_Present_Workforce, Total_Staff_Needed, Additional_Headcount_Needed,
Recommendation
```

### Prediction Verification

**Function:** `verify_prediction_for_historical_date(target_date, ...)`

**Purpose:** Validate model on known dates

**Process:**
1. Select historical date with known leave count
2. Generate prediction using same process as future dates
3. Compare predicted vs. actual
4. Calculate errors

**Tolerance Parameters:**
- Absolute tolerance (default: ±5 employees)
- Percentage tolerance (default: ±10%)

**Output:**
- Predicted and actual leave counts
- Absolute and percentage errors
- Boolean flags for tolerance checks
- Useful for model validation and selection

---

## Model Persistence

### Model Saving

**Artifacts Directory:** `artifacts/`

**Saved Files:**

1. **leave_forecasting_model.pkl**
   - Serialized trained model (XGBoost or selected algorithm)
   - Format: joblib pickle
   - Contains: Model weights, tree structure, parameters

2. **leave_forecasting_metadata.pkl**
   - Complete metadata and evaluation results
   - Contains:
     - Feature column lists (all categories)
     - Selected model name
     - Target column name
     - Forecast horizon
     - Workforce parameters
     - Training end date
     - Evaluation metrics (CV, test, baseline, sequence)
     - Example staffing scenarios
     - Verification examples

### Model Reloading

```python
reloaded_model = joblib.load(model_path)
metadata = joblib.load(metadata_path)
```

**Use Case:** Production inference without retraining

---

## Verification Process

### Step-by-Step Verification Guide

#### Step 1: Select Historical Date
- Choose a date that already exists in dataset
- Example: 2026-03-10

#### Step 2: Run Verification
```python
verify_prediction_for_historical_date("2026-03-10")
```

#### Step 3: Compare Results
- Review `Predicted_Leave_Count` vs `Actual_Leave_Count`
- Check `Absolute_Error` and `Percentage_Error`

#### Step 4: Review Model Performance
- Consult model comparison table
- Verify selected model beats naive lag-1 baseline on:
  - MAE (Mean Absolute Error)
  - RMSE (Root Mean Squared Error)
  - MAPE (Mean Absolute Percentage Error)
  - WAPE (Weighted Absolute Percentage Error)

#### Step 5: Error Analysis
- Examine residual plots:
  - Distribution histogram (should be centered near 0)
  - Residuals vs predicted (check for heteroscedasticity)
  - Residuals over time (look for trends)
- Identify if systematic patterns exist (overprediction/underprediction)

#### Step 6: High Error Day Investigation
- Review days with largest errors in holdout set
- Investigate business context:
  - Public holidays or festivals
  - Unusual shutdowns or events
  - System outages or data issues
  - End-of-quarter or financial cycles

#### Step 7: Holdout Period Validation
- Use recent held-out data not in training
- Verify consistent behavior on unseen dates
- Important for production readiness

#### Step 8: Define Acceptance Criteria
- Set business rules for acceptable error:
  - Example: `Absolute_Error <= 5 employees or Percentage_Error <= 10%`
- Monitor adherence over time
- Remodel if metrics degrade

### Confidence Indicators

**High Confidence Prediction:**
- Recent similar days have good predictions
- Calendar features don't indicate anomalies (holiday, long weekend)
- Leave type patterns are stable
- Workforce composition is stable

**Low Confidence Prediction:**
- Date is near major festival or shutdown
- Unusual workforce changes (large joins/exits)
- Leave type patterns changing dramatically
- New data patterns not seen in training

---

## Summary and Key Takeaways

### Data Quality Outcomes
- Clean, validated leave records with 90%+ master match
- Daily aggregation creates robust time-series target
- Complete date ranges enable proper lag calculations

### Feature Engineering Success
- 50+ diverse features capturing temporal, organizational, and behavioral patterns
- Lag features provide autocorrelation signal
- Workforce composition features capture organizational context

### Model Performance
- **Primary Model:** Tuned XGBoost with time-series aware evaluation
- **Baseline Comparison:** Significantly outperforms naive lag-1 method
- **Production Ready:** Model saved with full metadata for reproducible inference

### Business Applications
1. **Staffing Optimization:** 30-day forecasts guide resource allocation
2. **Contingency Planning:** Recommendation engine identifies high-risk days
3. **Workforce Analytics:** Understand leave patterns by department, type, festival
4. **Capacity Planning:** Project available workforce with confidence intervals

### Limitations and Considerations
- Model assumes historical patterns continue (suitable for 30-day horizon)
- Unusual events (lockdowns, policy changes) may invalidate predictions
- Calibration important for business adoption
- Regular retraining recommended (monthly or quarterly)

### Next Steps
1. Deploy model to production environment
2. Integrate with HR systems for real-time predictions
3. Create dashboards for workforce planning teams
4. Monitor forecast accuracy over time
5. Gather feedback for model improvement
6. Implement retraining pipeline as new data arrives

