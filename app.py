import streamlit as st
import subprocess
import sys
import os
import glob
import time
from datetime import datetime

# 页面配置
st.set_page_config(page_title="AIOps 智能根因分析平台", layout="wide")

st.title("🔍 AIOps 智能根因分析平台")
st.markdown("---")

# 侧边栏：配置参数
with st.sidebar:
    st.header("⚙️ 分析配置")
    max_iter = st.slider("最大迭代次数 (max-iter)", 1, 5, 2)
    fault_type = st.selectbox("强制指定故障类型 (可选)", ["自动识别", "cpu", "delay", "disk", "loss", "mem"])
    st.info("提示：直接输入告警描述，系统将自动识别故障类型并进行多轮分析。")

# 初始化会话状态
if "messages" not in st.session_state:
    st.session_state.messages = []

# 展示历史对话
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 处理用户输入
if prompt := st.chat_input("例如：过去1小时frontend服务CPU飙升，请分析根因"):
    # 1. 显示用户消息
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 2. 调用后端脚本
    with st.chat_message("assistant"):
        with st.status("🚀 正在启动 AIOps 多智能体分析...", expanded=True) as status:
            st.write("正在解析自然语言查询...")
            
            # 构建命令行参数（使用当前 Python 可执行文件）
            cmd = [sys.executable, "main.py", "--query", prompt, "--max-iter", str(max_iter)]
            if fault_type != "自动识别":
                cmd.extend(["--fault", fault_type])
            
            # 执行脚本并捕获实时输出（不使用 shell）
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, shell=False)

            output_container = st.empty()
            full_output = ""

            # 可靠的逐行读取输出（避免阻塞）
            while True:
                line = process.stdout.readline()
                if line:
                    full_output += line
                    output_container.code(full_output[-500:])  # 滚动显示最后500字符
                else:
                    if process.poll() is not None:
                        # 进程已退出且无更多输出
                        break
                    time.sleep(0.05)

            # 等待进程结束并检查返回码
            returncode = process.wait()
            if returncode == 0:
                try:
                    status.update(label="✅ 分析完成！", state="complete", expanded=False)
                except Exception:
                    pass
            else:
                try:
                    status.update(label="⚠️ 分析异常结束", state="error", expanded=False)
                except Exception:
                    pass
                output_container.code(full_output)
                st.error(f"后端分析脚本退出，返回码={returncode}。请检查日志。")

        # 3. 寻找并展示最新的报告
        # 使用基于文件的 reports 目录（更可靠的路径）
        report_dir = os.path.join(os.path.dirname(__file__), "reports")
        if os.path.exists(report_dir):
            list_of_files = glob.glob(os.path.join(report_dir, '*.md'))
            if list_of_files:
                latest_report = max(list_of_files, key=os.path.getctime)
                
                with st.expander("📄 查看原始分析日志", expanded=False):
                    st.code(full_output)
                
                st.success(f"根因分析报告已生成：`{os.path.basename(latest_report)}`")
                
                # 读取并渲染 Markdown 报告
                with open(latest_report, 'r', encoding='utf-8') as f:
                    report_content = f.read()
                
                st.markdown("---")
                st.markdown(report_content)
                
                # 将结果存入会话
                st.session_state.messages.append({"role": "assistant", "content": report_content})
            else:
                st.error("未找到生成的报告文件，请检查 main.py 运行状态。")