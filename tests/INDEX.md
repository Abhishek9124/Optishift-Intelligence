# Test Suite Index

## Quick Navigation

### Getting Started
- **[QUICK_START.md](QUICK_START.md)** - 30-second setup and key commands
- **[README.md](README.md)** - Full documentation and troubleshooting
- **[TEST_EXECUTION_SUMMARY.md](TEST_EXECUTION_SUMMARY.md)** - Detailed test breakdown

### Installation & Configuration
- **[requirements-test.txt](requirements-test.txt)** - All test dependencies
- **[pytest.ini](pytest.ini)** - Pytest configuration with markers
- **[conftest.py](conftest.py)** - Shared fixtures and utilities

### Test Execution
- **[run_tests.py](run_tests.py)** - Python script to run tests easily

---

## Test Files by Category

### Data Pipeline (TC-01 to TC-03)
Essential data preparation and feature engineering tests

| Test Case | File | Methods | Purpose |
|-----------|------|---------|---------|
| **TC-01** | [test_01_data_loading.py](test_01_data_loading.py) | 10 | Load 500K+ records, validate schema |
| **TC-02** | [test_02_data_cleaning.py](test_02_data_cleaning.py) | 9 | Remove duplicates, clean data |
| **TC-03** | [test_03_feature_engineering.py](test_03_feature_engineering.py) | 9 | Generate 50+ features |

### Model Pipeline (TC-04 to TC-05)
Machine learning model training and forecasting

| Test Case | File | Methods | Purpose |
|-----------|------|---------|---------|
| **TC-04** | [test_04_model_training.py](test_04_model_training.py) | 8 | XGBoost training in <5 min |
| **TC-05** | [test_05_forecasting.py](test_05_forecasting.py) | 9 | 60-day forecast generation |

### Dashboard & UI (TC-06 to TC-07)
User interface and interactive features

| Test Case | File | Methods | Purpose |
|-----------|------|---------|---------|
| **TC-06 & TC-07** | [test_06_07_dashboard.py](test_06_07_dashboard.py) | 13 | Dashboard loading & filtering |

### Validation (TC-08 to TC-10)
Model accuracy and quality assurance

| Test Case | File | Methods | Purpose |
|-----------|------|---------|---------|
| **TC-08** | [test_08_model_accuracy.py](test_08_model_accuracy.py) | 9 | WAPE <15% accuracy threshold |
| **TC-09** | [test_09_data_leakage.py](test_09_data_leakage.py) | 9 | No data leakage detection |
| **TC-10** | [test_10_confidence_intervals.py](test_10_confidence_intervals.py) | 10 | Confidence interval validation |

---

## Directory Structure

```
tests/
├── README.md                        # Main documentation
├── QUICK_START.md                  # 30-second setup guide
├── TEST_EXECUTION_SUMMARY.md       # Detailed test breakdown
├── INDEX.md                         # This file
│
├── Configuration
├── conftest.py                      # Shared fixtures
├── pytest.ini                       # Pytest config
├── requirements-test.txt            # Dependencies
├── __init__.py                      # Package init
│
├── Test Runners
├── run_tests.py                     # Easy test execution script
│
├── Test Cases
├── test_01_data_loading.py          # TC-01
├── test_02_data_cleaning.py         # TC-02
├── test_03_feature_engineering.py   # TC-03
├── test_04_model_training.py        # TC-04
├── test_05_forecasting.py           # TC-05
├── test_06_07_dashboard.py          # TC-06 & TC-07
├── test_08_model_accuracy.py        # TC-08
├── test_09_data_leakage.py          # TC-09
└── test_10_confidence_intervals.py  # TC-10
```

---

## Quick Command Reference

### Installation
```bash
cd tests
pip install -r requirements-test.txt
```

### Run Tests
```bash
pytest -v                          # All tests
pytest -v test_04_model_training.py  # Specific file
pytest -v -m tc04                  # By marker
pytest -v --cov=..                 # With coverage
python run_tests.py --tc04         # Using script
```

