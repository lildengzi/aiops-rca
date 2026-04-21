"""
多智能体工作流编排器 - 基于 LangGraph 实现 ReAct 模式
实现 运维专家 → 数据Agent → 值班长 → 循环/停止 → 运营专家 的完整流程

注意：此文件为兼容层，所有实现已重构到以下模块：
- workflow/state.py: 状态定义
- workflow/nodes/: 各节点实现
- workflow/builder.py: 工作流构建与执行
- workflow/utils.py: 通用工具函数
"""
from workflow.builder import build_rca_workflow, run_rca
from workflow.state import RCAState
from workflow.utils import _create_llm, _calculate_optimal_parallel_degree
from workflow.nodes import (
    master_node,
    metric_node,
    log_node,
    trace_node,
    aggregate_node,
    analyst_node,
    reporter_node,
)

__all__ = [
    "RCAState",
    "build_rca_workflow",
    "run_rca",
    "master_node",
    "metric_node",
    "log_node",
    "trace_node",
    "aggregate_node",
    "analyst_node",
    "reporter_node",
]
