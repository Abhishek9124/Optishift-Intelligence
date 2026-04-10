"""
Streamlit SQL Visualization Dashboard
Pure CSV-based analytics with dynamic date filtering
Mirrors streamlit_app.py structure for consistency
No model artifacts - data-driven insights only
"""

import streamlit as st
import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, datetime, timedelta
import warnings

warnings.filterwarnings("ignore")

# ════════════════════════════════════════════════════════════════════════════════════
# PAGE CONFIGURATION
# ════════════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="Leave Management - SQL Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📊 Leave Management - SQL Analytics Dashboard")
st.markdown("**CSV-Based Analysis** | Dynamic Date Filtering | Real-Time Insights")

# ════════════════════════════════════════════════════════════════════════════════════
# SIDEBAR - DATE FILTERS & CONTROLS
# ════════════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.header("⚙️ Dashboard Controls")
    
    # Get date range from CSV
    con = duckdb.connect()
    date_query = """
    SELECT
        MIN(CAST("From Date" AS DATE)) as min_date,
        MAX(CAST("From Date" AS DATE)) as max_date
    FROM read_csv_auto('Data/Combined_All_Leave_Data.csv')
    WHERE Status = 'Approved'
    """
    date_bounds = con.execute(date_query).df()
    min_date = date_bounds['min_date'].iloc[0].date() if not date_bounds.empty else date(2022, 1, 1)
    max_date = date_bounds['max_date'].iloc[0].date() if not date_bounds.empty else date(2026, 3, 20)
    
    # Set default to today to next 2 months (60 days)
    today = datetime.now().date()
    max_allowed_end = today + timedelta(days=60)
    default_end = min(max_date, max_allowed_end)
    default_start = min(today, default_end)
    
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input(
            "Start Date",
            value=default_start,
            min_value=today,
            max_value=max_allowed_end,
            key="sql_start_date"
        )
    with col2:
        end_date = st.date_input(
            "End Date",
            value=default_end,
            min_value=start_date,
            max_value=min(start_date + timedelta(days=60), max_allowed_end),
            key="sql_end_date"
        )
    
    # Validate date ranges
    if start_date < today:
        st.error("❌ Start date must be at least today's date.")
        st.stop()
    if (end_date - start_date).days > 60:
        st.error("❌ End date must be within 60 days (2 months) from the start date.")
        st.stop()
    
    st.markdown("---")
    st.caption(f"📅 Analyzing: {start_date} → {end_date} ({(end_date - start_date).days + 1} days)")
    st.caption(f"📁 Data Source: Combined_All_Leave_Data.csv")

# ════════════════════════════════════════════════════════════════════════════════════
# DYNAMIC SQL QUERY FUNCTIONS
# ════════════════════════════════════════════════════════════════════════════════════

def build_daily_summary_query(start_dt, end_dt):
    """Daily leave summary with planned/unplanned breakdown"""
    return f"""
    SELECT
        CAST("From Date" AS DATE) AS Leave_Date,
        COUNT(DISTINCT EmpNo) AS Total_Employees_On_Leave,
        SUM(Days) AS Total_Leave_Days,
        COUNT(CASE WHEN Type = 'Planned' THEN 1 END) AS Planned_Events,
        COUNT(CASE WHEN Type = 'Un-Planned' THEN 1 END) AS Unplanned_Events,
        COUNT(DISTINCT CASE WHEN Type = 'Planned' THEN EmpNo END) AS Planned_Employees,
        COUNT(DISTINCT CASE WHEN Type = 'Un-Planned' THEN EmpNo END) AS Unplanned_Employees,
        ROUND(COUNT(CASE WHEN Type = 'Planned' THEN 1 END)::FLOAT / 
              NULLIF(COUNT(*), 0) * 100, 2) AS Planned_Percentage
    FROM read_csv_auto('Data/Combined_All_Leave_Data.csv')
    WHERE
        Status = 'Approved'
        AND CAST("From Date" AS DATE) >= DATE '{start_dt}'
        AND CAST("From Date" AS DATE) <= DATE '{end_dt}'
    GROUP BY Leave_Date
    ORDER BY Leave_Date
    """

