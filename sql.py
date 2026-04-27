"""
SQL Query Execution: Count Leave Records by Date Range
File: sql.py
Purpose: Execute SQL-like queries on output/full_expanded_frame.csv
"""

import pandas as pd
from pathlib import Path
from datetime import datetime

# Get project paths
def get_csv_path():
    """Get path to full_expanded_frame.csv"""
    project_dir = Path(__file__).resolve().parent
    csv_path = project_dir / "output" / "full_expanded_frame.csv"
    return csv_path

# Load data
def load_leave_data():
    """Load leave data from full_expanded_frame.csv"""
    csv_path = get_csv_path()
    print(f"Loading data from: {csv_path}")
    
    df = pd.read_csv(csv_path)
    print(f"✓ Loaded {len(df)} records from CSV\n")
    
    return df

# Query 1: Count total leave records between dates
def count_leave_records_by_date_range(df, start_date='2023-02-01', end_date='2023-03-31'):
    """
    SELECT COUNT(*) AS total_leave_records
    FROM Combined_All_Leave_Data
    WHERE leave_date >= '2023-02-01'
      AND leave_date <= '2023-03-01';
    """
    
    print("=" * 70)
    print("QUERY 1: COUNT LEAVE RECORDS BY DATE RANGE")
    print("=" * 70)
    print(f"\nOriginal SQL Query:")
    print(f"""
    SELECT COUNT(*) AS total_leave_records
    FROM Combined_All_Leave_Data
    WHERE leave_date >= '{start_date}'
      AND leave_date <= '{end_date}';
    """)
    
    # Convert date columns to datetime
    date_columns = ['From Date', 'To Date', 'Applied On', 'Approved On']
    for col in date_columns:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')
    
    # Convert input dates
    start = pd.to_datetime(start_date)
    end = pd.to_datetime(end_date)
    
    # Filter: leave records where From Date >= start_date AND To Date <= end_date
    filtered_df = df[
        (df['From Date'] >= start) & 
        (df['To Date'] <= end)
    ]
    
    total_count = len(filtered_df)
    
    print(f"\nExecution Result:")
    print(f"─" * 70)
    print(f"total_leave_records: {total_count}")
    print(f"─" * 70)
    
    return filtered_df, total_count

# Query 2: Count with status filter
def count_approved_leave_records(df, start_date='2023-02-01', end_date='2023-03-31'):
    """Count only APPROVED leave records in date range"""
    
    print("\n\n" + "=" * 70)
    print("QUERY 2: COUNT APPROVED LEAVE RECORDS")
    print("=" * 70)
    print(f"\nSQL Query:")
    print(f"""
    SELECT COUNT(*) AS approved_leave_records
    FROM Combined_All_Leave_Data
    WHERE Status = 'Approved'
      AND 'From Date' >= '{start_date}'
      AND 'To Date' <= '{end_date}';
    """)
    
    # Convert date columns to datetime
    date_columns = ['From Date', 'To Date', 'Applied On', 'Approved On']
    for col in date_columns:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')
    
    start = pd.to_datetime(start_date)
    end = pd.to_datetime(end_date)
    
    # Filter with Status condition
    filtered_df = df[
        (df['Status'] == 'Approved') &
        (df['From Date'] >= start) & 
        (df['To Date'] <= end)
    ]
    
    total_count = len(filtered_df)
    
    print(f"\nExecution Result:")
    print(f"─" * 70)
    print(f"approved_leave_records: {total_count}")
    print(f"─" * 70)
    
    return filtered_df, total_count

# Query 3: Group by Leave Type
def count_by_leave_type(df, start_date='2023-02-01', end_date='2023-03-31'):
    """Count leave records by Leave Type"""
    
    print("\n\n" + "=" * 70)
    print("QUERY 3: COUNT RECORDS BY LEAVE TYPE")
    print("=" * 70)
    print(f"\nSQL Query:")
    print(f"""
    SELECT Leave_Type, COUNT(*) AS count
    FROM Combined_All_Leave_Data
    WHERE 'From Date' >= '{start_date}'
      AND 'To Date' <= '{end_date}'
    GROUP BY Leave_Type
    ORDER BY count DESC;
    """)
    
    # Convert date columns to datetime
    date_columns = ['From Date', 'To Date', 'Applied On', 'Approved On']
    for col in date_columns:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')
    
    start = pd.to_datetime(start_date)
    end = pd.to_datetime(end_date)
    
    # Filter
    filtered_df = df[
        (df['From Date'] >= start) & 
        (df['To Date'] <= end)
    ]
    
    # Group by Leave Type
    result = filtered_df.groupby('Leave Type').size().reset_index(name='count')
    result = result.sort_values('count', ascending=False)
    
    print(f"\nExecution Result:")
    print(f"─" * 70)
    print(result.to_string(index=False))
    print(f"─" * 70)
    
    return result

