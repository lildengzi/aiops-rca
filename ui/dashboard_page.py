import streamlit as st
import os
import sys
from datetime import datetime
import pandas as pd


def render_dashboard_page():
    """Render fault trend and statistics page"""
    st.header("Fault Trend and Statistics")
    
    app_dir = os.path.dirname(os.path.dirname(__file__))
    sys.path.insert(0, app_dir)
    from data_stats import get_dashboard_data, analyze_fault_trends, generate_mock_realtime_data
    
    col_d1, col_d2 = st.columns([2, 1])
    with col_d1:
        time_range = st.selectbox("Time Range", ["Last 1 hour", "Last 6 hours", "Last 24 hours", "Last 7 days"], index=2)
    with col_d2:
        st.write("")
        if st.button("Refresh", width='stretch'):
            st.rerun()
    
    hours_map = {"Last 1 hour": 1, "Last 6 hours": 6, "Last 24 hours": 24, "Last 7 days": 168}
    hours = hours_map.get(time_range, 24)
    
    trend_data = generate_mock_realtime_data(hours=hours)
    trends = analyze_fault_trends(trend_data)
    
    st.markdown("---")
    st.subheader("Fault Trend Chart")
    
    if trends["labels"]:
        chart_data = pd.DataFrame({
            "Time": trends["labels"],
            "Avg CPU": trends["values"]
        })
        
        import altair as alt
        base = alt.Chart(chart_data).encode(
            x=alt.X("Time", title=None, sort=None),
            y=alt.Y("Avg CPU", title="CPU Usage (%)", scale=alt.Scale(domain=[0, 100]))
        )
        
        line = base.mark_line(color="#FF4B4B", point=True).encode(
            tooltip=["Time", "Avg CPU"]
        )
        
        rule = base.mark_rule(color="gray", strokeDash=[4,4]).encode(
            y=alt.Y(datum=70)
        )
        
        st.altair_chart(line + rule, width='stretch')
        
        col_t1, col_t2, col_t3 = st.columns(3)
        with col_t1:
            st.metric("Data Points", trends.get("total_points", 0))
        with col_t2:
            st.metric("Faults Detected", trends.get("fault_count", 0))
        with col_t3:
            avg_cpu = sum(trends["values"]) / len(trends["values"]) if trends["values"] else 0
            st.metric("Avg CPU", f"{avg_cpu:.1f}%")
    else:
        st.info("No trend data available")
    
    st.markdown("---")
    st.subheader("High Frequency Fault Statistics")
    
    col_s1, col_s2 = st.columns(2)
    
    with col_s1:
        st.markdown("**Fault Type Distribution**")
        fault_types = [
            {"name": "CPU", "count": int(trends.get("fault_count", 0) * 0.4)},
            {"name": "Memory", "count": int(trends.get("fault_count", 0) * 0.3)},
            {"name": "Latency", "count": int(trends.get("fault_count", 0) * 0.2)},
            {"name": "Network", "count": int(trends.get("fault_count", 0) * 0.1)},
        ]
        fault_types = [f for f in fault_types if f["count"] > 0]
        if not fault_types:
            fault_types = [{"name": "Normal", "count": 100}]
        
        ft_df = pd.DataFrame(fault_types)
        if not ft_df.empty:
            bar_chart = alt.Chart(ft_df).encode(
                x=alt.X("count", title="Count"),
                y=alt.Y("name", title=None, sort="-x"),
                color=alt.Color("name", legend=None)
            ).mark_bar().properties(height=150)
            st.altair_chart(bar_chart, width='stretch')
    
    with col_s2:
        st.markdown("**High Frequency Service Faults**")
        services = [
            {"name": "frontend", "count": int(trends.get("fault_count", 0) * 0.25)},
            {"name": "checkoutservice", "count": int(trends.get("fault_count", 0) * 0.2)},
            {"name": "paymentservice", "count": int(trends.get("fault_count", 0) * 0.18)},
            {"name": "cartservice", "count": int(trends.get("fault_count", 0) * 0.15)},
            {"name": "redis", "count": int(trends.get("fault_count", 0) * 0.12)},
        ]
        services = [s for s in services if s["count"] > 0]
        if not services:
            services = [{"name": "No Fault", "count": 1}]
        
        svc_df = pd.DataFrame(services)
        if not svc_df.empty:
            bar_chart2 = alt.Chart(svc_df).encode(
                x=alt.X("count", title="Count"),
                y=alt.Y("name", title=None, sort="-x"),
                color=alt.Color("name", legend=None)
            ).mark_bar().properties(height=150)
            st.altair_chart(bar_chart2, width='stretch')
    
    st.markdown("---")
    st.subheader("Historical Fault Records")
    
    st.info(f"Simulated analysis based on {trends.get('total_points', 0)} data points")
    st.caption(f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")