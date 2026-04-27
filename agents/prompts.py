from __future__ import annotations

from typing import Any


TOOL_GROUNDED_NOTES = [
    "Only reason from the provided tool outputs, retrieved knowledge hits, topology details, and user input.",
    "Do not invent metric values, timestamps, log messages, trace paths, anomaly scores, or affected services.",
    "If evidence is insufficient or conflicting, state that explicitly and lower confidence.",
    "Historical knowledge is reference-only and cannot override current tool evidence.",
    "Every conclusion must be traceable to at least one evidence field in the provided inputs.",
]


REPORT_HEADER_FIELDS = [
    "fault_type",
    "analysis_question",
    "generated_at",
    "iteration",
    "root_cause",
    "secondary_causes",
    "decision",
    "confidence",
    "affected_services",
    "report_version",
]


def build_agent_prompt(
    role: str,
    objective: str,
    inputs: dict[str, Any],
    output_schema: dict[str, Any],
    notes: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "role": role,
        "objective": objective,
        "inputs": inputs,
        "output_schema": output_schema,
        "notes": notes or [],
    }


def to_langchain_messages(prompt: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    system_prompt = "\n".join(
        [
            f"Role: {prompt['role']}",
            f"Objective: {prompt['objective']}",
            "Return valid JSON matching the provided output schema.",
            *(f"Note: {note}" for note in prompt.get("notes", [])),
        ]
    )
    human_payload = {
        "inputs": prompt.get("inputs", {}),
        "output_schema": prompt.get("output_schema", {}),
    }
    return system_prompt, human_payload


def master_prompt(state_summary: dict[str, Any], user_input: str) -> dict[str, Any]:
    return build_agent_prompt(
        role="MasterAgent",
        objective="Generate the next investigation plan from user symptoms and dataset-level signals without making final RCA conclusions.",
        inputs={
            "user_input": user_input,
            "services": state_summary.get("services", []),
            "service_metrics": state_summary.get("service_metrics", {}),
            "fault_types": state_summary.get("fault_types", []),
            "knowledge_hits": state_summary.get("knowledge_hits", []),
            "topology_details": state_summary.get("topology_details", {}),
        },
        output_schema={
            "hypotheses": [
                {
                    "service": "str",
                    "role": "origin|propagated|symptom",
                    "hypothesis": "str",
                    "evidence_basis": "str",
                    "knowledge_support": "str|optional",
                    "priority": "high|medium|low",
                }
            ],
            "actions": [
                {
                    "tool": "metric|log|trace",
                    "service": "str",
                    "metric": "str|optional",
                    "why": "str",
                    "expected_signal": "str",
                    "derived_from_knowledge": "bool|optional",
                }
            ],
            "selected_services": ["str"],
            "knowledge_guidance": ["str"],
        },
        notes=TOOL_GROUNDED_NOTES
        + [
            "This agent is a planner, not the final decision maker.",
            "Each hypothesis must bind to a concrete service from the candidate list.",
            "Label each hypothesis as likely origin, propagated impact, or symptom candidate.",
            "Each action must explain why the tool is needed and what evidence would confirm or reject the hypothesis.",
            "Prefer a focused plan that verifies the strongest suspects first.",
            "Use historical knowledge to prioritize checks, add differential checks, and identify missing evidence, but never treat it as direct proof.",
            "If historical knowledge conflicts with current candidate signals, add actions that explicitly resolve the conflict.",
        ],
    )


def metric_prompt(plan: dict[str, Any], time_window: dict[str, Any]) -> dict[str, Any]:
    return build_agent_prompt(
        role="MetricAgent",
        objective="Inspect requested service metrics and summarize anomaly evidence.",
        inputs={"actions": plan.get("actions", []), "time_window": time_window},
        output_schema={
            "metrics": [
                {
                    "service": "str",
                    "metric": "str",
                    "stats": "dict",
                    "is_anomalous": "bool",
                    "anomaly_timestamps": ["int"],
                    "peak_value": "float|None",
                }
            ]
        },
        notes=TOOL_GROUNDED_NOTES,
    )


def log_prompt(plan: dict[str, Any], time_window: dict[str, Any]) -> dict[str, Any]:
    return build_agent_prompt(
        role="LogAgent",
        objective="Inspect requested services and summarize simulated log patterns in the active window.",
        inputs={"actions": plan.get("actions", []), "time_window": time_window},
        output_schema={
            "logs": [
                {
                    "service": "str",
                    "log_count": "int",
                    "top_patterns": "list[dict]",
                    "sample_logs": "list[dict]",
                }
            ]
        },
        notes=TOOL_GROUNDED_NOTES,
    )


def trace_prompt(plan: dict[str, Any], time_window: dict[str, Any]) -> dict[str, Any]:
    return build_agent_prompt(
        role="TraceAgent",
        objective="Inspect requested services and summarize propagation paths in the active window.",
        inputs={"actions": plan.get("actions", []), "time_window": time_window},
        output_schema={
            "traces": [
                {
                    "service": "str",
                    "trace_count": "int",
                    "propagation_paths": "list[str]",
                    "sample_traces": "list[dict]",
                }
            ]
        },
        notes=TOOL_GROUNDED_NOTES,
    )


def analyst_prompt(
    evidence: dict[str, Any],
    iteration: int,
    max_iter: int,
    knowledge_hits: list[dict[str, Any]] | None = None,
    topology_details: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return build_agent_prompt(
        role="AnalystAgent",
        objective="Fuse metric, log, trace, topology, and historical knowledge into a ranked root-cause decision grounded in tool evidence.",
        inputs={
            "evidence": evidence,
            "iteration": iteration,
            "max_iter": max_iter,
            "knowledge_hits": knowledge_hits or [],
            "topology_details": topology_details or {},
        },
        output_schema={
            "decision": "stop|continue",
            "confidence": "float",
            "root_cause": "str",
            "secondary_causes": "list[str]",
            "ranked_services": "list[dict(service, score, role, evidence_count)]",
            "reasoning": "list[str]",
            "evidence_links": "list[dict(source_service, target_service, relation, evidence)]",
            "evidence_gaps": "list[str]",
            "recommended_actions": "list[str]",
            "knowledge_alignment": "list[str]|optional",
            "symptom_service": "str|optional",
            "primary_root_cause": "str|optional",
            "secondary_root_causes": "list[str]|optional",
            "impact_summary": "dict(core_services, affected_services, narrative)|optional",
            "propagation_summary": "dict(summary_lines, paths)|optional",
            "excluded_hypotheses": "list[dict(hypothesis, reason)]|optional",
            "evidence_matrix": "list[dict(service, role, metric, log, trace, knowledge, notes)]|optional",
            "recommendation_tiers": "dict(immediate, verification, hardening)|optional",
        },
        notes=TOOL_GROUNDED_NOTES
        + [
            "The reported root_cause must be a real service supported by current metrics/logs/traces evidence.",
            "If only one evidence dimension supports a service, confidence should stay below 0.8.",
            "Distinguish between likely origin service, propagated impact service, and symptom service.",
            "Use evidence_links to describe explicit cause, dependency, or propagation relationships between services.",
            "Use evidence_gaps to state what is still missing before a stronger stop decision would be justified.",
            "If the evidence does not justify a stop decision, return continue with clear evidence gaps.",
            "State whether historical knowledge supports, conflicts with, or is neutral to the current tool evidence.",
            "Historical knowledge may improve prioritization and explanation, but cannot replace missing tool evidence.",
        ],
    )



def reporter_prompt(state_view: dict[str, Any]) -> dict[str, Any]:
    return build_agent_prompt(
        role="ReporterAgent",
        objective="Generate a dual-layer Markdown incident report with a stable machine-readable header and a high-quality Chinese RCA narrative grounded in evidence.",
        inputs=state_view,
        output_schema={
            "report_path": "str",
            "report_preview": "str",
            "report_header": {field: "str|list|float|int|None" for field in REPORT_HEADER_FIELDS},
        },
        notes=TOOL_GROUNDED_NOTES
        + [
            "Use a stable top header so UI pages can parse fault_type, root_cause, decision, and confidence.",
            "Separate verified facts, inferred causes, propagation impacts, evidence gaps, and recommendations.",
            "Prefer writing a causal narrative instead of only restating tables.",
            "Use knowledge hits as supporting context only when they align with current evidence.",
            "Do not add JVM, thread pool, middleware, or code-level details unless present in evidence or retrieved knowledge.",
            "Write a defense-friendly but evidence-grounded report: persuasive structure is allowed, invented facts are not.",
        ],
    )
