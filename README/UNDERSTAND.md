# Leave Dashboard - Easy Guide to Understand the Trends

This guide explains the dashboard in simple business language.

It is written for non-technical people who want to understand:

- what each tab is showing
- what each trend means
- what to worry about
- what looks normal
- what action to consider

This guide is based on:

- `streamlit_app.py`
- `End_to_End_ML_Lifecycle_Training.ipynb`

The easiest way to understand the dashboard is this:

The dashboard is trying to answer five questions:

1. How many people are on leave?
2. Is the leave level going up or down?
3. Where is the pressure coming from?
4. What may happen next?
5. Will we still have enough people to work safely?

---

## 1. Before reading any chart

There are only three things you need to remember.

### A. `Employees` means people

If a label says `Employees on Leave`, it means unique people.

Example:

- Ravi is on leave for 5 days
- Neha is on leave for 2 days

Employees on Leave = 2

### B. `Days` means total leave days

If a label says `Leave Days`, it means total daily leave volume.

Same example:

- Ravi = 5 leave days
- Neha = 2 leave days

Leave Days = 7

### C. `Predicted` means future estimate

If a label says `Predicted`, it is a future estimate made by the saved forecasting model.

If a label says `Actual`, it comes from real historical leave records.

---

## 2. What kind of trends are good and bad

This is the simplest way to read trends in the dashboard.

### Usually good trends

- leave is stable, not jumping suddenly
- planned leave is higher than unplanned leave
- no single cost centre is repeatedly spiking
- sick leave is not rising sharply
- forecast and actual lines stay close together
- coverage gap stays at zero

### Warning trends

- leave rises suddenly in a short time
- unplanned leave keeps increasing
- one cost centre keeps showing dark or high spikes
- comp-off keeps rising month after month
- forecast upper bound is much higher than normal
- projected available workforce falls near required workforce

### Serious warning trends

- staffing gap becomes positive
- one department or cost centre repeatedly carries most absences
- sick leave becomes a major growing share
- unplanned leave becomes normal instead of occasional
- forecast is unstable and hard to trust

---

## 3. What the dashboard does in simple words

The system reads approved leave records, cleans them, converts them into daily absence rows, and then:

- counts how many people were absent each day
- studies patterns by weekday, month, leave type, and cost centre
- uses a trained model to estimate future leave
- converts forecasted leave into staffing impact

Simple meaning:

It turns leave records into trend signals and planning signals.

---

## 4. Tab 1 - Forecasting

### What this tab is for

This tab helps answer:

- What may happen next?
- Can we trust the forecast?
- How many people may be absent?
- Will staffing still be okay?

### What the main numbers mean

### MAE

How many employees the forecast is usually off by.

Example:

If MAE is 8, the forecast is usually off by about 8 people.

### WAPE

How big the total forecast error is compared to the total real leave volume.

Simple reading:

- lower is better
- lower means the forecast is more dependable

### R2

How well the forecast follows the real pattern.

Simple reading:

- closer to 1 = better
- low value = weak pattern fit

### 90% error band

This is the normal planning buffer around the forecast.

Simple reading:

If the forecast says 80 and the error band is about 10, management should be ready for the real number to move around that range.

### Predicted leave

The expected number of employees on leave for the selected date.

### Upper bound leave

The more cautious higher estimate.

### Projected available

How many people may still be available after expected absences.

### Additional headcount needed

How many more people may be required if the current workforce is not enough.

### How to read the trends in this tab

### Graph: Actual vs Predicted Leave Count

What it shows:

- actual leave line
- predicted leave line
- simple baseline line

How to read the trend:

- if actual and predicted move together, the model is understanding the pattern
- if the predicted line misses sharp rises or falls, the model is weaker on sudden changes
- if the baseline is almost as good as the model, the model may not be adding enough value

What question it answers:

"Can I trust this forecast?"

What a manager should do:

