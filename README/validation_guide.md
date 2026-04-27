# OptiShift Intelligence — Complete Validation Guide

> **Who this is for:** A non-technical person who provided the CSV and wants to verify every number on every dashboard page using Excel. Every metric shows exactly which CSV columns are used and the Excel formula to reproduce it.

---

## 📄 Your Data File

**File:** `Data/Combined_All_Leave_Data.csv`

### Actual data facts (pulled directly from your CSV)

| Fact | Value |
|------|-------|
| Total rows in CSV | **237,623** |
| Approved rows (only these count) | **235,925** |
| Pending rows (ignored everywhere) | **1,698** |
| Unique employees | **1,965** |
| Cost Centres | **6** |
| Departments | **13** |
| Date range | Jan 2023 → Dec 2025 |
| Location | Pune only |

### Every column — what it means and example values

| Column | What it holds | Example |
|--------|--------------|---------|
| `EmpNo` | Unique employee number | `40051088` |
| `Name` | Employee full name | `Mangash Jayawant Jaunjal` |
| `Cost Centre` | Shop/unit (6 values — see below) | `Assembly shop Production` |
| `Business Area` | Broad division | `Production & Logistics` |
| `Department` | Sub-division (13 values) | `Car Production Pune` |
| `Location` | City — all Pune | `Pune` |
| `Sub Group Category` | Employee grade | `White collar` / `Randstad` |
| `Work Contract External` | Contract type | `WC- Direct` / `WC - Indirect` |
| `Leave Type` | Category of leave | `Earned/Privilege Leave` |
| `From Date` | Leave start date (dd-mm-yyyy) | `27-11-2023` |
| `To Date` | Leave end date (dd-mm-yyyy) | `02-12-2023` |
| `Days` | Self-reported working days (**not used** for counting) | `6.0` |
| `Applied On` | When employee submitted the request | `17-04-2023 18:56:49` |
| `Approved On` | When manager approved | `30-11-2023 15:25:19` |
| `Delay` | Days between Applied On and Approved On | `227.0` |
| `Leave Reason` | Free text entered by employee | `Personal Work` |
| `Type` | **Planned** or **Un-Planned** | `Planned` |
| `Status` | **Approved** or Pending | `Approved` |
| `Approved By` | Manager who approved | `Sunil Bharat Sadegaonkar (40030824)` |

---

## 🗂️ Reference Data: Cost Centres and Their Departments

| Cost Centre | Departments under it |
|-------------|---------------------|
| **Assembly shop Production** | Car Production Pune, Car Production Aurangabad, Components Region India, Quality Management, Integ Verif Valid Complet Car, Logistics Region India, Management Care, HR Planning, HR Operations |
| **Body shop Production** | Car Production Pune, Components Region India, Quality Management, Integ Verif Valid Complet Car, Launch Management, Production Services, Management Care, HR Planning, HR Operations |
| **Finish Center** | Car Production Pune, Components Region India, Quality Management, Integ Verif Valid Complet Car, Management Care, HR Planning |
| **Paint shop Production** | Car Production Pune, Components Region India, Quality Management, Integ Verif Valid Complet Car, Management Care, HR Planning, VW Passenger Cars, HR Operations |
| **QM Production PUN** | Car Production Pune, Components Region India, Quality Management, Logistics Region India, Management Care, Production Planning (PP), Production Services, HR Planning |
| **Technical Services PUN 1** | Car Production Pune, Components Region India, Quality Management, Management Care, Production Planning (PP), HR Planning |

---

## 📊 Leave Types in Your Data

| Leave Type | Approved Applications |
|-----------|-----------------------|
| Special Leave [Not Call ON Duty] | 132,057 |
| Sick Leave | 33,253 |
| Casual Leave | 30,136 |
| Earned/Privilege Leave | 21,612 |
| Comp-Off | 19,638 |
| Paternity Leave | 304 |
| Others | 582 |

**Excel formula to count a specific leave type:**
```excel
=COUNTIFS(Status_col, "Approved", LeaveType_col, "Sick Leave")
```

---

## 🔑 Rule 1 — Only Approved Rows Are Used

Every calculation ignores rows where `Status ≠ "Approved"`.

**Excel check:**
```excel
=COUNTIF(Status_col, "Approved")
```
Expected: **235,925**

---

## 🔄 Rule 2 — One CSV Row Becomes Multiple Daily Rows

This is the most critical concept for validation.

