import streamlit as st
import subprocess
import sys
import os
import glob
import time
import json
from datetime import datetime

# 页面配置
st.set_page_config(page_title="AIOps 智能根因分析平台", layout="wide")

# 初始化会话状态
if "current_page" not in st.session_state:
    st.session_state.current_page = "analysis"

# 标题
st.title("🔍 AIOps 智能根因分析平台")
st.markdown("---")

# 侧边栏：导航
with st.sidebar:
    st.header("📋 导航菜单")
    page = st.radio(
        "选择功能:",
        ["🔍 故障分析", "📜 历史报告", "📚 知识库管理"],
        label_visibility="collapsed"
    )
    
    if page == "🔍 故障分析":
        st.session_state.current_page = "analysis"
    elif page == "📜 历史报告":
        st.session_state.current_page = "history"
    elif page == "📚 知识库管理":
        st.session_state.current_page = "knowledge"
    
    st.markdown("---")
    
    # 分析配置（仅在分析页面显示）
    if st.session_state.current_page == "analysis":
        st.header("⚙️ 分析配置")
        max_iter = st.slider("最大迭代次数 (max-iter)", 1, 5, 2)
        fault_type = st.selectbox("强制指定故障类型 (可选)", ["自动识别", "cpu", "delay", "disk", "loss", "mem"])
        full_analysis = st.checkbox("启用全指标分析模式", value=True, help="分析所有服务的所有指标，而非仅目标服务")
        show_raw_logs = st.checkbox("显示原始分析日志", value=False)
    
    st.markdown("---")
    st.subheader("📊 系统状态")
    st.info("✅ 多智能体系统就绪")
    st.success("🔍 知识库已加载")
    
    st.markdown("---")
    st.info("提示：直接输入告警描述，系统将自动识别故障类型并进行多轮分析。")

