"""
工作流状态定义
"""
import operator
from typing import Annotated, TypedDict


class RCAState(TypedDict):
    """根因分析工作流的全局状态"""
    # 用户输入
    user_query: str
    fault_type: str
    full_analysis: bool  # 全指标分析模式

    # 迭代控制
    iteration: int
    max_iterations: int
    should_stop: bool

    # 并行度控制
    parallel_degree: int  # 当前并行度

    # 各阶段输出
    master_plan: str              # 运维专家的计划
    metric_results: Annotated[list[str], operator.add]   # 指标分析结果累积
    log_results: Annotated[list[str], operator.add]      # 日志分析结果累积
    trace_results: Annotated[list[str], operator.add]    # 链路分析结果累积
    analyst_decision: str         # 值班长决策
    final_report: str             # 最终报告

    # 过程日志
    thinking_log: Annotated[list[str], operator.add]
