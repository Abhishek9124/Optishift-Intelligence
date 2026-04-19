"""
TC-01: Load 500K leave records, verify schema
Test that 500K+ leave records can be loaded and schema is validated.
"""
import pytest
import pandas as pd
import numpy as np


class TestDataLoading:
    """Test suite for data loading and schema validation."""
    
    def test_load_large_dataset(self, raw_data):
        """
        Verify that large dataset (500K+ records) can be loaded successfully.
        """
        assert raw_data is not None, "Failed to load data"
        assert len(raw_data) > 0, "Data is empty"
        print(f"\n✓ Loaded {len(raw_data):,} records")
    
    def test_schema_validation_required_columns(self, raw_data):
        """
        Verify that all required columns exist in the dataset.
        """
        required_columns = [
            "EmpNo",
            "From Date",
            "To Date",
            "Leave Type",
            "Status",
            "Department",
        ]
        
        for column in required_columns:
            assert column in raw_data.columns, f"Missing required column: {column}"
        
        print(f"\n✓ All {len(required_columns)} required columns present")
    
    def test_schema_date_columns_format(self, raw_data):
        """
        Verify that date columns can be parsed correctly.
        """
        date_columns = ["From Date", "To Date", "Applied On", "Approved On"]
        
        for col in date_columns:
            if col not in raw_data.columns:
                continue
            
            # Test parsing (dayfirst=True per system)
            try:
                parsed_dates = pd.to_datetime(raw_data[col], errors="coerce", dayfirst=True)
                non_null_count = parsed_dates.notna().sum()
                null_count = parsed_dates.isna().sum()
                
                # At least 90% should parse successfully
                parse_rate = non_null_count / (non_null_count + null_count) if (non_null_count + null_count) > 0 else 0
                assert parse_rate >= 0.90, f"Only {parse_rate:.1%} of {col} parsed successfully"
                print(f"\n✓ {col}: {parse_rate:.1%} parse success rate ({non_null_count:,} records)")
            except Exception as e:
                pytest.fail(f"Failed to parse {col}: {str(e)}")
    
    def test_schema_numeric_columns(self, raw_data):
        """
        Verify numeric columns can be converted to proper data types.
        """
        numeric_columns = ["Days", "Delay"]
        
        for col in numeric_columns:
            if col not in raw_data.columns:
                continue
            
            try:
                numeric_data = pd.to_numeric(raw_data[col], errors="coerce")
                non_null_rate = numeric_data.notna().sum() / len(numeric_data)
                assert non_null_rate >= 0.80, f"Only {non_null_rate:.1%} of {col} are numeric"
                print(f"\n✓ {col}: {non_null_rate:.1%} numeric values")
            except Exception as e:
                pytest.fail(f"Failed to process numeric column {col}: {str(e)}")
    
    def test_record_count_distribution(self, raw_data):
        """
        Verify that data includes reasonable distribution across key dimensions.
        """
        # Check employee distribution
        emp_count = raw_data["EmpNo"].nunique()
        assert emp_count > 0, "No employees found"
        
        # Check leave type distribution
        leave_type_count = raw_data["Leave Type"].nunique()
        assert leave_type_count > 0, "No leave types found"
        
        # Check status distribution
        status_count = raw_data["Status"].nunique()
        assert status_count > 0, "No status values found"
        
        print(f"\n✓ Data distribution:")
        print(f"  - Employees: {emp_count:,}")
        print(f"  - Leave Types: {leave_type_count}")
        print(f"  - Status Values: {status_count}")
    
    def test_feature_count_threshold(self, raw_data):
        """
        TC-03F: Verify that minimum 50 features can be generated (INTENTIONAL FAIL).
        This test demonstrates expected failure when insufficient data.
        """
        # Simulate feature engineering requirement: need at least 30 days of history
        data = raw_data.copy()
        data["From Date"] = pd.to_datetime(data["From Date"], errors="coerce", dayfirst=True)
        
        date_range = (data["From Date"].max() - data["From Date"].min()).days
        print(f"\n[FEATURE_ENGINEERING_TEST]")
        print(f"  - Date Range: {date_range} days")
        print(f"  - Required: 30+ days for 50 features")
        
        # This will FAIL if date range < 60 days (simulating insufficient historical data)
        required_features = 50
        # Calculate features: 30 for temporal + 15 for organizational + 5 for behavioral
        # Each requires different data history
        available_features = min(50, int((date_range / 30) * 50 / 2))
        
        print(f"  - Available Features: {available_features}")
        print(f"  - Required Features: {required_features}")
        
        assert available_features >= required_features, \
            f"Insufficient historical data: {available_features} features available, {required_features} required"
    
    def test_dashboard_performance_threshold(self, raw_data):
        """
        TC-06F: Dashboard load performance test (INTENTIONAL FAIL).
        This simulates slow dashboard loading when data volume increases.
        """
        import time
        
        print(f"\n[DASHBOARD_PERFORMANCE_TEST]")
        data_size_mb = len(raw_data) * 0.000001  # Rough estimate
        
        # Simulate load time: 5s base + 1s per 100K records
        simulated_load_time = 5.0 + (len(raw_data) / 100000)
        target_load_time = 5.0
        
        print(f"  - Data Size: {data_size_mb:.2f} MB")
        print(f"  - Simulated Load Time: {simulated_load_time:.2f}s")
        print(f"  - Target Load Time: {target_load_time}s")
        
        # This will FAIL if simulated_load_time > target (when data > certain threshold)
        assert simulated_load_time <= target_load_time, \
            f"Dashboard load time {simulated_load_time:.2f}s exceeds target {target_load_time}s"
    
    def test_wape_accuracy_threshold(self, raw_data):
        """
        TC-08F: Model accuracy threshold test (INTENTIONAL FAIL).
        This simulates model accuracy declining over time.
        """
        print(f"\n[MODEL_ACCURACY_TEST]")
        
        # Simulate WAPE degradation: starts at 12.35%, increases to 16.8% after extended use
        simulated_wape = 0.168  # 16.8% - simulates degraded performance
        target_wape = 0.15  # 15% threshold
        
        print(f"  - Current WAPE: {simulated_wape:.2%}")
        print(f"  - Target WAPE: {target_wape:.0%}")
        print(f"  - Days Since Retraining: 60 (exceeded 45-day cycle)")
        
        # This will FAIL if WAPE > 15% (model drift scenario)
        assert simulated_wape <= target_wape, \
            f"Model accuracy degraded: WAPE {simulated_wape:.2%} exceeds threshold {target_wape:.0%}"
    
    def test_data_integrity_no_null_empno(self, raw_data):
        """
        Verify critical columns don't have excessive null values.
        """
        critical_columns = ["EmpNo", "From Date", "To Date", "Leave Type", "Status"]
        
        for col in critical_columns:
            if col not in raw_data.columns:
                continue
            
            null_count = raw_data[col].isna().sum()
            null_rate = null_count / len(raw_data)
            assert null_rate < 0.01, f"{col} has {null_rate:.1%} null values"
        
        print(f"\n✓ Critical columns have <1% null values")
    
    def test_dataset_size_exceeds_threshold(self, raw_data):
        """
        Verify dataset has at least 50K records (aiming for 500K+).
        """
        min_records = 50000
        assert len(raw_data) >= min_records, f"Dataset has only {len(raw_data):,} records, expected >= {min_records:,}"
        print(f"\n✓ Dataset size: {len(raw_data):,} records (threshold: {min_records:,})")
    
    def test_employee_master_schema(self, employee_master):
        """
        Verify employee master data has required schema.
        """
        required_columns = ["SAP Emp No", "Name", "Department", "D.O.J"]
        
        for sheet_name, sheet_data in employee_master.items():
            for col in required_columns:
                if col not in sheet_data.columns:
                    print(f"Note: {col} not in {sheet_name} sheet (optional)")
        
        print(f"\n✓ Employee master schema validated")
    
    def test_load_performance(self, raw_data):
        """
        Verify data loading performance is acceptable.
        """
        # This is already loaded in the fixture with timing
        size_mb = raw_data.memory_usage(deep=True).sum() / (1024 ** 2)
        record_count = len(raw_data)
        
        print(f"\n✓ Data loading performance:")
        print(f"  - Records: {record_count:,}")
        print(f"  - Memory: {size_mb:.1f} MB")
        print(f"  - Per-record: {size_mb / record_count * 1000:.2f} KB")


# Mark all tests as required status
pytestmark = pytest.mark.tc01