### Run by Category
```bash
pytest -v -m "tc01 or tc02 or tc03"  # Data pipeline
pytest -v -m "tc04 or tc05"          # Model pipeline
pytest -v test_06_07_dashboard.py    # Dashboard
pytest -v -m "tc08 or tc09 or tc10"  # Validation
```

### Advanced
```bash
pytest -v -n auto                  # Parallel
pytest -v -x                       # Stop on failure
pytest -v --lf                     # Last failed
pytest --collect-only              # Show tests only
```

---

## File Size Summary

| File | Lines | Purpose |
|------|-------|---------|
| conftest.py | 130 | Shared fixtures |
| pytest.ini | 35 | Configuration |
| __init__.py | 35 | Package init |
| test_01_data_loading.py | 180 | TC-01 (10 tests) |
| test_02_data_cleaning.py | 180 | TC-02 (9 tests) |
| test_03_feature_engineering.py | 180 | TC-03 (9 tests) |
| test_04_model_training.py | 200 | TC-04 (8 tests) |
| test_05_forecasting.py | 160 | TC-05 (9 tests) |
| test_06_07_dashboard.py | 220 | TC-06 & TC-07 (13 tests) |
| test_08_model_accuracy.py | 170 | TC-08 (9 tests) |
| test_09_data_leakage.py | 210 | TC-09 (9 tests) |
| test_10_confidence_intervals.py | 210 | TC-10 (10 tests) |
| run_tests.py | 180 | Test runner script |
| requirements-test.txt | 25 | Dependencies |
| README.md | 400 | Full docs |
| QUICK_START.md | 150 | Quick guide |
| TEST_EXECUTION_SUMMARY.md | 450 | Test breakdown |
| **Total** | **~2,900** | **Complete suite** |

---

## Test Statistics

- **Total Test Cases:** 10 (TC-01 to TC-10)
- **Total Test Methods:** 85+
- **Total Lines of Code:** ~2,900
- **Expected Execution Time:** 10-15 minutes
- **Success Criteria:** 100% PASS rate
- **Code Coverage Target:** >80%

---

## Recommended Reading Order

1. **New to tests?** → Start with [QUICK_START.md](QUICK_START.md)
2. **Want details?** → Read [README.md](README.md)
3. **Understand breakdown?** → Check [TEST_EXECUTION_SUMMARY.md](TEST_EXECUTION_SUMMARY.md)
4. **Run specific test?** → Use file links above or `pytest` command
5. **Setup issues?** → See README troubleshooting section

---

## Key Features

✓ **Comprehensive** - 85+ test methods covering all 10 test cases  
✓ **Well-Documented** - Clear docstrings and assertions  
✓ **Easy to Run** - Multiple execution methods  
✓ **Flexible** - Run all, by category, or individual tests  
✓ **Robust** - Handles edge cases and missing dependencies  
✓ **Fast** - Parallel execution support  
✓ **Detailed Output** - Clear pass/fail/skip reporting  

---

## Support

### Getting Help
1. Check [QUICK_START.md](QUICK_START.md) for common commands
2. Review [README.md](README.md) troubleshooting section
3. Run `pytest --help` for pytest options
4. Check individual test file docstrings

### Test Markers
```bash
pytest -v -m tc01   # TC-01 tests
pytest -v -m tc02   # TC-02 tests
# ... and so on for TC-03 through TC-10
```

### Debug Mode
```bash
pytest -v -s                    # Show print output
pytest -v --tb=long             # Full traceback
pytest -v test_file.py::TestClass::test_method  # Single test
```

---

## Status

- **Last Updated:** 2026-04-16
- **Version:** 1.0.0
- **Status:** ✓ Production Ready
- **Test Suite:** Complete with all 10 test cases

---

**Next Step:** Run `python run_tests.py` or see [QUICK_START.md](QUICK_START.md) for setup!
