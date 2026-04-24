"""
值班长节点实现 - 增强版，输出结构化仲裁结果
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
    值班长节点：整合证据、结构化仲裁、决定是否继续。
    知识库仅作为参考，观测证据优先；是唯一有权决定停止的节点。
    """
    llm = _create_llm()
    ts = datetime.now().strftime("%H:%M:%S")
    iteration = state.get("iteration", 0)
    max_iter = state.get("max_iterations", 3)
    
    # 获取聚合证据汇总（优先使用结构化汇总）
    aggregate_summary = state.get("aggregate_summary", {})
    
    # 知识库参考（仅作参考，不覆盖观测证据）
    effective_fault_type = state.get("detected_fault_type") or "unknown"
    km = get_knowledge_manager()
    fault_pattern = km.get_fault_pattern(effective_fault_type)
    
    # 构建证据文本（结构化优先）
    evidence_parts = [
        f"=== 第 {iteration} 轮分析证据汇总 ===",
        f"【检测标签参考】{effective_fault_type}（仅作参考，不驱动推理）",
        f"【用户问题】{state.get('user_query', '')}",
        "",
        "【聚合证据汇总】（结构化）",
        json.dumps(aggregate_summary, ensure_ascii=False, indent=2) if aggregate_summary else "暂无汇总",
        "",
        "【运维专家计划】",
        state.get('master_plan', '无'),
        "",
        "【指标分析（最新）】",
        json.dumps(state.get('metric_analysis', {}), ensure_ascii=False) if state.get('metric_analysis') else '暂无',
        "",
        "【日志分析（最新）】",
        json.dumps(state.get('log_analysis', {}), ensure_ascii=False) if state.get('log_analysis') else '暂无',
        "",
        "【链路分析（最新）】",
        json.dumps(state.get('trace_analysis', {}), ensure_ascii=False) if state.get('trace_analysis') else '暂无',
        "",
        "【知识库参考】（仅作参考，观测证据优先）",
        f"故障模式: {fault_pattern['name'] if fault_pattern else '未知'}",
        f"典型根因参考: {', '.join(fault_pattern.get('common_roots', [])) if fault_pattern else '无'}",
        "",
        f"【迭代进度】第 {iteration + 1} / {max_iter} 轮",
    ]
    
    evidence = "\n".join(evidence_parts)
    
    # 系统提示词（强制结构化输出）
    system_prompt = get_analyst_prompt(evidence)
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content="""请评估当前证据，输出严格符合以下JSON格式的结构化仲裁结果：
{
    "direct_root_cause": "直接根因服务或原因，无则null",
    "amplifiers": ["放大问题的服务/因素"],
    "propagation_hubs": ["传播枢纽服务"],
    "affected_services": ["被动受影响的服务"],
    "candidate_root_causes": ["候选根因列表"],
    "missing_evidence": ["缺失的关键证据"],
    "confidence": 0.0-1.0,
    "should_continue": true/false,
    "reasoning": "从证据到结论的推理链"
}

注意：
1. 直接根因必须有观测证据支撑，无则填null
2. 置信度>0.8且证据充分时可停止（should_continue=false）
3. 知识库信息仅作参考，观测证据冲突时以观测为准
4. 输出必须是合法JSON，不要包含```json标记"""),
    ]

    response = llm.invoke(messages)
    decision_text = response.content

    # 解析结构化决策
    analyst_output = {
        "direct_root_cause": None,
        "amplifiers": [],
        "propagation_hubs": [],
        "affected_services": [],
        "candidate_root_causes": [],
        "missing_evidence": [],
        "confidence": 0.0,
        "should_continue": True,
        "reasoning": "",
        "raw_output": decision_text,
    }
    
    try:
        # 提取JSON
        json_str = decision_text.strip()
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0].strip()
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0].strip()
        
        decision = json.loads(json_str)
        
        # 赋值（带类型检查）
        analyst_output["direct_root_cause"] = decision.get("direct_root_cause")
        analyst_output["amplifiers"] = decision.get("amplifiers", []) if isinstance(decision.get("amplifiers"), list) else []
        analyst_output["propagation_hubs"] = decision.get("propagation_hubs", []) if isinstance(decision.get("propagation_hubs"), list) else []
        analyst_output["affected_services"] = decision.get("affected_services", []) if isinstance(decision.get("affected_services"), list) else []
        analyst_output["candidate_root_causes"] = decision.get("candidate_root_causes", []) if isinstance(decision.get("candidate_root_causes"), list) else []
        analyst_output["missing_evidence"] = decision.get("missing_evidence", []) if isinstance(decision.get("missing_evidence"), list) else []
        analyst_output["confidence"] = float(decision.get("confidence", 0.0))
        analyst_output["should_continue"] = bool(decision.get("should_continue", True))
        analyst_output["reasoning"] = str(decision.get("reasoning", ""))
        
        # 置信度阈值判断
        if analyst_output["confidence"] >= WORKFLOW_CONFIG.get("convergence_threshold", 0.8):
            analyst_output["should_continue"] = False
            
    except (json.JSONDecodeError, IndexError, KeyError, ValueError) as e:
        # 解析失败，保持继续迭代
        analyst_output["reasoning"] = f"解析失败: {str(e)}，继续迭代"
    
    # 达到最大迭代次数强制停止
    if iteration + 1 >= max_iter:
        analyst_output["should_continue"] = False
        analyst_output["reasoning"] += "；已达最大迭代次数，强制停止"
    
    # 生成thinking_log
    log_entry = f"[{ts}] 分析师仲裁: 根因={analyst_output['direct_root_cause']}, 置信度={analyst_output['confidence']:.2f}, 继续={analyst_output['should_continue']}"
    
    return {
        "analyst_output": analyst_output,
        "thinking_log": [log_entry],
    }
