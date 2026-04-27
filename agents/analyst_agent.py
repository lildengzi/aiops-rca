from __future__ import annotations

import json
from typing import Any

from agents.prompts import analyst_prompt, to_langchain_messages
from knowledge_base.retriever import KnowledgeRetriever
from llm.model_factory import LLMAdapter
from llm.structured_output import extract_json_object
from workflow.state import RCAState


ANALYST_SYSTEM_PROMPT = """You are the Analyst Agent of an AIOps RCA workflow.
Return valid JSON only.
Fuse metric, log, trace, topology, and historical knowledge into a final RCA decision.
Required fields: decision, confidence, root_cause, secondary_causes, ranked_services, reasoning, evidence_links, evidence_gaps, recommended_actions.
Use confidence between 0 and 1.
Only conclude from the provided evidence. Do not invent metric values, log messages, trace paths, propagation chains, or timestamps.
Historical knowledge is supportive context only and cannot override current tool evidence.
If evidence is insufficient or conflicting, explicitly state the gap and keep confidence conservative.
If only one evidence dimension supports a service, confidence must remain below 0.8.
Distinguish between symptom services, propagated impact, and likely origin services.
Set decision to stop only when the current evidence is sufficient, otherwise continue.
State whether historical knowledge supports, conflicts with, or is neutral to the current tool evidence.
"""


