import streamlit as st
from ui import (
    render_sidebar,
    render_analysis_page,
    render_history_page,
    render_knowledge_page,
    render_dashboard_page
)

PAGE_TITLES = {
    "dashboard": "📊 AIOps 智能根因分析平台 - 故障趋势监控",
    "analysis": "🔍 AIOps 智能根因分析平台",
    "history": "📜 AIOps 智能根因分析平台 - 历史报告",
    "knowledge": "📚 AIOps 智能根因分析平台 - 知识库管理"
}

PAGE_DESCRIPTIONS = {
    "dashboard": "查看系统故障趋势和高频故障统计",
    "analysis": "💡 直接输入告警描述，系统将自动识别故障类型并进行多轮分析。",
    "history": "查看历史故障分析报告。",
    "knowledge": "管理和编辑故障知识库。"
}

st.set_page_config(page_title="AIOps 智能根因分析平台", layout="wide")

if "selected_page" not in st.session_state:
    st.session_state.selected_page = "🔍 故障分析"
if "current_page" not in st.session_state:
    st.session_state.current_page = "analysis"

config = render_sidebar()

current_page = st.session_state.current_page

st.title(PAGE_TITLES.get(current_page, "AIOps 智能根因分析平台"))
st.markdown("---")

st.info(PAGE_DESCRIPTIONS.get(current_page, ""))

if current_page == "dashboard":
    render_dashboard_page()
elif current_page == "analysis":
    render_analysis_page(config)
elif current_page == "history":
    render_history_page()
elif current_page == "knowledge":
    render_knowledge_page()