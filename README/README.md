# Leave Management and Forecasting System

This repository contains a leave analytics and forecasting system for HR and workforce planning teams. It turns historical leave records into daily trends, business-area views, cost centre views, and forecast outputs that help planners understand what is happening, why it is happening, and how much confidence to place in the result.

## What this system is for

The system is designed for operational leave planning. A business user can answer questions such as:

- How many people are on leave on a given day or during a date range?
- Which cost centres or departments are driving the load?
- Is the leave mostly planned or unplanned?
- Which leave types or reasons are contributing most to absence?
- How much leave demand is expected in the next period?

The output is meant to support staffing, approvals, backup planning, and management visibility. It is not a payroll system and it does not replace HR master data governance.

## How the system works

The application reads approved leave records, cleans the data, enriches it with calendar features, and then produces dashboard views and forecast outputs.

The important point is that the charts and forecasts are only as good as the source data. The system filters to approved leave, normalizes dates, removes duplicates, fills missing text with "Unknown" where needed, and uses the business fields already present in the dataset to group the results.

At a high level:

1. Source leave records are loaded from CSV files.
2. Records are cleaned and standardized.
3. Leave periods are expanded into daily rows so every leave day is counted.
4. The model and dashboard aggregate those rows by date, department, leave type, and cost centre.
5. Forecasts combine historical patterns with calendar effects such as weekends, holidays, and month boundaries.

## Data sources

The main data file used by the dashboards is [Data/Combined_All_Leave_Data.csv](../Data/Combined_All_Leave_Data.csv). The system also reads employee master data from the employee master workbook referenced in the app.

Only approved leave is included in most views. If a record is not approved, it is excluded from the operational summaries. This is intentional because the dashboard is meant to show confirmed leave demand, not pending requests.

## Business fields and what they mean

These are the fields most relevant to users.

`EmpNo` is the employee identifier used to count unique employees on leave.

`Department` is the internal department used for operational grouping.

`Business Area` is a broader business grouping that can be used to see which line of business is affected.

`Cost Centre` is the financial and managerial grouping most useful for planning ownership. In practice, this is often the field leaders care about when they want to know which budget or operating unit is carrying the leave load.

`Leave Type` describes the type of leave taken, such as earned leave, sick leave, special leave, or comp-off.

`Type` usually indicates whether the leave is planned or unplanned. Planned leave is useful for advance coverage; unplanned leave is more disruptive and usually more important for immediate staffing decisions.

`Leave Reason` captures the reason text when available and is used for reason-based analysis.

`From Date` and `To Date` define the leave period. The application expands the interval into daily records so multi-day leave is counted on each affected day.

`Days` is the duration of the leave event.

`Status` is used as a filter. Approved leave is included in the operational views.

`SourceApp`, `Approved By`, `Location`, `Sub Department 1`, `Sub Department 2`, and `Sub Department 3` are supporting dimensions that can help explain the same leave activity from different perspectives.

## How to read the tabs

### Forecast tab

This is the main planning view. It shows the expected leave count for future dates. The forecast is built from historical daily leave patterns and calendar features such as day of week, month, holiday, long weekend, and post-holiday effects.

Use this tab when you want to know how much staffing pressure to expect on upcoming days. A forecast spike does not mean a problem by itself; it means the system sees a pattern in the data that resembles a higher leave load.

### Intelligence tab

This tab explains the model output and the important drivers behind it. It is the transparency layer for the forecast. Instead of only showing a number, it helps answer why the system expects that number.

Use this tab to understand which input features are influencing the prediction. For a business audience, that usually means day type, holidays, weekends, and the historical leave trend rather than the mathematics of the model itself.

### Special Leave and Comp-Off tab

This tab isolates leave types that are treated differently by the business logic. In this project, special leave and comp-off are tracked separately because they may not require the same operational response as regular absence.

Use this tab when you need to understand whether leave volume is being inflated by policy-specific leave categories rather than normal staffing-impacting leave.

### Cost Centre tab

This is one of the most important business tabs. It shows leave activity grouped by cost centre so leaders can see which operating unit is generating the highest load.

Use this tab to answer questions like:

- Which cost centre has the highest total leave days?
- Which cost centre has the highest number of unique employees on leave?
- Is leave mostly planned or unplanned inside a specific cost centre?

### Planned vs Unplanned tab

This tab separates leave into planned and unplanned categories. It is useful because the two types have different business impacts.

Planned leave can usually be covered ahead of time. Unplanned leave is often the more important signal for operational risk because it reduces predictability.

### Leave Reason tab

This tab summarizes leave by reason, leave type, cost centre, and planned/unplanned status. It is useful for spotting patterns such as recurring short-notice leave in a specific unit or a particular leave type being concentrated in one business area.

## How the results relate back to the data

The dashboard does not invent new business meaning. It calculates summaries from the underlying rows.

If a leave event runs from Monday to Wednesday, the system expands that event into three daily records. That is why the daily charts may show higher counts than the raw number of leave applications.

If a cost centre appears at the top of the chart, that means the approved leave rows associated with that cost centre have the highest total leave days or employee counts in the selected period.

