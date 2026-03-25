"""
数据模型定义 - 多智能体间结构化信息传递的 Schema
"""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


# ==================== 指标数据模型 ====================
class MetricDataPoint(BaseModel):
    """单个指标数据点"""
    timestamp: int
    value: float


class MetricSeries(BaseModel):
    """指标时序数据"""
    service: str
    metric_name: str
    metric_type: str = Field(description="resource|performance|traffic|error")
    unit: str = ""
    values: list[MetricDataPoint] = []
    is_anomalous: bool = False
    anomaly_score: float = 0.0
    anomaly_description: str = ""


class MetricAgentOutput(BaseModel):
    """Metric Agent 输出"""
    agent_type: str = "metric"
    status: str = Field(description="success|failure")
    summary: str = ""
    data: dict = Field(default_factory=lambda: {"metrics": []})
    error_message: Optional[str] = None


# ==================== 日志数据模型 ====================
class LogEntry(BaseModel):
    """单条日志"""
    timestamp: str
    level: str
    message: str
    source: dict = {}
    fields: dict = {}


class LogAgentOutput(BaseModel):
    """Log Agent 输出"""
    agent_type: str = "log"
    status: str = "success"
    data: dict = Field(default_factory=lambda: {"logs": []})
    survey_summary: str = ""
    error_message: Optional[str] = None


# ==================== 链路数据模型 ====================
class TraceSpan(BaseModel):
    """调用链 Span"""
    operation_name: str = ""
    service_name: str = ""
    span_id: str = ""
    parent_span_id: str = ""
    start_time: str = ""
    duration: str = ""
    tags: dict = {}
    error_type: Optional[str] = None
    error_message: Optional[str] = None


class TraceData(BaseModel):
    """单条 Trace"""
    trace_id: str
    spans: list[TraceSpan] = []


class TraceAgentOutput(BaseModel):
    """Trace Agent 输出"""
    agent_type: str = "trace"
    status: str = "success"
    summary: str = ""
    data: dict = Field(default_factory=lambda: {"traces": []})
    error_message: Optional[str] = None


# ==================== 任务规划模型 ====================
class PlanStep(BaseModel):
    """执行步骤"""
    step_id: int
    agent: str = Field(description="metric|trace|log")
    date: str = ""
    query_background: str = ""
    query: str = ""
    reason: str = ""


class MasterAgentOutput(BaseModel):
    """Master Agent（运维专家）输出"""
    agent_type: str = "master"
    data: dict = Field(default_factory=lambda: {"plan": [], "reflection": ""})
    error_message: Optional[str] = None


# ==================== 分析决策模型 ====================
class AnalystDecision(BaseModel):
    """值班长决策"""
    conclusion: str = ""
    evidence: list[str] = []
    logic_chain: str = ""
    confidence: float = 0.0
    should_continue: bool = True
    next_steps: str = ""


# ==================== 最终报告模型 ====================
class RCAReport(BaseModel):
    """根因分析报告"""
    summary: str = ""
    impact: str = ""
    root_cause: str = ""
    root_cause_category: str = ""
    evidence: list[str] = []
    monitoring_findings: str = ""
    recommendations: list[str] = []


# ==================== 工作流状态 ====================
class WorkflowState(BaseModel):
    """LangGraph 工作流全局状态"""
    # 用户输入
    user_query: str = ""
    fault_type: str = ""
    anomaly_timestamp: Optional[int] = None

    # 迭代控制
    iteration: int = 0
    max_iterations: int = 5
    should_stop: bool = False

    # 各 Agent 输出累积
    master_output: Optional[dict] = None
    metric_outputs: list[dict] = Field(default_factory=list)
    log_outputs: list[dict] = Field(default_factory=list)
    trace_outputs: list[dict] = Field(default_factory=list)
    analyst_outputs: list[dict] = Field(default_factory=list)

    # 最终报告
    final_report: Optional[dict] = None

    # 过程日志（透明化）
    thinking_log: list[str] = Field(default_factory=list)

    class Config:
        arbitrary_types_allowed = True
