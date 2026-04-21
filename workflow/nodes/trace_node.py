"""
链路分析节点实现
"""
from datetime import datetime
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage

from workflow.utils import _create_llm
from agents.trace_agent import get_trace_prompt
from tools.trace_tools import TRACE_TOOLS
from tools.topology_tools import TOPOLOGY_TOOLS
from workflow.state import RCAState


def trace_node(state: RCAState) -> dict:
    """
    链路分析节点：分析调用链和故障传播路径
    支持全指标分析模式和容错处理
    """
    llm = _create_llm()
    ts = datetime.now().strftime("%H:%M:%S")

    try:
        trace_agent = create_react_agent(
            llm,
            tools=TRACE_TOOLS + TOPOLOGY_TOOLS,
            prompt=get_trace_prompt(),
        )

        # 全指标分析模式：完整拓扑分析+全链路追踪
        if state.get("full_analysis", True):
            task = f"""请全面分析 {state['fault_type']} 故障场景下的调用链数据和服务拓扑。

运维专家的计划：
{state.get('master_plan', '请分析服务调用链')}

已知的异常信息：
- 指标: {state['metric_results'][-1][:800] if state.get('metric_results') else '暂无'}
- 日志: {state['log_results'][-1][:500] if state.get('log_results') else '暂无'}

请执行以下操作：
1. 调用 get_full_topology 了解完整系统架构
2. 调用 analyze_call_chain 分析完整故障传播路径，fault_type 为 "{state['fault_type']}"
3. 对所有异常服务调用 query_service_traces 获取调用链详情
4. 分析服务间依赖关系和故障传播方向
5. 总结完整的故障传播路径和根因位置判断
6. 标记关键瓶颈节点"""
        else:
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
    except Exception as e:
        log_entry = f"[{ts}] 链路分析异常: {str(e)[:100]}"
        return {
            "trace_results": [f"链路分析执行异常: {str(e)}"],
            "thinking_log": [log_entry],
        }
