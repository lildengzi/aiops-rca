"""
工作流图构建与执行入口
"""
from langgraph.graph import StateGraph, END
from copy import deepcopy
from config import WORKFLOW_CONFIG
from workflow.state import RCAState
from workflow.nodes import (
    detect_fault_node,
    master_node,
    metric_node,
    log_node,
    trace_node,
    aggregate_node,
    analyst_node,
    reporter_node,
)


def should_continue_or_stop(state: RCAState) -> str:
    """决定是继续迭代还是生成最终报告（仅基于分析师输出）"""
    analyst_output = state.get("analyst_output")
    if analyst_output and isinstance(analyst_output, dict):
        # 优先使用分析师的结构化决策
        if not analyst_output.get("should_continue", True):
            return "reporter"
        # 达到最大迭代次数也停止
        if state.get("iteration", 0) >= state.get("max_iterations", 3):
            return "reporter"
    # 达到最大迭代次数强制停止
    if state.get("iteration", 0) >= state.get("max_iterations", 3):
        return "reporter"
    return "master"


def build_rca_workflow() -> StateGraph:
    """
    构建完整的 RCA 多智能体工作流

    流程：
    detect_fault → master → (metric, log, trace) 并行 → aggregate → analyst → (继续 → master / 停止 → reporter) → END
    """
    workflow = StateGraph(RCAState)

    # 添加节点
    workflow.add_node("detect_fault", detect_fault_node)
    workflow.add_node("master", master_node)
    workflow.add_node("metric", metric_node)
    workflow.add_node("log", log_node)
    workflow.add_node("trace", trace_node)
    workflow.add_node("aggregate", aggregate_node)
    workflow.add_node("analyst", analyst_node)
    workflow.add_node("reporter", reporter_node)

    # 设置入口
    workflow.set_entry_point("detect_fault")

    # 自动检测完成后进入计划节点
    workflow.add_edge("detect_fault", "master")

    # 添加并行边：从 master 到三个数据收集智能体（并行执行）
    workflow.add_edge("master", "metric")
    workflow.add_edge("master", "log")
    workflow.add_edge("master", "trace")

    # 三个数据收集智能体都指向汇总节点（等待所有并行任务完成）
    workflow.add_edge("metric", "aggregate")
    workflow.add_edge("log", "aggregate")
    workflow.add_edge("trace", "aggregate")

    # 汇总节点指向分析师节点
    workflow.add_edge("aggregate", "analyst")

    # 条件分支：分析师决定是否继续（分析师是唯一仲裁者）
    workflow.add_conditional_edges(
        "analyst",
        should_continue_or_stop,
        {
            "master": "master",     # 继续迭代
            "reporter": "reporter",  # 生成报告
        },
    )

    # 报告完成后结束
    workflow.add_edge("reporter", END)

    return workflow.compile()


def run_rca(
    user_query: str,
    fault_type: str = "unknown",  # 默认unknown，不预设固定类型
    max_iterations: int = None,
    full_analysis: bool = True,
    progress_callback = None,
) -> dict:
    """
    执行根因分析

    Args:
        user_query: 用户问题描述
        fault_type: 故障类型参考标签（默认为unknown，不驱动核心分析）
        max_iterations: 最大迭代次数
        full_analysis: 是否启用全指标分析模式（默认启用）
        progress_callback: 进度回调函数，接收(node_name, status)参数

    Returns:
        包含完整分析结果的状态字典
    """
    if max_iterations is None:
        max_iterations = WORKFLOW_CONFIG["max_iterations"]

    app = build_rca_workflow()

    initial_state: RCAState = {
        "user_query": user_query,
        "fault_type": fault_type,
        "detected_fault_type": "unknown",  # 初始为unknown，由detect_fault节点更新
        "iteration": 0,
        "max_iterations": max_iterations,
        "parallel_degree": 3,  # 默认并行度
        "full_analysis": full_analysis,
        "master_plan": "",
        "master_reflection": "",
        "metric_analysis": None,
        "log_analysis": None,
        "trace_analysis": None,
        "aggregate_summary": None,
        "analyst_output": None,
        "metric_history": [],
        "log_history": [],
        "trace_history": [],
        "final_report": "",
        "thinking_log": [],
    }

    # 执行工作流并跟踪进度
    if progress_callback:
        # 使用stream模式跟踪每个节点执行
        final_state = deepcopy(initial_state)
        for event in app.stream(initial_state):
            for node_name, output in event.items():
                progress_callback(node_name, "completed")
                # 正确合并输出
                if output:
                    list_fields = ['metric_history', 'log_history', 'trace_history', 'thinking_log']
                    for key, value in output.items():
                        if key in list_fields and isinstance(value, list):
                            if key in final_state:
                                final_state[key].extend(value)
                            else:
                                final_state[key] = value
                        else:
                            final_state[key] = value
        return final_state
    else:
        # 执行工作流
        final_state = app.invoke(initial_state)
        return final_state