def build_cost_centre_query(start_dt, end_dt):
    """Cost centre wise leave analysis"""
    return f"""
    SELECT
        "Cost Centre",
        COUNT(DISTINCT EmpNo) AS Unique_Employees,
        SUM(Days) AS Total_Leave_Days,
        COUNT(DISTINCT CAST("From Date" AS DATE)) AS Days_With_Leave,
        COUNT(CASE WHEN Type = 'Planned' THEN 1 END) AS Planned_Events,
        COUNT(CASE WHEN Type = 'Un-Planned' THEN 1 END) AS Unplanned_Events,
        ROUND(SUM(Days)::FLOAT / NULLIF(COUNT(DISTINCT EmpNo), 0), 2) AS Avg_Days_Per_Employee,
        ROUND(COUNT(CASE WHEN Type = 'Planned' THEN 1 END)::FLOAT / 
              NULLIF(COUNT(*), 0) * 100, 2) AS Planned_Percentage
    FROM read_csv_auto('Data/Combined_All_Leave_Data.csv')
    WHERE
        Status = 'Approved'
        AND CAST("From Date" AS DATE) >= DATE '{start_dt}'
        AND CAST("From Date" AS DATE) <= DATE '{end_dt}'
    GROUP BY "Cost Centre"
    ORDER BY Total_Leave_Days DESC
    """

def build_leave_type_query(start_dt, end_dt):
    """Leave type breakdown"""
    return f"""
    SELECT
        "Leave Type",
        COUNT(DISTINCT EmpNo) AS Unique_Employees,
        SUM(Days) AS Total_Leave_Days,
        COUNT(*) AS Leave_Events,
        COUNT(CASE WHEN Type = 'Planned' THEN 1 END) AS Planned_Count,
        COUNT(CASE WHEN Type = 'Un-Planned' THEN 1 END) AS Unplanned_Count,
        ROUND(AVG(Days), 2) AS Avg_Duration_Days
    FROM read_csv_auto('Data/Combined_All_Leave_Data.csv')
    WHERE
        Status = 'Approved'
        AND CAST("From Date" AS DATE) >= DATE '{start_dt}'
        AND CAST("From Date" AS DATE) <= DATE '{end_dt}'
    GROUP BY "Leave Type"
    ORDER BY Total_Leave_Days DESC
    """

def build_planned_vs_unplanned_query(start_dt, end_dt):
    """Planned vs Unplanned leave trends"""
    return f"""
    SELECT
        CAST("From Date" AS DATE) AS Leave_Date,
        COUNT(CASE WHEN Type = 'Planned' THEN 1 END) AS Planned_Events,
        COUNT(CASE WHEN Type = 'Un-Planned' THEN 1 END) AS Unplanned_Events,
        COUNT(DISTINCT CASE WHEN Type = 'Planned' THEN EmpNo END) AS Planned_Employees,
        COUNT(DISTINCT CASE WHEN Type = 'Un-Planned' THEN EmpNo END) AS Unplanned_Employees,
        SUM(CASE WHEN Type = 'Planned' THEN Days ELSE 0 END) AS Planned_Days,
        SUM(CASE WHEN Type = 'Un-Planned' THEN Days ELSE 0 END) AS Unplanned_Days
    FROM read_csv_auto('Data/Combined_All_Leave_Data.csv')
    WHERE
        Status = 'Approved'
        AND CAST("From Date" AS DATE) >= DATE '{start_dt}'
        AND CAST("From Date" AS DATE) <= DATE '{end_dt}'
    GROUP BY Leave_Date
    ORDER BY Leave_Date
    """

def build_special_leave_query(start_dt, end_dt):
    """Special Leave & Comp-Off analysis"""
    return f"""
    SELECT
        CAST("From Date" AS DATE) AS Leave_Date,
        "Leave Type",
        COUNT(DISTINCT EmpNo) AS Employees,
        SUM(Days) AS Total_Days,
        COUNT(*) AS Events
    FROM read_csv_auto('Data/Combined_All_Leave_Data.csv')
    WHERE
        Status = 'Approved'
        AND CAST("From Date" AS DATE) >= DATE '{start_dt}'
        AND CAST("From Date" AS DATE) <= DATE '{end_dt}'
        AND "Leave Type" IN ('Special Leave [Not Call ON Duty]', 'Comp-Off')
    GROUP BY Leave_Date, "Leave Type"
    ORDER BY Leave_Date, "Leave Type"
    """

