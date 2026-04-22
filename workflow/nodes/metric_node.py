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
    指标分析节点：使用 ReAct 模式调用指标工具进行分析
    支持全指标分析模式和容错处理
    支持故障类型自动检测（当fault_type为unknown时，使用detected_fault_type）
    """
    llm = _create_llm()
    ts = datetime.now().strftime("%H:%M:%S")

    # 使用检测到的故障类型（优先）或初始故障类型
    fault_type = state.get("detected_fault_type") or state.get("fault_type", "cpu")
    is_first_iter = state.get("iteration", 0) == 0

    try:
        # 创建带工具的 ReAct Agent
        metric_agent = create_react_agent(
            llm,
            tools=METRIC_TOOLS,
            prompt=get_metric_prompt(),
        )

        # 首次迭代且故障类型为unknown时，需要扫描所有数据集
        if is_first_iter and (state.get("fault_type") == "unknown" or not state.get("detected_fault_type")):
            task = f"""用户问题: {state['user_query']}
运维专家计划: {state.get('master_plan', '请扫描各数据集发现异常')}

请执行以下操作进行故障类型自动检测：
1. 依次扫描 cpu, delay, disk, loss, mem 五个数据集的全局异常
2. 对每个数据集调用 query_all_services_overview 获取异常概览
3. 分析各数据集的异常指标数量和严重程度
4. 根据异常特征判断最可能的故障类型
5. 然后对确定的数据集进行详细指标分析

请先完成故障类型判断，再进行详细分析。"""
        elif state.get("full_analysis", True):
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
        # 提取最终回复
        final_msg = result["messages"][-1].content if result["messages"] else "指标分析未返回结果"
        
        log_entry = f"[{ts}] 指标分析完成: {final_msg[:300]}..."
        
        updates = {
            "metric_results": [final_msg],
            "thinking_log": [log_entry],
        }
        
        # 尝试从结果中提取检测到的故障类型
        if is_first_iter and not state.get("detected_fault_type"):
            result_lower = final_msg.lower()
            for ft in ["cpu", "delay", "disk", "loss", "mem"]:
                if ft in result_lower and ("故障类型" in final_msg or "分析结果" in final_msg):
                    updates["detected_fault_type"] = ft
                    log_entry += f"\n→ 从指标分析中推断故障类型: {ft}"
                    updates["thinking_log"] = [log_entry]
                    break
        
        return updates
    except Exception as e:
        log_entry = f"[{ts}] 指标分析异常: {str(e)[:100]}"
        return {
            "metric_results": [f"指标分析执行异常: {str(e)}"],
            "thinking_log": [log_entry],
        }
