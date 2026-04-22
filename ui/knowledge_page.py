import streamlit as st
import json
from knowledge_base.knowledge_manager import get_knowledge_manager


def render_knowledge_page():
    """渲染知识库管理页面"""
    st.header("📚 知识库管理")
    
    km = get_knowledge_manager()
    
    tab1, tab2, tab3 = st.tabs(["📖 故障模式库", "✏️ 编辑知识库", "🔧 工具"])
    
    with tab1:
        _render_fault_patterns(km)
    
    with tab2:
        _render_edit_pattern(km)
    
    with tab3:
        _render_tools(km)


def _render_fault_patterns(km):
    """渲染故障模式列表"""
    st.subheader("已定义故障模式")
    for fault_type, pattern in km.fault_patterns.items():
        with st.expander(f"🔹 {fault_type.upper()} - {pattern['name']}", expanded=False):
            st.write(f"**典型指标**: {', '.join(pattern['typical_metrics'])}")
            st.write(f"**典型服务**: {', '.join(pattern['typical_services'])}")
            
            st.write("**常见根因**:")
            for root in pattern['common_roots']:
                st.write(f"- {root}")
            
            st.write("**典型传播路径**:")
            st.info(pattern['propagation_path'])
            
            st.write("**缓解措施**:")
            for mitigation in pattern['mitigation']:
                st.write(f"- {mitigation}")


def _render_edit_pattern(km):
    """渲染编辑故障模式"""
    st.subheader("编辑故障模式")
    fault_type_edit = st.selectbox("选择故障类型:", list(km.fault_patterns.keys()))
    
    if fault_type_edit:
        pattern = km.fault_patterns[fault_type_edit]
        
        col1, col2 = st.columns(2)
        with col1:
            new_name = st.text_input("故障名称:", value=pattern['name'])
            new_metrics = st.text_area("典型指标 (每行一个):", value='\n'.join(pattern['typical_metrics']))
            new_services = st.text_area("典型服务 (每行一个):", value='\n'.join(pattern['typical_services']))
        
        with col2:
            new_roots = st.text_area("常见根因 (每行一个):", value='\n'.join(pattern['common_roots']))
            new_propagation = st.text_area("传播路径:", value=pattern['propagation_path'])
            new_mitigations = st.text_area("缓解措施 (每行一个):", value='\n'.join(pattern['mitigation']))
        
        if st.button("💾 保存修改", width='stretch'):
            km.fault_patterns[fault_type_edit] = {
                "name": new_name,
                "typical_metrics": [m.strip() for m in new_metrics.split('\n') if m.strip()],
                "typical_services": [s.strip() for s in new_services.split('\n') if s.strip()],
                "common_roots": [r.strip() for r in new_roots.split('\n') if r.strip()],
                "propagation_path": new_propagation,
                "mitigation": [m.strip() for m in new_mitigations.split('\n') if m.strip()]
            }
            km.save_learned_patterns()
            st.success("知识库已更新！")


def _render_tools(km):
    """渲染知识库工具"""
    st.subheader("知识库工具")
    if st.button("🔄 从数据集重建知识库", width='stretch'):
        with st.spinner("正在分析所有数据集..."):
            results = km.build_knowledge_from_all_datasets()
            st.success("知识库重建完成！")
            st.json(results, expanded=False)
    
    if st.button("📋 导出知识库", width='stretch'):
        kb_json = json.dumps(km.fault_patterns, ensure_ascii=False, indent=2)
        st.download_button(
            label="下载知识库JSON",
            data=kb_json,
            file_name="fault_patterns.json",
            mime="application/json",
            width='stretch'
        )