**Example:**
```
EmpNo: 40037184  |  From Date: 04-12-2023  |  To Date: 09-12-2023
```
The system generates **6 rows** — one for each calendar day Dec 4 through Dec 9.

**Excel: count calendar days in one leave row:**
```excel
=(DATEVALUE(ToDate) - DATEVALUE(FromDate)) + 1
```

> ⚠️ The `Days` column in the CSV = **working days** (self-reported). The dashboard counts **calendar days** (including weekends). These will differ for leaves spanning a weekend.

---

---

## 📈 Page 1 — Forecasting

### CSV columns used for training
`EmpNo`, `From Date`, `To Date`, `Status`, `Department`, `Cost Centre`, `Leave Type`, `Type`  
+ Employee Master: `D.O.J` (Date of Joining), `D.O.L` (Date of Leaving)

### Model Evaluation Table

| Metric | Value | Plain meaning | How to sanity-check |
|--------|-------|---------------|---------------------|
| **MAE** | 7.99 | Average daily prediction error = ~8 employees | Filter CSV to any 30-day period → count employees on leave each day → compare to model predictions |
| **RMSE** | 14.71 | Large-error penalty metric → ~15 employees off on worst days | — |
| **R²** | 0.998 | Model explains 99.8% of variation | A value near 1.0 means the line in "Holdout Chart" closely follows actual data |
| **WAPE** | 3.38% | Primary metric: total error ÷ total actual leaves | — |

### Workforce Planner — CSV columns + formula

**CSV used:** None directly — uses sidebar number inputs + model prediction.

| Field on screen | Formula | Excel equivalent |
|-----------------|---------|-----------------|
| Total Expected Absent | Predicted Leave + Known Absences (sidebar) | `=B2 + C2` |
| Projected Available | Total Workforce − Total Expected Absent | `=D2 - B2 - C2` |
| Coverage Gap | max(Required Present − Projected Available, 0) | `=MAX(E2 - F2, 0)` |
| Total Staff Needed | Required Present + Total Expected Absent | `=E2 + B2 + C2` |
| Additional Headcount Needed | max(Total Staff Needed − Total Workforce, 0) | `=MAX(G2 - D2, 0)` |

---

## 🧭 Page 2 — Executive Intelligence

### CSV columns used
`EmpNo`, `From Date`, `To Date`, `Status`, `Type`, `Leave Type`, `Cost Centre`, `Department`

### How every metric is calculated from CSV

| Metric | CSV columns | Calculation | Excel formula |
|--------|------------|-------------|---------------|
| **Employees On Leave** on date X | `EmpNo`, `From Date`, `To Date`, `Status` | Count unique EmpNo where Status=Approved AND FromDate≤X AND ToDate≥X | Filter rows → `=SUMPRODUCT(1/COUNTIF(EmpNo_range, EmpNo_range))` |
| **Staffing Relevant Employees** | Same + `Leave Type` | Same as above, but **exclude** `Leave Type` = "Special Leave [Not Call ON Duty]" or "Comp-Off" | Add filter: `Leave Type <> "Special Leave..."` |
| **Unplanned Days** | `Type`, `From Date`, `To Date` | Count expanded daily rows where `Type = "Un-Planned"` | `=COUNTIFS(Status,"Approved", Type,"Un-Planned", FromDate,"<="&X, ToDate,">="&X)` |
| **Unplanned Share %** | `Type` | Unplanned Days ÷ Total Days × 100 | `=Unplanned/Total*100` |
| **Cost Centres Affected** | `Cost Centre` | Distinct Cost Centre values in filtered rows for date X | Pivot table: count distinct Cost Centre |
| **Departments Affected** | `Department` | Distinct Department values in filtered rows for date X | Pivot table: count distinct Department |

### Step-by-step Excel validation for date 15-Jan-2024

```
1. Open CSV → enable AutoFilter
2. Filter: Status = "Approved"
3. Filter: From Date <= 15/01/2024
4. Filter: To Date >= 15/01/2024
5. Copy visible rows to new sheet
6. Count unique EmpNo:
   =SUMPRODUCT(1/COUNTIF(A2:A500, A2:A500))   ← A = EmpNo column
7. Result = Employees On Leave on 15-Jan-2024
```

---

## 🔵 Page 3 — Special Leave & Comp-Off

### CSV columns used
`Leave Type`, `Status`, `EmpNo`, `From Date`, `To Date`, `Department`