def build_reason_query(start_dt, end_dt):
    """Leave reason analysis"""
    return f"""
    SELECT
        "Leave Type",
        "Cost Centre",
        Type,
        COUNT(DISTINCT EmpNo) AS Employees,
        SUM(Days) AS Total_Days,
        ROUND(AVG(Days), 2) AS Avg_Duration,
        COUNT(*) AS Events
    FROM read_csv_auto('Data/Combined_All_Leave_Data.csv')
    WHERE
        Status = 'Approved'
        AND CAST("From Date" AS DATE) >= DATE '{start_dt}'
        AND CAST("From Date" AS DATE) <= DATE '{end_dt}'
    GROUP BY "Leave Type", "Cost Centre", Type
    ORDER BY Total_Days DESC
    """

# ════════════════════════════════════════════════════════════════════════════════════
# EXECUTE QUERIES
# ════════════════════════════════════════════════════════════════════════════════════

def execute_query(query):
    """Execute DuckDB query safely"""
    try:
        con = duckdb.connect()
        return con.execute(query).df()
    except Exception as e:
        st.error(f"Query error: {e}")
        return pd.DataFrame()

# Load all data
with st.spinner("⏳ Loading data from CSV..."):
    df_daily = execute_query(build_daily_summary_query(start_date, end_date))
    df_cost_centre = execute_query(build_cost_centre_query(start_date, end_date))
    df_leave_type = execute_query(build_leave_type_query(start_date, end_date))
    df_planned_unplanned = execute_query(build_planned_vs_unplanned_query(start_date, end_date))
    df_special_leave = execute_query(build_special_leave_query(start_date, end_date))
    df_reason = execute_query(build_reason_query(start_date, end_date))

# ════════════════════════════════════════════════════════════════════════════════════
# TAB NAVIGATION (Same structure as streamlit_app.py)
# ════════════════════════════════════════════════════════════════════════════════════

tab_trends, tab_costcentre, tab_planned, tab_special, tab_reason, tab_explorer = st.tabs([
    "📈 Daily Leave Trends",
    "🏭 Cost Centre Analysis",
    "📊 Planned vs Unplanned",
    "🔵 Special Leave & Comp-Off",
    "🔍 Leave Reason Analysis",
    "📁 Data Explorer"
])

# ════════════════════════════════════════════════════════════════════════════════════
# TAB 1: DAILY LEAVE TRENDS
# ════════════════════════════════════════════════════════════════════════════════════

with tab_trends:
    st.subheader("📈 Daily Leave Trends")
    st.caption("Overview of leave patterns over the selected period")
    
    if df_daily.empty:
        st.warning("📭 No data available for selected period")
    else:
        # Key Metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric(
                "Avg Employees/Day",
                f"{df_daily['Total_Employees_On_Leave'].mean():.1f}",
                delta=f"Peak: {int(df_daily['Total_Employees_On_Leave'].max())}"
            )
        with col2:
            st.metric(
                "Total Leave Days",
                f"{int(df_daily['Total_Leave_Days'].sum())}",
                delta=f"{df_daily.shape[0]} days analysed"
            )
        with col3:
            planned_pct = df_daily['Planned_Percentage'].mean()
            st.metric(
                "Planned Leave %",
                f"{planned_pct:.1f}%",
                delta=f"{100-planned_pct:.1f}% unplanned"
            )
        with col4:
            st.metric(
                "Total Employees",
                f"{int(df_daily['Total_Employees_On_Leave'].sum())}",
                delta="unique on leave"
            )
        
        st.divider()
        
        # Charts
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Daily Leave Count Trend**")
            fig_daily = px.line(
                df_daily,
                x="Leave_Date",
                y="Total_Employees_On_Leave",
                markers=True,
                title="Employees on Leave Over Time",
                template="plotly_white",
                color_discrete_sequence=["#1f77b4"]
            )
            fig_daily.update_xaxes(tickangle=45)
            fig_daily.update_layout(height=400, hovermode="x unified", showlegend=False)
            st.plotly_chart(fig_daily, width="stretch")
        
        with col2:
            st.markdown("**Planned vs Unplanned Events**")
            fig_type = px.bar(
                df_daily.set_index('Leave_Date')[['Planned_Events', 'Unplanned_Events']],
                barmode='group',
                title="Daily Event Count: Planned vs Unplanned",
                template="plotly_white",
                color_discrete_map={
                    'Planned_Events': '#2ca02c',
                    'Unplanned_Events': '#d62728'
                }
            )
            fig_type.update_xaxes(tickangle=45)
            fig_type.update_layout(height=400, hovermode="x unified")
            st.plotly_chart(fig_type, width="stretch")
        
        # Data table
        st.markdown("**Daily Details**")
        st.dataframe(
            df_daily.style.format({
                'Leave_Date': str,
                'Total_Employees_On_Leave': '{:.0f}',
                'Total_Leave_Days': '{:.0f}',
                'Planned_Percentage': '{:.1f}%'
            }),
            width="stretch",
            hide_index=True
        )

