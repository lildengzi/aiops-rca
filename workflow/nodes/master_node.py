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
    """
    llm = _create_llm()
    iteration = state.get("iteration", 0)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 计算最优并行度
    parallel_degree = _calculate_optimal_parallel_degree()

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
    system_prompt = get_master_prompt(context)

    user_msg = f"""当前时间: {ts}
故障类型: {state['fault_type']}
用户问题: {state['user_query']}
当前迭代轮次: {iteration + 1}/{state['max_iterations']}
当前系统并行度: {parallel_degree}

请制定本轮排查计划。"""

    messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_msg)]
    response = llm.invoke(messages)
    plan = response.content

    # 全指标分析模式强制启用所有数据来源
    if state.get("full_analysis", True):
        log_entry = f"[{ts}] 运维专家 - 第{iteration+1}轮计划(全指标模式):\n{plan[:500]}"
    else:
        log_entry = f"[{ts}] 运维专家 - 第{iteration+1}轮计划:\n{plan[:500]}"

    return {
        "master_plan": plan,
        "iteration": iteration + 1,
        "parallel_degree": parallel_degree,
        "full_analysis": state.get("full_analysis", True),
        "thinking_log": [log_entry],
    }
