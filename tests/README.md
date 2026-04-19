# Leave Management System - Comprehensive Test Suite

This folder contains a comprehensive test suite covering all 10 test cases (TC-01 through TC-10) for the Leave Management System with machine learning-based leave forecasting.

## Test Cases Overview

| Test ID | Description | Status | Location |
|---------|-------------|--------|----------|
| TC-01 | Load 500K leave records, verify schema | ✓ Implemented | [test_01_data_loading.py](test_01_data_loading.py) |
| TC-02 | Data cleaning removes duplicates | ✓ Implemented | [test_02_data_cleaning.py](test_02_data_cleaning.py) |
| TC-03 | Feature engineering produces 50 features | ✓ Implemented | [test_03_feature_engineering.py](test_03_feature_engineering.py) |
| TC-04 | XGBoost model trains in <5 min | ✓ Implemented | [test_04_model_training.py](test_04_model_training.py) |
| TC-05 | Forecast generates 60-day predictions | ✓ Implemented | [test_05_forecasting.py](test_05_forecasting.py) |
| TC-06 | Streamlit dashboard loads <5 seconds | ✓ Implemented | [test_06_07_dashboard.py](test_06_07_dashboard.py) |
| TC-07 | Date range filtering updates visualizations | ✓ Implemented | [test_06_07_dashboard.py](test_06_07_dashboard.py) |
| TC-08 | Model accuracy maintained (WAPE <15%) | ✓ Implemented | [test_08_model_accuracy.py](test_08_model_accuracy.py) |
| TC-09 | No data leakage in train/test split | ✓ Implemented | [test_09_data_leakage.py](test_09_data_leakage.py) |
| TC-10 | Confidence intervals calculated correctly | ✓ Implemented | [test_10_confidence_intervals.py](test_10_confidence_intervals.py) |

## Setup Instructions

### 1. Install Test Dependencies

```bash
# Navigate to the tests directory
cd tests

# Install required packages
pip install -r requirements-test.txt
```

### 2. Verify Project Structure

Ensure the following files exist in the parent directory:
- `streamlit_app.py` - Main application
- `retrain_model.py` - Model training script
- `Data/Combined_All_Leave_Data.csv` - Raw leave data (50K+)
- `Employee Master - Feb 2026 Team Member.xlsx` - Employee data
- `artifacts/` - Model artifacts folder

## Running Tests

### Run All Tests

```bash
# Run all tests with verbose output
pytest -v

# Run with coverage report
pytest -v --cov=.. --cov-report=html

# Run with specific markers
pytest -v -m "tc01 or tc02"
```

### Run Specific Test Cases

```bash
# TC-01: Data Loading
pytest test_01_data_loading.py -v

# TC-02: Data Cleaning
pytest test_02_data_cleaning.py -v

# TC-03: Feature Engineering
pytest test_03_feature_engineering.py -v

# TC-04: Model Training
pytest test_04_model_training.py -v

# TC-05: Forecasting
pytest test_05_forecasting.py -v

# TC-06 & TC-07: Dashboard
pytest test_06_07_dashboard.py -v

# TC-08: Model Accuracy
pytest test_08_model_accuracy.py -v

# TC-09: Data Leakage
pytest test_09_data_leakage.py -v

# TC-10: Confidence Intervals
pytest test_10_confidence_intervals.py -v
```

### Run Tests by Marker

```bash
# Run all tests with a specific marker
pytest -v -m tc04  # XGBoost model training tests

# Exclude specific markers
pytest -v -m "not tc04"  # All tests except model training
```

### Run with Options

```bash
# Run with timeout (5 minutes per test)
pytest -v --timeout=300

# Run in parallel (faster execution)
pytest -v -n auto

# Run with custom output
pytest -v --tb=long --capture=no

# Run and stop on first failure
pytest -v -x

# Run last failed tests
pytest -v --lf
```

## Test Structure

Each test file follows this structure:

### Fixtures (`conftest.py`)
- `project_dir` - Project root directory
- `data_paths` - Paths to data and model files
- `raw_data` - Loaded leave data
- `employee_master` - Employee master data
- `trained_model` - Pre-trained ML model
- `model_metadata` - Model metadata
- `sample_leave_records` - Sample test data
- `sample_feature_data` - Sample feature data

### Test Classes
Each test file contains one main test class:
- Methods follow `test_*` naming convention
- Each method tests a specific aspect
- Descriptive names and docstrings
- Clear assertions and error messages

## Test Details

### TC-01: Data Loading (test_01_data_loading.py)
- **Tests:** 10 test methods
- **Purpose:** Validate data can be loaded and schema is correct
- **Key Assertions:**
  - Dataset has 50K+ records
  - All required columns present
  - Date columns parse correctly
  - No excessive null values

### TC-02: Data Cleaning (test_02_data_cleaning.py)
- **Tests:** 9 test methods
- **Purpose:** Verify data cleaning removes duplicates and maintains integrity
- **Key Assertions:**
  - Duplicates removed
  - Non-approved records filtered
  - Date ranges valid
  - Missing values filled appropriately