# ========== 故障分析页面 ==========
if st.session_state.current_page == "analysis":
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
        start_time = time.time()
        
        with st.status("🚀 正在启动 AIOps 多智能体分析...", expanded=True) as status:
            # 构建命令行参数（使用当前 Python 可执行文件）
            cmd = [sys.executable, "main.py", "--query", prompt, "--max-iter", str(max_iter)]
            if fault_type != "自动识别":
                cmd.extend(["--fault", fault_type])
            if not full_analysis:
                cmd.append("--disable-full-analysis")
            
            # 增强：关键词预识别，提升成功率
            query_lower = prompt.lower()
            if fault_type == "自动识别":
                # 前端先做一次快速关键词匹配
                if any(kw in query_lower for kw in ["cpu", "处理器", "占用高", "飙升"]):
                    cmd.extend(["--fault", "cpu"])
                    st.info("🔍 自动匹配故障类型: CPU")
                elif any(kw in query_lower for kw in ["mem", "内存", "oom", "泄漏", "溢出"]):
                    cmd.extend(["--fault", "mem"])
                    st.info("🔍 自动匹配故障类型: 内存")
                elif any(kw in query_lower for kw in ["delay", "延迟", "慢", "超时", "响应慢"]):
                    cmd.extend(["--fault", "delay"])
                    st.info("🔍 自动匹配故障类型: 延迟")
                elif any(kw in query_lower for kw in ["disk", "磁盘", "io", "存储", "满了"]):
                    cmd.extend(["--fault", "disk"])
                    st.info("🔍 自动匹配故障类型: 磁盘")
                elif any(kw in query_lower for kw in ["loss", "丢包", "网络", "连接失败", "错误率"]):
                    cmd.extend(["--fault", "loss"])
                    st.info("🔍 自动匹配故障类型: 网络")
            
            # 执行脚本并捕获实时输出
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, shell=False)

            output_container = st.empty()
            full_output = ""
            agent_progress = {}

            # 实时输出显示 - 与命令行一致的体验
            while True:
                line = process.stdout.readline()
                if line:
                    full_output += line
                    
                    # 检测智能体完成状态
                    if "[完成]" in line and "任务完成" in line:
                        for agent_name in ["运维专家", "指标分析专家", "日志分析专家", "链路分析专家", "数据汇总", "值班长", "运营专家"]:
                            if agent_name in line:
                                agent_progress[agent_name] = "[✓]"
                    
                    # 根据用户选择显示输出
                    if show_raw_logs:
                        # 显示完整原始日志
                        output_container.code(full_output[-1500:])
                    else:
                        # 只显示智能体进度，更简洁
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

            # 等待进程结束
            returncode = process.wait()
            
            # 处理执行结果
            if returncode == 0:
                status.update(label="✅ 分析完成！", state="complete", expanded=False)
            else:
                status.update(label="⚠️ 分析执行失败", state="error", expanded=True)
                st.error(f"分析进程异常退出，返回码: {returncode}")
                with st.expander("📋 查看错误日志", expanded=True):
                    st.code(full_output, language="text")
                st.session_state.messages.append({"role": "assistant", "content": "❌ 分析执行失败，请查看错误日志。"})
                st.stop()

        # 3. 寻找并展示本次分析生成的报告（通过时间戳判断新旧）
        report_dir = os.path.join(os.path.dirname(__file__), "reports")
        latest_report = None
        
        if os.path.exists(report_dir):
            list_of_files = glob.glob(os.path.join(report_dir, '*.md'))
            # 严格只选择本次运行之后生成的报告（避免显示历史报告）
            new_reports = [f for f in list_of_files if os.path.getctime(f) > start_time]
            
            if new_reports:
                latest_report = max(new_reports, key=os.path.getctime)
            else:
                # 容忍2秒的时间差，防止系统时间精度问题
                new_reports = [f for f in list_of_files if os.path.getctime(f) > start_time - 2]
                if new_reports:
                    latest_report = max(new_reports, key=os.path.getctime)
        
        # 显示报告或失败信息
        if latest_report:
            with st.expander("📄 查看原始分析日志", expanded=False):
                st.code(full_output)
            
            st.success(f"✅ 根因分析报告已生成：`{os.path.basename(latest_report)}`")
            
            # 读取并渲染 Markdown 报告
            with open(latest_report, 'r', encoding='utf-8') as f:
                report_content = f.read()
            
            st.markdown("---")
            st.markdown(report_content)
            
            # 下载按钮
            st.download_button(
                label="📥 下载分析报告",
                data=report_content,
                file_name=os.path.basename(latest_report),
                mime="text/markdown",
                use_container_width=True
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

# ========== 历史报告页面 ==========
elif st.session_state.current_page == "history":
    st.header("📜 历史分析报告")
    
    report_dir = os.path.join(os.path.dirname(__file__), "reports")
    if os.path.exists(report_dir):
        list_of_files = glob.glob(os.path.join(report_dir, '*.md'))
        if list_of_files:
            # 按创建时间排序
            list_of_files.sort(key=os.path.getctime, reverse=True)
            
            st.info(f"共找到 {len(list_of_files)} 份历史报告")
            
            # 报告选择器
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
                        use_container_width=True
                    )
                    if st.button("🗑️ 删除报告", use_container_width=True, type="secondary"):
                        os.remove(selected_report)
                        st.rerun()
        else:
            st.warning("暂无历史报告，请先运行故障分析。")
    else:
        st.warning("报告目录不存在，请先运行故障分析。")

# ========== 知识库管理页面 ==========
elif st.session_state.current_page == "knowledge":
    st.header("📚 知识库管理")
    
    # 加载知识库
    from knowledge_base.knowledge_manager import get_knowledge_manager, FAULT_PATTERNS
    km = get_knowledge_manager()
    
    tab1, tab2, tab3 = st.tabs(["📖 故障模式库", "✏️ 编辑知识库", "🔧 工具"])
    
    with tab1:
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
    
    with tab2:
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
            
            if st.button("💾 保存修改", use_container_width=True):
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
    
    with tab3:
        st.subheader("知识库工具")
        if st.button("🔄 从数据集重建知识库", use_container_width=True):
            with st.spinner("正在分析所有数据集..."):
                results = km.build_knowledge_from_all_datasets()
                st.success("知识库重建完成！")
                st.json(results, expanded=False)
        
        if st.button("📋 导出知识库", use_container_width=True):
            kb_json = json.dumps(km.fault_patterns, ensure_ascii=False, indent=2)
            st.download_button(
                label="下载知识库JSON",
                data=kb_json,
                file_name="fault_patterns.json",
                mime="application/json",
                use_container_width=True
            )