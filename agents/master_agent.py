from __future__ import annotations

import json
from typing import Any

from agents.prompts import master_prompt, to_langchain_messages
from knowledge_base.retriever import KnowledgeRetriever
from llm.model_factory import LLMAdapter
from llm.structured_output import extract_json_object
from tools.metric_tools import MetricToolbox
from workflow.state import RCAState


MASTER_SYSTEM_PROMPT = """You are the Master Agent of an AIOps RCA workflow.
Return valid JSON only.
Your job is planning, not final root-cause confirmation.
Use the provided dataset summary, detected fault types, candidate metric evidence, retrieved historical cases, and topology details.
Each action must use one of: metric, log, trace.
Only plan investigations for services grounded in the provided candidates or topology context.
Do not invent services, metrics, timestamps, or supporting evidence.
Historical knowledge is reference-only and cannot be treated as proof of the current incident.
Every hypothesis must be tied to a concrete service and every action must explain why that tool is needed.
Use historical knowledge to prioritize checks, add differential checks, and surface missing evidence.
If knowledge hits conflict with current candidate signals, add actions that explicitly resolve the conflict.
"""


class MasterAgent:
    name = "master"

    def __init__(
        self,
        metric_toolbox: MetricToolbox,
        knowledge_retriever: KnowledgeRetriever | None = None,
        llm_adapter: LLMAdapter | None = None,
    ):
        self.metric_toolbox = metric_toolbox
        self.knowledge_retriever = knowledge_retriever
        self.llm_adapter = llm_adapter

    def build_prompt(self, state: RCAState) -> dict[str, Any]:
        summary = {
            **state.dataset_summary,
            "fault_types": state.detected_fault.get("fault_types", []),
            "knowledge_hits": state.knowledge_hits,
            "topology_details": state.topology_details,
        }
        return master_prompt(summary, state.user_input)

    def _metric_priority(self, metric_name: str) -> float:
        weights = {
            "error": 0.42,
            "latency": 0.34,
            "cpu": 0.28,
            "mem": 0.24,
            "load": 0.26,
        }
        return weights.get(metric_name, 0.18)

    def _knowledge_map(self, hits: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for hit in hits:
            service = str(hit.get("service") or "").strip()
            if not service:
                continue
            grouped.setdefault(service, []).append(hit)
        return grouped

    def _knowledge_guidance_for_service(
        self,
        service: str,
        hits: list[dict[str, Any]],
        fault_types: set[str],
    ) -> tuple[list[str], list[dict[str, Any]], str]:
        guidance: list[str] = []
        extra_actions: list[dict[str, Any]] = []
        support_fragments: list[str] = []

        for hit in hits[:3]:
            hit_fault_type = str(hit.get("fault_type") or "").strip()
            metadata = hit.get("metadata") or {}
            metric = str(metadata.get("metric") or "").strip()
            candidate_role = str(metadata.get("candidate_role") or "").strip()
            title = str(hit.get("title") or hit.get("document_id") or "历史案例").strip()
            solution = str(hit.get("solution") or "").strip()

            if hit_fault_type and hit_fault_type in fault_types:
                guidance.append(f"历史案例《{title}》提示 {service} 曾出现相同故障类型 {hit_fault_type}")
                support_fragments.append(f"历史案例《{title}》与当前故障类型一致")
            elif hit_fault_type:
                guidance.append(f"历史案例《{title}》涉及 {service}，但故障类型为 {hit_fault_type}，需排除误导")
                extra_actions.append(
                    {
                        "tool": "trace",
                        "service": service,
                        "why": f"历史案例《{title}》提示 {service} 可能不是同类首因，需要通过调用链确认当前异常是首发还是传播结果",
                        "expected_signal": "若当前故障与历史模式不同，调用链角色应与历史案例表现出差异",
                        "derived_from_knowledge": True,
                    }
                )

            if metric:
                guidance.append(f"历史案例《{title}》建议优先验证 {service} 的 {metric} 指标")
                extra_actions.append(
                    {
                        "tool": "metric",
                        "service": service,
                        "metric": metric,
                        "why": f"历史案例《{title}》表明 {metric} 是关键验证点，需要确认当前窗口是否出现同类异常",
                        "expected_signal": f"若当前事件与历史模式接近，则 {service} 的 {metric} 应在当前窗口出现持续异常",
                        "derived_from_knowledge": True,
                    }
                )
            if candidate_role == "symptom_or_propagated":
                guidance.append(f"历史案例《{title}》提示 {service} 可能是症状或传播节点，不能只看表面异常")
                extra_actions.append(
                    {
                        "tool": "log",
                        "service": service,
                        "why": f"历史案例《{title}》提示 {service} 可能是传播放大点，需要用日志确认是否存在本地错误模式而非单纯被拖累",
                        "expected_signal": "若日志缺少本地错误信号，则该服务更可能是传播结果",
                        "derived_from_knowledge": True,
                    }
                )
            if solution:
                support_fragments.append(f"历史建议动作包括：{solution}")

        support_text = "；".join(support_fragments) if support_fragments else ""
        return guidance, extra_actions, support_text

    def _deduplicate_actions(self, actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[tuple[str, str, str]] = set()
        deduped: list[dict[str, Any]] = []
        for action in actions:
            key = (
                str(action.get("tool") or ""),
                str(action.get("service") or ""),
                str(action.get("metric") or ""),
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(action)
        return deduped

    def _build_rule_based_plan(self, state: RCAState, prompt: dict[str, Any]) -> dict[str, Any]:
        summary = state.dataset_summary
        service_metrics = summary.get("service_metrics", {})
        topology_details = state.topology_details
        fault_types = set(state.detected_fault.get("fault_types", []))
        knowledge_map = self._knowledge_map(state.knowledge_hits)
        candidates: list[dict[str, Any]] = []

        for service, metrics in service_metrics.items():
            score = 0.0
            metric_actions: list[dict[str, str]] = []
            metric_evidence: list[dict[str, Any]] = []
            anomalous_metrics: list[str] = []

            for metric in ["cpu", "load", "latency", "error", "mem"]:
                if metric not in metrics:
                    continue
                metric_summary = self.metric_toolbox.summarize_metric(
                    service=service,
                    metric=metric,
                    start=state.start,
                    end=state.end,
                )
                metric_evidence.append(metric_summary)
                if metric_summary["is_anomalous"]:
                    anomalous_metrics.append(metric)
                    score += self._metric_priority(metric)
                    if metric in fault_types:
                        score += 0.08
                    metric_actions.append({"service": service, "metric": metric})

            if not metric_actions:
                continue

            topology = topology_details.get(service, {})
            upstreams = topology.get("upstreams") or []
            downstreams = topology.get("downstreams") or []
            if upstreams:
                score += 0.03
            if downstreams:
                score += 0.05
            if service in knowledge_map:
                score += 0.07

            role = "origin"
            if any(metric in {"latency", "error"} for metric in anomalous_metrics) and not any(
                metric in {"cpu", "mem", "load"} for metric in anomalous_metrics
            ):
                role = "symptom"
            elif upstreams and any(metric in {"latency", "error"} for metric in anomalous_metrics):
                role = "propagated"

            candidates.append(
                {
                    "service": service,
                    "score": round(score, 4),
                    "actions": metric_actions,
                    "metric_evidence": metric_evidence,
                    "anomalous_metrics": anomalous_metrics,
                    "role": role,
                    "upstreams": upstreams,
                    "downstreams": downstreams,
                }
            )

        candidates.sort(key=lambda item: item["score"], reverse=True)
        selected = candidates[:3]
        hypotheses = []
        actions: list[dict[str, Any]] = []
        knowledge_guidance: list[str] = []

        for item in selected:
            service = item["service"]
            anomalous_metrics = item["anomalous_metrics"]
            role = item["role"]
            basis_parts = [f"异常指标: {', '.join(anomalous_metrics)}"]
            if item["upstreams"]:
                basis_parts.append(f"上游依赖: {', '.join(item['upstreams'])}")

            service_guidance, extra_actions, knowledge_support = self._knowledge_guidance_for_service(
                service,
                knowledge_map.get(service, []),
                fault_types,
            )
            knowledge_guidance.extend(service_guidance)
            if knowledge_support:
                basis_parts.append("存在相关历史案例命中")

            hypotheses.append(
                {
                    "service": service,
                    "role": role,
                    "hypothesis": f"{service} 可能是当前事件中的 {role} 候选，需要进一步核验其异常是首发还是传播结果。",
                    "evidence_basis": "；".join(basis_parts),
                    "knowledge_support": knowledge_support,
                    "priority": "high" if item is selected[0] else "medium",
                }
            )

            for metric_action in item["actions"]:
                metric_name = metric_action["metric"]
                actions.append(
                    {
                        "tool": "metric",
                        "service": service,
                        "metric": metric_name,
                        "why": f"确认 {service} 的 {metric_name} 异常强度与持续性，判断它更像首发异常还是传播症状",
                        "expected_signal": f"若 {service} 是关键候选，则 {metric_name} 应在当前窗口持续异常",
                        "derived_from_knowledge": False,
                    }
                )
            actions.append(
                {
                    "tool": "log",
                    "service": service,
                    "why": f"检查 {service} 是否存在与异常时间重合的错误模式或资源争用信号",
                    "expected_signal": "日志中应出现与当前异常时间窗口对齐的高频错误或资源异常模式",
                    "derived_from_knowledge": False,
                }
            )
            actions.append(
                {
                    "tool": "trace",
                    "service": service,
                    "why": f"确认 {service} 在传播链中的位置，区分首因、放大点和症状节点",
                    "expected_signal": "调用链应揭示该服务是异常起点还是被上游依赖拖累",
                    "derived_from_knowledge": False,
                }
            )
            actions.extend(extra_actions)

        actions = self._deduplicate_actions(actions)
        knowledge_guidance = list(dict.fromkeys(knowledge_guidance))

        return {
            "prompt": prompt,
            "user_input": state.user_input,
            "hypotheses": hypotheses,
            "actions": actions,
            "selected_services": [item["service"] for item in selected],
            "knowledge_guidance": knowledge_guidance,
            "planner_mode": "rule",
        }

    def run(self, state: RCAState) -> dict[str, Any]:
        prompt = self.build_prompt(state)
        fallback_result = self._build_rule_based_plan(state, prompt)

        if not self.llm_adapter or not self.llm_adapter.enabled:
            state.llm_enabled = False
            state.llm_reason = self.llm_adapter.reason if self.llm_adapter else "LLM adapter is unavailable."
            fallback_result["llm_status"] = state.llm_reason
            return fallback_result

        candidate_evidence = []
        for service in state.dataset_summary.get("service_metrics", {}):
            service_metrics = state.dataset_summary["service_metrics"].get(service, [])
            candidate_evidence.append(
                {
                    "service": service,
                    "available_metrics": service_metrics,
                }
            )

        llm_payload = {
            "prompt": prompt,
            "candidate_services": candidate_evidence,
            "knowledge_hits": state.knowledge_hits,
            "topology_details": state.topology_details,
            "time_window": {"start": state.start, "end": state.end},
        }

        try:
            system_prompt, human_payload = to_langchain_messages(prompt)
            response = self.llm_adapter.invoke_messages(
                [
                    ("system", f"{MASTER_SYSTEM_PROMPT}\n\n{system_prompt}"),
                    ("human", json.dumps({**human_payload, **llm_payload}, ensure_ascii=False, indent=2)),
                ]
            )
            parsed = extract_json_object(response["raw_text"])
            state.llm_enabled = True
            state.llm_reason = ""
            hypotheses = parsed.get("hypotheses", fallback_result["hypotheses"])
            actions = parsed.get("actions", fallback_result["actions"])
            selected_services = parsed.get("selected_services", fallback_result["selected_services"])
            knowledge_guidance = parsed.get("knowledge_guidance", fallback_result["knowledge_guidance"])
            if not isinstance(hypotheses, list):
                hypotheses = fallback_result["hypotheses"]
            if not isinstance(actions, list):
                actions = fallback_result["actions"]
            if not isinstance(selected_services, list):
                selected_services = fallback_result["selected_services"]
            if not isinstance(knowledge_guidance, list):
                knowledge_guidance = fallback_result["knowledge_guidance"]
            return {
                "prompt": prompt,
                "user_input": state.user_input,
                "hypotheses": hypotheses,
                "actions": self._deduplicate_actions(actions),
                "selected_services": selected_services,
                "knowledge_guidance": knowledge_guidance,
                "planner_mode": "llm",
                "llm_raw": response["raw_text"][:4000],
            }
        except Exception as exc:
            state.llm_enabled = False
            state.llm_reason = str(exc)
            fallback_result["llm_status"] = str(exc)
            return fallback_result
