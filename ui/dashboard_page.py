import streamlit as st
import json
import os
import sys
from datetime import datetime
import pandas as pd


def render_dashboard_page():
    """渲染故障趋势和统计页面"""
    st.header("📊 故障趋势与高频故障统计")
    
    app_dir = os.path.dirname(os.path.dirname(__file__))
    sys.path.insert(0, app_dir)
    from data_stats import get_dashboard_data, analyze_fault_trends, generate_mock_realtime_data
    
    col_d1, col_d2 = st.columns([2, 1])
    with col_d1:
        time_range = st.selectbox("时间范围", ["最近1小时", "最近6小时", "最近24小时", "最近7天"], index=2)
    with col_d2:
        st.write("")
        if st.button("🔄 刷新数据", width='stretch'):
            st.rerun()
    
    hours_map = {"最近1小时": 1, "最近6小时": 6, "最近24小时": 24, "最近7天": 168}
    hours = hours_map.get(time_range, 24)
    
    trend_data = generate_mock_realtime_data(hours=hours)
    trends = analyze_fault_trends(trend_data)
    
    st.markdown("---")
    st.subheader("📈 故障趋势图")
    
    if trends["labels"]:
        chart_data = pd.DataFrame({
            "时间": trends["labels"],
            "平均CPU使用率": trends["values"]
        })
        
        import altair as alt
        base = alt.Chart(chart_data).encode(
            x=alt.X("时间", title=None, sort=None),
            y=alt.Y("平均CPU使用率", title="CPU使用率 (%)", scale=alt.Scale(domain=[0, 100]))
        )
        
        line = base.mark_line(color="#FF4B4B", point=True).encode(
            tooltip=["时间", "平均CPU使用率"]
        )
        
        rule = base.mark_rule(color="gray", strokeDash=[4,4]).encode(
            y=alt.Y(datum=70)
        )
        
        st.altair_chart(line + rule, width='stretch')
        
        col_t1, col_t2, col_t3 = st.columns(3)
        with col_t1:
            st.metric("数据点数", trends.get("total_points", 0))
        with col_t2:
            st.metric("检测故障数", trends.get("fault_count", 0))
        with col_t3:
            avg_cpu = sum(trends["values"]) / len(trends["values"]) if trends["values"] else 0
            st.metric("平均CPU", f"{avg_cpu:.1f}%")
    else:
        st.info("暂无趋势数据")
    
    st.markdown("---")
    st.subheader("🔍 高频故障统计")
    
    col_s1, col_s2 = st.columns(2)
    
    with col_s1:
        st.markdown("**故障类型分布**")
        fault_types = [
            {"name": "CPU", "count": int(trends.get("fault_count", 0) * 0.4)},
            {"name": "内存", "count": int(trends.get("fault_count", 0) * 0.3)},
            {"name": "延迟", "count": int(trends.get("fault_count", 0) * 0.2)},
            {"name": "网络", "count": int(trends.get("fault_count", 0) * 0.1)},
        ]
        fault_types = [f for f in fault_types if f["count"] > 0]
        if not fault_types:
            fault_types = [{"name": "正常", "count": 100}]
        
        ft_df = pd.DataFrame(fault_types)
        if not ft_df.empty:
            bar_chart = alt.Chart(ft_df).encode(
                x=alt.X("count", title="次数"),
                y=alt.Y("name", title=None, sort="-x"),
                color=alt.Color("name", legend=None)
            ).mark_bar().properties(height=150)
            st.altair_chart(bar_chart, width='stretch')
    
    with col_s2:
        st.markdown("**高频服务故障**")
        services = [
            {"name": "frontend", "count": int(trends.get("fault_count", 0) * 0.25)},
            {"name": "checkoutservice", "count": int(trends.get("fault_count", 0) * 0.2)},
            {"name": "paymentservice", "count": int(trends.get("fault_count", 0) * 0.18)},
            {"name": "cartservice", "count": int(trends.get("fault_count", 0) * 0.15)},
            {"name": "redis", "count": int(trends.get("fault_count", 0) * 0.12)},
        ]
        services = [s for s in services if s["count"] > 0]
        if not services:
            services = [{"name": "无故障", "count": 1}]
        
        svc_df = pd.DataFrame(services)
        if not svc_df.empty:
            bar_chart2 = alt.Chart(svc_df).encode(
                x=alt.X("count", title="次数"),
                y=alt.Y("name", title=None, sort="-x"),
                color=alt.Color("name", legend=None)
            ).mark_bar().properties(height=150)
            st.altair_chart(bar_chart2, width='stretch')
    
    st.markdown("---")
    st.subheader("📋 历史故障记录")
    
    st.info(f"基于 {trends.get('total_points', 0)} 个数据点的模拟分析")
    st.caption(f"数据生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")