### Which rows qualify
Only rows where `Leave Type` is exactly:
- `Special Leave [Not Call ON Duty]` → 132,057 applications
- `Comp-Off` → 19,638 applications

### Calculations + Excel formulas

| Metric | CSV columns | Excel formula |
|--------|------------|---------------|
| Total Special Leave applications | `Leave Type`, `Status` | `=COUNTIFS(Status,"Approved",LeaveType,"Special Leave [Not Call ON Duty]")+COUNTIFS(Status,"Approved",LeaveType,"Comp-Off")` |
| Total calendar leave days | `Leave Type`, `From Date`, `To Date`, `Status` | `=SUMPRODUCT((Status="Approved")*((LeaveType="Special Leave [Not Call ON Duty]")+(LeaveType="Comp-Off"))*(ToDate-FromDate+1))` |
| Unique employees | `EmpNo`, `Leave Type`, `Status` | Filter Status=Approved + Leave Type = Special/Comp → `=SUMPRODUCT(1/COUNTIF(EmpNo_range, EmpNo_range))` |
| By Department | `Department`, `Leave Type`, `Status` | Insert Pivot Table → Rows: Department, Values: Count of EmpNo, Filter: Status=Approved + LeaveType=Special/Comp |

---

## 🏭 Page 4 — Cost Centre Analysis

### CSV columns used
`Cost Centre`, `EmpNo`, `From Date`, `To Date`, `Status`, `Type`, `Department`

### Your 6 Cost Centres (actual names from CSV)
1. `Assembly shop Production`
2. `Body shop Production`
3. `Finish Center`
4. `Paint shop Production`
5. `QM Production PUN`
6. `Technical Services PUN 1`

### Calculations + Excel formulas

| Metric | CSV columns | Excel formula |
|--------|------------|---------------|
| **Employees on Leave** (CC, month) | `Cost Centre`, `EmpNo`, `From Date`, `To Date`, `Status` | Filter CC + Approved + date overlap → `=SUMPRODUCT(1/COUNTIF(EmpNo_range,EmpNo_range))` |
| **Total Leave Days** (CC) | `Cost Centre`, `From Date`, `To Date`, `Status` | `=SUMPRODUCT((Status="Approved")*(CostCentre="Assembly shop Production")*(ToDate-FromDate+1))` |
| **Risk Score %** | `Cost Centre`, `Type`, `Status` | `=COUNTIFS(Status,"Approved",CC,"Assembly shop Production",Type,"Un-Planned")/COUNTIFS(Status,"Approved",CC,"Assembly shop Production")*100` |

### Validation example: Assembly shop Production, January 2024

```excel
Step 1: Filter Status = Approved
Step 2: Filter Cost Centre = "Assembly shop Production"
Step 3: Filter From Date <= 31/01/2024
Step 4: Filter To Date >= 01/01/2024
Step 5: Count unique EmpNo in result
        =SUMPRODUCT(1/COUNTIF(A2:A300, A2:A300))
→ This = "Employees on Leave in Jan 2024 for Assembly shop Production"
```

---

## 📊 Page 5 — Planned vs Unplanned

### CSV columns used
`Type`, `Status`, `EmpNo`, `From Date`, `To Date`, `Cost Centre`, `Department`

### Actual values from your CSV
| Type value in CSV | Count |
|-------------------|-------|
| `Un-Planned` | 205,137 (86%) |
| `Planned` | 32,486 (14%) |

> ⚠️ "Un-Planned" = the `Type` column literally says `"Un-Planned"`. It does **not** mean unauthorised. These are still Approved leaves applied close to or on the leave date.

### Calculations + Excel formulas

| Metric | CSV columns | Excel formula |
|--------|------------|---------------|
| **Planned applications** | `Type`, `Status` | `=COUNTIFS(Status_col,"Approved",Type_col,"Planned")` |
| **Unplanned applications** | `Type`, `Status` | `=COUNTIFS(Status_col,"Approved",Type_col,"Un-Planned")` |
| **Planned calendar days** | `Type`, `From Date`, `To Date`, `Status` | `=SUMPRODUCT((Status="Approved")*(Type="Planned")*(ToDate-FromDate+1))` |
| **Unplanned calendar days** | `Type`, `From Date`, `To Date`, `Status` | `=SUMPRODUCT((Status="Approved")*(Type="Un-Planned")*(ToDate-FromDate+1))` |
| **Unplanned %** | `Type`, `Status` | `=COUNTIFS(Status,"Approved",Type,"Un-Planned")/COUNTIF(Status,"Approved")*100` |
| **Planned unique employees** | `EmpNo`, `Type`, `Status` | Filter Type=Planned + Approved → `=SUMPRODUCT(1/COUNTIF(EmpNo_range,EmpNo_range))` |
| **Unplanned unique employees** | `EmpNo`, `Type`, `Status` | Filter Type=Un-Planned + Approved → `=SUMPRODUCT(1/COUNTIF(EmpNo_range,EmpNo_range))` |