class AnalystAgent:
    name = "analyst"

    def __init__(
        self,
        knowledge_retriever: KnowledgeRetriever | None = None,
        llm_adapter: LLMAdapter | None = None,
    ):
        self.knowledge_retriever = knowledge_retriever
        self.llm_adapter = llm_adapter

    def build_prompt(self, state: RCAState) -> dict[str, Any]:
        return analyst_prompt(
            state.evidence,
            state.iteration,
            state.max_iter,
            knowledge_hits=state.knowledge_hits,
            topology_details=state.topology_details,
        )

    def _metric_weight(self, metric_name: str) -> float:
        weights = {
            "cpu": 0.28,
            "mem": 0.24,
            "latency": 0.34,
            "error": 0.38,
            "load": 0.26,
        }
        return weights.get(metric_name, 0.2)

    def _normalize_list_of_strings(self, value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item) for item in value if str(item).strip()]
        if value in (None, ""):
            return []
        return [str(value)]

    def _normalize_ranked_services(self, value: Any, fallback: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return fallback

        normalized: list[dict[str, Any]] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            service = str(item.get("service", "")).strip()
            if not service:
                continue
            try:
                score = round(float(item.get("score", 0.0)), 2)
            except (TypeError, ValueError):
                score = 0.0
            normalized.append(
                {
                    "service": service,
                    "score": score,
                    "role": str(item.get("role", "candidate")),
                    "evidence_count": int(item.get("evidence_count", 0) or 0),
                }
            )
        return normalized or fallback

    def _normalize_evidence_links(self, value: Any, fallback: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return fallback

        normalized: list[dict[str, Any]] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            source_service = str(item.get("source_service", "")).strip()
            target_service = str(item.get("target_service", "")).strip()
            relation = str(item.get("relation", "related"))
            evidence = str(item.get("evidence", "")).strip()
            if not source_service and not target_service:
                continue
            normalized.append(
                {
                    "source_service": source_service,
                    "target_service": target_service,
                    "relation": relation,
                    "evidence": evidence,
                }
            )
        return normalized or fallback

    def _normalize_excluded_hypotheses(
        self,
        value: Any,
        fallback: list[dict[str, str]],
    ) -> list[dict[str, str]]:
        if not isinstance(value, list):
            return fallback

        normalized: list[dict[str, str]] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            hypothesis = str(item.get("hypothesis", "")).strip()
            reason = str(item.get("reason", "")).strip()
            if not hypothesis:
                continue
            normalized.append({"hypothesis": hypothesis, "reason": reason})
        return normalized or fallback

    def _normalize_evidence_matrix(
        self,
        value: Any,
        fallback: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return fallback

        normalized: list[dict[str, Any]] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            service = str(item.get("service", "")).strip()
            if not service:
                continue
            normalized.append(
                {
                    "service": service,
                    "role": str(item.get("role", "candidate")),
                    "metric": bool(item.get("metric", False)),
                    "log": bool(item.get("log", False)),
                    "trace": bool(item.get("trace", False)),
                    "knowledge": bool(item.get("knowledge", False)),
                    "notes": self._normalize_list_of_strings(item.get("notes")),
                }
            )
        return normalized or fallback

    def _normalize_recommendation_tiers(
        self,
        value: Any,
        fallback: dict[str, list[str]],
    ) -> dict[str, list[str]]:
        if not isinstance(value, dict):
            return fallback
        return {
            "immediate": self._normalize_list_of_strings(value.get("immediate", fallback.get("immediate", []))),
            "verification": self._normalize_list_of_strings(value.get("verification", fallback.get("verification", []))),
            "hardening": self._normalize_list_of_strings(value.get("hardening", fallback.get("hardening", []))),
        }

    def _normalize_impact_summary(
        self,
        value: Any,
        fallback: dict[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(value, dict):
            return fallback
        return {
            "core_services": self._normalize_list_of_strings(value.get("core_services", fallback.get("core_services", []))),
            "affected_services": self._normalize_list_of_strings(value.get("affected_services", fallback.get("affected_services", []))),
            "narrative": str(value.get("narrative", fallback.get("narrative", ""))).strip(),
        }

    def _normalize_propagation_summary(
        self,
        value: Any,
        fallback: dict[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(value, dict):
            return fallback
        return {
            "summary_lines": self._normalize_list_of_strings(value.get("summary_lines", fallback.get("summary_lines", []))),
            "paths": self._normalize_list_of_strings(value.get("paths", fallback.get("paths", []))),
        }

    def _knowledge_map(self, hits: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for hit in hits:
            service = str(hit.get("service") or "").strip()
            if not service:
                continue
            grouped.setdefault(service, []).append(hit)
        return grouped

    def _knowledge_alignment_for_service(
        self,
        service: str,
        hits: list[dict[str, Any]],
        fault_types: set[str],
        supported_dimensions: set[str],
        role: str,
    ) -> tuple[float, list[str], list[str], list[str], list[str], bool]:
        score_delta = 0.0
        reasoning: list[str] = []
        gaps: list[str] = []
        recommended_actions: list[str] = []
        alignments: list[str] = []
        has_conflict = False

        for hit in hits[:3]:
            title = str(hit.get("title") or hit.get("document_id") or "历史案例").strip()
            hit_fault_type = str(hit.get("fault_type") or "").strip()
            metadata = hit.get("metadata") or {}
            metric = str(metadata.get("metric") or "").strip()
            candidate_role = str(metadata.get("candidate_role") or "").strip()
            solution = str(hit.get("solution") or "").strip()

            if hit_fault_type and hit_fault_type in fault_types:
                score_delta += 0.08
                alignments.append(f"历史案例《{title}》与 {service} 当前故障类型一致，属于支持性参考")
                reasoning.append(f"历史案例《{title}》显示 {service} 曾出现同类故障类型，可作为当前判断的辅助背景")
            elif hit_fault_type:
                score_delta -= 0.05
                has_conflict = True
                alignments.append(f"历史案例《{title}》与 {service} 服务相关，但故障类型为 {hit_fault_type}，与当前信号不完全一致")
                gaps.append(f"{service} 的历史案例《{title}》指向不同故障类型 {hit_fault_type}，需要更多当前证据排除误判")

            if metric:
                if metric in supported_dimensions:
                    score_delta += 0.04
                    reasoning.append(f"当前证据已覆盖历史案例《{title}》强调的 {metric} 维度，与历史模式形成呼应")
                else:
                    has_conflict = True
                    gaps.append(f"历史案例《{title}》提示应重点验证 {service} 的 {metric}，但当前证据尚未覆盖该维度")
                    recommended_actions.append(f"补查 {service} 的 {metric} 相关证据，验证是否符合历史案例《{title}》提示的模式")

            if candidate_role == "symptom_or_propagated" and role == "origin":
                score_delta -= 0.04
                has_conflict = True
                alignments.append(f"历史案例《{title}》提示 {service} 更像传播/症状节点，而当前规则判断偏向首因")
                gaps.append(f"{service} 的历史角色更偏向传播或症状节点，需要继续确认其是否真是首发服务")
                recommended_actions.append(f"继续核对 {service} 的调用链上下游关系，确认其是否只是传播链中的放大点")
            elif candidate_role == "origin_candidate" and role in {"symptom", "propagated"}:
                alignments.append(f"历史案例《{title}》提示 {service} 可能具备首因特征，但当前证据更像传播影响")
                gaps.append(f"{service} 的历史案例具备首因倾向，但当前证据尚未充分证明这一点")

            if solution:
                reasoning.append(f"历史案例《{title}》的建议动作包括：{solution}")

        return score_delta, reasoning, gaps, recommended_actions, alignments, has_conflict

    def _deduplicate_strings(self, items: list[str]) -> list[str]:
        return list(dict.fromkeys(item for item in items if item))

    def _build_rule_based_result(self, state: RCAState, prompt: dict[str, Any]) -> dict[str, Any]:
        metric_results = state.evidence.get("metrics", [])
        log_results = state.evidence.get("logs", [])
        trace_results = state.evidence.get("traces", [])
        knowledge_hits = state.knowledge_hits
        topology_details = state.topology_details
        fault_types = set(state.detected_fault.get("fault_types", []))
        knowledge_map = self._knowledge_map(knowledge_hits)

        service_scores: dict[str, float] = {}
        service_reasons: dict[str, list[str]] = {}
        evidence_counts: dict[str, int] = {}
        dimension_support: dict[str, set[str]] = {}
        service_roles: dict[str, str] = {}
        trace_links: list[dict[str, Any]] = []
        missing_dimensions: set[str] = set()
        trace_sources: dict[str, int] = {}
        trace_targets: dict[str, int] = {}
        knowledge_alignment: list[str] = []
        knowledge_conflicts: set[str] = set()
        service_recommended_actions: dict[str, list[str]] = {}
        service_gaps: dict[str, list[str]] = {}

        for item in metric_results:
            service = str(item.get("service", "")).strip()
            metric_name = str(item.get("metric", "")).strip()
            if not service:
                continue
            if item.get("is_anomalous"):
                score = self._metric_weight(metric_name)
                if metric_name in state.detected_fault.get("fault_types", []):
                    score += 0.08
                if topology_details.get(service, {}).get("upstreams"):
                    score += 0.03
                service_scores[service] = service_scores.get(service, 0.0) + score
                evidence_counts[service] = evidence_counts.get(service, 0) + 1
                dimension_support.setdefault(service, set()).add("metric")
                peak_value = item.get("peak_value")
                service_reasons.setdefault(service, []).append(
                    f"{service} 出现 {metric_name} 指标异常，峰值为 {peak_value if peak_value is not None else '-'}"
                )
                current_role = service_roles.get(service)
                if metric_name in {"latency", "error"}:
                    service_roles[service] = current_role or "symptom"
                else:
                    service_roles[service] = current_role or "candidate"

        if not metric_results:
            missing_dimensions.add("metrics")

        for item in log_results:
            service = str(item.get("service", "")).strip()
            if not service:
                continue
            log_count = int(item.get("log_count", 0) or 0)
            top_patterns = item.get("top_patterns", [])
            if log_count > 0:
                service_scores[service] = service_scores.get(service, 0.0) + min(0.28, log_count / 25)
                evidence_counts[service] = evidence_counts.get(service, 0) + 1
                dimension_support.setdefault(service, set()).add("log")
                top_pattern = top_patterns[0].get("pattern") if top_patterns else "日志模式待人工展开"
                service_reasons.setdefault(service, []).append(
                    f"{service} 日志维度出现 {log_count} 条相关事件，代表模式为 {top_pattern}"
                )
                if service_roles.get(service) in {None, "candidate"}:
                    service_roles[service] = "origin"

        if not log_results:
            missing_dimensions.add("logs")

        downstream_targets: set[str] = set()
        for item in trace_results:
            service = str(item.get("service", "")).strip()
            if not service:
                continue
            trace_count = int(item.get("trace_count", 0) or 0)
            propagation_paths = item.get("propagation_paths", [])
            if trace_count > 0:
                service_scores[service] = service_scores.get(service, 0.0) + 0.18
                evidence_counts[service] = evidence_counts.get(service, 0) + 1
                dimension_support.setdefault(service, set()).add("trace")
                service_reasons.setdefault(service, []).append(
                    f"{service} 在调用链证据中出现 {trace_count} 次，相关传播路径 {len(propagation_paths)} 条"
                )
                if service_roles.get(service) in {None, "candidate"}:
                    service_roles[service] = "propagated"

            for path in propagation_paths:
                nodes = [part.strip() for part in str(path).split("->") if part.strip()]
                if len(nodes) >= 2:
                    source = nodes[0]
                    target = nodes[-1]
                    trace_sources[source] = trace_sources.get(source, 0) + 1
                    trace_targets[target] = trace_targets.get(target, 0) + 1
                    if target != source:
                        downstream_targets.add(target)
                    trace_links.append(
                        {
                            "source_service": source,
                            "target_service": target,
                            "relation": "propagates_to",
                            "evidence": f"trace path: {path}",
                        }
                    )

        if not trace_results:
            missing_dimensions.add("traces")

        for service in list(service_scores):
            supported_dimensions = dimension_support.get(service, set())
            source_hits = trace_sources.get(service, 0)
            target_hits = trace_targets.get(service, 0)
            if len(supported_dimensions) == 1:
                service_scores[service] *= 0.72
                service_reasons.setdefault(service, []).append(
                    f"{service} 当前仅有单一证据维度支撑，需要补充更多交叉验证"
                )
            if target_hits > source_hits and target_hits > 0:
                service_scores[service] *= 0.88
                service_roles[service] = "symptom"
                service_reasons.setdefault(service, []).append(
                    f"{service} 在调用链中更常作为下游终点出现，更像传播结果而非首发节点"
                )
            elif source_hits > target_hits and source_hits > 0 and len(supported_dimensions) >= 2:
                service_scores[service] += 0.08
                service_roles[service] = "origin"
                service_reasons.setdefault(service, []).append(
                    f"{service} 在调用链中更常作为上游起点出现，较符合首发异常特征"
                )
            if service in downstream_targets and "trace" in supported_dimensions and len(supported_dimensions) <= 2:
                service_scores[service] *= 0.9
                service_roles[service] = "symptom"
                service_reasons.setdefault(service, []).append(
                    f"{service} 更像传播链上的受影响节点，而不是唯一首发点"
                )
            elif {"metric", "log", "trace"}.issubset(supported_dimensions):
                service_scores[service] += 0.12
                service_roles[service] = "origin"
                service_reasons.setdefault(service, []).append(
                    f"{service} 同时获得指标、日志、调用链三维支撑，首因可信度更高"
                )

        for service, hits in knowledge_map.items():
            if service not in service_scores:
                continue
            score_delta, reasoning, gaps, recommended_actions, alignments, has_conflict = self._knowledge_alignment_for_service(
                service,
                hits,
                fault_types,
                dimension_support.get(service, set()),
                service_roles.get(service, "candidate"),
            )
            service_scores[service] = service_scores.get(service, 0.0) + score_delta
            service_reasons.setdefault(service, []).extend(reasoning)
            service_gaps.setdefault(service, []).extend(gaps)
            service_recommended_actions.setdefault(service, []).extend(recommended_actions)
            knowledge_alignment.extend(alignments)
            if has_conflict:
                knowledge_conflicts.add(service)

        for service in knowledge_map:
            if service not in service_scores:
                knowledge_alignment.append(f"历史知识命中包含 {service}，但当前工具证据尚未把它提升为主要候选")

        ranked = sorted(service_scores.items(), key=lambda pair: pair[1], reverse=True)
        root_cause = ranked[0][0] if ranked else "unknown"
        root_reasons = service_reasons.get(root_cause, ["当前证据不足，仍需继续补充验证。"])
        root_dimensions = dimension_support.get(root_cause, set())

        confidence = 0.22
        if ranked:
            top_score = ranked[0][1]
            confidence = min(0.92, 0.28 + top_score / 2.2)
            if len(root_dimensions) == 1:
                confidence = min(confidence, 0.79)
            elif len(root_dimensions) == 2:
                confidence = min(confidence, 0.84)
            if root_cause in knowledge_conflicts:
                confidence = min(confidence, 0.76)
        confidence = round(confidence, 2)
        decision = "stop" if (confidence >= 0.8 and len(root_dimensions) >= 2) or state.iteration >= state.max_iter else "continue"
        if root_cause in knowledge_conflicts and state.iteration < state.max_iter:
            decision = "continue"

        secondary_causes = [service for service, _ in ranked[1:3] if service != root_cause]
        symptom_service = ""
        for service, _score in ranked:
            if service_roles.get(service) == "symptom":
                symptom_service = service
                break
        if not symptom_service and ranked:
            symptom_service = ranked[0][0]

        ranked_services = [
            {
                "service": service,
                "score": round(score, 2),
                "role": service_roles.get(service, "candidate"),
                "evidence_count": evidence_counts.get(service, 0),
            }
            for service, score in ranked
        ]

        evidence_matrix = [
            {
                "service": item["service"],
                "role": item.get("role", "candidate"),
                "metric": "metric" in dimension_support.get(item["service"], set()),
                "log": "log" in dimension_support.get(item["service"], set()),
                "trace": "trace" in dimension_support.get(item["service"], set()),
                "knowledge": item["service"] in knowledge_map,
                "notes": self._deduplicate_strings(service_reasons.get(item["service"], [])[:3]),
            }
            for item in ranked_services
        ]

        affected_services = [item["service"] for item in ranked_services if item.get("service")]
        core_services = affected_services[:3]

        impact_summary = {
            "core_services": core_services,
            "affected_services": affected_services,
            "narrative": (
                f"当前多维证据主要集中在 {', '.join(core_services)}"
                if core_services
                else "当前尚未形成稳定的受影响服务范围"
            ),
        }

        propagation_paths = [
            path
            for item in trace_results
            for path in item.get("propagation_paths", [])
            if path
        ]
        propagation_summary = {
            "summary_lines": self._deduplicate_strings(
                [
                    f"{root_cause} 当前位于候选排序前列，且与调用链传播证据存在关联"
                    if root_cause != "unknown"
                    else "当前还无法从传播证据中锁定明确起点",
                    *[
                        f"传播链样例显示 {link['source_service']} 到 {link['target_service']} 存在 {link['relation']} 关系"
                        for link in trace_links[:3]
                        if link.get("source_service") or link.get("target_service")
                    ],
                ]
            ),
            "paths": propagation_paths[:6],
        }

        excluded_hypotheses: list[dict[str, str]] = []
        for service, role in service_roles.items():
            if service == root_cause:
                continue
            if role == "symptom":
                excluded_hypotheses.append(
                    {
                        "hypothesis": f"{service} 是唯一首发根因",
                        "reason": f"当前证据更支持 {service} 属于症状或传播结果，而非唯一首发节点",
                    }
                )
        if root_cause == "unknown":
            excluded_hypotheses.append(
                {
                    "hypothesis": "当前已存在可直接确认的单一根因",
                    "reason": "现有证据覆盖不足，仍缺少足够的跨维度交叉验证",
                }
            )

        evidence_links = trace_links[:6]
        if root_cause != "unknown" and secondary_causes:
            for service in secondary_causes:
                evidence_links.append(
                    {
                        "source_service": root_cause,
                        "target_service": service,
                        "relation": "co_occurs_with",
                        "evidence": f"{root_cause} 与 {service} 同时位于高优先级候选列表中",
                    }
                )

        evidence_gaps: list[str] = []
        if missing_dimensions:
            evidence_gaps.append(f"当前缺少完整的 {', '.join(sorted(missing_dimensions))} 结果，交叉验证仍不充分")
        if root_cause == "unknown":
            evidence_gaps.append("尚未识别出被多维证据稳定支撑的候选服务")
        elif len(root_dimensions) < 2:
            evidence_gaps.append(f"{root_cause} 目前仍缺少跨维度佐证，无法高置信度定为首因")
        if not evidence_links:
            evidence_gaps.append("调用链证据还不足以恢复清晰的传播关系")
        if not knowledge_hits:
            evidence_gaps.append("当前没有可用的历史案例命中，无法借助相似事故补强判断")
        elif root_cause in service_gaps:
            evidence_gaps.extend(service_gaps[root_cause])

        recommended_actions: list[str] = []
        if root_cause != "unknown":
            if "log" not in root_dimensions:
                recommended_actions.append(f"优先补查 {root_cause} 的日志模式，确认是否存在与异常时间重合的错误信号")
            if "trace" not in root_dimensions:
                recommended_actions.append(f"继续补抓 {root_cause} 相关调用链，确认其是首发点还是下游传播结果")
            if "metric" not in root_dimensions:
                recommended_actions.append(f"继续补查 {root_cause} 的关键指标时间窗口，确认异常强度和持续时间")
            recommended_actions.extend(service_recommended_actions.get(root_cause, []))
        if secondary_causes:
            recommended_actions.append(
                f"并行复核次级候选服务 {', '.join(secondary_causes)}，排除并发故障或放大链路"
            )
        if not recommended_actions:
            recommended_actions.append("扩大时间窗口并补充指标、日志、调用链三路证据后再做裁决")

        recommendation_tiers = {
            "immediate": recommended_actions[:2] or ["优先锁定当前最高优先级候选服务并保留现场证据"],
            "verification": self._deduplicate_strings(evidence_gaps[:3]) or ["补齐缺失证据后再次执行分析"],
            "hardening": [
                "将高频根因模式沉淀为可复用知识条目，提升后续相似故障分析效率",
                "为关键依赖链补充跨指标、日志、调用链的联合监控与回溯能力",
            ],
        }

        reasoning = root_reasons[:]
        if knowledge_alignment:
            reasoning.append(f"历史知识对齐结论：{'；'.join(knowledge_alignment[:3])}")
        if secondary_causes:
            reasoning.append(f"次级候选服务包括 {', '.join(secondary_causes)}，它们可能是并发根因或传播放大点")
        if decision == "continue":
            reasoning.append("当前证据仍存在缺口，因此建议继续迭代排查而不是直接终止分析")

        return {
            "prompt": prompt,
            "decision": decision,
            "confidence": confidence,
            "root_cause": root_cause,
            "secondary_causes": secondary_causes,
            "ranked_services": ranked_services,
            "reasoning": self._deduplicate_strings(reasoning),
            "evidence_links": evidence_links,
            "evidence_gaps": self._deduplicate_strings(evidence_gaps),
            "recommended_actions": self._deduplicate_strings(recommended_actions),
            "knowledge_alignment": self._deduplicate_strings(knowledge_alignment),
            "symptom_service": symptom_service,
            "primary_root_cause": root_cause,
            "secondary_root_causes": secondary_causes,
            "impact_summary": impact_summary,
            "propagation_summary": propagation_summary,
            "excluded_hypotheses": excluded_hypotheses,
            "evidence_matrix": evidence_matrix,
            "recommendation_tiers": recommendation_tiers,
            "analysis_mode": "rule",
        }

    def run(self, state: RCAState) -> dict[str, Any]:
        prompt = self.build_prompt(state)
        fallback_result = self._build_rule_based_result(state, prompt)

        if not self.llm_adapter or not self.llm_adapter.enabled:
            state.llm_enabled = False
            state.llm_reason = self.llm_adapter.reason if self.llm_adapter else "LLM adapter is unavailable."
            fallback_result["llm_status"] = state.llm_reason
            return fallback_result

        llm_payload = {
            "prompt": prompt,
            "evidence": state.evidence,
            "knowledge_hits": state.knowledge_hits,
            "topology_details": state.topology_details,
            "iteration": state.iteration,
            "max_iter": state.max_iter,
        }

        try:
            system_prompt, human_payload = to_langchain_messages(prompt)
            response = self.llm_adapter.invoke_messages(
                [
                    ("system", f"{ANALYST_SYSTEM_PROMPT}\n\n{system_prompt}"),
                    ("human", json.dumps({**human_payload, **llm_payload}, ensure_ascii=False, indent=2)),
                ]
            )
            parsed = extract_json_object(response["raw_text"])
            confidence = float(parsed.get("confidence", fallback_result["confidence"]))
            confidence = round(max(0.0, min(1.0, confidence)), 2)
            ranked_services = self._normalize_ranked_services(
                parsed.get("ranked_services"),
                fallback_result["ranked_services"],
            )
            reasoning = self._normalize_list_of_strings(parsed.get("reasoning", fallback_result["reasoning"]))
            evidence_gaps = self._normalize_list_of_strings(parsed.get("evidence_gaps", fallback_result["evidence_gaps"]))
            recommended_actions = self._normalize_list_of_strings(
                parsed.get("recommended_actions", fallback_result["recommended_actions"])
            )
            knowledge_alignment = self._normalize_list_of_strings(
                parsed.get("knowledge_alignment", fallback_result["knowledge_alignment"])
            )
            secondary_causes = self._normalize_list_of_strings(
                parsed.get("secondary_causes", fallback_result["secondary_causes"])
            )
            evidence_links = self._normalize_evidence_links(
                parsed.get("evidence_links"),
                fallback_result["evidence_links"],
            )
            decision = str(parsed.get("decision", fallback_result["decision"]))
            if decision not in {"stop", "continue"}:
                decision = fallback_result["decision"]
            root_cause = str(parsed.get("root_cause", fallback_result["root_cause"]))
            if not root_cause:
                root_cause = fallback_result["root_cause"]
            if len({item.get("service") for item in ranked_services if item.get("service")}) <= 1:
                confidence = min(confidence, 0.79)
            if knowledge_alignment and any("不一致" in item or "冲突" in item for item in knowledge_alignment):
                confidence = min(confidence, 0.76)
                if state.iteration < state.max_iter:
                    decision = "continue"
            symptom_service = str(parsed.get("symptom_service") or fallback_result["symptom_service"]).strip()
            primary_root_cause = str(parsed.get("primary_root_cause") or root_cause).strip() or root_cause
            secondary_root_causes = self._normalize_list_of_strings(
                parsed.get("secondary_root_causes", secondary_causes)
            )
            impact_summary = self._normalize_impact_summary(
                parsed.get("impact_summary"),
                fallback_result["impact_summary"],
            )
            propagation_summary = self._normalize_propagation_summary(
                parsed.get("propagation_summary"),
                fallback_result["propagation_summary"],
            )
            excluded_hypotheses = self._normalize_excluded_hypotheses(
                parsed.get("excluded_hypotheses"),
                fallback_result["excluded_hypotheses"],
            )
            evidence_matrix = self._normalize_evidence_matrix(
                parsed.get("evidence_matrix"),
                fallback_result["evidence_matrix"],
            )
            recommendation_tiers = self._normalize_recommendation_tiers(
                parsed.get("recommendation_tiers"),
                fallback_result["recommendation_tiers"],
            )
            return {
                "prompt": prompt,
                "decision": decision,
                "confidence": confidence,
                "root_cause": root_cause,
                "secondary_causes": secondary_causes,
                "ranked_services": ranked_services,
                "reasoning": reasoning or fallback_result["reasoning"],
                "evidence_links": evidence_links,
                "evidence_gaps": evidence_gaps or fallback_result["evidence_gaps"],
                "recommended_actions": recommended_actions or fallback_result["recommended_actions"],
                "knowledge_alignment": knowledge_alignment or fallback_result["knowledge_alignment"],
                "symptom_service": symptom_service,
                "primary_root_cause": primary_root_cause,
                "secondary_root_causes": secondary_root_causes or secondary_causes,
                "impact_summary": impact_summary,
                "propagation_summary": propagation_summary,
                "excluded_hypotheses": excluded_hypotheses,
                "evidence_matrix": evidence_matrix,
                "recommendation_tiers": recommendation_tiers,
                "analysis_mode": "llm",
                "llm_raw": response["raw_text"][:4000],
            }
        except Exception as exc:
            fallback_result["llm_status"] = str(exc)
            return fallback_result
