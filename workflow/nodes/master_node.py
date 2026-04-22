"""
运维专家节点实现
"""
from datetime import datetime
from langchain_core.messages import HumanMessage, SystemMessage

from workflow.utils import _create_llm, _calculate_optimal_parallel_degree
from agents.master_agent import get_master_prompt
from workflow.state import RCAState


def master_node(state: RCAState) -> dict:
    """
    运维专家节点：分析问题、制定排查计划
    首次迭代时自动检测故障类型
    """
    llm = _create_llm()
    iteration = state.get("iteration", 0)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 计算最优并行度
    parallel_degree = _calculate_optimal_parallel_degree()

    fault_type = state.get("fault_type", "unknown")
    detected_type = state.get("detected_fault_type", "")

    # 首次迭代且未确定故障类型时，自动检测
    is_first_iter = iteration == 0
    need_auto_detect = is_first_iter and (fault_type == "unknown" or not detected_type)

    # 构建上下文
    context_parts = []
    if iteration > 0:
        context_parts.append(f"=== 第 {iteration} 轮迭代结果 ===")
        if state.get("metric_results"):
            context_parts.append(f"【指标分析结果】\n{state['metric_results'][-1]}")
        if state.get("log_results"):
            context_parts.append(f"【日志分析结果】\n{state['log_results'][-1]}")
        if state.get("trace_results"):
            context_parts.append(f"【链路分析结果】\n{state['trace_results'][-1]}")
        if state.get("analyst_decision"):
            context_parts.append(f"【值班长决策】\n{state['analyst_decision']}")

    context = "\n\n".join(context_parts)
    system_prompt = get_master_prompt(context, detected_type)

    # 构建用户消息
    user_msg_parts = [
        f"当前时间: {ts}",
        f"故障类型: {detected_type or fault_type}",
        f"用户问题: {state['user_query']}",
        f"当前迭代轮次: {iteration + 1}/{state['max_iterations']}",
        f"当前系统并行度: {parallel_degree}",
    ]

    if need_auto_detect:
        user_msg_parts.append(
            "\n【重要】故障类型为unknown，请先调用 query_all_services_overview('cpu/delay/disk/loss/mem') "
            "扫描各数据集的异常指标，分析数据特征后自动判断最可能的故障类型，并在计划中说明判断依据。"
        )

    user_msg = "\n".join(user_msg_parts) + "\n\n请制定本轮排查计划。"

    messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_msg)]
    response = llm.invoke(messages)
    plan = response.content

    # 尝试从计划中提取检测到的故障类型
    new_detected_type = detected_type
    if need_auto_detect:
        plan_lower = plan.lower()
        for ft in ["cpu", "delay", "disk", "loss", "mem"]:
            if ft in plan_lower:
                new_detected_type = ft
                break

    # 全指标分析模式强制启用所有数据来源
    if state.get("full_analysis", True):
        log_entry = f"[{ts}] 运维专家 - 第{iteration+1}轮计划(全指标模式):\n{plan[:500]}"
    else:
        log_entry = f"[{ts}] 运维专家 - 第{iteration+1}轮计划:\n{plan[:500]}"

    if new_detected_type and new_detected_type != detected_type:
        log_entry += f"\n→ 自动检测故障类型: {new_detected_type}"

    updates = {
        "master_plan": plan,
        "iteration": iteration + 1,
        "parallel_degree": parallel_degree,
        "full_analysis": state.get("full_analysis", True),
        "thinking_log": [log_entry],
    }

    if new_detected_type:
        updates["detected_fault_type"] = new_detected_type

    return updates
