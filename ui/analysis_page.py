import streamlit as st
import subprocess
import sys
import os
import glob
import time


def render_analysis_page(config):
    """渲染故障分析页面"""
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    prompt = None
    
    input_tab1, input_tab2, input_tab3 = st.tabs(["💬 文本输入", "🎤 语音输入", "🖼️ 图表上传"])
    
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


def _run_analysis(prompt, config):
    """执行故障分析"""
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        start_time = time.time()
        
        with st.status("🚀 正在启动 AIOps 多智能体分析...", expanded=True) as status:
            cmd = [sys.executable, "main.py", "--query", prompt, "--max-iter", str(config["max_iter"])]
            if not config["full_analysis"]:
                cmd.append("--disable-full-analysis")
            
            st.info("🔍 故障类型将根据数据分析自动识别")
            
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, shell=False)

            output_container = st.empty()
            full_output = ""
            agent_progress = {}

            while True:
                line = process.stdout.readline()
                if line:
                    full_output += line
                    
                    if "[完成]" in line and "任务完成" in line:
                        for agent_name in ["运维专家", "指标分析专家", "日志分析专家", "链路分析专家", "数据汇总", "值班长", "运营专家"]:
                            if agent_name in line:
                                agent_progress[agent_name] = "[✓]"
                    
                    if config["show_raw_logs"]:
                        output_container.code(full_output[-1500:])
                    else:
                        progress_text = "🔄 分析进行中...\n\n"
                        progress_text += "  智能体执行状态:\n"
                        for agent, status_icon in agent_progress.items():
                            progress_text += f"    {status_icon} {agent}\n"
                        progress_text += "\n  ⏳ 分析中..."
                        output_container.markdown(progress_text)
                else:
                    if process.poll() is not None:
                        break
                    time.sleep(0.05)

            returncode = process.wait()
            
            if returncode == 0:
                status.update(label="✅ 分析完成！", state="complete", expanded=False)
            else:
                status.update(label="⚠️ 分析执行失败", state="error", expanded=True)
                st.error(f"分析进程异常退出，返回码: {returncode}")
                with st.expander("📋 查看错误日志", expanded=True):
                    st.code(full_output, language="text")
                st.session_state.messages.append({"role": "assistant", "content": "❌ 分析执行失败，请查看错误日志。"})
                st.stop()

        _show_report(start_time, full_output)


def _show_report(start_time, full_output):
    """展示分析报告"""
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
        with st.expander("📄 查看原始分析日志", expanded=False):
            st.code(full_output)
        
        st.success(f"✅ 根因分析报告已生成：`{os.path.basename(latest_report)}`")
        
        with open(latest_report, 'r', encoding='utf-8') as f:
            report_content = f.read()
        
        st.markdown("---")
        st.markdown(report_content)
        
        st.download_button(
            label="📥 下载分析报告",
            data=report_content,
            file_name=os.path.basename(latest_report),
            mime="text/markdown",
            width='stretch'
        )
        
        st.session_state.messages.append({"role": "assistant", "content": report_content})
    else:
        st.error("❌ 分析执行完成但未生成报告文件")
        with st.expander("📋 查看完整分析日志", expanded=True):
            st.code(full_output, language="text")
        st.info("可能的原因：\n"
                "1. LLM API 调用失败或超时\n"
                "2. 工作流执行异常中断\n"
                "3. 报告保存时发生错误\n"
                "4. 迭代过程未达到收敛条件")
        st.session_state.messages.append({"role": "assistant", "content": "❌ 分析完成但未生成报告，请查看日志。"})