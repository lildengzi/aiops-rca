"""
运营专家节点实现 - 增强版，仅基于分析师结构化输出生成报告
"""
from datetime import datetime
from langchain_core.messages import HumanMessage, SystemMessage

from workflow.utils import _create_llm
from agents.reporter_agent import get_reporter_prompt
from workflow.state import RCAState


def reporter_node(state: RCAState) -> dict:
    """
    运营专家节点：仅基于分析师结构化输出生成报告，不自行拔高结论。
    """
    llm = _create_llm()
    ts = datetime.now().strftime("%H:%M:%S")

    # 仅使用分析师结构化输出和观测证据（不自行拔高）
    analyst_output = state.get("analyst_output")
    metric_analysis = state.get("metric_analysis")
    log_analysis = state.get("log_analysis")
    trace_analysis = state.get("trace_analysis")

    # 构建提示词（仅传入分析师输出和观测证据）
    system_prompt = get_reporter_prompt(
        analyst_output=analyst_output,
        metric_analysis=metric_analysis,
        log_analysis=log_analysis,
        trace_analysis=trace_analysis,
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content="请严格基于分析师仲裁结果生成报告，不得添加或拔高结论。"),
    ]

    response = llm.invoke(messages)
    report = response.content
    log_entry = f"[{ts}] 运营专家 - 报告生成完成"

    return {
        "final_report": report,
        "thinking_log": [log_entry],
    }