# ════════════════════════════════════════════════════════════════════════════════════
# TAB 2: COST CENTRE ANALYSIS
# ════════════════════════════════════════════════════════════════════════════════════

with tab_costcentre:
    st.subheader("🏭 Cost Centre Wise Leave Analysis")
    st.caption("Identify which departments have highest leave volumes")
    
    if df_cost_centre.empty:
        st.warning("📭 No data available for selected period")
    else:
        # Key Metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Cost Centres", f"{len(df_cost_centre)}")
        with col2:
            st.metric("Total Leave Days", f"{int(df_cost_centre['Total_Leave_Days'].sum())}")
        with col3:
            st.metric("Unique Employees", f"{int(df_cost_centre['Unique_Employees'].sum())}")
        
        st.divider()
        
        # Charts
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Leave Days by Cost Centre (Top 15)**")
            top_cc = df_cost_centre.nlargest(15, 'Total_Leave_Days')
            fig_cc_days = px.bar(
                top_cc,
                x="Total_Leave_Days",
                y="Cost Centre",
                orientation='h',
                title="Top Cost Centres by Leave Days",
                template="plotly_white",
                color="Total_Leave_Days",
                color_continuous_scale="Blues"
            )
            fig_cc_days.update_layout(height=450, showlegend=False)
            st.plotly_chart(fig_cc_days, width="stretch")
        
        with col2:
            st.markdown("**Employees by Cost Centre (Top 15)**")
            top_emp = df_cost_centre.nlargest(15, 'Unique_Employees')
            fig_cc_emp = px.bar(
                top_emp,
                x="Unique_Employees",
                y="Cost Centre",
                orientation='h',
                title="Top Cost Centres by Employee Count",
                template="plotly_white",
                color="Unique_Employees",
                color_continuous_scale="Greens"
            )
            fig_cc_emp.update_layout(height=450, showlegend=False)
            st.plotly_chart(fig_cc_emp, width="stretch")
        
        # Data table
        st.markdown("**Cost Centre Details**")
        st.dataframe(
            df_cost_centre.style.format({
                'Unique_Employees': '{:.0f}',
                'Total_Leave_Days': '{:.0f}',
                'Days_With_Leave': '{:.0f}',
                'Avg_Days_Per_Employee': '{:.2f}',
                'Planned_Percentage': '{:.1f}%'
            }),
            width="stretch",
            hide_index=True
        )

# ════════════════════════════════════════════════════════════════════════════════════
# TAB 3: PLANNED VS UNPLANNED
# ════════════════════════════════════════════════════════════════════════════════════

