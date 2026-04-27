from __future__ import annotations

from typing import Any

from workflow.state import RCAState


DEFAULT_ANALYSIS_QUESTION = "frontend 延迟升高，请分析根因"


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [value]


def _collect_evidence_services(evidence: dict[str, Any]) -> list[str]:
    services = {
        item.get("service")
        for group in (evidence.get("metrics", []), evidence.get("logs", []), evidence.get("traces", []))
        for item in group
        if isinstance(item, dict) and item.get("service")
    }
    return sorted(str(service) for service in services)


def _build_report_header(state: RCAState) -> dict[str, Any]:
    header = dict(state.report_header or {})
    final_result = state.final_result or {}
    detected_fault = state.detected_fault or {}
    if not header.get("fault_type"):
        fault_types = detected_fault.get("fault_types") or []
        header["fault_type"] = fault_types[0] if fault_types else "unknown"
    if not header.get("analysis_question"):
        header["analysis_question"] = state.user_input
    if not header.get("iteration"):
        header["iteration"] = state.iteration
    if not header.get("root_cause"):
        header["root_cause"] = final_result.get("root_cause")
    if "secondary_causes" not in header:
        header["secondary_causes"] = _as_list(final_result.get("secondary_causes"))
    if not header.get("decision"):
        header["decision"] = final_result.get("decision")
    if header.get("confidence") is None:
        header["confidence"] = final_result.get("confidence")
    if "affected_services" not in header:
        ranked_services = final_result.get("ranked_services") or []
        header["affected_services"] = [
            item.get("service")
            for item in ranked_services
            if isinstance(item, dict) and item.get("service")
        ]
    if not header.get("report_version"):
        header["report_version"] = "v2"
    return header


def _build_decision_capabilities(final_result: dict[str, Any]) -> dict[str, Any]:
    evidence_matrix = final_result.get("evidence_matrix") or []
    ranked_services = final_result.get("ranked_services") or []
    dimensions_used: list[str] = []
    for dimension in ("metric", "log", "trace", "knowledge"):
        if any(bool(item.get(dimension)) for item in evidence_matrix if isinstance(item, dict)):
            dimensions_used.append(dimension)

    role_breakdown: dict[str, list[str]] = {}
    for item in ranked_services:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "candidate")
        service = item.get("service")
        if not service:
            continue
        role_breakdown.setdefault(role, []).append(str(service))

    propagation_summary = final_result.get("propagation_summary") or {}
    has_propagation_chain = bool(
        _as_list(propagation_summary.get("paths")) or _as_list(final_result.get("evidence_links"))
    )
    has_excluded_hypotheses = bool(_as_list(final_result.get("excluded_hypotheses")))

    return {
        "evidence_dimensions_used": dimensions_used,
        "service_role_breakdown": role_breakdown,
        "has_propagation_chain": has_propagation_chain,
        "has_excluded_hypotheses": has_excluded_hypotheses,
    }


def build_investigation_summary(state: RCAState) -> dict[str, Any]:
    final_result = state.final_result or {}
    evidence = state.evidence or {}
    report_header = _build_report_header(state)
    evidence_services = _collect_evidence_services(evidence)
    capability_summary = _build_decision_capabilities(final_result)
    return {
        "investigation_input": {
            "csv_path": state.csv_path,
            "user_input": state.user_input,
            "start": state.start,
            "end": state.end,
            "iteration": state.iteration,
            "max_iter": state.max_iter,
        },
        "decision_summary": {
            "root_cause": final_result.get("root_cause"),
            "secondary_causes": _as_list(final_result.get("secondary_causes")),
            "decision": final_result.get("decision"),
            "confidence": final_result.get("confidence"),
            "ranked_services": final_result.get("ranked_services") or [],
            "reasoning": final_result.get("reasoning") or [],
            "evidence_links": final_result.get("evidence_links") or [],
            "evidence_gaps": final_result.get("evidence_gaps") or [],
            "recommended_actions": final_result.get("recommended_actions") or [],
            "symptom_service": final_result.get("symptom_service"),
            "primary_root_cause": final_result.get("primary_root_cause") or final_result.get("root_cause"),
            "secondary_root_causes": final_result.get("secondary_root_causes") or _as_list(final_result.get("secondary_causes")),
            "impact_summary": final_result.get("impact_summary") or {},
            "propagation_summary": final_result.get("propagation_summary") or {},
            "excluded_hypotheses": final_result.get("excluded_hypotheses") or [],
            "evidence_matrix": final_result.get("evidence_matrix") or [],
            "recommendation_tiers": final_result.get("recommendation_tiers") or {},
            "analysis_mode": final_result.get("analysis_mode"),
            **capability_summary,
        },
        "evidence_summary": {
            "metric_count": len(evidence.get("metrics", [])),
            "log_count": len(evidence.get("logs", [])),
            "trace_count": len(evidence.get("traces", [])),
            "knowledge_hit_count": len(state.knowledge_hits or []),
            "services": evidence_services,
        },
        "artifacts": {
            "report_path": state.report_path,
            "think_log_path": state.think_log_path,
        },
        "report_header": report_header,
        "node_history": state.node_history or [],
    }
