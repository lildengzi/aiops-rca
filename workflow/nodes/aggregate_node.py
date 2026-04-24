"""
并行结果汇总节点实现 - 增强版，生成结构化证据汇总
"""
from datetime import datetime
from typing import Dict, Any, Set, List
from workflow.state import RCAState


def _extract_services_from_analysis(analysis: Dict[str, Any]) -> Set[str]:
    """从智能体分析中提取提到的服务"""
    services = set()
    if not analysis:
        return services
    
    # 尝试从不同格式中提取服务名
    # 1. 直接包含services字段
    if "services" in analysis and isinstance(analysis["services"], list):
        services.update(analysis["services"])
    
    # 2. 从anomalous_services提取
    if "anomalous_services" in analysis and isinstance(analysis["anomalous_services"], list):
        for svc in analysis["anomalous_services"]:
            if isinstance(svc, dict) and "service" in svc:
                services.add(svc["service"])
            elif isinstance(svc, str):
                services.add(svc)
    
    # 3. 从文本中简单提取（fallback）
    if not services and "summary" in analysis and isinstance(analysis["summary"], str):
        summary = analysis["summary"].lower()
        # 简单关键词匹配（实际应从state中获取SERVICE_TOPOLOGY）
        from config import SERVICE_TOPOLOGY
        for svc in SERVICE_TOPOLOGY.keys():
            if svc.lower() in summary:
                services.add(svc)
    
    return services


def _extract_candidate_roots(analysis: Dict[str, Any]) -> List[str]:
    """从分析中提取候选根因"""
    roots = []
    if not analysis:
        return roots
    
    # 从candidate_root_causes字段提取
    if "candidate_root_causes" in analysis and isinstance(analysis["candidate_root_causes"], list):
        roots.extend(analysis["candidate_root_causes"])
    
    # 从anomalous_services中提取高分异常
    if "anomalous_services" in analysis and isinstance(analysis["anomalous_services"], list):
        for svc in analysis["anomalous_services"]:
            if isinstance(svc, dict) and svc.get("anomaly_score", 0) > 0.7:
                roots.append(svc.get("service", ""))
    
    return list(set(roots))


def aggregate_node(state: RCAState) -> dict:
    """
    并行结果汇总节点：汇总metric/log/trace三方证据，生成结构化摘要
    输出包含：共同指向的服务、候选根因、传播节点、证据冲突、缺失证据
    """
    ts = datetime.now().strftime("%H:%M:%S")
    
    metric_analysis = state.get("metric_analysis")
    log_analysis = state.get("log_analysis")
    trace_analysis = state.get("trace_analysis")
    
    # 提取各智能体提到的服务
    metric_svcs = _extract_services_from_analysis(metric_analysis)
    log_svcs = _extract_services_from_analysis(log_analysis)
    trace_svcs = _extract_services_from_analysis(trace_analysis)
    
    # 共同服务（至少两个智能体提到）
    all_svcs = metric_svcs | log_svcs | trace_svcs
    common_services = []
    for svc in all_svcs:
        count = sum([svc in metric_svcs, svc in log_svcs, svc in trace_svcs])
        if count >= 2:
            common_services.append(svc)
    
    # 候选根因
    candidate_roots = set()
    candidate_roots.update(_extract_candidate_roots(metric_analysis))
    candidate_roots.update(_extract_candidate_roots(log_analysis))
    candidate_roots.update(_extract_candidate_roots(trace_analysis))
    
    # 传播枢纽（从trace或log中提取）
    propagation_hubs = []
    if trace_analysis and "propagation_hubs" in trace_analysis:
        propagation_hubs = trace_analysis["propagation_hubs"]
    elif log_analysis and "propagation_hubs" in log_analysis:
        propagation_hubs = log_analysis["propagation_hubs"]
    
    # 受影响服务（所有提到过的服务）
    affected_services = list(all_svcs)
    
    # 证据冲突（不同智能体指向不同根因）
    conflicts = []
    m_roots = _extract_candidate_roots(metric_analysis)
    l_roots = _extract_candidate_roots(log_analysis)
    t_roots = _extract_candidate_roots(trace_analysis)
    
    if m_roots and l_roots and set(m_roots) != set(l_roots):
        conflicts.append(f"指标分析指向: {m_roots}, 日志分析指向: {l_roots}")
    if m_roots and t_roots and set(m_roots) != set(t_roots):
        conflicts.append(f"指标分析指向: {m_roots}, 链路分析指向: {t_roots}")
    if l_roots and t_roots and set(l_roots) != set(t_roots):
        conflicts.append(f"日志分析指向: {l_roots}, 链路分析指向: {t_roots}")
    
    # 缺失证据
    missing_evidence = []
    if not metric_analysis:
        missing_evidence.append("缺少指标分析证据")
    if not log_analysis:
        missing_evidence.append("缺少日志分析证据")
    if not trace_analysis:
        missing_evidence.append("缺少链路分析证据")
    
    # 构建结构化汇总
    summary = {
        "common_services": common_services,
        "candidate_root_causes": list(candidate_roots),
        "propagation_hubs": propagation_hubs,
        "affected_services": affected_services,
        "conflicts": conflicts,
        "missing_evidence": missing_evidence,
        "metric_services": list(metric_svcs),
        "log_services": list(log_svcs),
        "trace_services": list(trace_svcs),
        "iteration": state.get("iteration", 0),
    }
    
    # 生成thinking_log
    log_entry = f"[{ts}] 证据汇总完成 - 共同服务: {common_services}, 候选根因: {list(candidate_roots)[:3]}"
    
    return {
        "aggregate_summary": summary,
        "thinking_log": [log_entry],
    }
