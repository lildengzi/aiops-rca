import streamlit as st
import os
import glob


def render_history_page():
    """Render history reports page"""
    st.header("Historical Analysis Reports")
    
    report_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "reports")
    if os.path.exists(report_dir):
        list_of_files = glob.glob(os.path.join(report_dir, '*.md'))
        if list_of_files:
            list_of_files.sort(key=os.path.getctime, reverse=True)
            
            st.info(f"Found {len(list_of_files)} historical reports")
            
            selected_report = st.selectbox(
                "Select report to view:",
                list_of_files,
                format_func=lambda x: os.path.basename(x)
            )
            
            if selected_report:
                with open(selected_report, 'r', encoding='utf-8') as f:
                    report_content = f.read()
                
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown("---")
                    st.markdown(report_content)
                with col2:
                    st.download_button(
                        label="Download Report",
                        data=report_content,
                        file_name=os.path.basename(selected_report),
                        mime="text/markdown",
                        width='stretch'
                    )
                    if st.button("Delete Report", width='stretch', type="secondary"):
                        os.remove(selected_report)
                        st.rerun()
        else:
            st.warning("No historical reports. Please run fault analysis first.")
    else:
        st.warning("Report directory does not exist. Please run fault analysis first.")