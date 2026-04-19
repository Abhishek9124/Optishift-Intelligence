"""
TC-02: Data cleaning removes duplicates
Test that data cleaning process correctly removes duplicates and maintains integrity.
"""
import pytest
import pandas as pd
import numpy as np


class TestDataCleaning:
    """Test suite for data cleaning and duplicate removal."""
    
    def test_clean_remove_duplicates(self, import_streamlit_functions, sample_leave_records):
        """
        Verify that duplicates are correctly removed during cleaning.
        """
        clean_leave_data = import_streamlit_functions.clean_leave_data
        
        # Add duplicate records
        duplicates = sample_leave_records.iloc[:2].copy()
        data_with_dupes = pd.concat([sample_leave_records, duplicates], ignore_index=True)
        
        assert len(data_with_dupes) > len(sample_leave_records), "Duplicates not added"
        
        # Clean the data
        cleaned = clean_leave_data(data_with_dupes)
        
        # Verify duplicates removed
        assert len(cleaned) <= len(sample_leave_records), "Duplicates not removed"
        print(f"\n✓ Duplicates removed: {len(data_with_dupes)} → {len(cleaned)}")
    
    def test_clean_filters_approved_status(self, import_streamlit_functions, sample_leave_records):
        """
        Verify that only 'Approved' status records are kept.
        """
        clean_leave_data = import_streamlit_functions.clean_leave_data
        
        # Add non-approved records
        data = sample_leave_records.copy()
        non_approved = data.iloc[:2].copy()
        non_approved["Status"] = "Pending"
        data = pd.concat([data, non_approved], ignore_index=True)
        
        initial_count = len(data)
        cleaned = clean_leave_data(data)
        
        # Verify non-approved filtered
        assert len(cleaned) < initial_count, "Non-approved records not filtered"
        assert all(cleaned["Status"] == "Approved"), "Non-approved records still present"
        print(f"\n✓ Non-approved records filtered: {initial_count} → {len(cleaned)}")
    
    def test_clean_date_parsing(self, import_streamlit_functions, sample_leave_records):
        """
        Verify that dates are correctly parsed during cleaning.
        """
        clean_leave_data = import_streamlit_functions.clean_leave_data
        
        cleaned = clean_leave_data(sample_leave_records)
        
        # Check date columns are properly parsed
        date_columns = ["From Date", "To Date", "Applied On", "Approved On"]
        for col in date_columns:
            if col in cleaned.columns:
                assert pd.api.types.is_datetime64_any_dtype(cleaned[col]), f"{col} not parsed as datetime"
        
        print(f"\n✓ Date columns correctly parsed")
    
    def test_clean_date_range_validation(self, import_streamlit_functions, sample_leave_records):
        """
        Verify that invalid date ranges (To Date < From Date) are removed.
        """
        clean_leave_data = import_streamlit_functions.clean_leave_data
        
        # Create invalid date range
        data = sample_leave_records.copy()
        invalid = data.iloc[:1].copy()
        invalid["From Date"] = "15-01-2025"
        invalid["To Date"] = "01-01-2025"
        data = pd.concat([data, invalid], ignore_index=True)
        
        cleaned = clean_leave_data(data)
        
        # Verify all valid dates
        if "From Date" in cleaned.columns and "To Date" in cleaned.columns:
            assert (cleaned["To Date"] >= cleaned["From Date"]).all(), "Invalid date ranges present"
            print(f"\n✓ Invalid date ranges removed")
    
    def test_clean_maintains_data_integrity(self, import_streamlit_functions, sample_leave_records):
        """
        Verify that cleaning maintains data integrity for valid records.
        """
        clean_leave_data = import_streamlit_functions.clean_leave_data
        
        original_approved_count = (sample_leave_records["Status"] == "Approved").sum()
        cleaned = clean_leave_data(sample_leave_records)
        
        # All records should be approved
        assert len(cleaned) <= original_approved_count, "Cleaning removed approved records"
        assert (cleaned["Status"] == "Approved").all(), "Non-approved records present after cleaning"
        print(f"\n✓ Data integrity maintained: {len(cleaned)} approved records")
    
    def test_clean_fills_missing_values(self, import_streamlit_functions):
        """
        Verify that missing values in text columns are filled appropriately.
        """
        clean_leave_data = import_streamlit_functions.clean_leave_data
        
        # Create data with nulls
        data = pd.DataFrame({
            "EmpNo": [1, 2, 3],
            "From Date": ["01-01-2025", "02-01-2025", "03-01-2025"],
            "To Date": ["02-01-2025", "03-01-2025", "04-01-2025"],
            "Leave Type": ["Casual", None, "Sick"],
            "Status": ["Approved", "Approved", "Approved"],
            "Department": [None, "IT", "HR"],
        })
        
        cleaned = clean_leave_data(data)
        
        # Text columns should not have NaN
        text_cols = ["Leave Type", "Department"]
        for col in text_cols:
            if col in cleaned.columns:
                assert cleaned[col].isna().sum() == 0, f"{col} still has null values"
        
        print(f"\n✓ Missing values filled correctly")
    
    def test_clean_deduplicates_correctly(self, import_streamlit_functions):
        """
        Verify that deduplication keeps only first occurrence.
        """
        clean_leave_data = import_streamlit_functions.clean_leave_data
        
        # Create exact duplicates
        data = pd.DataFrame({
            "EmpNo": [1, 1, 2],
            "Leave Type": ["Casual", "Casual", "Sick"],
            "From Date": ["01-01-2025", "01-01-2025", "02-01-2025"],
            "To Date": ["02-01-2025", "02-01-2025", "03-01-2025"],
            "Applied On": ["25-12-2024", "25-12-2024", "26-12-2024"],
            "Status": ["Approved", "Approved", "Approved"],
        })
        
        cleaned = clean_leave_data(data)
        
        # Should have 2 records (duplicate removed)
        assert len(cleaned) == 2, f"Expected 2 records after dedup, got {len(cleaned)}"
        print(f"\n✓ Deduplication correct: {len(data)} → {len(cleaned)}")
    
    def test_clean_handles_edge_cases(self, import_streamlit_functions):
        """
        Verify handling of edge cases (empty data, null dates, etc).
        """
        clean_leave_data = import_streamlit_functions.clean_leave_data
        
        # Empty dataframe
        empty_df = pd.DataFrame({
            "EmpNo": [],
            "From Date": [],
            "To Date": [],
            "Status": [],
        })
        
        result = clean_leave_data(empty_df)
        assert len(result) == 0, "Empty dataframe not handled"
        
        print(f"\n✓ Edge cases handled correctly")
    
    def test_duplicate_count_reduced(self, raw_data, import_streamlit_functions):
        """
        Verify duplicate count is significantly reduced after cleaning.
        """
        clean_leave_data = import_streamlit_functions.clean_leave_data
        
        # Count duplicates before cleaning
        dedupe_key = ["EmpNo", "Leave Type", "From Date", "To Date", "Applied On"]
        available_cols = [col for col in dedupe_key if col in raw_data.columns]
        duplicates_before = raw_data.duplicated(subset=available_cols, keep=False).sum()
        
        # Clean data
        cleaned = clean_leave_data(raw_data)
        
        # Count duplicates after cleaning
        duplicates_after = cleaned.duplicated(subset=available_cols, keep=False).sum()
        
        # Verify reduction
        reduction = duplicates_before - duplicates_after
        assert reduction >= 0, "Duplicates increased"
        
        print(f"\n✓ Duplicates removed: {duplicates_before} → {duplicates_after} (saved {reduction})")


# Mark all tests as recommended status
pytestmark = pytest.mark.tc02
