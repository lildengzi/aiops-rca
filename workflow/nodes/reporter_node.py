"""
运营专家节点实现
"""
from datetime import datetime
from langchain_core.messages import HumanMessage, SystemMessage

from workflow.utils import _create_llm
from agents.reporter_agent import get_reporter_prompt
from knowledge_base.knowledge_manager import get_knowledge_manager
from workflow.state import RCAState


def reporter_node(state: RCAState) -> dict:
    """
    运营专家节点：生成最终的结构化分析报告
    集成知识库提供标准缓解建议
    """
    llm = _create_llm()
    ts = datetime.now().strftime("%H:%M:%S")
    
    # 知识库增强：获取标准建议
    km = get_knowledge_manager()
    mitigations = km.recommend_mitigations(state['fault_type'])
    fault_info = km.get_fault_pattern(state['fault_type'])

    # 汇总所有分析数据 + 知识库增强
    all_evidence = f"""=== 完整分析数据 ===

【故障类型】{state['fault_type']}
【用户问题】{state['user_query']}
【分析轮次】共 {state['iteration']} 轮
【分析模式】{'全指标分析' if state.get('full_analysis', True) else '定向分析'}

【知识库参考信息】
故障模式: {fault_info['name'] if fault_info else '未知'}
标准缓解建议: {chr(10).join([f'- {m}' for m in mitigations]) if mitigations else '无标准建议'}

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
