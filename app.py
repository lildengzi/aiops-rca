import streamlit as st
from ui import (
    render_sidebar,
    render_analysis_page,
    render_history_page,
    render_knowledge_page,
    render_dashboard_page,
    render_feedback_page,
    render_monitoring_page,
)

PAGE_TITLES = {
    "dashboard": "AIOps - Fault Trend Monitor",
    "analysis": "AIOps - Fault Analysis",
    "monitoring": "AIOps - Monitoring Data",
    "history": "AIOps - History Reports",
    "knowledge": "AIOps - Knowledge Base",
    "feedback": "AIOps - User Feedback"
}

PAGE_DESCRIPTIONS = {
    "dashboard": "View system fault trends and high-frequency fault statistics",
    "analysis": "Enter alert description, system will auto-detect fault type.",
    "monitoring": "Upload and manage monitoring data for RCA analysis.",
    "history": "View historical fault analysis reports.",
    "knowledge": "Manage fault knowledge base.",
    "feedback": "Submit diagnostic feedback to help improve the model."
}

st.set_page_config(page_title="AIOps Fault Analysis Platform", layout="wide")

if "selected_page" not in st.session_state:
    st.session_state.selected_page = "analysis"
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
elif current_page == "monitoring":
    render_monitoring_page()
elif current_page == "history":
    render_history_page()
elif current_page == "knowledge":
    render_knowledge_page()
elif current_page == "feedback":
    render_feedback_page()