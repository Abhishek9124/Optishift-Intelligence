"""
Leave Management System Test Suite

This package contains comprehensive tests for the Leave Management System
covering all aspects of the ML pipeline including data loading, cleaning,
feature engineering, model training, forecasting, and dashboard functionality.

Test Cases:
- TC-01: Data Loading (500K records)
- TC-02: Data Cleaning (duplicate removal)
- TC-03: Feature Engineering (50+ features)
- TC-04: Model Training (<5 minutes)
- TC-05: Forecasting (60-day predictions)
- TC-06: Dashboard Loading (<5 seconds)
- TC-07: Interactive Filtering
- TC-08: Model Accuracy (WAPE <15%)
- TC-09: Data Leakage Prevention
- TC-10: Confidence Intervals

Usage:
    pytest -v              # Run all tests
    pytest -v -m tc04      # Run specific test case
    pytest --cov=..        # Run with coverage
"""

__version__ = "1.0.0"
__author__ = "ML Engineering Team"
__all__ = [
    "conftest",
    "test_01_data_loading",
    "test_02_data_cleaning",
    "test_03_feature_engineering",
    "test_04_model_training",
    "test_05_forecasting",
    "test_06_07_dashboard",
    "test_08_model_accuracy",
    "test_09_data_leakage",
    "test_10_confidence_intervals",
]