---

## 🔍 Page 6 — Leave Reason & Prediction

### CSV columns used
`Leave Reason`, `Status`, `EmpNo`, `From Date`

### Top Leave Reasons (actual from your CSV)
| Leave Reason (exact text in CSV) | Count |
|----------------------------------|-------|
| `External Import` | 134,081 |
| `Personal Work` | 47,402 |
| `Sickness` | 32,216 |
| `Posted by the system because of Set Off CO` | 11,521 |
| `Relative/Family Death` | 1,324 |
| `PERSONAL WORK` | 834 *(same as Personal Work — different capitalisation)* |

> The `Leave Reason` column is free text. "Personal Work", "PERSONAL WORK", "personal work" are all treated as separate values — the dashboard shows them as-is without grouping.

### Calculations + Excel formulas

| Metric | CSV columns | Excel formula |
|--------|------------|---------------|
| Top reasons | `Leave Reason`, `Status` | Pivot Table → Rows: Leave Reason, Values: Count of Rows, Filter: Status=Approved → Sort descending |
| Count of specific reason | `Leave Reason`, `Status` | `=COUNTIFS(Status_col,"Approved",LeaveReason_col,"Personal Work")` |
| Reason by month | `Leave Reason`, `From Date`, `Status` | Pivot Table → Rows: Month(From Date), Columns: Leave Reason, Values: Count |

---

## 📈 Page 7 — Daily CC Leave (Main Analytics Tab)

### CSV columns used
`Cost Centre`, `Department`, `EmpNo`, `From Date`, `To Date`, `Leave Type`, `Type`, `Status`

### Slicer → CSV Column Mapping

| Slicer on Dashboard | CSV Column | Filter logic |
|--------------------|-----------|--------------|
| From / To Date | `From Date` + `To Date` (expanded) | Keep rows where expanded day falls in selected range |
| Year | `From Date` | `YEAR(From Date)` in selected years |
| Granularity | — | Groups result into Daily/Weekly/Monthly buckets |
| Leave Type | `Leave Type` | Rows where `Leave Type` is in selected list |
| Cost Centre | `Cost Centre` | Rows where `Cost Centre` is in selected list |
| Department | `Department` | Only shows depts belonging to selected CC (cascading) |
| Planned / Unplanned | `Type` | Rows where `Type` is in selected list |
| Compare vs Last Year | — | Toggle — loads prior-year data with same filters |

### KPI Calculations

| KPI | CSV columns | Calculation | Excel formula |
|-----|------------|-------------|---------------|
| **Total Leave Days** | `EmpNo`, `From Date`, `To Date`, `Status` | Count of expanded daily rows after all filters | `=SUMPRODUCT((Status="Approved")*(YEAR(FromDate)=2025)*(ToDate-FromDate+1))` |
| **Cost Centres** | `Cost Centre` | Distinct Cost Centre values in filtered result | Pivot table → count distinct Cost Centre |
| **Employees on Leave** | `EmpNo` | Distinct EmpNo in filtered result | `=SUMPRODUCT(1/COUNTIF(EmpNo_filtered, EmpNo_filtered))` |
| **Avg Days / Employee** | `EmpNo`, `From Date`, `To Date` | Total Leave Days ÷ Employees on Leave | `=TotalLeaveDays / UniqueEmployees` |

### Cost Centre Chart — how the bar height is calculated

**Question: "How many employees were on leave in Assembly shop Production in March 2025?"**

```
CSV logic:
  Take all rows where:
    Status = "Approved"
    Cost Centre = "Assembly shop Production"
    From Date <= 31-Mar-2025
    To Date >= 01-Mar-2025
  → Expand each row to daily rows
  → For each day in March 2025, count unique EmpNo
  → Sum those daily unique counts = bar height

Excel shortcut (gives employees who had ANY leave in March 2025 for that CC):
  Step 1: Filter Status=Approved, CC="Assembly shop Production",
          From Date <= 31/03/2025, To Date >= 01/03/2025
  Step 2: =SUMPRODUCT(1/COUNTIF(EmpNo_range, EmpNo_range))
```