- if the lines stay close, use the forecast with more confidence
- if they stay far apart, use larger safety buffers

### Graph: Top Forecast Drivers

What it shows:

The biggest factors influencing the forecast.

Common examples:

- recent leave pattern
- holidays
- long weekends
- weekday pattern
- month pattern

How to read the trend:

- if holiday features are strong, festival periods matter a lot
- if recent leave features are strong, recent behavior is heavily influencing future days

What question it answers:

"Why is the forecast moving the way it is?"

### Graph: Previous Year Actual vs Predicted

What it shows:

How well the model matched the last 12 months of historical pattern.

How to read the trend:

- if the lines stay close all year, the model is seasonally reliable
- if one month shows a big gap, that month is harder to predict

What question it answers:

"Are there certain months where the forecast becomes less reliable?"

### Graph: Next 30 Days Forecast

What it shows:

- the future forecast line
- the lower range
- the upper range

How to read the trend:

- rising line = expected leave pressure is increasing
- falling line = expected leave pressure is decreasing
- flat line = expected leave level is steady
- wide band = more uncertainty
- narrow band = more confidence

What question it answers:

"What is likely to happen over the next month?"

What a manager should do:

- use the middle line for normal planning
- use the upper band for cautious planning

### Graph: Forecast Window / Workforce Plan

What it shows:

- expected absences
- available workforce
- required workforce level

How to read the trend:

- if available stays above required, staffing looks safer
- if available touches or drops below required, action is needed

What question it answers:

"Will we still have enough people to run operations?"

### Graph: Why This Forecast

What it shows:

Which factors push the forecast up or down.

How to read the trend:

- positive contributors push leave forecast higher
- negative contributors push it lower

What question it answers:

"What is driving this particular forecast?"

---

## 5. Tab 2 - Executive Leave Intelligence

### What this tab is for

This tab shows where the business risk is right now.

It helps answer:

- how serious the absence pressure is
- how much of it affects real staffing
- which cost centre looks risky

### What the main numbers mean

### Today's Actual On Leave

How many people are truly on leave today.

### Week Average Leave

The normal average level for the selected period.

### Peak Day (Next 7)

The biggest leave day in the short period shown.

### Highest Risk Centre

The cost centre with the strongest combined risk signal.

### Staffing Relevant

This means absence that really affects staffing.

It excludes:

- Comp-Off
- Special Leave [Not Call ON Duty]

### Unplanned Days

Leave days that were not planned in advance.

### How to read the trends in this tab

### Graph: Daily Leave Intelligence Trend

What it shows:

- total employees on leave
- staffing-relevant employees on leave

How to read the trend:

- if both lines rise together, staffing pressure is truly increasing
- if total leave rises but staffing-relevant leave does not rise as much, some of the absence may be from special categories
- if the line keeps climbing, absence pressure is building

What question it answers:

"Is the real staffing pressure going up or staying manageable?"

### Graph: Highest Risk Cost Centres

What it shows:

Cost centres ranked by risk.

How to read the trend:

- the highest bar is the area needing attention first
- repeated appearance of the same cost centre is a strong warning sign

What question it answers:

"Which area of the business is under the most pressure?"

### Graph: Projected Availability vs Required Presence

What it shows:

- projected available workforce
- required workforce level

How to read the trend:

- if projected available stays above required, operations look safer
- if it drops below required, the business may face shortage

What question it answers:

"Will daily operations remain covered?"

---

## 6. Tab 3 - Special Leave & Comp-Off

### What this tab is for

This tab separates special categories so leaders do not confuse them with normal staffing pressure.

### What the main numbers mean

### Total Special Leave Days

Total leave days in the special leave category.

### Total Comp-Off Days

Total leave days in the comp-off category.

### Unique Employees

How many people are using those categories.

### How to read the trends in this tab

### Graph: Weekly Special Leave & Comp-Off

How to read the trend:

- repeated weekly spikes in comp-off may show overtime settlement behavior
- repeated weekly spikes in special leave may show recurring events or planned activities

What question it answers:

"Are these categories happening in regular bursts?"

### Graph: Monthly Special Leave & Comp-Off

How to read the trend:

- rising comp-off trend can suggest overtime pressure
- sudden jumps may suggest policy or event effects

What question it answers:

"Are these special categories growing over time?"

### Graph: Day-of-Week Pattern

How to read the trend:

- if one weekday is always high, that is a pattern, not random behavior

What question it answers:

"Do these categories happen on certain days more often?"

---

## 7. Tab 4 - Cost Centre Wise Leave Analysis

### What this tab is for

This tab shows where in the organization leave is concentrated.

### What the main numbers mean

### Total Leave Days

Total leave-day volume in the filtered view.

### Cost Centres

How many cost centres are included in the filtered view.

### Employees on Leave

How many unique people are absent in that filtered view.

### Avg Days per Employee

Average leave-day load per absent employee.

Simple reading:

- high value can mean fewer people taking longer leaves
- low value can mean many people taking short leaves

### How to read the trends in this tab

### Graph: Employee Distribution Across Cost Centres

How to read the trend:

- bigger share means that cost centre contributes more absent employees
- if one cost centre always dominates, it deserves closer attention

What question it answers:

"Which cost centre contributes the largest share of absence?"

### Graph: Employees on Leave per Cost Centre

How to read the trend:

- longest bar = highest absent employee count

What question it answers:

"Which cost centre ranks highest right now?"

### Graph: Treemap by Cost Centre and Leave Type

How to read the trend:

- bigger block = bigger problem area
- the split inside the block shows which leave types dominate

What question it answers:

"What kind of leave is driving the burden in each cost centre?"

### Graph: Single-Date Breakdown

How to read the trend:

- this is the exact day view
- it helps identify where the absent employees are coming from on one selected date

What question it answers:

"For this day, which cost centre is carrying the load?"

### Graph: Daily Employees on Leave per Cost Centre

How to read the trend:

- a sudden spike means a one-day pressure event
- repeated spikes on similar days suggest a pattern
- a slowly rising line suggests growing pressure

What question it answers:

"Which cost centre is showing unstable or rising absence?"

### Graph: Weekly Employee Count on Leave by Cost Centre

How to read the trend:

- helps smooth daily noise
- shows which cost centre has the largest weekly burden

What question it answers:

"Which cost centre is carrying the biggest weekly absence load?"

### Graph: Monthly Heatmap

How to read the trend:

- darker color means higher absence concentration
- repeated dark months suggest a seasonal or structural pattern

What question it answers:

"Which cost centres have recurring hot months?"

---

## 8. Tab 5 - Planned vs Unplanned Leave Dashboard

### What this tab is for

This tab shows predictability.

Planned leave is easier to manage.
Unplanned leave is more disruptive.

### What the main numbers mean

### Planned Days

Leave days known in advance.

### Unplanned Days

Leave days that happen without advance notice.

### Unplanned %

The share of total leave that is unplanned.

Simple reading:

- lower is healthier
- higher means more disruption

### Employees - Planned

People on planned leave.

### Employees - Unplanned

People on unplanned leave.

### How to read the trends in this tab

### Graph: Leave Days Split

How to read the trend:

- bigger planned share = easier workforce planning
- bigger unplanned share = lower predictability

What question it answers:

"Is leave mostly predictable or mostly surprise?"

### Graph: Employees on Leave by Leave Type

How to read the trend:

- if one leave type shows much more unplanned than planned, that category is disruptive

What question it answers:

"Which leave type creates the most surprise absence?"

### Graph: Total Employee Headcount by Leave Type

How to read the trend:

- bigger total bar = larger leave category overall
- large red or unplanned section = more disruption in that category

What question it answers:

"Which leave categories are biggest, and how much of them is unplanned?"