If planned leave is high, that usually means employees are taking leave with notice. If unplanned leave is high, the business may need stronger coverage or exception management.

Forecast numbers are generated from historical patterns, not from manual estimates. The model uses the patterns already present in the data, along with calendar features, to project the next period.

## Why some rows are excluded

The app intentionally filters out some records to keep the dashboard trustworthy.

- Records with `Status` other than Approved are excluded from the main operational views.
- Duplicate leave rows are removed using employee/date/leave-type keys where possible.
- Missing text values are normalized to avoid broken group-by results.
- Invalid or incomplete date ranges are removed.

This is important because users should see the effective operational leave picture, not raw data entry noise.

## Forecast transparency

The model is not a black box in the business sense, even if the underlying algorithm is technical. The system exposes the main drivers that influence the forecast so users can see whether a spike is coming from:

- A weekday pattern such as Fridays or Mondays
- Holiday effects
- Long weekends
- Month start or month end behavior
- Recent leave history

This makes the forecast easier to trust and easier to challenge when business conditions change.

## Typical user workflow

1. Select the date range you want to inspect.
2. Review the overall daily leave trend.
3. Check whether the pattern is planned or unplanned.
4. Drill into cost centre, department, and leave type.
5. Use the forecast and intelligence tabs to plan the next period.
6. Compare the result with recent business events such as holidays, policy changes, or staffing changes.

## Practical interpretation guidance

- A high cost centre value means that the load is concentrated in that operating unit.
- A high unplanned share usually deserves priority because it is harder to absorb.
- A spike around a holiday or long weekend may be normal rather than anomalous.
- Leave type mix matters. A large number of comp-off or special leave records should be interpreted differently from ordinary absence.
- Forecast accuracy depends on stable behavior. If the organization recently changed policy, structure, or approval practice, the forecast may need retraining.

## Inputs and outputs

### Inputs

- Historical approved leave records
- Employee master data
- Calendar and holiday information

### Outputs

- Daily leave trend charts
- Cost centre summaries
- Planned vs unplanned breakdowns
- Special leave and comp-off analysis
- Leave reason analysis
- Forecast tables and charts
- Model artifacts in `artifacts/`

## Deployment and usage

Run the Streamlit application locally to view the dashboard in a browser. If you want a website-style documentation page, GitHub Pages can host a separate static documentation site built from this README or from a docs folder, but the application itself still runs as a Python dashboard.

If the goal is a user-facing handbook, this README can be published as the project home page or split later into a GitHub Pages documentation site with sections for overview, tab guide, field glossary, and FAQ.

## Recommended documentation structure for business users

If this repository is turned into a proper documentation site, the most useful pages would be:

- Overview
- How to use the dashboard
- Tab-by-tab guide
- Field glossary
- Forecast methodology
- Data quality rules
- Common business questions
- FAQ

## Notes for maintainers

- Keep the business glossary aligned with the actual columns in the input files.
- If a new cost centre, leave type, or approval status is introduced, update the README so users understand the new category.
- If the forecasting logic changes, describe the new assumptions in the forecast transparency section.
- If you publish to GitHub Pages, keep this README as the source of truth and generate the site from it.

62. **Network Bandwidth**: Limited bandwidth may affect large model artifact transfers and deployment speed.

63. **Knowledge Transfer**: Team must acquire skills in modern ML stack and operational deployment practices.

5. **Phase 5 (Week 8)**: Comprehensive testing, documentation finalization, and production deployment preparation.

6. **Post-Deployment**: Continuous monitoring, periodic retraining, and iterative improvements based on performance metrics.

7. **Milestone 1**: Successful completion of data pipeline and feature engineering (End of Week 4).

8. **Milestone 2**: Model selection and performance validation completed (End of Week 6).

9. **Milestone 3**: Dashboard deployment to production environment (End of Week 7).

10. **Milestone 4**: System validation, documentation, and operational readiness (End of Week 8).

#### 4.3.1 Timeline Chart

1. **Week 1**: Historical data collection from multiple organizational sources into unified repository.

2. **Week 2**: Data quality assessment, issue identification, and initial data cleaning protocols.

3. **Week 3**: Systematic feature engineering across temporal, organizational, and behavioral dimensions.

4. **Week 4**: Baseline model development with standard ML algorithms and performance evaluation.

5. **Week 5**: Advanced model experimentation with hyperparameter optimization and cross-validation.

6. **Week 6**: Comprehensive model benchmarking and best model selection based on evaluation metrics.

7. **Week 7**: Dashboard development, forecast generation, model persistence, and system integration testing.

8. **Week 8**: Comprehensive system testing, documentation, monitoring setup, and deployment readiness validation.

#### 4.3.2 Resource Allocation

1. **Data Engineer Resource**: 50% allocation for data pipeline, quality assurance, and infrastructure maintenance.

2. **ML Engineer Resource**: 40% allocation for model development, optimization, and performance monitoring.

3. **Full-Stack Developer Resource**: 30% allocation for dashboard development and web interface implementation.

4. **Data Scientist Resource**: 60% allocation for feature engineering, model experimentation, and analysis.

