"""
日志分析节点实现
"""
from datetime import datetime
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage

from workflow.utils import _create_llm
from agents.log_agent import get_log_prompt
from tools.log_tools import LOG_TOOLS
from workflow.state import RCAState


def log_node(state: RCAState) -> dict:
    """
    日志分析节点：使用 ReAct 模式查询和分析日志
    支持全指标分析模式和容错处理
    支持故障类型自动检测
    """
    llm = _create_llm()
    ts = datetime.now().strftime("%H:%M:%S")

    # 使用检测到的故障类型（优先）或初始故障类型
    fault_type = state.get("detected_fault_type") or state.get("fault_type", "cpu")
    is_first_iter = state.get("iteration", 0) == 0

    try:
        log_agent = create_react_agent(
            llm,
            tools=LOG_TOOLS,
            prompt=get_log_prompt(),
        )

        # 全指标分析模式：强制全局搜索+所有异常服务日志
        if state.get("full_analysis", True):
            task = f"""请全面分析 {fault_type} 故障场景下的所有日志数据。

运维专家的计划：
{state.get('master_plan', '请搜索全局错误模式')}

已知的指标异常信息：
{state['metric_results'][-1][:1000] if state.get('metric_results') else '暂无'}

请执行以下操作：
1. 调用 search_error_patterns 搜索全局错误模式，fault_type 为 "{fault_type}"
2. 对所有发现的异常服务，调用 query_service_logs 获取详细日志
3. 分析错误频率、分布和相关性
4. 总结所有错误模式和异常堆栈
5. 标记高优先级错误"""
        else:
            task = f"""请分析 {fault_type} 故障场景下的日志数据。

运维专家的计划：
{state.get('master_plan', '请搜索全局错误模式')}

已知的指标异常信息：
{state['metric_results'][-1][:1000] if state.get('metric_results') else '暂无'}

请执行以下操作：
1. 调用 search_error_patterns 搜索全局错误模式，fault_type 为 "{fault_type}"
2. 对关键异常服务，调用 query_service_logs 获取详细日志
3. 总结日志分析结果，关注错误模式和异常堆栈"""

        result = log_agent.invoke({"messages": [HumanMessage(content=task)]})
        final_msg = result["messages"][-1].content if result["messages"] else "日志分析未返回结果"

        log_entry = f"[{ts}] 日志分析完成: {final_msg[:300]}..."
        return {
            "log_results": [final_msg],
            "thinking_log": [log_entry],
        }
    except Exception as e:
        log_entry = f"[{ts}] 日志分析异常: {str(e)[:100]}"
        return {
            "log_results": [f"日志分析执行异常: {str(e)}"],
            "thinking_log": [log_entry],
        }
