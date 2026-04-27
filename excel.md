# Excel Formulas Documentation
## OptiShift Intelligence - Leave Forecasting System
### Date Range: February 1, 2023 to March 1, 2023

---

## Data Source CSVs Reference

### Primary Data Sources Used:
1. **Combined_All_Leave_Data.csv** - Main leave transaction data
   - Columns: EmpNo, From Date, To Date, Leave Type, Department, Location, Cost Centre, Status, Days, Applied On, Approved On, etc.
   
2. **Employee Master Final.csv** - Employee information
   - Columns: EmpNo, Employee Name, Department, Cost Centre, Location, Designation, etc.

3. **India Holiday Calendar** - Holiday dates for calculations
   - Reference: Indian public holidays (maintained separately or in holiday_dates.csv)

### Secondary/Output CSVs:
4. **Daily_Aggregation_[DateRange].csv** - Generated daily aggregations
5. **Forecast_Results_[DateRange].csv** - Forecast values and predictions

---

## Table of Contents
1. [Data Summary Tab](#1-data-summary-tab)
2. [Daily Aggregation Tab](#2-daily-aggregation-tab)
3. [Leave Type Analysis Tab](#3-leave-type-analysis-tab)
4. [Department Analytics Tab](#4-department-analytics-tab)
5. [Calendar Features Tab](#5-calendar-features-tab)
6. [Forecasting Metrics Tab](#6-forecasting-metrics-tab)
7. [Risk Analysis Tab](#7-risk-analysis-tab)

---

## 1. Data Summary Tab

### Overview Metrics (as of Period End: March 1, 2023)

#### 1.1 Total Leave Records
```
CSV Source: Combined_All_Leave_Data.csv
Column Used: All rows (any column can be used to count)
Formula: =COUNTA(A:A)-1
Purpose: Count all leave records in the dataset
Result for Feb-Mar 2023: [Based on actual data]
```

#### 1.2 Unique Employees on Leave
```
CSV Source: Combined_All_Leave_Data.csv
Column Used: EmpNo
Formula: =SUMPRODUCT(1/COUNTIFS(EmpNo:EmpNo,EmpNo:EmpNo,"<>"))
Alternative: =SUMPRODUCT(--(COUNTIFS(EmpNo$2:EmpNo$500,EmpNo$2:EmpNo$500,ROW(EmpNo$2:EmpNo$500),"<="&ROW())=1))
Purpose: Count distinct employees who took leave during period
```

#### 1.3 Total Leave Days (Feb 1 - Mar 1, 2023)
```
CSV Source: Combined_All_Leave_Data.csv
Columns Used: Days, From_Date, To_Date
Formula: =SUMIFS(Days, From_Date, ">=2023-02-01", To_Date, "<=2023-03-01")
Purpose: Sum all leave days within the date range
```

#### 1.4 Average Leave Days per Employee
```
CSV Source: Combined_All_Leave_Data.csv
Columns Used: Days, From_Date, To_Date, EmpNo
Formula: =SUMIFS(Days, From_Date, ">=2023-02-01", To_Date, "<=2023-03-01") / 
         =SUMPRODUCT(--(COUNTIFS(EmpNo$2:EmpNo$500,EmpNo$2:EmpNo$500,ROW(EmpNo$2:EmpNo$500),"<="&ROW())=1))
Purpose: Calculate average leave duration per employee
```

#### 1.5 Leave Approval Rate
```
CSV Source: Combined_All_Leave_Data.csv
Columns Used: Status, From_Date, To_Date
Formula: =COUNTIFS(Status:Status, "Approved", From_Date, ">=2023-02-01", To_Date, "<=2023-03-01") / 
         =COUNTIFS(From_Date, ">=2023-02-01", To_Date, "<=2023-03-01")
Purpose: Percentage of approved leave requests
```

---

## 2. Daily Aggregation Tab

### Date Range: February 1, 2023 to March 1, 2023 (29 days)

**CSV Source: Combined_All_Leave_Data.csv**
**Related CSV: Employee Master Final.csv** (for employee count validation)

#### 2.1 Column Structure
| Column | CSV Source | Column Name | Formula | Purpose |
|--------|-----------|------------|---------|---------|
| A | N/A | Date | Sequential dates from 2023-02-01 to 2023-03-01 | Date reference |
| B | Combined_All_Leave_Data.csv | From_Date, To_Date | =TEXT(A2,"DDD") | Day of week name |
| C | Combined_All_Leave_Data.csv | EmpNo, From_Date, To_Date, Status | =SUMPRODUCT formula | Total unique employees on leave |
| D | Combined_All_Leave_Data.csv | Leave_Type="Casual" | SUMPRODUCT + Leave_Type filter | Casual leave count |
| E | Combined_All_Leave_Data.csv | Leave_Type="Sick" | SUMPRODUCT + Leave_Type filter | Sick leave count |
| F | Combined_All_Leave_Data.csv | Leave_Type="Planned" | SUMPRODUCT + Leave_Type filter | Planned leave count |
| G | Combined_All_Leave_Data.csv | All Leave_Types | =C2-F2 | Unplanned leave count |

#### 2.2 Daily Leave Count Calculation (Column C - Primary Metric)
```
CSV Source: Combined_All_Leave_Data.csv
Columns Used: From_Date, To_Date, Status, EmpNo
Formula: =SUMPRODUCT(
           (From_Date$2:From_Date$500 <= A2) * 
           (To_Date$2:To_Date$500 >= A2) * 
           (Status$2:Status$500 = "Approved")
         )

For 2023-02-15 Example:
=SUMPRODUCT((From_Date$2:From_Date$500 <= DATE(2023,2,15)) * 
            (To_Date$2:To_Date$500 >= DATE(2023,2,15)) * 
            (Status$2:Status$500 = "Approved"))
Result: X unique employees on leave
```

#### 2.3 Leave Type Breakdown (Columns D, E, F)

**Casual Leave Count:**
```
CSV Source: Combined_All_Leave_Data.csv
Columns Used: From_Date, To_Date, Status, Leave_Type
Formula: =SUMPRODUCT(
           (From_Date$2:From_Date$500 <= A2) * 
           (To_Date$2:To_Date$500 >= A2) * 
           (Status$2:Status$500 = "Approved") * 
           (Leave_Type$2:Leave_Type$500 = "Casual")
         )
```

**Sick Leave Count:**
```
CSV Source: Combined_All_Leave_Data.csv
Columns Used: From_Date, To_Date, Status, Leave_Type
Formula: =SUMPRODUCT(
           (From_Date$2:From_Date$500 <= A2) * 
           (To_Date$2:To_Date$500 >= A2) * 
           (Status$2:Status$500 = "Approved") * 
           (Leave_Type$2:Leave_Type$500 = "Sick")
         )
```

**Planned Leave Count:**
```
CSV Source: Combined_All_Leave_Data.csv
Columns Used: From_Date, To_Date, Status, Leave_Type
Formula: =SUMPRODUCT(
           (From_Date$2:From_Date$500 <= A2) * 
           (To_Date$2:To_Date$500 >= A2) * 
           (Status$2:Status$500 = "Approved") * 
           (Leave_Type$2:Leave_Type$500 = "Planned")
         )
```

#### 2.4 Unplanned Leave Count (Column G)
```
CSV Source: Combined_All_Leave_Data.csv (derived)
Formula: =C2 - F2
Purpose: Subtracts planned leaves from total to get unplanned
Alternative: =SUMPRODUCT((From_Date<=A2)*(To_Date>=A2)*(Status="Approved")*(Leave_Type<>"Planned"))
```

#### 2.5 Is Weekend Indicator
```
CSV Source: None (calculated from date)
Formula: =IF(OR(WEEKDAY(A2)=1, WEEKDAY(A2)=7), 1, 0)
Purpose: 1 = Saturday/Sunday, 0 = Weekday
```

#### 2.6 Is Holiday Indicator
```
CSV Source: Holiday_Calendar.csv (or Holiday_Dates reference table)
Formula: =IF(COUNTIFS(Holiday_Date, A2) > 0, 1, 0)
Purpose: 1 if date is in holiday calendar, 0 otherwise
Note: Holiday list must be maintained separately (India holidays)
```

#### 2.7 7-Day Rolling Average (Column H)
```
CSV Source: Combined_All_Leave_Data.csv (indirect, uses Column C)
Formula: =IFERROR(AVERAGE(C2:C8), C2)
Purpose: Rolling 7-day average of daily leave count
Adjusted for row 2-7 to use available data
```

#### 2.8 30-Day Rolling Average (Column I)
```
CSV Source: Combined_All_Leave_Data.csv (indirect, uses Column C)
Formula: =IFERROR(AVERAGE(OFFSET(A2,-29,2,30,1)), C2)
Purpose: Rolling 30-day average of daily leave count
```

---

## 3. Leave Type Analysis Tab

### Leave Type Breakdown for Feb-Mar 2023

**CSV Source: Combined_All_Leave_Data.csv**

#### 3.1 Leave Type Summary Table
| Leave Type | Total Count | Total Days | Avg Days/Request | % of Total |
|------------|-------------|-----------|------------------|-----------|
| Casual | =COUNTIFS(Leave_Type, "Casual", From_Date, ">=2023-02-01", To_Date, "<=2023-03-01", Status, "Approved") | =SUMIFS(Days, Leave_Type, "Casual", From_Date, ">=2023-02-01", To_Date, "<=2023-03-01", Status, "Approved") | =E2/B2 | =B2/SUM(B$2:B$5) |
| Sick | =COUNTIFS(Leave_Type, "Sick", From_Date, ">=2023-02-01", To_Date, "<=2023-03-01", Status, "Approved") | =SUMIFS(Days, Leave_Type, "Sick", From_Date, ">=2023-02-01", To_Date, "<=2023-03-01", Status, "Approved") | =E3/B3 | =B3/SUM(B$2:B$5) |
| Planned | =COUNTIFS(Leave_Type, "Planned", From_Date, ">=2023-02-01", To_Date, "<=2023-03-01", Status, "Approved") | =SUMIFS(Days, Leave_Type, "Planned", From_Date, ">=2023-02-01", To_Date, "<=2023-03-01", Status, "Approved") | =E4/B4 | =B4/SUM(B$2:B$5) |
| Other | =COUNTIFS(Leave_Type, "Other", From_Date, ">=2023-02-01", To_Date, "<=2023-03-01", Status, "Approved") | =SUMIFS(Days, Leave_Type, "Other", From_Date, ">=2023-02-01", To_Date, "<=2023-03-01", Status, "Approved") | =E5/B5 | =B5/SUM(B$2:B$5) |

**Columns Used (from Combined_All_Leave_Data.csv):**
- Leave_Type, Days, From_Date, To_Date, Status

#### 3.2 Daily Leave Type Distribution (Pivot Analysis)
```
For Casual Leave:
CSV Source: Combined_All_Leave_Data.csv
Column: Daily_Casual_Leaves
Formula: =SUMPRODUCT(
           (From_Date$2:From_Date$500 <= A2) * 
           (To_Date$2:To_Date$500 >= A2) * 
           (Status$2:Status$500 = "Approved") * 
           (Leave_Type$2:Leave_Type$500 = "Casual")
         )

For Sick Leave:
CSV Source: Combined_All_Leave_Data.csv
Column: Daily_Sick_Leaves
Formula: =SUMPRODUCT(
           (From_Date$2:From_Date$500 <= A2) * 
           (To_Date$2:To_Date$500 >= A2) * 
           (Status$2:Status$500 = "Approved") * 
           (Leave_Type$2:Leave_Type$500 = "Sick")
         )
```

---

## 4. Department Analytics Tab

### Department-Level Leave Analysis (Feb 1 - Mar 1, 2023)

**CSV Sources: Combined_All_Leave_Data.csv + Employee Master Final.csv**

#### 4.1 Department Summary Table
```
Column Headers: Department | Total Requests | Total Days | Avg Leaves/Day | Risk Score

CSV Columns Used:
- From Combined_All_Leave_Data.csv: Department, Days, From_Date, To_Date, Status, Leave_Type, Cost_Centre
- From Employee Master Final.csv: Department (for validation)

Formula for Total Requests per Department:
=COUNTIFS(Department$2:Department$500, A2, From_Date$2:From_Date$500, ">=2023-02-01", To_Date$2:To_Date$500, "<=2023-03-01", Status$2:Status$500, "Approved")

Formula for Total Days per Department:
=SUMIFS(Days$2:Days$500, Department$2:Department$500, A2, From_Date$2:From_Date$500, ">=2023-02-01", To_Date$2:To_Date$500, "<=2023-03-01", Status$2:Status$500, "Approved")

Formula for Avg Leaves/Day:
=SUMPRODUCT(
  (From_Date$2:From_Date$500 <= TODAY()) * 
  (To_Date$2:To_Date$500 >= DATE(2023,2,1)) * 
  (Status$2:Status$500 = "Approved") * 
  (Department$2:Department$500 = A2)
) / 29  [29 days in Feb-Mar 2023 period]
```

#### 4.2 Department Risk Score
```
CSV Sources: Combined_All_Leave_Data.csv
Formula: =(Avg_Leaves_Per_Day * 0.50) + (Unplanned_Leaves * 0.30) + (Cost_Centres_Affected * 0.20)

Example for a Department:
=((D2 * 0.50) + (E2 * 0.30) + (F2 * 0.20))

Where:
D2 = Average employees on leave per day in department (from Combined_All_Leave_Data)
E2 = Count of unplanned leave requests (Leave_Type<>"Planned" from Combined_All_Leave_Data)
F2 = Number of distinct cost centres affected (SUMPRODUCT UNIQUE from Cost_Centre column)
```

#### 4.3 Department vs Company Average
```
CSV Source: Combined_All_Leave_Data.csv

Company Average Daily Leaves:
=AVERAGE(Daily_Leave_Count_Column)  [from Daily Aggregation tab]

Department Variance:
=D2 - SUM(D$2:D$30) / COUNTA(D$2:D$30)

Risk Level:
=IF(ABS(D2 - Department_Avg) > (Company_Avg * 0.2), "HIGH", 
   IF(ABS(D2 - Department_Avg) > (Company_Avg * 0.1), "MEDIUM", "LOW"))
```

---

## 5. Calendar Features Tab

### Time-Based Calculations for Feb-Mar 2023

**CSV Source: None (calculated directly from Date column)**
**Related: Holiday_Calendar.csv (for holiday indicators)**

#### 5.1 Date Component Breakdown
| Date | Day of Week | Week Number | Is Month Start | Is Month End | Is Weekend | Days Since Period Start |
|------|------------|------------|----------------|--------------|-----------|------------------------|
| 2023-02-01 | =WEEKDAY(A2) | =WEEKNUM(A2) | =IF(DAY(A2)=1,1,0) | =IF(DAY(A2)=DAY(EOMONTH(A2,0)),1,0) | =IF(OR(WEEKDAY(A2)=1,WEEKDAY(A2)=7),1,0) | =A2-MIN($A$2:$A$500) |

**Note:** All formulas in this section do NOT require CSV data; they calculate directly from date values

#### 5.2 Day of Week Name
```
Formula: =TEXT(A2, "DDD")
Values: Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday
CSV Source: None (date-based calculation)
```

#### 5.3 Week of Year
```
Formula: =WEEKNUM(A2, 21)
Purpose: ISO week numbering (weeks start Monday)
Range for Feb-Mar 2023: Week 5-9
CSV Source: None (date-based calculation)
```

#### 5.4 Month Indicators
```
Is Month Start:
Formula: =IF(DAY(A2)=1, 1, 0)
CSV Source: None

Is Month End:
Formula: =IF(DAY(A2)=DAY(EOMONTH(A2,0)), 1, 0)
CSV Source: None
```

#### 5.5 Weekend Indicator
```
Formula: =IF(OR(WEEKDAY(A2)=1, WEEKDAY(A2)=7), 1, 0)
Purpose: 1 for Saturday/Sunday, 0 for weekdays
CSV Source: None (date-based calculation)
```

#### 5.6 Circular Encoding for Seasonality

**Month Sin (Cyclical Month):**
```
Formula: =SIN(2*PI()*MONTH(A2)/12)
Purpose: Encodes month seasonality as continuous variable
Range: -1 to 1
CSV Source: None
```

**Month Cos (Cyclical Month):**
```
Formula: =COS(2*PI()*MONTH(A2)/12)
Purpose: Complements sin encoding for circular month representation
Range: -1 to 1
CSV Source: None
```

**Week Sin (Cyclical Week):**
```
Formula: =SIN(2*PI()*WEEKNUM(A2,21)/52)
Purpose: Encodes week seasonality
Range: -1 to 1
CSV Source: None
```

**Day Sin (Cyclical Day of Week):**
```
Formula: =SIN(2*PI()*(WEEKDAY(A2)-1)/7)
Purpose: Encodes day-of-week seasonality
Range: -1 to 1
CSV Source: None
```

---

## 6. Forecasting Metrics Tab

### Forecast Performance for Feb-Mar 2023 Period

**CSV Sources: Combined_All_Leave_Data.csv (for Actual) + Forecast_Results_[DateRange].csv (for Predictions)**

#### 6.1 Forecast vs Actual Comparison
| Date | Actual Leaves | Forecast | Forecast Error | Absolute Error | MAPE | 
|------|---------------|----------|----------------|----------------|------|

**Column Details:**
- **Actual Leaves**: From Daily Aggregation tab (derived from Combined_All_Leave_Data.csv)
- **Forecast**: From Forecast_Results_[DateRange].csv
- **Forecast Error**: =C2-B2 (Actual - Forecast)
- **Absolute Error**: =ABS(C2-B2)
- **MAPE**: =ABS((B2-C2)/B2)*100

#### 6.2 Mean Absolute Error (MAE)
```
CSV Source: Combined_All_Leave_Data.csv (actual) + Forecast_Results_[DateRange].csv (forecast)
Formula: =AVERAGE(ABS(Actual_Column - Forecast_Column))
Purpose: Average magnitude of errors regardless of direction
Example for Feb-Mar 2023:
=AVERAGE(ABS(Actual$2:Actual$30 - Forecast$2:Forecast$30))
```

#### 6.3 Root Mean Squared Error (RMSE)
```
CSV Source: Combined_All_Leave_Data.csv (actual) + Forecast_Results_[DateRange].csv (forecast)
Formula: =SQRT(AVERAGE((Actual_Column - Forecast_Column)^2))
Purpose: Penalizes larger errors more heavily
Example:
=SQRT(AVERAGE((Actual$2:Actual$30 - Forecast$2:Forecast$30)^2))
```

#### 6.4 Mean Absolute Percentage Error (MAPE)
```
CSV Source: Combined_All_Leave_Data.csv (actual) + Forecast_Results_[DateRange].csv (forecast)
Formula: =AVERAGE(ABS((Actual - Forecast) / Actual)) * 100
Purpose: Percentage error accounting for magnitude
Example:
=AVERAGE(ABS((Actual$2:Actual$30 - Forecast$2:Forecast$30) / Actual$2:Actual$30)) * 100

Handling Zero Values:
=IFERROR(ABS((Actual2 - Forecast2) / Actual2), IF(Actual2=0, IF(Forecast2=0, 0, 1), 0)) * 100
```

#### 6.5 Weighted Absolute Percentage Error (WAPE)
```
CSV Source: Combined_All_Leave_Data.csv (actual) + Forecast_Results_[DateRange].csv (forecast)
Formula: =(SUM(ABS(Actual - Forecast)) / SUM(ABS(Actual))) * 100
Purpose: PRIMARY METRIC - Weighted by actual volumes
Example:
=(SUM(ABS(Actual$2:Actual$30 - Forecast$2:Forecast$30)) / SUM(ABS(Actual$2:Actual$30))) * 100

For Feb-Mar 2023:
Numerator (Total Absolute Error): [Sum of daily errors from Forecast_Results]
Denominator (Total Actual Volume): [Sum of actual daily leaves from Combined_All_Leave_Data]
Result: X% WAPE
```

#### 6.6 R-Squared (R²)
```
CSV Source: Combined_All_Leave_Data.csv (actual) + Forecast_Results_[DateRange].csv (forecast)
Formula: =1 - (SUM((Actual - Forecast)^2) / SUM((Actual - Average(Actual))^2))
Purpose: Variance explanation (0-1 scale, higher is better)
Example:
=1 - (SUMPRODUCT((Actual$2:Actual$30 - Forecast$2:Forecast$30)^2) / 
      SUMPRODUCT((Actual$2:Actual$30 - AVERAGE(Actual$2:Actual$30))^2))
```

#### 6.7 Prediction Intervals (95% Confidence)
```
CSV Source: Combined_All_Leave_Data.csv (actual) + Forecast_Results_[DateRange].csv (forecast + residuals)

Lower Bound (5th Percentile):
Formula: =Forecast - PERCENTILE(Residuals, 0.05)

Upper Bound (95th Percentile):
Formula: =Forecast + PERCENTILE(Residuals, 0.95)

Where Residuals = Actual - Forecast from historical test data

Example for 2023-02-15:
Lower: =C15 - PERCENTILE(Residuals_Range, 0.05)
Upper: =C15 + PERCENTILE(Residuals_Range, 0.95)

Residuals Range: From Forecast_Results_[DateRange].csv, column "Residual"
```

---

## 7. Risk Analysis Tab

### Operational Risk Scoring (Feb-Mar 2023)

**CSV Source: Combined_All_Leave_Data.csv + Daily Aggregation output**

#### 7.1 Daily Risk Score
```
CSV Columns Used: From_Date, To_Date, Status, Leave_Type, Department

Formula: =(Daily_Leaves * 0.55) + (Unplanned_Leaves * 0.30) + (Departments_Affected * 0.15)

Example for 2023-02-15:
=($C15 * 0.55) + ($G15 * 0.30) + (CountUniqueDepartments * 0.15)

Where:
- $C15 = Daily leave count from Combined_All_Leave_Data (SUMPRODUCT formula)
- $G15 = Unplanned leave count (Leave_Type<>"Planned" from Combined_All_Leave_Data)
- CountUniqueDepartments = SUMPRODUCT to count unique departments with leaves

Breakdown:
- 55% weight on staffing impact (leaves)
- 30% weight on unpredictability (unplanned leaves)
- 15% weight on coordination complexity (department spread)
```

#### 7.2 Risk Level Classification
```
CSV Source: Calculated from Daily Risk Score (uses Combined_All_Leave_Data)

Formula: =IF(Risk_Score > 8, "HIGH", 
             IF(Risk_Score > 5, "MEDIUM", "LOW"))

Thresholds:
- HIGH RISK: Score > 8 (critical staffing/unplanned issues)
- MEDIUM RISK: Score 5-8 (manageable but needs monitoring)
- LOW RISK: Score < 5 (normal operations)
```

#### 7.3 Coverage Gap Analysis
```
CSV Source: Combined_All_Leave_Data.csv + Employee Master Final.csv

Formula: =(Available_Workforce - Required_Workforce) / Required_Workforce * 100

Available Workforce: =Total_Employees - Daily_Leaves
  (Where Total_Employees from Employee Master Final.csv)
  (Where Daily_Leaves from Combined_All_Leave_Data.csv)

Required Workforce: =Estimated_Workload (from staffing plan or configured value)

Example:
=((1000 - C15) / 900) * 100
Result: Positive = surplus capacity, Negative = understaffed
```

#### 7.4 Department Risk Variance
```
CSV Source: Combined_All_Leave_Data.csv (aggregated by Department)

Formula: =STDEV(Department_Risk_Scores)
Purpose: Identifies consistency in risk levels across departments
High variance = uneven risk distribution requiring intervention

Calculation: =STDEV(F2:F15)  [where F column contains Department Risk Scores]
```

#### 7.5 Cost Centre Analysis
```
CSV Source: Combined_All_Leave_Data.csv

Total Cost Centres Affected:
=SUMPRODUCT((From_Date$2:From_Date$500<=A2)*(To_Date$2:To_Date$500>=A2)*(Status$2:Status$500="Approved")/
            COUNTIFS(Cost_Centre$2:Cost_Centre$500,Cost_Centre$2:Cost_Centre$500))

Cost Centre with Highest Leave Rate:
=INDEX(Cost_Centre, MATCH(MAX(Cost_Centre_Leave_Count), Cost_Centre_Leave_Count, 0))

Where Cost_Centre_Leave_Count = SUMPRODUCT for each cost centre
```

#### 7.6 Trend Analysis
```
CSV Source: Combined_All_Leave_Data.csv (multiple periods)

Leave Count Trend (vs Previous Period):
=((Current_Avg - Previous_Avg) / Previous_Avg) * 100

Current_Avg (Feb-Mar 2023): 
=AVERAGE(Daily_Leaves_Feb_Mar)  [from Daily Aggregation using Combined_All_Leave_Data]

Previous_Avg (Jan 2023): 
=AVERAGE(Daily_Leaves_January)  [from previous month's Daily Aggregation]

Interpretation:
Positive % = Increase in leaves (potential risk increase)
Negative % = Decrease in leaves (improving situation)
```

---

## Summary of Key Calculations

### Most Critical Formulas for Feb-Mar 2023:

1. **Daily Unique Employees on Leave** (Primary Target Variable)
```
CSV Source: Combined_All_Leave_Data.csv
Columns: From_Date, To_Date, Status, EmpNo
Formula: =SUMPRODUCT((From_Date<=Today)*(To_Date>=Today)*(Status="Approved"))
```

2. **Daily Breakdown by Leave Type**
```
CSV Source: Combined_All_Leave_Data.csv
Columns: From_Date, To_Date, Status, Leave_Type
Casual: SUMPRODUCT(conditions + Leave_Type="Casual")
Sick: SUMPRODUCT(conditions + Leave_Type="Sick")
Planned: SUMPRODUCT(conditions + Leave_Type="Planned")
```

3. **Forecast Quality (WAPE)**
```
CSV Sources: Combined_All_Leave_Data.csv (Actual) + Forecast_Results_[DateRange].csv (Forecast)
Formula: =SUM(ABS(Actual-Forecast)) / SUM(ABS(Actual)) * 100
```

4. **Risk Scoring**
```
CSV Source: Combined_All_Leave_Data.csv + Daily Aggregation
Formula: =(Leaves*0.55) + (Unplanned*0.30) + (Departments*0.15)
```

5. **Rolling Averages**
```
CSV Source: Combined_All_Leave_Data.csv (indirect, via Daily Aggregation)
7-Day: =AVERAGE(OFFSET(CurrentRow, -6, 0, 7, 1))
30-Day: =AVERAGE(OFFSET(CurrentRow, -29, 0, 30, 1))
```

---

## Data Source References

### Primary CSVs Used:
1. **Combined_All_Leave_Data.csv**
   - Contains: Leave transaction records with dates, types, departments, employees
   - Key Columns: EmpNo, From_Date, To_Date, Days, Leave_Type, Department, Location, Cost_Centre, Status, Approved_By

2. **Employee Master Final.csv**
   - Contains: Employee master data
   - Key Columns: EmpNo, Employee_Name, Department, Cost_Centre, Location, Designation

3. **Holiday_Calendar.csv** (or reference)
   - Contains: Indian public holidays for 2023
   - Key Columns: Holiday_Date, Holiday_Name

### Generated Output CSVs:
4. **Daily_Aggregation_[DateRange].csv**
   - Generated from Combined_All_Leave_Data.csv
   - Contains: Daily leave counts, rolling averages, calendar features

5. **Forecast_Results_[DateRange].csv**
   - Contains: Predictions, actual values, residuals, confidence intervals

6. **Department_Risk_Analysis_[DateRange].csv**
   - Contains: Department-level risk scores and metrics

### Date Range: 
- **Analysis Period**: February 1, 2023 to March 1, 2023 (29 days)
- **Status Filter**: Only "Approved" leave records included
- **Calculation Period**: All formulas use 2023-02-01 to 2023-03-01 date boundaries

---

## Notes

- All dates in formulas use format: DATE(2023, 2, 1) or "2023-02-01"
- SUMPRODUCT is used instead of array formulas for Excel compatibility
- Empty cells treated as 0 in calculations
- Department and Cost Centre matching is case-sensitive
- Leave Type values: "Casual", "Sick", "Planned", "Other"
- Status filter: Only "Approved" records counted (Pending/Rejected excluded)
- CSV file paths assume files are in the same directory as the Excel workbook
- All text-based matching (Department, Leave_Type, etc.) is case-sensitive
- Numeric columns should be formatted as numbers, date columns as date format

---

*Last Updated: April 26, 2026*
*Document Author: OptiShift Intelligence System*

