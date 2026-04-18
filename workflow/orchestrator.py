"""
多智能体工作流编排器 - 基于 LangGraph 实现 ReAct 模式
实现 运维专家 → 数据Agent → 值班长 → 循环/停止 → 运营专家 的完整流程
"""
import json
import operator
from typing import Annotated, TypedDict
from datetime import datetime

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import create_react_agent

from config import LLM_CONFIG, WORKFLOW_CONFIG
from agents.master_agent import get_master_prompt
from agents.metric_agent import get_metric_prompt
from agents.log_agent import get_log_prompt
from agents.trace_agent import get_trace_prompt
from agents.analyst_agent import get_analyst_prompt
from agents.reporter_agent import get_reporter_prompt
from tools.metric_tools import METRIC_TOOLS
from tools.log_tools import LOG_TOOLS
from tools.trace_tools import TRACE_TOOLS
from tools.topology_tools import TOPOLOGY_TOOLS


# ===================== 工作流状态定义 =====================
class RCAState(TypedDict):
    """根因分析工作流的全局状态"""
    # 用户输入
    user_query: str
    fault_type: str

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


def _create_llm() -> ChatOpenAI:
    """创建 LLM 实例"""
    return ChatOpenAI(
        model=LLM_CONFIG["model"],
        api_key=LLM_CONFIG["api_key"],
        base_url=LLM_CONFIG["base_url"],
        temperature=LLM_CONFIG["temperature"],
        max_tokens=LLM_CONFIG["max_tokens"],
    )


# ===================== 节点函数定义 =====================

import psutil

def _calculate_optimal_parallel_degree() -> int:
    """
    根据系统资源计算最优并行度
    """
    # 获取CPU核心数
    cpu_count = psutil.cpu_count(logical=True)
    # 获取可用内存比例
    memory = psutil.virtual_memory()
    memory_available_percent = memory.available / memory.total
    
    # 基于系统资源计算并行度
    # 保守策略：最多使用一半的CPU核心
    max_parallel = max(1, cpu_count // 2)
    
    # 根据内存可用性调整
    if memory_available_percent < 0.2:
        # 内存不足，降低并行度
        return max(1, max_parallel // 2)
    elif memory_available_percent < 0.5:
        # 内存紧张，保持保守并行度
        return max(1, max_parallel)
    else:
        # 内存充足，可以增加并行度
        return min(3, max_parallel)  # 最多并行3个智能体


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

    log_entry = f"[{ts}] 运维专家 - 第{iteration+1}轮计划:\n{plan[:500]}"

    return {
        "master_plan": plan,
        "iteration": iteration + 1,
        "parallel_degree": parallel_degree,
        "thinking_log": [log_entry],
    }


def metric_node(state: RCAState) -> dict:
    """
    指标分析节点：使用 ReAct 模式调用指标工具进行分析
    """
    llm = _create_llm()
    ts = datetime.now().strftime("%H:%M:%S")

    # 创建带工具的 ReAct Agent
    metric_agent = create_react_agent(
        llm,
        tools=METRIC_TOOLS,
        prompt=get_metric_prompt(),
    )

    task = f"""请分析 {state['fault_type']} 故障场景下的监控指标数据。

运维专家的计划：
{state.get('master_plan', '请先全局扫描发现异常服务')}

请执行以下操作：
1. 调用 query_all_services_overview 进行全局扫描，fault_type 为 "{state['fault_type']}"
2. 对发现的异常服务，调用 query_service_metrics 获取详细指标
3. 对关键异常指标，调用 query_metric_correlation 分析相关性
4. 总结分析结果"""

    result = metric_agent.invoke({"messages": [HumanMessage(content=task)]})
    # 提取最终回复
    final_msg = result["messages"][-1].content if result["messages"] else "指标分析未返回结果"

    log_entry = f"[{ts}] 指标分析完成: {final_msg[:300]}..."
    return {
        "metric_results": [final_msg],
        "thinking_log": [log_entry],
    }


def log_node(state: RCAState) -> dict:
    """
    日志分析节点：使用 ReAct 模式查询和分析日志
    """
    llm = _create_llm()
    ts = datetime.now().strftime("%H:%M:%S")

    log_agent = create_react_agent(
        llm,
        tools=LOG_TOOLS,
        prompt=get_log_prompt(),
    )

    task = f"""请分析 {state['fault_type']} 故障场景下的日志数据。

运维专家的计划：
{state.get('master_plan', '请搜索全局错误模式')}

已知的指标异常信息：
{state['metric_results'][-1][:1000] if state.get('metric_results') else '暂无'}

请执行以下操作：
1. 调用 search_error_patterns 搜索全局错误模式，fault_type 为 "{state['fault_type']}"
2. 对关键异常服务，调用 query_service_logs 获取详细日志
3. 总结日志分析结果，关注错误模式和异常堆栈"""

    result = log_agent.invoke({"messages": [HumanMessage(content=task)]})
    final_msg = result["messages"][-1].content if result["messages"] else "日志分析未返回结果"

    log_entry = f"[{ts}] 日志分析完成: {final_msg[:300]}..."
    return {
        "log_results": [final_msg],
        "thinking_log": [log_entry],
    }


def trace_node(state: RCAState) -> dict:
    """
    链路分析节点：分析调用链和故障传播路径
    """
    llm = _create_llm()
    ts = datetime.now().strftime("%H:%M:%S")

    trace_agent = create_react_agent(
        llm,
        tools=TRACE_TOOLS + TOPOLOGY_TOOLS,
        prompt=get_trace_prompt(),
    )

    task = f"""请分析 {state['fault_type']} 故障场景下的调用链数据和服务拓扑。

运维专家的计划：
{state.get('master_plan', '请分析服务调用链')}

已知的异常信息：
- 指标: {state['metric_results'][-1][:800] if state.get('metric_results') else '暂无'}
- 日志: {state['log_results'][-1][:500] if state.get('log_results') else '暂无'}

请执行以下操作：
1. 调用 get_full_topology 了解系统架构
2. 调用 analyze_call_chain 分析故障传播路径，fault_type 为 "{state['fault_type']}"
3. 对关键服务调用 query_service_traces 获取调用链详情
4. 总结故障传播路径和根因位置判断"""

    result = trace_agent.invoke({"messages": [HumanMessage(content=task)]})
    final_msg = result["messages"][-1].content if result["messages"] else "链路分析未返回结果"

    log_entry = f"[{ts}] 链路分析完成: {final_msg[:300]}..."
    return {
        "trace_results": [final_msg],
        "thinking_log": [log_entry],
    }


def analyst_node(state: RCAState) -> dict:
    """
    值班长节点：整合证据、推理判断、决定是否继续
    """
    llm = _create_llm()
    ts = datetime.now().strftime("%H:%M:%S")

    # 汇总所有证据
    evidence = f"""=== 第 {state['iteration']} 轮分析证据汇总 ===

【故障类型】{state['fault_type']}
【用户问题】{state['user_query']}

【运维专家计划】
{state.get('master_plan', '无')}

【指标分析结果】
{state['metric_results'][-1] if state.get('metric_results') else '暂无'}

【日志分析结果】
{state['log_results'][-1] if state.get('log_results') else '暂无'}

【链路分析结果】
{state['trace_results'][-1] if state.get('trace_results') else '暂无'}

【当前迭代】第 {state['iteration']} / {state['max_iterations']} 轮
"""

    system_prompt = get_analyst_prompt(evidence)
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content="请评估当前证据，给出决策结论。注意输出必须是合法的JSON格式。"),
    ]

    response = llm.invoke(messages)
    decision_text = response.content

    # 尝试解析决策
    should_stop = False
    try:
        # 提取 JSON
        json_str = decision_text
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0]
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0]
        decision = json.loads(json_str.strip())
        should_stop = not decision.get("should_continue", True)
        confidence = decision.get("confidence", 0)
        if confidence >= WORKFLOW_CONFIG["convergence_threshold"]:
            should_stop = True
    except (json.JSONDecodeError, IndexError, KeyError):
        # 解析失败，继续迭代
        pass

    # 达到最大迭代次数强制停止
    if state["iteration"] >= state["max_iterations"]:
        should_stop = True

    log_entry = f"[{ts}] 值班长决策: stop={should_stop}, 详情: {decision_text[:300]}..."

    return {
        "analyst_decision": decision_text,
        "should_stop": should_stop,
        "thinking_log": [log_entry],
    }


