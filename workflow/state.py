"""
工作流状态定义 - 增强版，支持结构化证据汇总和仲裁输出
"""
import operator
from typing import Annotated, TypedDict, Optional, List, Dict, Any


class RCAState(TypedDict):
    """根因分析工作流的全局状态"""
    # 用户输入
    user_query: str
    fault_type: str  # 初始故障类型（可能为unknown，仅作参考标签）
    detected_fault_type: str  # 自动检测后的候选异常模式（仅参考）
    full_analysis: bool  # 全指标分析模式

    # 迭代控制
    iteration: int
    max_iterations: int

    # 并行度控制
    parallel_degree: int  # 当前并行度

    # 各阶段输出
    master_plan: str              # 运维专家的计划
    master_reflection: str        # 运维专家每轮反思
    
    # 智能体结构化输出（覆盖式更新，非累积）
    metric_analysis: Optional[Dict[str, Any]]   # 指标分析结果（结构化）
    log_analysis: Optional[Dict[str, Any]]      # 日志分析结果（结构化）
    trace_analysis: Optional[Dict[str, Any]]    # 链路分析结果（结构化）
    
    # 聚合节点输出（结构化证据汇总）
    aggregate_summary: Optional[Dict[str, Any]] # 三方证据汇总
    
    # 分析师结构化仲裁输出
    analyst_output: Optional[Dict[str, Any]]    # 结构化仲裁结果
    
    # 保留历史输出用于迭代参考（累积）
    metric_history: Annotated[list[Dict[str, Any]], operator.add]
    log_history: Annotated[list[Dict[str, Any]], operator.add]
    trace_history: Annotated[list[Dict[str, Any]], operator.add]
    
    # 最终报告
    final_report: str             # 最终报告
    
    # 过程日志
    thinking_log: Annotated[list[str], operator.add]


