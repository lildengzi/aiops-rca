import streamlit as st

PAGE_OPTIONS = ["Fault Trend", "Fault Analysis", "Monitoring Data", "History", "Knowledge Base", "Feedback"]
PAGE_KEYS = {
    "Fault Trend": "dashboard",
    "Fault Analysis": "analysis",
    "Monitoring Data": "monitoring",
    "History": "history",
    "Knowledge Base": "knowledge",
    "Feedback": "feedback"
}


def render_sidebar():
    """Render sidebar navigation"""
    if "selected_page" not in st.session_state:
        st.session_state.selected_page = "Fault Analysis"
    
    st.sidebar.header("Navigation")
    
    selected = st.sidebar.selectbox(
        "Select function:",
        PAGE_OPTIONS,
        index=PAGE_OPTIONS.index(st.session_state.selected_page) if st.session_state.selected_page in PAGE_OPTIONS else 1,
        key="page_selector"
    )
    
    if selected != st.session_state.selected_page:
        st.session_state.selected_page = selected
    
    st.session_state.current_page = PAGE_KEYS[st.session_state.selected_page]
    
    st.sidebar.markdown("---")
    
    config = {"max_iter": 2, "fault_type": "Auto", "full_analysis": True, "show_raw_logs": False}
    
    if st.session_state.current_page == "analysis":
        st.sidebar.header("Analysis Config")
        config["max_iter"] = st.sidebar.slider("Max iterations", 1, 5, 2)
        config["fault_type"] = st.sidebar.selectbox(
            "Force fault type (optional)", 
            ["Auto", "cpu", "delay", "disk", "loss", "mem"]
        )
        config["full_analysis"] = st.sidebar.checkbox(
            "Full analysis mode", 
            value=True, 
            help="Analyze all services and metrics"
        )
        config["show_raw_logs"] = st.sidebar.checkbox("Show raw logs", value=False)
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("System Status")
    st.sidebar.info("Multi-agent system ready")
    st.sidebar.success("Knowledge base loaded")
    
    return config