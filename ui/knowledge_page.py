import streamlit as st
import json
from knowledge_base.knowledge_manager import get_knowledge_manager


def render_knowledge_page():
    """Render knowledge base management page"""
    st.header("Knowledge Base Management")
    
    km = get_knowledge_manager()
    
    tab1, tab2, tab3 = st.tabs(["Fault Patterns", "Edit Knowledge", "Tools"])
    
    with tab1:
        _render_fault_patterns(km)
    
    with tab2:
        _render_edit_pattern(km)
    
    with tab3:
        _render_tools(km)


def _render_fault_patterns(km):
    """Render fault pattern list"""
    st.subheader("Defined Fault Patterns")
    for fault_type, pattern in km.fault_patterns.items():
        with st.expander(f"{fault_type.upper()} - {pattern['name']}", expanded=False):
            st.write(f"**Typical Metrics**: {', '.join(pattern['typical_metrics'])}")
            st.write(f"**Typical Services**: {', '.join(pattern['typical_services'])}")
            
            st.write("**Common Root Causes**:")
            for root in pattern['common_roots']:
                st.write(f"- {root}")
            
            st.write("**Typical Propagation Path**:")
            st.info(pattern['propagation_path'])
            
            st.write("**Mitigation**:")
            for mitigation in pattern['mitigation']:
                st.write(f"- {mitigation}")


def _render_edit_pattern(km):
    """Render edit fault pattern"""
    st.subheader("Edit Fault Pattern")
    fault_type_edit = st.selectbox("Select fault type:", list(km.fault_patterns.keys()))
    
    if fault_type_edit:
        pattern = km.fault_patterns[fault_type_edit]
        
        col1, col2 = st.columns(2)
        with col1:
            new_name = st.text_input("Fault name:", value=pattern['name'])
            new_metrics = st.text_area("Typical metrics (one per line):", value='\n'.join(pattern['typical_metrics']))
            new_services = st.text_area("Typical services (one per line):", value='\n'.join(pattern['typical_services']))
        
        with col2:
            new_roots = st.text_area("Common root causes (one per line):", value='\n'.join(pattern['common_roots']))
            new_propagation = st.text_area("Propagation path:", value=pattern['propagation_path'])
            new_mitigations = st.text_area("Mitigation (one per line):", value='\n'.join(pattern['mitigation']))
        
        if st.button("Save Changes", width='stretch'):
            km.fault_patterns[fault_type_edit] = {
                "name": new_name,
                "typical_metrics": [m.strip() for m in new_metrics.split('\n') if m.strip()],
                "typical_services": [s.strip() for s in new_services.split('\n') if s.strip()],
                "common_roots": [r.strip() for r in new_roots.split('\n') if r.strip()],
                "propagation_path": new_propagation,
                "mitigation": [m.strip() for m in new_mitigations.split('\n') if m.strip()]
            }
            km.save_learned_patterns()
            st.success("Knowledge base updated!")


def _render_tools(km):
    """Render knowledge base tools"""
    st.subheader("Knowledge Base Tools")
    if st.button("Rebuild Knowledge Base", width='stretch'):
        with st.spinner("Analyzing all datasets..."):
            results = km.build_knowledge_from_all_datasets()
            st.success("Knowledge base rebuilt!")
            st.json(results, expanded=False)
    
    if st.button("Export Knowledge Base", width='stretch'):
        kb_json = json.dumps(km.fault_patterns, ensure_ascii=False, indent=2)
        st.download_button(
            label="Download Knowledge Base JSON",
            data=kb_json,
            file_name="fault_patterns.json",
            mime="application/json",
            width='stretch'
        )