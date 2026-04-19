# Quick Start Guide - Test Suite

## 30-Second Setup

```bash
# 1. Navigate to tests directory
cd tests

# 2. Install dependencies
pip install -r requirements-test.txt

# 3. Run all tests
pytest -v
```

## Key Commands

```bash
# Run all tests
pytest -v

# Run specific test case
pytest -v test_04_model_training.py  # Run TC-04 only

# Run with markers
pytest -v -m tc01   # Run all TC-01 tests
pytest -v -m "tc01 or tc02"  # Run TC-01 and TC-02

# Run with coverage
pytest -v --cov=..

# Run with parallel execution
pytest -v -n auto

# Run with timeout (stop slow tests)
pytest -v --timeout=300

# Stop on first failure
pytest -v -x

# Run last failed tests
pytest -v --lf
```

## Expected Output

All tests should complete successfully:

```
tests/test_01_data_loading.py::TestDataLoading::test_load_large_dataset PASSED
tests/test_01_data_loading.py::TestDataLoading::test_schema_validation_required_columns PASSED
...
=========== 95 passed in 45.23s ===========
```

## Test Status Key

- **PASSED** ✓ - Test completed successfully
- **FAILED** ✗ - Test failed (check output)
- **SKIPPED** ⊘ - Test skipped (missing data/dependency)

## Troubleshooting

### Tests not found?
```bash
# Check pytest is installed
pip list | grep pytest

# Run from correct directory
cd tests
pytest -v
```

### Import errors?
```bash
# Ensure parent modules can be imported
export PYTHONPATH="${PYTHONPATH}:../."
pytest -v
```

### Out of memory?
```bash
# Run smaller tests first
pytest -v test_01_data_loading.py

# Or reduce data size in conftest.py
```

### Slow tests?
```bash
# Run in parallel
pytest -v -n auto

# Or run specific test
pytest -v test_04_model_training.py::TestModelTraining::test_model_training_completes
```

## Test Categories

### Data Pipeline (TC-01 to TC-03)
```bash
pytest -v -m "tc01 or tc02 or tc03"
```

### Model Pipeline (TC-04 to TC-05)
```bash
pytest -v -m "tc04 or tc05"
```

### UI & Analytics (TC-06 to TC-07)
```bash
pytest -v test_06_07_dashboard.py
```

### Validation (TC-08 to TC-10)
```bash
pytest -v -m "tc08 or tc09 or tc10"
```

## Performance Targets

- **Data Loading:** < 2 seconds
- **Data Cleaning:** < 5 seconds  
- **Feature Engineering:** < 30 seconds
- **Model Training:** < 300 seconds (5 minutes)
- **Forecasting:** < 5 seconds
- **Dashboard:** < 5 seconds

## Next Steps

1. **Review Test Results** - Check output for any FAILED or skipped tests
2. **Read Full Documentation** - See [README.md](README.md) for details
3. **Fix Issues** - Address any failures or setup problems
4. **Run Full Suite** - `pytest -v` to run all tests
5. **Generate Reports** - `pytest --cov=.. --cov-report=html`

## File Structure

```
tests/
├── __init__.py                    # Package init
├── conftest.py                    # Shared fixtures
├── pytest.ini                     # Pytest configuration
├── requirements-test.txt          # Test dependencies
├── README.md                       # Full documentation
├── QUICK_START.md                 # This file
├── test_01_data_loading.py        # TC-01
├── test_02_data_cleaning.py       # TC-02
├── test_03_feature_engineering.py # TC-03
├── test_04_model_training.py      # TC-04
├── test_05_forecasting.py         # TC-05
├── test_06_07_dashboard.py        # TC-06 & TC-07
├── test_08_model_accuracy.py      # TC-08
├── test_09_data_leakage.py        # TC-09
└── test_10_confidence_intervals.py # TC-10
```

## Debugging

### Print test output
```bash
pytest -v -s test_01_data_loading.py
```

### Show full traceback
```bash
pytest -v --tb=long
```

### Run single test
```bash
pytest -v tests/test_01_data_loading.py::TestDataLoading::test_load_large_dataset
```

### Show test collection
```bash
pytest --collect-only
```

## Success Criteria

✓ All tests PASS  
✓ No FAILED tests  
✓ Coverage > 80%  
✓ Execution time < 10 minutes  
✓ All data quality checks pass  
✓ Model accuracy threshold met  

Run tests to verify!
