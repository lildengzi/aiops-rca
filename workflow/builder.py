"""
工作流图构建与执行入口
"""
from langgraph.graph import StateGraph, END
from config import WORKFLOW_CONFIG
from workflow.state import RCAState
from workflow.nodes import (
    master_node,
    metric_node,
    log_node,
    trace_node,
    aggregate_node,
    analyst_node,
    reporter_node,
)


def should_continue_or_stop(state: RCAState) -> str:
    """决定是继续迭代还是生成最终报告"""
    if state.get("should_stop", False):
        return "reporter"
    return "master"


def build_rca_workflow() -> StateGraph:
    """
    构建完整的 RCA 多智能体工作流

    流程：
    master → (metric, log, trace) 并行 → aggregate → analyst → (继续 → master / 停止 → reporter) → END
    """
    workflow = StateGraph(RCAState)

    # 添加节点
    workflow.add_node("master", master_node)
    workflow.add_node("metric", metric_node)
    workflow.add_node("log", log_node)
    workflow.add_node("trace", trace_node)
    workflow.add_node("aggregate", aggregate_node)
    workflow.add_node("analyst", analyst_node)
    workflow.add_node("reporter", reporter_node)

    # 设置入口
    workflow.set_entry_point("master")

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

    # 条件分支：分析师决定是否继续
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
    fault_type: str = "cpu",
    max_iterations: int = None,
    full_analysis: bool = True,
    progress_callback = None,
) -> dict:
    """
    执行根因分析

    Args:
        user_query: 用户问题描述
        fault_type: 故障类型 (cpu/delay/disk/loss/mem)
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
        "iteration": 0,
        "max_iterations": max_iterations,
        "should_stop": False,
        "parallel_degree": 3,  # 默认并行度
        "full_analysis": full_analysis,
        "master_plan": "",
        "metric_results": [],
        "log_results": [],
        "trace_results": [],
        "analyst_decision": "",
        "final_report": "",
        "thinking_log": [],
    }

    # 执行工作流并跟踪进度
    if progress_callback:
        # 使用stream模式跟踪每个节点执行
        final_state = None
        for event in app.stream(initial_state):
            for node_name, output in event.items():
                progress_callback(node_name, "completed")
                final_state = output if output else final_state
        return final_state
    else:
        # 执行工作流
        final_state = app.invoke(initial_state)
        return final_state
