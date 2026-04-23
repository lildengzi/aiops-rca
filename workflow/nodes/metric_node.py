"""
指标分析节点实现
"""
from datetime import datetime
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage

from workflow.utils import _create_llm
from agents.metric_agent import get_metric_prompt
from tools.metric_tools import METRIC_TOOLS
from workflow.state import RCAState


def metric_node(state: RCAState) -> dict:
    """
    指标分析节点：使用 ReAct 模式调用指标工具进行分析。
    自动检测故障类型由 detect_fault_node 预先完成，此处统一使用最终生效的故障类型。
    """
    llm = _create_llm()
    ts = datetime.now().strftime("%H:%M:%S")

    detected_fault_type = state.get("detected_fault_type", "")
    fault_type = detected_fault_type or state.get("fault_type", "unknown")

    try:
        # 创建带工具的 ReAct Agent
        metric_agent = create_react_agent(
            llm,
            tools=METRIC_TOOLS,
            prompt=get_metric_prompt(),
        )

        if state.get("full_analysis", True):
            task = f"""请全面分析 {fault_type} 故障场景下的所有监控指标数据。

运维专家的计划：
{state.get('master_plan', '请先全局扫描发现异常服务')}

请执行以下操作：
1. 调用 query_all_services_overview 进行全局扫描，fault_type 为 "{fault_type}"
2. 对所有异常服务，调用 query_service_metrics 获取详细指标
3. 对关键异常指标，调用 query_metric_correlation 分析相关性
4. 总结所有发现的异常指标和关联关系
5. 标记高风险指标"""
        else:
            task = f"""请分析 {fault_type} 故障场景下的监控指标数据。

运维专家的计划：
{state.get('master_plan', '请先全局扫描发现异常服务')}

请执行以下操作：
1. 调用 query_all_services_overview 进行全局扫描，fault_type 为 "{fault_type}"
2. 对发现的异常服务，调用 query_service_metrics 获取详细指标
3. 对关键异常指标，调用 query_metric_correlation 分析相关性
4. 总结分析结果"""

        result = metric_agent.invoke({"messages": [HumanMessage(content=task)]})
        final_msg = result["messages"][-1].content if result["messages"] else "指标分析未返回结果"

        log_entry = f"[{ts}] 指标分析完成:\n{final_msg}"
        if detected_fault_type:
            log_entry += f"\n→ 使用自动检测故障类型: {detected_fault_type}"

        return {
            "metric_results": [final_msg],
            "thinking_log": [log_entry],
        }
    except Exception as e:
        log_entry = f"[{ts}] 指标分析异常: {str(e)[:100]}"
        return {
            "metric_results": [f"指标分析执行异常: {str(e)}"],
            "thinking_log": [log_entry],
        }