### Department Chart — how the bar height is calculated

Same logic as Cost Centre chart but grouped by `Department` instead of `Cost Centre`.

**Example: Car Production Pune, March 2025:**
```excel
Step 1: Filter Status=Approved, Department="Car Production Pune",
        From Date <= 31/03/2025, To Date >= 01/03/2025
Step 2: =SUMPRODUCT(1/COUNTIF(EmpNo_range, EmpNo_range))
```

### Department Summary Table columns

| Column | CSV column | Calculation | Excel |
|--------|-----------|-------------|-------|
| Department | `Department` | Group by | — |
| Total_Leave_Days | `From Date`, `To Date`, `Status` | `SUM(ToDate - FromDate + 1)` per dept | `=SUMPRODUCT((Dept=D)*(Status="Approved")*(ToDate-FromDate+1))` |
| Unique_Employees | `EmpNo` | Distinct EmpNo per dept | Filter dept → `=SUMPRODUCT(1/COUNTIF(...))` |
| % of Total | `EmpNo` | Dept employees ÷ all employees × 100 | `=DeptEmp / TotalEmp * 100` |

### Planned vs Unplanned Bifurcation

| KPI | CSV columns | Excel formula |
|-----|------------|---------------|
| Planned Days | `Type`, `From Date`, `To Date`, `Status` | `=SUMPRODUCT((Status="Approved")*(Type="Planned")*(ToDate-FromDate+1))` |
| Unplanned Days | `Type`, `From Date`, `To Date`, `Status` | `=SUMPRODUCT((Status="Approved")*(Type="Un-Planned")*(ToDate-FromDate+1))` |
| Unplanned % | `Type`, `Status` | `=UnplannedDays/(PlannedDays+UnplannedDays)*100` |
| Planned Employees | `EmpNo`, `Type`, `Status` | Filter Type=Planned → distinct EmpNo |
| Unplanned Employees | `EmpNo`, `Type`, `Status` | Filter Type=Un-Planned → distinct EmpNo |

### Year-over-Year Comparison

**How it works now:** Each selected year gets its **own separate line** in the chart.

Example — you select years 2024 and 2026:
- Line 1: **2026** (blue) — employees on leave Jan–Dec 2026
- Line 2: **2024** (blue) — employees on leave Jan–Dec 2024
- Line 3: **2025** (orange) — prior year of 2026
- Line 4: **2023** (orange) — prior year of 2024

All lines share the same x-axis (Jan through Dec) so you can directly compare the same month across years.

| KPI Card | CSV columns | Calculation | Excel |
|----------|------------|-------------|-------|
| Current Period Leave Days | `From Date`, `To Date`, `Status` | Total calendar-day rows in selected date range | `=SUMPRODUCT((Status="Approved")*(FromDate>=StartDate)*(ToDate<=EndDate)*(ToDate-FromDate+1))` |
| Prior Year Leave Days | Same | Same for dates minus 1 year | Same formula with `StartDate-365`, `EndDate-365` |
| Delta (red/green arrow) | — | Current − Prior | `=Current - Prior` (red = more leave = worse for staffing) |
| Current Period Employees | `EmpNo`, `From Date`, `To Date` | Unique EmpNo in current date range | Filter current range → distinct EmpNo |
| Prior Year Employees | `EmpNo` | Unique EmpNo in prior-year range | Filter prior range → distinct EmpNo |

**Department-Level YoY Table:**

| Column | Meaning | Excel |
|--------|---------|-------|
| Department | `Department` column | Group by |
| [Year e.g. 2025] | Unique employees on leave in that year | Filter year → distinct EmpNo per dept |
| [Prior year e.g. 2024] | Unique employees on leave in prior year | Filter prior year → distinct EmpNo per dept |
| Δ | Current year − Prior year | `=CurrentYear - PriorYear` (+ = more leave this year) |

---

## 🗓️ Page 8 — Indian Festival Calendar

### What comes from CSV vs built-in

| Section | Source |
|---------|--------|
| Festival names and dates | **Built-in** — from Indian calendar sources (Kalnirnay / gazette). NOT from your CSV. |
| Leave counts on festival dates | **Your CSV** — `EmpNo`, `From Date`, `To Date`, `Status` |

