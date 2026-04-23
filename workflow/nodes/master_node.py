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
    运维专家节点：分析问题、制定排查计划。
    故障类型自动检测由 detect_fault_node 负责，此处直接基于已确定类型制定计划。
    """
    llm = _create_llm()
    iteration = state.get("iteration", 0)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 计算最优并行度
    parallel_degree = _calculate_optimal_parallel_degree()

    fault_type = state.get("fault_type", "unknown")
    detected_type = state.get("detected_fault_type", "")
    effective_fault_type = detected_type or fault_type

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
        f"故障类型: {effective_fault_type}",
        f"用户问题: {state['user_query']}",
        f"当前迭代轮次: {iteration + 1}/{state['max_iterations']}",
        f"当前系统并行度: {parallel_degree}",
    ]

    if detected_type:
        user_msg_parts.append(f"系统已基于真实数据自动识别故障类型为: {detected_type}，请围绕该类型制定排查计划。")
    elif fault_type != "unknown":
        user_msg_parts.append(f"用户已显式指定故障类型为: {fault_type}，请围绕该类型制定排查计划。")
    else:
        user_msg_parts.append("当前仍未可靠识别故障类型，请先做保守的全局排查规划。")

    user_msg = "\n".join(user_msg_parts) + "\n\n请制定本轮排查计划。"

    messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_msg)]
    response = llm.invoke(messages)
    plan = response.content

    log_entry = f"[{ts}] 运维专家 - 第{iteration+1}轮计划:\n{plan}"
    if detected_type:
        log_entry += f"\n→ 当前采用故障类型: {detected_type}"
    elif fault_type != "unknown":
        log_entry += f"\n→ 当前采用用户指定故障类型: {fault_type}"

    return {
        "master_plan": plan,
        "iteration": iteration + 1,
        "parallel_degree": parallel_degree,
        "full_analysis": state.get("full_analysis", True),
        "thinking_log": [log_entry],
    }
