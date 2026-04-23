"""
值班长节点实现
"""
import json
from datetime import datetime
from langchain_core.messages import HumanMessage, SystemMessage

from workflow.utils import _create_llm
from agents.analyst_agent import get_analyst_prompt
from knowledge_base.knowledge_manager import get_knowledge_manager
from config import WORKFLOW_CONFIG
from workflow.state import RCAState


def analyst_node(state: RCAState) -> dict:
    """
    值班长节点：整合证据、推理判断、决定是否继续。
    集成知识库进行根因匹配和模式识别，并优先使用自动检测出的故障类型。
    """
    llm = _create_llm()
    ts = datetime.now().strftime("%H:%M:%S")
    effective_fault_type = state.get("detected_fault_type") or state.get("fault_type", "unknown")
    
    # 知识库增强：获取已知故障模式
    km = get_knowledge_manager()
    fault_pattern = km.get_fault_pattern(effective_fault_type)
    recommended_roots = km.recommend_root_causes(effective_fault_type)
    propagation_path = km.get_propagation_path(effective_fault_type)
    mitigations = km.recommend_mitigations(effective_fault_type)

    # 汇总所有证据 + 知识库增强信息
    evidence = f"""=== 第 {state['iteration']} 轮分析证据汇总 ===

【故障类型】{effective_fault_type}
【用户问题】{state['user_query']}

【知识库参考信息】
故障模式: {fault_pattern['name'] if fault_pattern else '未知'}
典型根因: {chr(10).join([f'- {r}' for r in recommended_roots]) if recommended_roots else '无参考'}
典型传播路径: {propagation_path}
建议缓解措施: {chr(10).join([f'- {m}' for m in mitigations]) if mitigations else '无参考'}

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

    # 生成thinking_log
    log_entry = f"[{ts}] 值班长决策: stop={should_stop}, fault_type={effective_fault_type}\n{decision_text}"
    
    return {
        "analyst_decision": decision_text,
        "should_stop": should_stop,
        "thinking_log": [log_entry],
    }