# Query 4: Summary statistics
def get_date_range_summary(df, start_date='2023-02-01', end_date='2023-03-31'):
    """Get summary statistics for date range"""
    
    print("\n\n" + "=" * 70)
    print("QUERY 4: SUMMARY STATISTICS FOR DATE RANGE")
    print("=" * 70)
    print(f"\nFiltering data from {start_date} to {end_date}")
    
    # Convert date columns to datetime
    date_columns = ['From Date', 'To Date', 'Applied On', 'Approved On']
    for col in date_columns:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')
    
    start = pd.to_datetime(start_date)
    end = pd.to_datetime(end_date)
    
    # Filter
    filtered_df = df[
        (df['From Date'] >= start) & 
        (df['To Date'] <= end)
    ]
    
    print(f"\nExecution Results:")
    print(f"─" * 70)
    print(f"Total Leave Records:        {len(filtered_df)}")
    print(f"Unique Employees:           {filtered_df['EmpNo'].nunique()}")
    print(f"Total Leave Days:           {filtered_df['Days'].sum()}")
    print(f"Average Days per Record:    {filtered_df['Days'].mean():.2f}")
    print(f"Approved Records:           {len(filtered_df[filtered_df['Status'] == 'Approved'])}")
    print(f"Pending Records:            {len(filtered_df[filtered_df['Status'] == 'Pending'])}")
    print(f"Rejected Records:           {len(filtered_df[filtered_df['Status'] == 'Rejected'])}")
    print(f"─" * 70)
    
    return filtered_df

# Query 5: Planned vs Unplanned Days by Cost Centre
def calculate_planned_unplanned_days(df, start_date='2023-02-01', end_date='2023-03-01'):
    """
    Calculate Planned Days and Unplanned Days by Cost Centre
    Total Leave Days = Planned Days + Unplanned Days
    Using full_expanded_frame.csv (one row per day)
    Uses the "Type" column for Planned/Un-Planned classification
    """
    
    print("\n" + "=" * 90)
    print("QUERY: TOTAL LEAVE DAYS = PLANNED DAYS + UNPLANNED DAYS (BY COST CENTRE)")
    print("=" * 90)
    print(f"\nSQL Query:")
    print(f"""
    SELECT Cost_Centre,
           SUM(CASE WHEN Type = 'Planned' THEN 1 ELSE 0 END) AS Planned_Days,
           SUM(CASE WHEN Type = 'Un-Planned' THEN 1 ELSE 0 END) AS Unplanned_Days,
           COUNT(*) AS Total_Leave_Days
    FROM full_expanded_frame
    WHERE Date >= '{start_date}'
      AND Date <= '{end_date}'
    GROUP BY Cost_Centre
    ORDER BY Total_Leave_Days DESC;
    """)
    
    # Convert date column to datetime
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce', dayfirst=True)
    
    start = pd.to_datetime(start_date)
    end = pd.to_datetime(end_date)
    
    # Filter
    filtered_df = df[
        (df['Date'] >= start) & 
        (df['Date'] <= end)
    ].copy()
    
    # Group by Cost Centre and Type (Planned/Un-Planned)
    result = filtered_df.groupby(['Cost Centre', 'Type']).size().unstack(fill_value=0)
    
    # Rename columns if they exist
    if 'Planned' not in result.columns:
        result['Planned'] = 0
    if 'Un-Planned' not in result.columns:
        result['Un-Planned'] = 0
    
    # Reorder and rename
    result = result[['Planned', 'Un-Planned']]
    result.columns = ['Planned_Days', 'Unplanned_Days']
    
    # Calculate total
    result['Total_Leave_Days'] = result['Planned_Days'] + result['Unplanned_Days']
    
    # Sort by total descending
    result = result.sort_values('Total_Leave_Days', ascending=False)
    
    # Reset index
    result = result.reset_index()
    
    print(f"\nExecution Result:")
    print(f"─" * 90)
    print(result.to_string(index=False))
    print(f"─" * 90)
    
    # Summary totals
    print(f"\nTOTAL SUMMARY (All Cost Centres):")
    print(f"─" * 90)
    total_planned = result['Planned_Days'].sum()
    total_unplanned = result['Unplanned_Days'].sum()
    total_all = result['Total_Leave_Days'].sum()
    
    print(f"Total Planned Days:       {total_planned:,}")
    print(f"Total Unplanned Days:     {total_unplanned:,}")
    print(f"TOTAL LEAVE DAYS:         {total_all:,}")
    print(f"─" * 90)
    
    return result