### TC-03: Feature Engineering (test_03_feature_engineering.py)
- **Tests:** 9 test methods
- **Purpose:** Validate feature generation (50+ features)
- **Key Assertions:**
  - Calendar features created
  - Lag features generated
  - Rolling statistics calculated
  - No NaN or Inf values

### TC-04: Model Training (test_04_model_training.py)
- **Tests:** 8 test methods
- **Purpose:** Verify XGBoost trains successfully in <5 min
- **Key Assertions:**
  - Model trains without error
  - Training completes in <300 seconds
  - Predictions have correct shape
  - Metrics calculated correctly

### TC-05: Forecasting (test_05_forecasting.py)
- **Tests:** 9 test methods
- **Purpose:** Validate 60-day forecast generation
- **Key Assertions:**
  - Forecast has 60+ days
  - Predictions are non-negative
  - Confidence intervals present
  - Dates sequential

### TC-06 & TC-07: Dashboard (test_06_07_dashboard.py)
- **Tests:** 13 test methods
- **Purpose:** Verify dashboard loads and filtering works
- **Key Assertions:**
  - Module imports successfully
  - Syntax is valid
  - Date filtering works
  - Visualizations update

### TC-08: Model Accuracy (test_08_model_accuracy.py)
- **Tests:** 9 test methods
- **Purpose:** Verify model accuracy (WAPE <15%)
- **Key Assertions:**
  - WAPE calculated correctly
  - WAPE < 15% threshold
  - Multiple metrics available
  - No NaN/Inf values

### TC-09: Data Leakage (test_09_data_leakage.py)
- **Tests:** 9 test methods
- **Purpose:** Ensure no data leakage in train/test split
- **Key Assertions:**
  - Test dates after training dates
  - No future info in training
  - Temporal order preserved
  - No duplicate records

### TC-10: Confidence Intervals (test_10_confidence_intervals.py)
- **Tests:** 10 test methods
- **Purpose:** Validate confidence intervals
- **Key Assertions:**
  - Bounds present in forecast
  - Lower < Point < Upper
  - Width is reasonable
  - Coverage is appropriate

## Expected Test Results

### Passing Tests
All tests should PASS when:
- Data files exist and are accessible
- Models are trained and artifacts available
- Dependencies are properly installed
- System has sufficient memory for large data operations

### Skipped Tests
Tests will SKIP when:
- Required data files missing
- Optional dependencies not installed (e.g., Streamlit, XGBoost)
- Model artifacts not found
- Insufficient data for specific tests

### Failed Tests
Tests will FAIL when:
- Schema validation fails
- Critical functionality broken
- Performance thresholds not met
- Data quality issues detected

## Troubleshooting

### Common Issues

**Issue: "ModuleNotFoundError: No module named 'streamlit_app'"**
- Solution: Ensure tests are run from the `tests/` directory with parent directory in path

**Issue: "No approved leave dates found"**
- Solution: Verify `Data/Combined_All_Leave_Data.csv` exists and has valid data

**Issue: "XGBoost not available"**
- Solution: Run `pip install xgboost` or `pip install -r requirements-test.txt`

**Issue: "Timeout: test took >300 seconds"**
- Solution: Increase timeout in `pytest.ini` or use faster hardware

**Issue: "Memory Error" with large datasets**
- Solution: Use sample data or run on machine with more RAM

## Performance Benchmarks

- **Data Loading:** <2 seconds for 500K records
- **Data Cleaning:** <5 seconds for 500K records
- **Feature Engineering:** <30 seconds for 1800+ daily records
- **Model Training:** <300 seconds (5 minutes)
- **Forecasting:** <5 seconds for 60-day forecast
- **Dashboard Load:** <5 seconds

## Test Metrics

### Coverage
- **Target:** >80% code coverage
- **Command:** `pytest --cov=.. --cov-report=html`

### Execution Time
- **Target:** <10 minutes for all tests
- **Parallel:** Use `pytest -n auto` for faster execution

### Test Status Codes
- ✓ PASSED - Test successful
- ✗ FAILED - Test failed
- ⊘ SKIPPED - Test skipped (missing dependencies)
- ⚠ WARNING - Test passed with warnings

## Continuous Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.8, 3.9, 3.10, 3.11]
    
    steps:
    - uses: actions/checkout@v2
    - uses: actions/setup-python@v2
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install dependencies
      run: |
        pip install -r tests/requirements-test.txt
    
    - name: Run tests
      run: |
        cd tests
        pytest -v --cov=.. --timeout=300
```

## Contributing

When adding new tests:
1. Follow the existing structure and naming conventions
2. Add docstrings explaining test purpose
3. Use descriptive assertion messages
4. Update this README with new test details
5. Run full test suite before committing

## License

Same as parent project

## Support

For issues or questions:
1. Check test output and logs
2. Review test documentation
3. Verify setup instructions
4. Check project README