5. **DevOps Resource**: 20% allocation for deployment infrastructure, monitoring, and operational support.

6. **Total Team Size**: 3-4 FTE (Full-Time Equivalents) depending on organizational scale and requirements.

#### 4.3.3 Dependencies and Constraints

1. **Data Availability**: Historical leave data must be consolidated and accessible from all organizational sources.

2. **Infrastructure Access**: Cloud or on-premise infrastructure must be provisioned before development initiation.

3. **Stakeholder Availability**: HR stakeholders must participate in requirements gathering and validation activities.

4. **Regulatory Compliance**: Data handling must comply with organizational and legal data protection requirements.

5. **Integration Points**: System integration with existing HR systems requires coordination and API access.

6. **Hardware Constraints**: GPU resources limit deep learning model experimentation timelines.

7. **Network Bandwidth**: Limited bandwidth may affect large model artifact transfers and deployment speed.

8. **Knowledge Transfer Requirements**: Team must acquire skills in modern ML stack and operational deployment practices.
- Week 7: Dashboard integration and reporting.
- Week 8: Testing, review, and final documentation.

## 05 System Design

### 5.1 Proposed System Architecture/Block Diagram
Input leave data -> preprocessing pipeline -> feature engineering -> model training/evaluation -> forecast generation -> dashboard visualization -> reports/artifacts.

### 5.2 Mathematical Model
The forecasting model estimates leave demand as:
`y_hat = f(X)`
where `X` contains temporal, organizational, and leave-pattern features, and `f` is a trained ML model (e.g., XGBoost/Random Forest).

### 5.3 UML Diagrams

#### 5.3.1 Use Case Diagram
Actors: HR Analyst, Manager, System Admin. Use cases: upload data, run forecast, view insights, export reports.

#### 5.3.2 Activity Diagram
Flow: ingest data -> preprocess -> train/predict -> evaluate -> publish dashboard insights.

#### 5.3.3 Sequence Diagram
User triggers forecast request; backend loads artifacts and data; model generates predictions; dashboard renders outputs.

#### 5.3.4 Data Flow Diagram
Data flows from source files to processed dataset, into model pipeline, then to artifacts and visualization layers.

## 06 Project Implementation

### 6.1 Overview of Project Modules
- Data processing and cleaning.
- Feature engineering.
- Model training and evaluation.
- Forecast generation.
- Dashboard and visualization.
- Testing and quality checks.

### 6.2 Tools and Technologies Used
- Python
- pandas, NumPy, scikit-learn, XGBoost
- Streamlit and web dashboard components
- Jupyter Notebook for experimentation
- Git-based version control

### 6.3 Algorithm Details

#### 6.3.1 Algorithm 1: Data Cleaning and Validation Pipeline
Standardizes input schema, handles missing values, and filters invalid records.

#### 6.3.2 Algorithm 2: Feature Engineering and Aggregation
Builds temporal and behavior-driven features to improve prediction quality.

#### 6.3.3 Algorithm 3: Training and Validation Pipeline
Splits data, trains candidate models, validates using held-out sets, and stores metadata.

#### 6.3.4 Algorithm 4: Model Evaluation and Analysis
Computes forecast metrics, analyzes residuals, and compares model performance.

#### 6.3.5 Algorithm 5: Forecast and Visualization Pipeline
Generates forward-looking leave forecasts and publishes charts/reports for end users.

## 07 Software Testing

### 7.1 Type of Testing
- Unit testing for data and model components.
- Integration testing for end-to-end pipeline execution.
- Functional testing for dashboard behavior.

### 7.2 Test Conclusion
Testing confirms that core modules perform as expected for data ingestion, prediction generation, and visualization. Ongoing regression testing is recommended for new datasets and model updates.

## 08 Results

### 8.1 Traditional Machine Learning Model Results
Baseline and ensemble models were evaluated with standard metrics to quantify forecasting performance.

### 8.2 Optimized Forecasting Model Results
Tuned models (including XGBoost variants) delivered improved predictive accuracy and more stable forecasting behavior.

### 8.3 Outcomes
The project provides operationally useful leave forecasts, trend intelligence, and data-backed planning support for HR teams.

## 09 Conclusions

### 9.1 Conclusions
The system successfully transforms fragmented leave records into actionable forecasts and interactive insights.

### 9.2 Future Work
Future enhancements may include policy-aware forecasting, live database integration, advanced drift detection, and automated retraining schedules.

### 9.3 Applications
- Workforce planning
- Leave policy analytics
- Department-level staffing optimization
- Management reporting

## Appendix A: Details of Paper Publication, Details of Sponsorship Letter
To be added based on academic/organizational documentation status.

## Appendix B: Plagiarism Report of the Project Report
To be attached in final submission package.

## References
- Project source files and datasets in this repository.
- Internal documentation: `IMPLEMENTATION_SUMMARY.md`, `PROJECT_OBJECTIVES_AND_OUTPUTS.md`, `Dat_Cleaning.md`, `DASHBOARD_INTEGRATION.md`.
- Standard machine learning and software engineering references used during implementation.