with tab_planned:
    st.subheader("📊 Planned vs Unplanned Leave Analysis")
    st.caption("Assess leave predictability and workforce planning reliability")
    
    if df_planned_unplanned.empty:
        st.warning("📭 No data available for selected period")
    else:
        # Key Metrics
        planned_total = df_planned_unplanned['Planned_Days'].sum()
        unplanned_total = df_planned_unplanned['Unplanned_Days'].sum()
        planned_pct = (planned_total / (planned_total + unplanned_total) * 100) if (planned_total + unplanned_total) > 0 else 0
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Planned Days", f"{int(planned_total)}")
        with col2:
            st.metric("Unplanned Days", f"{int(unplanned_total)}")
        with col3:
            st.metric("Planned %", f"{planned_pct:.1f}%")
        with col4:
            st.metric("Unplanned %", f"{100-planned_pct:.1f}%")
        
        st.divider()
        
        # Charts
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Daily Breakdown: Planned vs Unplanned**")
            fig_pvu = px.bar(
                df_planned_unplanned,
                x="Leave_Date",
                y=["Planned_Days", "Unplanned_Days"],
                barmode="stack",
                title="Daily Leave Breakdown",
                template="plotly_white",
                color_discrete_map={
                    'Planned_Days': '#2ca02c',
                    'Unplanned_Days': '#d62728'
                }
            )
            fig_pvu.update_xaxes(tickangle=45)
            fig_pvu.update_layout(height=400, hovermode="x unified")
            st.plotly_chart(fig_pvu, width="stretch")
        
        with col2:
            st.markdown("**Distribution by Event Count**")
            fig_events = px.scatter(
                df_planned_unplanned,
                x="Planned_Events",
                y="Unplanned_Events",
                title="Planned vs Unplanned Events by Day",
                template="plotly_white",
                size="Planned_Employees",
                color_continuous_scale="Viridis"
            )
            fig_events.update_layout(height=400)
            st.plotly_chart(fig_events, width="stretch")
        
        # Data table
        st.markdown("**Daily Details**")
        st.dataframe(
            df_planned_unplanned.style.format({
                'Leave_Date': str,
                'Planned_Events': '{:.0f}',
                'Unplanned_Events': '{:.0f}',
                'Planned_Employees': '{:.0f}',
                'Unplanned_Employees': '{:.0f}',
                'Planned_Days': '{:.0f}',
                'Unplanned_Days': '{:.0f}'
            }),
            width="stretch",
            hide_index=True
        )

# ════════════════════════════════════════════════════════════════════════════════════
# TAB 4: SPECIAL LEAVE & COMP-OFF
# ════════════════════════════════════════════════════════════════════════════════════

with tab_special:
    st.subheader("🔵 Special Leave & Comp-Off Analysis")
    st.caption("Track special and compensatory leaves separately from operational absences")
    
    if df_special_leave.empty:
        st.info("ℹ️ No Special Leave or Comp-Off records in selected period")
    else:
        # Aggregate by type
        special_summary = df_special_leave.groupby('Leave Type').agg({
            'Employees': 'sum',
            'Total_Days': 'sum',
            'Events': 'sum'
        }).reset_index()
        
        # Key Metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Special Events", f"{int(df_special_leave['Events'].sum())}")
        with col2:
            st.metric("Special Leave Days", f"{int(df_special_leave['Total_Days'].sum())}")
        with col3:
            st.metric("Unique Employees", f"{int(df_special_leave['Employees'].sum())}")
        
        st.divider()
        
        # Charts
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Timeline: Special Leave & Comp-Off**")
            fig_special = px.line(
                df_special_leave,
                x="Leave_Date",
                y="Total_Days",
                color="Leave Type",
                markers=True,
                title="Daily Special Leave & Comp-Off Days",
                template="plotly_white"
            )
            fig_special.update_xaxes(tickangle=45)
            fig_special.update_layout(height=400, hovermode="x unified")
            st.plotly_chart(fig_special, width="stretch")
        
        with col2:
            st.markdown("**Breakdown by Type**")
            fig_pie = px.pie(
                special_summary,
                values="Total_Days",
                names="Leave Type",
                title="Special Leave vs Comp-Off Distribution",
                template="plotly_white"
            )
            fig_pie.update_layout(height=400)
            st.plotly_chart(fig_pie, width="stretch")
        
        # Data table
        st.markdown("**Daily Details**")
        st.dataframe(df_special_leave.sort_values('Leave_Date'), width="stretch", hide_index=True)

# ════════════════════════════════════════════════════════════════════════════════════
# TAB 5: LEAVE REASON ANALYSIS
# ════════════════════════════════════════════════════════════════════════════════════

