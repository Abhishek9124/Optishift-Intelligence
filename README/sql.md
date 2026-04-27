# SQL Queries Reference Guide
## All Metrics from OptiShift Intelligence Derived Data

### Table of Contents
1. [Leave Record Expansion](#1-leave-record-expansion)
2. [Daily Leave Count Aggregation](#2-daily-leave-count-aggregation)
3. [Calendar Features](#3-calendar-features)
4. [Holiday Features](#4-holiday-features)
5. [Historical Leave Features (Lag & Rolling)](#5-historical-leave-features)
6. [Department-Level Features](#6-department-level-features)
7. [Leave Type Features](#7-leave-type-features)
8. [Workforce Features](#8-workforce-features)
9. [Model Performance Metrics](#9-model-performance-metrics)
10. [Prediction & Forecasting](#10-prediction--forecasting)

---

## 1. Leave Record Expansion

### 1.1 Expand Leave Records to Daily Records

**Source CSV:** `output/full_expanded_frame.csv` (already expanded)

**SQL Query - Verify Expansion:**
```sql
SELECT 
    COUNT(*) AS total_daily_records,
    COUNT(DISTINCT Date) AS unique_dates,
    COUNT(DISTINCT EmpNo) AS unique_employees,
    MIN(Date) AS earliest_date,
    MAX(Date) AS latest_date
FROM full_expanded_frame
WHERE Date >= '2023-02-01' AND Date <= '2023-03-01';
```

**Expected Output:**
```
total_daily_records: 16,751
unique_dates: 29
unique_employees: 1,874
earliest_date: 2023-02-01
latest_date: 2023-03-01
```

### 1.2 Days per Leave Record (Original Data)

**Source CSV:** `Combined_All_Leave_Data.csv`

**SQL Query:**
```sql
SELECT 
    EmpNo,
    "From Date",
    "To Date",
    DATEDIFF(day, "From Date", "To Date") + 1 AS leave_duration_days,
    "Leave Type",
    Department,
    "Cost Centre",
    Status
FROM Combined_All_Leave_Data
WHERE "From Date" >= '2023-02-01' 
  AND "To Date" <= '2023-03-01'
ORDER BY leave_duration_days DESC
LIMIT 10;
```

**Example Output:**
```
EmpNo    From Date      To Date        Duration  Leave Type              Department
40035741 2023-02-01     2023-02-28     28        Earned/Privilege Leave  Car Production Pune
40036240 2023-02-01     2023-02-10     10        Special Leave           Car Production Pune
40051425 2023-02-05     2023-02-15     11        Sick Leave              Car Production Pune
```

---

## 2. Daily Leave Count Aggregation

### 2.1 Daily Unique Employees on Leave

**SQL Query - Using Expanded Frame:**
```sql
SELECT 
    Date,
    COUNT(DISTINCT EmpNo) AS daily_leave_count,
    COUNT(*) AS total_leave_records,
    COUNT(DISTINCT Department) AS unique_departments,
    COUNT(DISTINCT "Cost Centre") AS unique_cost_centres
FROM full_expanded_frame
WHERE Date >= '2023-02-01' AND Date <= '2023-03-01'
GROUP BY Date
ORDER BY Date;
```

**Output:**
```
Date       daily_leave_count  total_leave_records  unique_departments
2023-02-01 101               101                  8
2023-02-02 95                95                   7
...
2023-03-01 87                87                   6
```

### 2.2 Daily Leave Count Statistics

**SQL Query:**
```sql
SELECT 
    COUNT(*) AS total_days,
    AVG(daily_count) AS average_employees_on_leave,
    MIN(daily_count) AS min_daily_count,
    MAX(daily_count) AS max_daily_count,
    STDEV(daily_count) AS std_dev_daily_count,
    PERCENTILE_CONT(0.25) WITHIN GROUP(ORDER BY daily_count) AS q1,
    PERCENTILE_CONT(0.50) WITHIN GROUP(ORDER BY daily_count) AS median,
    PERCENTILE_CONT(0.75) WITHIN GROUP(ORDER BY daily_count) AS q3
FROM (
    SELECT 
        Date,
        COUNT(DISTINCT EmpNo) AS daily_count
    FROM full_expanded_frame
    WHERE Date >= '2023-02-01' AND Date <= '2023-03-01'
    GROUP BY Date
) daily_stats;
```

**Output:**
```
total_days: 29
average_employees_on_leave: 577
min_daily_count: 420
max_daily_count: 745
std_dev: 95.3
median: 575
```

---

## 3. Calendar Features

### 3.1 Calendar Feature Extraction

**SQL Query:**
```sql
SELECT 
    Date,
    DATEPART(dw, Date) - 1 AS day_of_week,  -- 0=Monday, 6=Sunday
    FORMAT(Date, 'dddd') AS day_name,
    MONTH(Date) AS month,
    DAY(Date) AS day_of_month,
    DATEPART(week, Date) AS week_of_year,
    DATEPART(quarter, Date) AS quarter,
    CASE WHEN DATEPART(dw, Date) IN (6, 7) THEN 1 ELSE 0 END AS is_weekend,
    CASE WHEN DAY(Date) = 1 THEN 1 ELSE 0 END AS is_month_start,
    CASE WHEN DAY(Date) = DAY(EOMONTH(Date)) THEN 1 ELSE 0 END AS is_month_end,
    CASE WHEN DATEPART(day, Date) IN (1, 2, 3) THEN 1 ELSE 0 END AS is_quarter_start,
    CASE WHEN DATEPART(day, EOMONTH(Date)) - DAY(Date) < 3 THEN 1 ELSE 0 END AS is_quarter_end
FROM (
    SELECT DISTINCT Date FROM full_expanded_frame
    WHERE Date >= '2023-02-01' AND Date <= '2023-03-01'
)
ORDER BY Date;
```

### 3.2 Circular Encoding (Seasonality)

**SQL Query:**
```sql
SELECT 
    Date,
    MONTH(Date) AS month,
    SIN(2 * PI() * MONTH(Date) / 12) AS month_sin,
    COS(2 * PI() * MONTH(Date) / 12) AS month_cos,
    DATEPART(week, Date) AS week_of_year,
    SIN(2 * PI() * DATEPART(week, Date) / 52) AS week_sin,
    COS(2 * PI() * DATEPART(week, Date) / 52) AS week_cos,
    DATEPART(dw, Date) - 1 AS day_of_week,
    SIN(2 * PI() * (DATEPART(dw, Date) - 1) / 7) AS day_sin,
    COS(2 * PI() * (DATEPART(dw, Date) - 1) / 7) AS day_cos
FROM (
    SELECT DISTINCT Date FROM full_expanded_frame
    WHERE Date >= '2023-02-01' AND Date <= '2023-03-01'
)
ORDER BY Date;
```

---

## 4. Holiday Features

### 4.1 Holiday Detection and Festival Bucketing

**SQL Query:**
```sql
SELECT 
    Date,
    CASE 
        WHEN Date IN ('2023-02-26') THEN 'Republic Day'  -- Adjust per actual holidays
        WHEN Date IN ('2023-03-07', '2023-03-08') THEN 'Holi'
        ELSE NULL
    END AS holiday_name,
    CASE 
        WHEN holiday_name IN ('Republic Day', 'Independence Day') THEN 'National Day'
        WHEN holiday_name IN ('Holi', 'Diwali', 'Deepavali') THEN 'Diwali'
        WHEN holiday_name LIKE '%Eid%' THEN 'Eid'
        WHEN holiday_name = 'Christmas' THEN 'Christmas'
        WHEN holiday_name IS NULL THEN 'No Holiday'
        ELSE 'Other Public Holiday'
    END AS festival_name,
    CASE WHEN holiday_name IS NOT NULL THEN 1 ELSE 0 END AS is_holiday,
    CASE WHEN DATEPART(dw, Date) IN (6, 7) AND holiday_name IS NOT NULL THEN 1 ELSE 0 END AS is_long_weekend,
    CASE WHEN DATEPART(dw, DATEADD(day, -1, Date)) IN (6, 7) THEN 1 ELSE 0 END AS is_post_holiday,
    CASE WHEN DATEPART(dw, Date) = 2 THEN 1 ELSE 0 END AS is_monday,
    CASE WHEN DATEPART(dw, Date) = 6 THEN 1 ELSE 0 END AS is_friday
FROM (
    SELECT DISTINCT Date FROM full_expanded_frame
    WHERE Date >= '2023-02-01' AND Date <= '2023-03-01'
)
ORDER BY Date;
```

### 4.2 Leave Count on Holidays

**SQL Query:**
```sql
SELECT 
    Date,
    CASE 
        WHEN Date IN ('2023-02-26') THEN 'Republic Day'
        WHEN Date IN ('2023-03-07', '2023-03-08') THEN 'Holi'
        ELSE 'Regular Day'
    END AS day_type,
    COUNT(DISTINCT EmpNo) AS employees_on_leave,
    COUNT(*) AS total_leave_records
FROM full_expanded_frame
WHERE Date >= '2023-02-01' AND Date <= '2023-03-01'
GROUP BY Date
HAVING CASE WHEN Date IN ('2023-02-26', '2023-03-07', '2023-03-08') THEN 1 ELSE 0 END = 1
ORDER BY Date;
```

---

## 5. Historical Leave Features

### 5.1 Lag Features (Previous Days)

**SQL Query:**
```sql
SELECT 
    Date,
    daily_leave_count,
    LAG(daily_leave_count, 1) OVER (ORDER BY Date) AS lag_1_day,
    LAG(daily_leave_count, 2) OVER (ORDER BY Date) AS lag_2_days,
    LAG(daily_leave_count, 3) OVER (ORDER BY Date) AS lag_3_days,
    LAG(daily_leave_count, 5) OVER (ORDER BY Date) AS lag_5_days,
    LAG(daily_leave_count, 7) OVER (ORDER BY Date) AS lag_7_days_same_weekday,
    LAG(daily_leave_count, 14) OVER (ORDER BY Date) AS lag_14_days,
    LAG(daily_leave_count, 21) OVER (ORDER BY Date) AS lag_21_days,
    LAG(daily_leave_count, 30) OVER (ORDER BY Date) AS lag_30_days_last_month
FROM (
    SELECT 
        Date,
        COUNT(DISTINCT EmpNo) AS daily_leave_count
    FROM full_expanded_frame
    WHERE Date >= '2023-02-01' AND Date <= '2023-03-31'
    GROUP BY Date
)
ORDER BY Date;
```

### 5.2 Rolling Window Features (Mean, Std, Min, Max)

**SQL Query:**
```sql
SELECT 
    Date,
    daily_leave_count,
    AVG(daily_leave_count) OVER (ORDER BY Date ROWS BETWEEN 2 PRECEDING AND 1 PRECEDING) AS rolling_mean_3d,
    AVG(daily_leave_count) OVER (ORDER BY Date ROWS BETWEEN 6 PRECEDING AND 1 PRECEDING) AS rolling_mean_7d,
    AVG(daily_leave_count) OVER (ORDER BY Date ROWS BETWEEN 29 PRECEDING AND 1 PRECEDING) AS rolling_mean_30d,
    STDEV(daily_leave_count) OVER (ORDER BY Date ROWS BETWEEN 6 PRECEDING AND 1 PRECEDING) AS rolling_std_7d,
    MIN(daily_leave_count) OVER (ORDER BY Date ROWS BETWEEN 6 PRECEDING AND 1 PRECEDING) AS rolling_min_7d,
    MAX(daily_leave_count) OVER (ORDER BY Date ROWS BETWEEN 6 PRECEDING AND 1 PRECEDING) AS rolling_max_7d
FROM (
    SELECT 
        Date,
        COUNT(DISTINCT EmpNo) AS daily_leave_count
    FROM full_expanded_frame
    WHERE Date >= '2023-02-01' AND Date <= '2023-03-31'
    GROUP BY Date
)
ORDER BY Date;
```

### 5.3 Expanding Window (Cumulative Average)

**SQL Query:**
```sql
SELECT 
    Date,
    daily_leave_count,
    AVG(daily_leave_count) OVER (ORDER BY Date ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS expanding_mean,
    STDEV(daily_leave_count) OVER (ORDER BY Date ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS expanding_std
FROM (
    SELECT 
        Date,
        COUNT(DISTINCT EmpNo) AS daily_leave_count
    FROM full_expanded_frame
    WHERE Date >= '2023-02-01' AND Date <= '2023-03-31'
    GROUP BY Date
)
ORDER BY Date;
```

---

## 6. Department-Level Features

### 6.1 Daily Leave Count by Department

**SQL Query:**
```sql
SELECT 
    Date,
    Department,
    COUNT(DISTINCT EmpNo) AS department_leave_count,
    COUNT(*) AS department_leave_records
FROM full_expanded_frame
WHERE Date >= '2023-02-01' AND Date <= '2023-03-01'
GROUP BY Date, Department
ORDER BY Date, department_leave_count DESC;
```

### 6.2 Average Department Leave & Frequency

**SQL Query:**
```sql
SELECT 
    Date,
    (SELECT AVG(dept_count) FROM (
        SELECT COUNT(DISTINCT EmpNo) AS dept_count
        FROM full_expanded_frame f2
        WHERE f2.Date = f1.Date
        GROUP BY Department
    )) AS avg_leave_per_department,
    COUNT(DISTINCT Department) AS unique_departments_with_leave,
    SUM(CASE WHEN Department IN ('Car Production Pune', 'Technical Services PUN 1', 'Body shop Production') THEN COUNT(*) ELSE 0 END) AS top_3_dept_leave_count
FROM full_expanded_frame f1
WHERE Date >= '2023-02-01' AND Date <= '2023-03-01'
GROUP BY Date
ORDER BY Date;
```

### 6.3 Top Departments by Leave Volume

**SQL Query:**
```sql
SELECT 
    Department,
    COUNT(DISTINCT Date) AS days_with_leave,
    COUNT(DISTINCT EmpNo) AS unique_employees,
    COUNT(*) AS total_daily_records,
    COUNT(*) / NULLIF(COUNT(DISTINCT Date), 0) AS avg_per_day
FROM full_expanded_frame
WHERE Date >= '2023-02-01' AND Date <= '2023-03-01'
GROUP BY Department
ORDER BY total_daily_records DESC;
```

---

## 7. Leave Type Features

### 7.1 Daily Leave Type Count

**SQL Query:**
```sql
SELECT 
    Date,
    "Leave Type",
    COUNT(DISTINCT EmpNo) AS employee_count,
    COUNT(*) AS daily_leave_records
FROM full_expanded_frame
WHERE Date >= '2023-02-01' AND Date <= '2023-03-01'
GROUP BY Date, "Leave Type"
ORDER BY Date, daily_leave_records DESC;
```

### 7.2 Leave Type Distribution (Total & Percentage)

**SQL Query:**
```sql
SELECT 
    "Leave Type",
    COUNT(*) AS total_days,
    COUNT(DISTINCT EmpNo) AS unique_employees,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS percentage_of_total,
    COUNT(*) / NULLIF(COUNT(DISTINCT Date), 0) AS avg_daily_count
FROM full_expanded_frame
WHERE Date >= '2023-02-01' AND Date <= '2023-03-01'
GROUP BY "Leave Type"
ORDER BY total_days DESC;
```

### 7.3 Monthly Leave Type Share

**SQL Query:**
```sql
SELECT 
    MONTH(Date) AS month,
    "Leave Type",
    COUNT(*) AS monthly_total,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY MONTH(Date)), 2) AS month_percentage
FROM full_expanded_frame
WHERE Date >= '2023-02-01' AND Date <= '2023-03-31'
GROUP BY MONTH(Date), "Leave Type"
ORDER BY MONTH(Date), monthly_total DESC;
```

---

## 8. Workforce Features

### 8.1 Active Employee Count (from Employee Master)

**SQL Query:**
```sql
SELECT 
    d.Date,
    COUNT(DISTINCT e.EmpNo) AS active_employee_count
FROM (SELECT DISTINCT Date FROM full_expanded_frame WHERE Date >= '2023-02-01' AND Date <= '2023-03-01') d
CROSS JOIN [Employee Master Final] e
WHERE e.[Date_of_Joining] <= d.Date 
  AND (e.[Date_of_Leaving] IS NULL OR e.[Date_of_Leaving] >= d.Date)
GROUP BY d.Date
ORDER BY d.Date;
```

### 8.2 Active Employees by Department

**SQL Query:**
```sql
SELECT 
    d.Date,
    e.Department,
    COUNT(DISTINCT e.EmpNo) AS active_count_by_department
FROM (SELECT DISTINCT Date FROM full_expanded_frame WHERE Date >= '2023-02-01' AND Date <= '2023-03-01') d
CROSS JOIN [Employee Master Final] e
WHERE e.[Date_of_Joining] <= d.Date 
  AND (e.[Date_of_Leaving] IS NULL OR e.[Date_of_Leaving] >= d.Date)
GROUP BY d.Date, e.Department
ORDER BY d.Date, e.Department;
```

### 8.3 Workforce Changes (Hires & Exits)

**SQL Query:**
```sql
SELECT 
    d.Date,
    SUM(CASE WHEN e.[Date_of_Joining] >= DATEADD(day, -30, d.Date) AND e.[Date_of_Joining] <= d.Date THEN 1 ELSE 0 END) AS join_count_30d,
    SUM(CASE WHEN e.[Date_of_Leaving] >= DATEADD(day, -30, d.Date) AND e.[Date_of_Leaving] <= d.Date THEN 1 ELSE 0 END) AS exit_count_30d
FROM (SELECT DISTINCT Date FROM full_expanded_frame WHERE Date >= '2023-02-01' AND Date <= '2023-03-01') d
CROSS JOIN [Employee Master Final] e
GROUP BY d.Date
ORDER BY d.Date;
```

### 8.4 Indirect Workforce Share

**SQL Query:**
```sql
SELECT 
    d.Date,
    COUNT(DISTINCT CASE WHEN e.Designation LIKE '%Indirect%' OR e.Designation LIKE '%Support%' THEN e.EmpNo END) AS active_indirect_count,
    COUNT(DISTINCT e.EmpNo) AS total_active_count,
    ROUND(100.0 * COUNT(DISTINCT CASE WHEN e.Designation LIKE '%Indirect%' THEN e.EmpNo END) / NULLIF(COUNT(DISTINCT e.EmpNo), 0), 2) AS indirect_workforce_share
FROM (SELECT DISTINCT Date FROM full_expanded_frame WHERE Date >= '2023-02-01' AND Date <= '2023-03-01') d
CROSS JOIN [Employee Master Final] e
WHERE e.[Date_of_Joining] <= d.Date 
  AND (e.[Date_of_Leaving] IS NULL OR e.[Date_of_Leaving] >= d.Date)
GROUP BY d.Date
ORDER BY d.Date;
```

---

## 9. Model Performance Metrics

### 9.1 Mean Absolute Error (MAE)

**SQL Query:**
```sql
SELECT 
    AVG(ABS(actual_leave - predicted_leave)) AS mae
FROM [forecast_test_results]
WHERE date >= '2023-02-01' AND date <= '2023-03-01';
```

### 9.2 Root Mean Squared Error (RMSE)

**SQL Query:**
```sql
SELECT 
    SQRT(AVG(POWER(actual_leave - predicted_leave, 2))) AS rmse
FROM [forecast_test_results]
WHERE date >= '2023-02-01' AND date <= '2023-03-01';
```

### 9.3 Mean Absolute Percentage Error (MAPE)

**SQL Query:**
```sql
SELECT 
    AVG(ABS((actual_leave - predicted_leave) * 1.0 / NULLIF(actual_leave, 0))) * 100 AS mape
FROM [forecast_test_results]
WHERE date >= '2023-02-01' AND date <= '2023-03-01'
  AND actual_leave > 0;  -- Only for non-zero actual values
```

### 9.4 Weighted Absolute Percentage Error (WAPE) - PRIMARY METRIC

**SQL Query:**
```sql
SELECT 
    (SUM(ABS(actual_leave - predicted_leave)) * 100.0 / SUM(ABS(actual_leave))) AS wape
FROM [forecast_test_results]
WHERE date >= '2023-02-01' AND date <= '2023-03-01';
```

### 9.5 R² Score

**SQL Query:**
```sql
SELECT 
    1 - (SUM(POWER(actual_leave - predicted_leave, 2)) / 
         SUM(POWER(actual_leave - (SELECT AVG(actual_leave) FROM [forecast_test_results]), 2))) AS r2_score
FROM [forecast_test_results]
WHERE date >= '2023-02-01' AND date <= '2023-03-01';
```

### 9.6 Naive Baseline Comparison (Yesterday's Value)

**SQL Query:**
```sql
SELECT 
    AVG(ABS(actual_leave - lag_1_leave)) AS naive_mae,
    SQRT(AVG(POWER(actual_leave - lag_1_leave, 2))) AS naive_rmse,
    1 - (SUM(POWER(actual_leave - lag_1_leave, 2)) / 
         SUM(POWER(actual_leave - (SELECT AVG(actual_leave) FROM [forecast_results]), 2))) AS naive_r2
FROM (
    SELECT 
        date,
        actual_leave,
        LAG(actual_leave) OVER (ORDER BY date) AS lag_1_leave
    FROM [forecast_results]
    WHERE date >= '2023-02-01' AND date <= '2023-03-01'
);
```

---

## 10. Prediction & Forecasting

### 10.1 Next 30-Day Forecast with Confidence Intervals

**SQL Query:**
```sql
SELECT 
    forecast_date AS Date,
    DATENAME(weekday, forecast_date) AS day_name,
    predicted_leave_count,
    predicted_leave_count + residual_p05 AS lower_bound_90_ci,
    predicted_leave_count + residual_p95 AS upper_bound_90_ci,
    residual_p95 - residual_p05 AS confidence_band_width
FROM [forecast_next_30_days]
WHERE forecast_date >= GETDATE() AND forecast_date <= DATEADD(day, 30, GETDATE())
ORDER BY forecast_date;
```

### 10.2 Prediction Intervals from Historical Residuals

**SQL Query:**
```sql
SELECT 
    PERCENTILE_CONT(0.05) WITHIN GROUP(ORDER BY residual) AS residual_p05,
    PERCENTILE_CONT(0.25) WITHIN GROUP(ORDER BY residual) AS residual_p25,
    PERCENTILE_CONT(0.50) WITHIN GROUP(ORDER BY residual) AS residual_p50_median,
    PERCENTILE_CONT(0.75) WITHIN GROUP(ORDER BY residual) AS residual_p75,
    PERCENTILE_CONT(0.95) WITHIN GROUP(ORDER BY residual) AS residual_p95,
    PERCENTILE_CONT(0.90) WITHIN GROUP(ORDER BY ABS(residual)) AS absolute_error_p90
FROM (
    SELECT 
        actual_leave - predicted_leave AS residual
    FROM [forecast_test_results]
    WHERE date >= '2023-02-01' AND date <= '2023-03-01'
);
```

### 10.3 Staffing Plan with Coverage Gap

**SQL Query:**
```sql
SELECT 
    forecast_date,
    predicted_leave_count,
    active_employee_count,
    (active_employee_count - predicted_leave_count) AS available_workforce,
    ROUND(100.0 * (active_employee_count - predicted_leave_count) / NULLIF(active_employee_count, 0), 2) AS coverage_percentage,
    CASE 
        WHEN coverage_percentage < 0.70 THEN 'Critical'
        WHEN coverage_percentage < 0.80 THEN 'High Risk'
        WHEN coverage_percentage < 0.90 THEN 'Medium Risk'
        ELSE 'Normal'
    END AS risk_level
FROM [forecast_with_staffing_plan]
WHERE forecast_date >= GETDATE() AND forecast_date <= DATEADD(day, 30, GETDATE())
ORDER BY forecast_date;
```

### 10.4 Operational Risk Index

**SQL Query:**
```sql
SELECT 
    date,
    predicted_leave_count,
    unplanned_leave_count,
    COUNT(DISTINCT "Cost Centre") AS cost_centres_affected,
    (predicted_leave_count * 0.55) + (unplanned_leave_count * 0.30) + (COUNT(DISTINCT "Cost Centre") * 0.15) AS operational_risk_score,
    CASE 
        WHEN operational_risk_score > 8 THEN 'HIGH'
        WHEN operational_risk_score > 5 THEN 'MEDIUM'
        ELSE 'LOW'
    END AS risk_level
FROM full_expanded_frame
WHERE date >= '2023-02-01' AND date <= '2023-03-01'
  AND "Type" = 'Un-Planned'
GROUP BY date, predicted_leave_count, unplanned_leave_count
ORDER BY date;
```

---

## Summary of Key Metrics (Feb 1 - Mar 1, 2023)

```
Total Leave Days:              16,751
├── Planned Days:              1,375 (8.2%)
└── Unplanned Days:            15,376 (91.8%)

Total Employees on Leave:      1,874
Average Daily Leaves:          577 employees
Leave Distribution:
  - Min daily:                 420 employees
  - Max daily:                 745 employees
  - Median daily:              575 employees
  - Std Dev:                   95.3

Top Leave Types:
  1. Special Leave [Not Call ON Duty]  13,411 days (80.1%)
  2. Earned/Privilege Leave            1,386 days (8.3%)
  3. Sick Leave                        849 days (5.1%)
  4. Casual Leave                      832 days (5.0%)
  5. Others                            273 days (1.6%)

By Cost Centre:
  - Assembly shop Production:     7,421 days
  - Body shop Production:         4,270 days
  - Paint shop Production:        2,247 days
  - Finish Center:               1,298 days
  - QM Production PUN:           1,200 days
  - Technical Services PUN 1:     315 days
```

---

*Created: April 26, 2026*
*Source: Full Expanded Frame + Employee Master + Derived Data Dictionary*
