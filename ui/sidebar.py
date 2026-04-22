import streamlit as st

PAGE_OPTIONS = ["📊 故障趋势", "🔍 故障分析", "📜 历史报告", "📚 知识库管理"]
PAGE_KEYS = {
    "📊 故障趋势": "dashboard",
    "🔍 故障分析": "analysis",
    "📜 历史报告": "history",
    "📚 知识库管理": "knowledge"
}


def render_sidebar():
    """渲染侧边栏导航"""
    if "selected_page" not in st.session_state:
        st.session_state.selected_page = "🔍 故障分析"
    
    st.sidebar.header("📋 导航菜单")
    
    selected = st.sidebar.selectbox(
        "选择功能:",
        PAGE_OPTIONS,
        index=PAGE_OPTIONS.index(st.session_state.selected_page),
        key="page_selector"
    )
    
    if selected != st.session_state.selected_page:
        st.session_state.selected_page = selected
    
    st.session_state.current_page = PAGE_KEYS[st.session_state.selected_page]
    
    st.sidebar.markdown("---")
    
    config = {"max_iter": 2, "fault_type": "自动识别", "full_analysis": True, "show_raw_logs": False}
    
    if st.session_state.current_page == "analysis":
        st.sidebar.header("⚙️ 分析配置")
        config["max_iter"] = st.sidebar.slider("最大迭代次数 (max-iter)", 1, 5, 2)
        config["fault_type"] = st.sidebar.selectbox(
            "强制指定故障类型 (可选)", 
            ["自动识别", "cpu", "delay", "disk", "loss", "mem"]
        )
        config["full_analysis"] = st.sidebar.checkbox(
            "启用全指标分析模式", 
            value=True, 
            help="分析所有服务的所有指标，而非仅目标服务"
        )
        config["show_raw_logs"] = st.sidebar.checkbox("显示原始分析日志", value=False)
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("📊 系统状态")
    st.sidebar.info("✅ 多智能体系统就绪")
    st.sidebar.success("🔍 知识库已加载")
    
    return config