import streamlit as st
import subprocess
import sys
import os
import glob
import time


AGENT_ORDER = ["故障类型检测", "运维专家", "指标分析专家", "日志分析专家", "链路分析专家", "数据汇总", "值班长", "运营专家"]


def render_analysis_page(config):
    """渲染故障分析页面"""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "latest_report_context" not in st.session_state:
        st.session_state.latest_report_context = None

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    prompt = None
    
    input_tab1, input_tab2, input_tab3 = st.tabs(["Text Input", "Voice Input", "Image Upload"])
    
    with input_tab1:
        prompt = st.chat_input("例如：过去1小时frontend服务CPU飙升，请分析根因")
    
    with input_tab2:
        from ui.voice_input import render_voice_input
        voice_result = render_voice_input()
        if voice_result:
            prompt = voice_result
    
    with input_tab3:
        from ui.image_input import render_image_input
        image_result = render_image_input()
        if image_result:
            prompt = image_result

    if prompt:
        _run_analysis(prompt, config)
    elif st.session_state.latest_report_context:
        _render_persisted_feedback_widget()


def _render_persisted_feedback_widget():
    """在 Streamlit 重跑后继续显示当前报告对应的反馈组件。"""
    report_context = st.session_state.get("latest_report_context")
    if not report_context:
        return

    st.markdown("---")
    st.caption(f"Current report: {report_context['report_name']}")

    from .feedback_page import render_feedback_widget
    render_feedback_widget(report_context["fault_id"], report_context["original_diagnosis"])


def _run_analysis(prompt, config):
    """执行故障分析"""
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        st.info("Fault type will be auto-detected from data analysis")
        
        cmd = [sys.executable, "main.py", "--query", prompt, "--max-iter", str(config["max_iter"])]
        if not config["full_analysis"]:
            cmd.append("--disable-full-analysis")
        
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, shell=False)

        col_progress, col_logs = st.columns([1, 2])
        
        with col_progress:
            progress_bar = st.progress(0)
            status_text = st.empty()
            completed_count = 0
            total_agents = len(AGENT_ORDER)
            agent_progress = {}
        
        with col_logs:
            log_container = st.empty()
            log_container.code("等待分析启动...", language="text")
        
        full_output = ""
        start_time = time.time()

        while True:
            line = process.stdout.readline()
            if line:
                full_output += line
                
                if "[完成]" in line and "任务完成" in line:
                    for agent_name in AGENT_ORDER:
                        if agent_name in line and agent_name not in agent_progress:
                            agent_progress[agent_name] = True
                            completed_count += 1
                            break
                
                with col_progress:
                    progress_percent = min(int((completed_count / total_agents) * 100), 99)
                    progress_bar.progress(progress_percent)
                    
                    status_info = "Running...\n\n"
                    status_info += "**智能体状态:**\n"
                    for agent in AGENT_ORDER:
                        if agent in agent_progress:
                            status_info += f"✅ {agent}\n"
                        else:
                            status_info += f"⏳ {agent}\n"
                    
                    current_agent = AGENT_ORDER[completed_count] if completed_count < total_agents else None
                    if current_agent:
                        status_info += f"\n**正在执行:**\n{current_agent}..."
                    else:
                        status_info += f"\n完成: {completed_count}/{total_agents}"
                    
                    status_text.markdown(status_info)
                
                with col_logs:
                    log_container.code(full_output[-5000:], language="text")
            else:
                if process.poll() is not None:
                    break
                time.sleep(0.05)

        returncode = process.wait()
        
        with col_progress:
            progress_bar.progress(100)
            status_text.markdown("✅ 分析完成!")
        
        with col_logs:
            log_container.code(full_output, language="text")
        
        if returncode != 0:
            st.error(f"⚠️ 分析进程异常退出，返回码: {returncode}")
            with st.expander("View Error Log", expanded=True):
                st.code(full_output, language="text")
            st.session_state.messages.append({"role": "assistant", "content": "❌ 分析执行失败，请查看错误日志。"})
            st.stop()

        _show_report(start_time, full_output, col_progress, col_logs)


def _show_report(start_time, full_output, col_progress=None, col_logs=None):
    """展示分析报告"""
    if col_progress:
        col_progress.empty()
    
    st.caption("Analysis Log")
    st.code(full_output, language="text")
    
    report_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "reports")
    latest_report = None
    
    if os.path.exists(report_dir):
        list_of_files = glob.glob(os.path.join(report_dir, '*.md'))
        new_reports = [f for f in list_of_files if os.path.getctime(f) > start_time]
        
        if new_reports:
            latest_report = max(new_reports, key=os.path.getctime)
        else:
            new_reports = [f for f in list_of_files if os.path.getctime(f) > start_time - 2]
            if new_reports:
                latest_report = max(new_reports, key=os.path.getctime)
    
    if latest_report:
        with st.expander("View Raw Log", expanded=False):
            st.code(full_output)
        
        st.success(f"✅ 根因分析报告已生成：`{os.path.basename(latest_report)}`")
        
        with open(latest_report, 'r', encoding='utf-8') as f:
            report_content = f.read()
        
        st.markdown("---")
        st.markdown(report_content)
        
        st.download_button(
            label="Download Report",
            data=report_content,
            file_name=os.path.basename(latest_report),
            mime="text/markdown",
            width='stretch'
        )
        
        st.session_state.messages.append({"role": "assistant", "content": report_content})
        
        fault_id = os.path.basename(latest_report).replace(".md", "")
        st.session_state.latest_report_context = {
            "fault_id": fault_id,
            "original_diagnosis": report_content[:500],
            "report_name": os.path.basename(latest_report),
        }

        from .feedback_page import render_feedback_widget
        render_feedback_widget(fault_id, report_content[:500])
    else:
        st.error("❌ 分析执行完成但未生成报告文件")
        with st.expander("View Full Log", expanded=True):
            st.code(full_output, language="text")
        st.info("可能的原因：\n"
                "1. LLM API 调用失败或超时\n"
                "2. 工作流执行异常中断\n"
                "3. 报告保存时发生错误\n"
                "4. 迭代过程未达到收敛条件")
        st.session_state.messages.append({"role": "assistant", "content": "❌ 分析完成但未生成报告，请查看日志。"})