def reporter_node(state: RCAState) -> dict:
    """
    运营专家节点：生成最终的结构化分析报告
    """
    llm = _create_llm()
    ts = datetime.now().strftime("%H:%M:%S")

    # 汇总所有分析数据
    all_evidence = f"""=== 完整分析数据 ===

【故障类型】{state['fault_type']}
【用户问题】{state['user_query']}
【分析轮次】共 {state['iteration']} 轮

【所有指标分析结果】
{chr(10).join(state.get('metric_results', ['暂无']))}

【所有日志分析结果】
{chr(10).join(state.get('log_results', ['暂无']))}

【所有链路分析结果】
{chr(10).join(state.get('trace_results', ['暂无']))}

【值班长最终决策】
{state.get('analyst_decision', '暂无')}

【分析过程日志】
{chr(10).join(state.get('thinking_log', [])[-10:])}
"""

    system_prompt = get_reporter_prompt(all_evidence)
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content="请基于以上完整分析数据，生成结构化的事件分析报告。"),
    ]

    response = llm.invoke(messages)
    report = response.content

    log_entry = f"[{ts}] 运营专家 - 报告生成完成"
    return {
        "final_report": report,
        "thinking_log": [log_entry],
    }


# ===================== 路由函数 =====================

def should_continue_or_stop(state: RCAState) -> str:
    """决定是继续迭代还是生成最终报告"""
    if state.get("should_stop", False):
        return "reporter"
    return "master"


def aggregate_node(state: RCAState) -> dict:
    """
    并行结果汇总节点：等待所有并行任务完成后汇总结果
    """
    ts = datetime.now().strftime("%H:%M:%S")
    log_entry = f"[{ts}] 并行任务汇总完成"
    return {
        "thinking_log": [log_entry],
    }


# ===================== 构建工作流图 =====================

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
) -> dict:
    """
    执行根因分析

    Args:
        user_query: 用户问题描述
        fault_type: 故障类型 (cpu/delay/disk/loss/mem)
        max_iterations: 最大迭代次数

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
        "master_plan": "",
        "metric_results": [],
        "log_results": [],
        "trace_results": [],
        "analyst_decision": "",
        "final_report": "",
        "thinking_log": [],
    }

    # 执行工作流
    final_state = app.invoke(initial_state)
    return final_state
