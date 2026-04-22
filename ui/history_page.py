import streamlit as st
import os
import glob


def render_history_page():
    """渲染历史报告页面"""
    st.header("📜 历史分析报告")
    
    report_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "reports")
    if os.path.exists(report_dir):
        list_of_files = glob.glob(os.path.join(report_dir, '*.md'))
        if list_of_files:
            list_of_files.sort(key=os.path.getctime, reverse=True)
            
            st.info(f"共找到 {len(list_of_files)} 份历史报告")
            
            selected_report = st.selectbox(
                "选择报告查看:",
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
                        label="📥 下载报告",
                        data=report_content,
                        file_name=os.path.basename(selected_report),
                        mime="text/markdown",
                        width='stretch'
                    )
                    if st.button("🗑️ 删除报告", width='stretch', type="secondary"):
                        os.remove(selected_report)
                        st.rerun()
        else:
            st.warning("暂无历史报告，请先运行故障分析。")
    else:
        st.warning("报告目录不存在，请先运行故障分析。")