### Graph: Daily Employee Headcount

How to read the trend:

- high unplanned section on a day means that day is more difficult to manage

What question it answers:

"Which exact days were hit by surprise absence?"

### Graph: Weekly Employee Headcount

How to read the trend:

- if unplanned bars stay large week after week, unpredictability is becoming a pattern

What question it answers:

"Is surprise absence becoming a weekly issue?"

### Graph: Daily and Weekly Leave Days

How to read the trend:

- these show total lost workdays, not just people
- high leave-day totals can mean significant productivity loss even if headcount is not extreme

What question it answers:

"How much total work time is being lost?"

### Graph: Employees on Leave by Cost Centre

How to read the trend:

- if one cost centre has a large unplanned section, it is harder to plan for

What question it answers:

"Which cost centre is least predictable?"

### Graph: Day-of-Week Pattern

How to read the trend:

- if Monday is always high in unplanned leave, Monday is a risk day
- if Friday planned leave is high, long weekends may be shaping behavior

What question it answers:

"Are some weekdays repeatedly riskier than others?"

### Graph: Monthly Trend

How to read the trend:

- rising unplanned trend means the business is becoming harder to schedule

What question it answers:

"Is unpredictability getting better or worse over time?"

---

## 9. Tab 6 - Leave Reason & Prediction Context

### What this tab is for

This tab explains why leave is happening and what usually happens on similar dates.

### What the main numbers mean

### Leave Days by Reason

This means how many leave-day rows belong to a specific reason.

### Top Cost Centres in Context

These are the cost centres most often seen on similar historical dates.

### Top Leave Reasons in Context

These are the reasons most often seen on similar historical dates.

### How to read the trends in this tab

### Graph: Top 15 Leave Reasons

How to read the trend:

- the biggest bar is the strongest reason behind leave volume
- if sickness reasons dominate, health may be the issue
- if personal or event reasons dominate, that may be normal planned behavior

What question it answers:

"What is mainly causing leave right now?"

### Graph: Leave Type by Cost Centre

How to read the trend:

- shows which type of leave is creating pressure in each cost centre

What question it answers:

"What type of leave is affecting each business area?"

### Prediction Context tables

How to read them:

- they do not say what will definitely happen
- they show what usually happened on dates with the same month and weekday

What question they answer:

"What normally happens on dates like the one we are planning for?"

---

## 10. The easiest way to read the dashboard

If you want a quick, non-technical way to use the dashboard, read it in this order:

### Step 1. Look at Forecasting

Ask:

- what is the next expected leave level?
- is the forecast range wide or narrow?
- will staffing still be enough?

### Step 2. Look at Executive Intelligence

Ask:

- where is the risk?
- which cost centre looks stressed?
- is real staffing pressure growing?

### Step 3. Look at Cost Centre Analysis

Ask:

- which business area is carrying the most absence?
- is it one area or many?

### Step 4. Look at Planned vs Unplanned

Ask:

- is leave becoming less predictable?
- are surprise absences rising?

### Step 5. Look at Leave Reason

Ask:

- why is this happening?
- is it sickness, personal leave, events, or something else?

### Step 6. Look at Special Leave & Comp-Off

Ask:

- are special categories building up?
- are they creating a misleading picture if mixed with normal leave?

---

## 11. Final takeaway

Every tab tells part of the story:

- Forecasting tells you what may happen next
- Executive Intelligence tells you where the pressure is
- Cost Centre Analysis tells you where in the business the pressure sits
- Planned vs Unplanned tells you how predictable the pressure is
- Leave Reason tells you why the pressure is happening
- Special Leave & Comp-Off tells you whether special categories are influencing the picture

The dashboard becomes easy to understand when you read trends in simple words:

- rising = growing pressure
- falling = easing pressure
- repeated spikes = recurring pattern
- large unplanned share = disruption risk
- one cost centre dominating = concentrated local problem
- available workforce below required workforce = action needed