# Query 6: Comprehensive Leave Summary
def calculate_comprehensive_summary(df, start_date='2023-02-01', end_date='2023-03-01'):
    """
    Calculate comprehensive leave summary:
    - Total Leave Days
    - Planned Days
    - Unplanned Days
    - Total Employees on Leave
    Uses the "Type" column for Planned/Un-Planned classification
    """
    
    print("\n\n" + "=" * 90)
    print("COMPREHENSIVE LEAVE ANALYSIS SUMMARY")
    print("=" * 90)
    print(f"\nSQL Query:")
    print(f"""
    SELECT 
        COUNT(*) AS Total_Leave_Days,
        SUM(CASE WHEN Type = 'Planned' THEN 1 ELSE 0 END) AS Planned_Days,
        SUM(CASE WHEN Type = 'Un-Planned' THEN 1 ELSE 0 END) AS Unplanned_Days,
        COUNT(DISTINCT EmpNo) AS Total_Employees_on_Leave
    FROM full_expanded_frame
    WHERE Date >= '{start_date}'
      AND Date <= '{end_date}';
    """)
    
    # Convert date column to datetime
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce', dayfirst=True)
    
    start = pd.to_datetime(start_date)
    end = pd.to_datetime(end_date)
    
    # Filter
    filtered_df = df[
        (df['Date'] >= start) & 
        (df['Date'] <= end)
    ].copy()
    
    # Calculate metrics using Type column
    total_leave_days = len(filtered_df)
    planned_days = len(filtered_df[filtered_df['Type'] == 'Planned'])
    unplanned_days = len(filtered_df[filtered_df['Type'] == 'Un-Planned'])
    total_employees = filtered_df['EmpNo'].nunique()
    
    # Display results
    print(f"\nExecution Result:")
    print(f"─" * 90)
    print(f"Total Leave Days:              {total_leave_days:,}")
    print(f"Planned Days:                  {planned_days:,}")
    print(f"Unplanned Days:                {unplanned_days:,}")
    print(f"Total Employees on Leave:      {total_employees:,}")
    print(f"─" * 90)
    
    # Verification
    print(f"\nVerification:")
    print(f"Planned Days + Unplanned Days = {planned_days:,} + {unplanned_days:,} = {planned_days + unplanned_days:,}")
    print(f"Total Leave Days = {total_leave_days:,}")
    print(f"Match: {planned_days + unplanned_days == total_leave_days}")
    print(f"─" * 90)
    
    return {
        'Total_Leave_Days': total_leave_days,
        'Planned_Days': planned_days,
        'Unplanned_Days': unplanned_days,
        'Total_Employees_on_Leave': total_employees
    }

# Main execution
def main():
    """Main execution function - Calculate Planned vs Unplanned Days by Cost Centre"""
    
    print("\n" + "=" * 90)
    print("  Planned vs Unplanned Leave Days Analysis (Feb 1 - Mar 1, 2023)")
    print("=" * 90 + "\n")
    
    # Load data
    df = load_leave_data()
    
    # Define date range
    START_DATE = '2023-02-01'
    END_DATE = '2023-03-01'
    
    print(f"Date Range: {START_DATE} to {END_DATE}\n")
    
    # Execute queries
    try:
        # Query 1: Cost Centre breakdown
        result = calculate_planned_unplanned_days(df, START_DATE, END_DATE)
        
        # Query 2: Comprehensive summary
        summary = calculate_comprehensive_summary(df, START_DATE, END_DATE)
        
        print("\n✓ All queries executed successfully!\n")
        
        return {
            'cost_centre_breakdown': result,
            'comprehensive_summary': summary
        }
        
    except Exception as e:
        print(f"\n✗ Error executing query: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    results = main()
