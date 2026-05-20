from __future__ import annotations

from typing import Any

from benchmark_case_loader import case_context_for_path
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


def _source_state(value: Any, real_value: str = "real") -> str:
    if value in (True, "real"):
        return real_value
    if value == "inferred":
        return "inferred"
    if value in ("support", "conflict", "neutral"):
        return str(value)
    return "none"


def _build_three_pillar_matrix(final_result: dict[str, Any], evidence: dict[str, Any], knowledge_hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    existing = final_result.get("three_pillar_matrix") or final_result.get("evidence_matrix") or []
    rows: dict[str, dict[str, Any]] = {}
    ranked_services = final_result.get("ranked_services") or []

    for item in ranked_services:
        if not isinstance(item, dict) or not item.get("service"):
            continue
        service = str(item["service"])
        rows[service] = {
            "service": service,
            "role": str(item.get("role") or "candidate"),
            "metric": "none",
            "log": "none",
            "trace": "none",
            "topology": "none",
            "knowledge": "none",
            "notes": [],
        }

    for item in existing:
        if not isinstance(item, dict) or not item.get("service"):
            continue
        service = str(item["service"])
        row = rows.setdefault(
            service,
            {
                "service": service,
                "role": str(item.get("role") or "candidate"),
                "metric": "none",
                "log": "none",
                "trace": "none",
                "topology": "none",
                "knowledge": "none",
                "notes": [],
            },
        )
        row["role"] = str(item.get("role") or row["role"])
        row["metric"] = _source_state(item.get("metric"))
        row["log"] = _source_state(item.get("log"))
        row["trace"] = _source_state(item.get("trace"))
        row["topology"] = _source_state(item.get("topology"), real_value="inferred")
        row["knowledge"] = _source_state(item.get("knowledge"), real_value="support")
        row["notes"] = [str(note) for note in _as_list(item.get("notes")) if str(note).strip()]

    for pillar, group_name in (("metric", "metrics"), ("log", "logs"), ("trace", "traces")):
        for item in evidence.get(group_name, []) or []:
            if not isinstance(item, dict) or not item.get("service"):
                continue
            service = str(item["service"])
            row = rows.setdefault(
                service,
                {
                    "service": service,
                    "role": "candidate",
                    "metric": "none",
                    "log": "none",
                    "trace": "none",
                    "topology": "none",
                    "knowledge": "none",
                    "notes": [],
                },
            )
            source_type = str(item.get("source_type") or "real")
            item_pillar = str(item.get("pillar") or pillar)
            if item_pillar == "topology" or source_type == "inferred":
                row["topology"] = "inferred"
                if "topology inferred only" not in row["notes"]:
                    row["notes"].append("topology inferred only")
            elif source_type == "real":
                row[pillar] = "real"

    for hit in knowledge_hits or []:
        if not isinstance(hit, dict) or not hit.get("service"):
            continue
        service = str(hit["service"])
        row = rows.setdefault(
            service,
            {
                "service": service,
                "role": "candidate",
                "metric": "none",
                "log": "none",
                "trace": "none",
                "topology": "none",
                "knowledge": "none",
                "notes": [],
            },
        )
        alignment = str(hit.get("alignment") or "support")
        row["knowledge"] = alignment if alignment in {"support", "conflict", "neutral"} else "support"

    return list(rows.values())


def _build_trace_interpretation(evidence: dict[str, Any]) -> dict[str, Any]:
    trace_items = [item for item in evidence.get("traces", []) or [] if isinstance(item, dict)]
    real_trace_available = any(item.get("source_type") == "real" and int(item.get("trace_count", 0) or 0) > 0 for item in trace_items)
    topology_inference_used = any(
        item.get("source_type") == "inferred" or item.get("pillar") == "topology" for item in trace_items
    )
    limitations: list[str] = []
    if not trace_items:
        limitations.append("No trace evidence item was produced.")
    if topology_inference_used and not real_trace_available:
        limitations.append("Topology inference was used as weak context because real traces were unavailable.")
    elif topology_inference_used:
        limitations.append("Topology inference appears alongside real trace evidence and should remain lower weight.")
    if not limitations:
        limitations.append("Real trace evidence is available for at least one requested service.")
    return {
        "real_trace_available": real_trace_available,
        "topology_inference_used": topology_inference_used,
        "trace_limitations": limitations,
    }


def _build_why_top1_failed(final_result: dict[str, Any], matrix: list[dict[str, Any]]) -> dict[str, Any]:
    ranked = [item for item in final_result.get("ranked_services", []) or [] if isinstance(item, dict)]
    if len(ranked) < 2:
        return {"available": False, "reason": "Need at least two ranked candidates to compare Top-1 alternatives."}
    top = ranked[0]
    runner_up = ranked[1]
    top_breakdown = top.get("score_breakdown") if isinstance(top.get("score_breakdown"), dict) else {}
    runner_breakdown = runner_up.get("score_breakdown") if isinstance(runner_up.get("score_breakdown"), dict) else {}
    top_pillars = set(top.get("evidence_pillars") or [])
    runner_pillars = set(runner_up.get("evidence_pillars") or [])
    explanations: list[str] = []
    if len(top_pillars) <= 1:
        explanations.append("Top-1 is supported by a single evidence dimension, so confidence should remain conservative.")
    if "topology" in top_pillars and "trace" not in top_pillars:
        explanations.append("Top-1 uses topology inference without real trace support.")
    if runner_pillars - top_pillars:
        explanations.append(f"Runner-up has additional evidence pillars: {', '.join(sorted(runner_pillars - top_pillars))}.")
    if float(top_breakdown.get("penalty", 0.0) or 0.0) < 0:
        explanations.append("Top-1 received a propagation or evidence-sparsity penalty.")
    if not explanations:
        explanations.append("Top-1 and runner-up are close; review score_breakdown and evidence matrix for tie-breaking.")
    return {
        "available": True,
        "top1_service": top.get("service"),
        "nearest_alternative": runner_up.get("service"),
        "top1_score_breakdown": top_breakdown,
        "alternative_score_breakdown": runner_breakdown,
        "explanations": explanations,
        "does_not_require_expected_label": True,
        "matrix_rows_considered": [row.get("service") for row in matrix[:5] if isinstance(row, dict)],
    }


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


def _build_decision_capabilities(final_result: dict[str, Any], evidence_matrix: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    evidence_matrix = evidence_matrix or final_result.get("three_pillar_matrix") or final_result.get("evidence_matrix") or []
    ranked_services = final_result.get("ranked_services") or []
    dimensions_used: list[str] = []
    for dimension in ("metric", "log", "trace", "knowledge"):
        if any(item.get(dimension) in (True, "real", "support", "conflict", "neutral") for item in evidence_matrix if isinstance(item, dict)):
            dimensions_used.append(dimension)
    if any(item.get("topology") == "inferred" for item in evidence_matrix if isinstance(item, dict)):
        dimensions_used.append("topology")

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
    three_pillar_matrix = _build_three_pillar_matrix(final_result, evidence, state.knowledge_hits or [])
    capability_summary = _build_decision_capabilities(final_result, three_pillar_matrix)
    trace_interpretation = _build_trace_interpretation(evidence)
    why_top1_failed = final_result.get("why_top1_failed") or _build_why_top1_failed(final_result, three_pillar_matrix)
    case_context = case_context_for_path(state.csv_path)
    return {
        "investigation_input": {
            "data_path": state.csv_path,
            "csv_path": state.csv_path,
            "case_context": case_context,
            "dataset": case_context.get("dataset"),
            "scenario": case_context.get("scenario"),
            "case_id": case_context.get("case_id"),
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
            "three_pillar_matrix": three_pillar_matrix,
            "trace_interpretation": trace_interpretation,
            "why_top1_failed": why_top1_failed,
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
            "observability_pillars": {
                "metric": bool(evidence.get("metrics", [])),
                "log": bool(evidence.get("logs", [])),
                "trace": trace_interpretation["real_trace_available"],
                "topology": trace_interpretation["topology_inference_used"],
                "knowledge": bool(state.knowledge_hits or []),
            },
            "three_pillar_matrix": three_pillar_matrix,
            "trace_interpretation": trace_interpretation,
        },
        "artifacts": {
            "report_path": state.report_path,
            "think_log_path": state.think_log_path,
        },
        "report_header": report_header,
        "node_history": state.node_history or [],
    }