### Leave Correlation calculation

For each festival date shown:
```
CSV columns: EmpNo, From Date, To Date, Status

For festival date F:
  Filter: Status=Approved, From Date <= F, To Date >= F
  Count unique EmpNo = "Employees on Leave on this festival"

Excel:
  Filter From Date <= [FestivalDate] AND To Date >= [FestivalDate] AND Status=Approved
  =SUMPRODUCT(1/COUNTIF(EmpNo_range, EmpNo_range))
```

### Overall Org Average (baseline line)
```
For every calendar day D in the data range:
  Count unique employees on leave on D
Average of all those daily counts = Org Average

Excel approach: Create a helper column for each date → COUNTIFS per date → AVERAGE of all
```

### ±3 Day Spike Chart

For each festival date, 7 data points are computed:
- Day −3, −2, −1: days before the festival
- Day 0: the festival day itself
- Day +1, +2, +3: days after the festival

Each point = average employees on leave on that offset day **across all festivals in the filtered list**.

**Excel validation for one festival (e.g. Diwali 1-Nov-2024):**
```excel
Day 0 (festival):    Filter From<=01/11/2024, To>=01/11/2024 → unique EmpNo
Day -1 (31-Oct):     Filter From<=31/10/2024, To>=31/10/2024 → unique EmpNo
Day +1 (02-Nov):     Filter From<=02/11/2024, To>=02/11/2024 → unique EmpNo
```

---

## ✅ Master Validation Checklist

| What to verify | CSV column(s) | Excel formula | Expected result |
|----------------|--------------|---------------|-----------------|
| Total approved rows | `Status` | `=COUNTIF(Status_col,"Approved")` | **235,925** |
| Total unique employees | `EmpNo`, `Status` | Filter Approved → `=SUMPRODUCT(1/COUNTIF(EmpNo_col,EmpNo_col))` | **1,965** |
| Un-Planned applications | `Type`, `Status` | `=COUNTIFS(Status,"Approved",Type,"Un-Planned")` | **205,137** |
| Planned applications | `Type`, `Status` | `=COUNTIFS(Status,"Approved",Type,"Planned")` | **32,486** |
| Distinct cost centres | `Cost Centre`, `Status` | Filter Approved → Pivot on Cost Centre → count | **6** |
| Distinct departments | `Department`, `Status` | Filter Approved → Pivot on Department → count | **13** |
| Employees on leave on date X | `EmpNo`,`From Date`,`To Date`,`Status` | Filter From≤X, To≥X, Status=Approved → distinct EmpNo | Matches dashboard |
| Leave days for CC in month | `Cost Centre`,`From Date`,`To Date`,`Status` | `=SUMPRODUCT((CC=target)*(Status="Approved")*(ToDate-FromDate+1))` | Matches "Total Leave Days" |
| Special Leave total | `Leave Type`,`Status` | `=COUNTIFS(Status,"Approved",LeaveType,"Special Leave [Not Call ON Duty]")` | **132,057** |
| Comp-Off total | `Leave Type`,`Status` | `=COUNTIFS(Status,"Approved",LeaveType,"Comp-Off")` | **19,638** |
| Unplanned % overall | `Type`,`Status` | `=COUNTIFS(Status,"Approved",Type,"Un-Planned")/COUNTIF(Status,"Approved")*100` | **~86.95%** |

---

## ⚠️ Why Your Excel Number May Differ Slightly from Dashboard

| Reason | Explanation |
|--------|-------------|
| **`Days` column ≠ calendar days** | Dashboard uses `ToDate − FromDate + 1` (calendar days). CSV `Days` = working days only |
| **Counting rows vs unique employees** | `COUNTIF` on EmpNo counts rows. Dashboard always counts **unique** EmpNo (`SUMPRODUCT(1/COUNTIF(...))`) |
| **Weekends included** | Friday-to-Monday = 4 calendar days in dashboard, 2 working days in CSV `Days` column |
| **Duplicate removal** | System removes exact duplicates (EmpNo + Leave Type + From Date + To Date + Applied On) |
| **Pending excluded** | Any `Status ≠ "Approved"` is always ignored — always apply this filter in Excel |
| **Day expansion** | Dashboard counts per-day attendance. Simple row count without expansion undercounts multi-day leaves |