with tab_reason:
    st.subheader("🔍 Leave Reason Analysis")
    st.caption("Understand leave patterns by type and cost centre")
    
    if df_reason.empty:
        st.warning("📭 No data available for selected period")
    else:
        # Key Metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Leave Types", f"{df_reason['Leave Type'].nunique()}")
        with col2:
            st.metric("Total Employees", f"{int(df_reason['Employees'].sum())}")
        with col3:
            st.metric("Total Events", f"{int(df_reason['Events'].sum())}")
        
        st.divider()
        
        # Charts
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Leave Days by Type**")
            leave_type_summary = df_reason.groupby('Leave Type').agg({
                'Total_Days': 'sum',
                'Employees': 'sum'
            }).reset_index().sort_values('Total_Days', ascending=False)
            
            fig_type = px.bar(
                leave_type_summary,
                x="Leave Type",
                y="Total_Days",
                title="Total Leave Days by Type",
                template="plotly_white",
                color="Total_Days",
                color_continuous_scale="Blues"
            )
            fig_type.update_xaxes(tickangle=45)
            fig_type.update_layout(height=400, showlegend=False)
            st.plotly_chart(fig_type, width="stretch")
        
        with col2:
            st.markdown("**Planned vs Unplanned by Leave Type**")
            type_breakdown = df_reason.groupby(['Leave Type', 'Type']).agg({
                'Total_Days': 'sum'
            }).reset_index()
            
            fig_breakdown = px.bar(
                type_breakdown,
                x="Leave Type",
                y="Total_Days",
                color="Type",
                barmode="group",
                title="Planned vs Unplanned by Leave Type",
                template="plotly_white"
            )
            fig_breakdown.update_xaxes(tickangle=45)
            fig_breakdown.update_layout(height=400)
            st.plotly_chart(fig_breakdown, width="stretch")
        
        # Data table
        st.markdown("**Detailed Leave Reason Data**")
        st.dataframe(
            df_reason.style.format({
                'Employees': '{:.0f}',
                'Total_Days': '{:.0f}',
                'Avg_Duration': '{:.2f}',
                'Events': '{:.0f}'
            }),
            width="stretch",
            hide_index=True
        )

# ════════════════════════════════════════════════════════════════════════════════════
# TAB 6: DATA EXPLORER
# ════════════════════════════════════════════════════════════════════════════════════

with tab_explorer:
    st.subheader("📁 SQL Data Explorer")
    st.caption("Raw data view and detailed inspection")
    
    # Options for data exploration
    col1, col2 = st.columns(2)
    with col1:
        view_option = st.selectbox(
            "Select View",
            [
                "Daily Summary",
                "Cost Centre Details",
                "Leave Type Details",
                "Planned vs Unplanned",
                "Special Leave Details",
                "Reason Analysis"
            ]
        )
    
    st.divider()
    
    # Display selected view
    if view_option == "Daily Summary":
        st.markdown(f"**Records: {len(df_daily)}**")
        st.dataframe(df_daily, width="stretch", hide_index=True)
        
    elif view_option == "Cost Centre Details":
        st.markdown(f"**Records: {len(df_cost_centre)}**")
        st.dataframe(df_cost_centre, width="stretch", hide_index=True)
        
    elif view_option == "Leave Type Details":
        st.markdown(f"**Records: {len(df_leave_type)}**")
        st.dataframe(df_leave_type, width="stretch", hide_index=True)
        
    elif view_option == "Planned vs Unplanned":
        st.markdown(f"**Records: {len(df_planned_unplanned)}**")
        st.dataframe(df_planned_unplanned, width="stretch", hide_index=True)
        
    elif view_option == "Special Leave Details":
        st.markdown(f"**Records: {len(df_special_leave)}**")
        st.dataframe(df_special_leave, width="stretch", hide_index=True)
        
    else:  # Reason Analysis
        st.markdown(f"**Records: {len(df_reason)}**")
        st.dataframe(df_reason, width="stretch", hide_index=True)

# ════════════════════════════════════════════════════════════════════════════════════
# FOOTER
# ════════════════════════════════════════════════════════════════════════════════════

st.divider()
st.caption(
    "📊 **SQL Analytics Dashboard** | CSV-Based Data | Dynamic Date Filtering | "
    f"Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
)

