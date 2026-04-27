from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from agents.prompts import REPORT_HEADER_FIELDS, reporter_prompt
from config import DEFAULT_REPORT_PREFIX, REPORTS_DIR
from workflow.state import RCAState


class ReporterAgent:
    name = "reporter"

    def build_prompt(self, state: RCAState) -> dict[str, Any]:
        return reporter_prompt(
            {
                "user_input": state.user_input,
                "csv_path": state.csv_path,
                "time_range": {"start": state.start, "end": state.end},
                "detected_fault": state.detected_fault,
                "final_result": state.final_result,
                "evidence": state.evidence,
                "knowledge_hits": state.knowledge_hits,
                "topology_details": state.topology_details,
            }
        )

    def _format_value(self, value: Any) -> str:
        if isinstance(value, (list, dict)):
            return json.dumps(value, ensure_ascii=False)
        if value is None:
            return ""
        return str(value)

    def _build_metric_rows(self, metrics: list[dict[str, Any]]) -> list[str]:
        rows: list[str] = []
        for item in metrics:
            peak_value = item.get("peak_value")
            anomaly_count = len(item.get("anomaly_timestamps", []))
            rows.append(
                f"| {item.get('service', '-')} | {item.get('metric', '-')} | {item.get('is_anomalous', False)} | {peak_value if peak_value is not None else '-'} | {anomaly_count} |"
            )
        return rows or ["| - | - | - | - | - |"]

    def _build_log_rows(self, logs: list[dict[str, Any]]) -> list[str]:
        rows: list[str] = []
        for item in logs:
            patterns = item.get("top_patterns", [])
            top_pattern = patterns[0].get("pattern") if patterns else "-"
            rows.append(
                f"| {item.get('service', '-')} | {item.get('log_count', 0)} | {top_pattern} |"
            )
        return rows or ["| - | - | - |"]

    def _build_trace_rows(self, traces: list[dict[str, Any]]) -> list[str]:
        rows: list[str] = []
        for item in traces:
            paths = item.get("propagation_paths", [])
            path = paths[0] if paths else "-"
            rows.append(
                f"| {item.get('service', '-')} | {item.get('trace_count', 0)} | {path} |"
            )
        return rows or ["| - | - | - |"]

    def _build_reasoning_lines(self, final_result: dict[str, Any]) -> list[str]:
        reasoning = final_result.get("reasoning", [])
        if not reasoning:
            return ["- 当前证据不足，尚未形成可展开的推理链。"]
        return [f"- 步骤 {index}. {item}" for index, item in enumerate(reasoning, start=1)]

    def _build_gap_lines(self, final_result: dict[str, Any]) -> list[str]:
        gaps = final_result.get("evidence_gaps", [])
        if not gaps:
            return ["- 当前没有额外暴露的证据缺口。"]
        return [f"- {item}" for item in gaps]

    def _build_action_lines(self, final_result: dict[str, Any]) -> list[str]:
        actions = final_result.get("recommended_actions", [])
        if not actions:
            root_cause = final_result.get("root_cause") or "当前候选服务"
            return [f"- 优先围绕 {root_cause} 继续补充指标、日志与调用链证据。"]
        return [f"- {item}" for item in actions]

    def _build_impact_lines(self, final_result: dict[str, Any], evidence: dict[str, Any]) -> list[str]:
        impact_summary = final_result.get("impact_summary") or {}
        core_services = [str(item) for item in impact_summary.get("core_services", []) if str(item).strip()]
        affected_services = [str(item) for item in impact_summary.get("affected_services", []) if str(item).strip()]
        narrative = str(impact_summary.get("narrative") or "").strip()

        if not affected_services:
            affected_services = [item.get("service") for item in final_result.get("ranked_services", []) if item.get("service")]
        if not affected_services:
            affected_services = sorted(
                {
                    item.get("service")
                    for group in [evidence.get("metrics", []), evidence.get("logs", []), evidence.get("traces", [])]
                    for item in group
                    if item.get("service")
                }
            )
        if not core_services:
            core_services = affected_services[:3]
        if not affected_services:
            return ["- 当前结果中尚未识别出明确的受影响服务范围。"]

        indirect_services = [service for service in affected_services if service not in core_services]
        lines = [f"- 核心受影响服务：{', '.join(core_services)}"]
        if indirect_services:
            lines.append(f"- 间接受影响服务：{', '.join(indirect_services)}")
        if narrative:
            lines.append(f"- 影响判断：{narrative}。")
        lines.append("- 受影响范围来自当前排序结果与已采集证据，后续可能随新增证据调整。")
        return lines

    def _build_header(self, state: RCAState, generated_at: str) -> dict[str, Any]:
        final_result = state.final_result
        fault_types = state.detected_fault.get("fault_types", [])
        affected_services = [item.get("service") for item in final_result.get("ranked_services", []) if item.get("service")]
        return {
            "fault_type": fault_types[0] if fault_types else "unknown",
            "analysis_question": state.user_input,
            "generated_at": generated_at,
            "iteration": state.iteration,
            "root_cause": final_result.get("root_cause"),
            "secondary_causes": final_result.get("secondary_causes", []),
            "decision": final_result.get("decision"),
            "confidence": final_result.get("confidence"),
            "affected_services": affected_services,
            "report_version": "v2",
        }

    def _build_ranked_service_lines(self, final_result: dict[str, Any]) -> list[str]:
        ranked_services = final_result.get("ranked_services", [])
        if not ranked_services:
            return ["- 当前没有形成稳定的服务排序结果。"]
        return [
            f"- {item.get('service', '-')}：score={item.get('score', '-')}, role={item.get('role', 'candidate')}, evidence_count={item.get('evidence_count', 0)}"
            for item in ranked_services
        ]

    def _build_evidence_link_lines(self, final_result: dict[str, Any]) -> list[str]:
        links = final_result.get("evidence_links", [])
        if not links:
            return ["- 当前缺少足够的跨服务证据链接，暂无法恢复完整传播链。"]
        lines: list[str] = []
        for item in links:
            source = item.get("source_service") or "unknown"
            target = item.get("target_service") or "unknown"
            relation = item.get("relation") or "related"
            evidence = item.get("evidence") or "-"
            lines.append(f"- `{source}` -> `{target}`（{relation}）：{evidence}")
        return lines

    def _build_knowledge_lines(self, knowledge_hits: list[dict[str, Any]]) -> list[str]:
        if not knowledge_hits:
            return ["- 当前未命中可直接辅助判断的历史案例。"]
        lines: list[str] = []
        for hit in knowledge_hits[:3]:
            title = hit.get("title") or hit.get("document_id") or "未命名案例"
            service = hit.get("service") or "unknown"
            root_cause = hit.get("root_cause") or "unknown"
            score = hit.get("score")
            lines.append(f"- 历史案例《{title}》涉及 `{service}`，历史根因 `{root_cause}`，相似度得分 {score}")
        return lines

    def _build_executive_summary_lines(self, state: RCAState, final_result: dict[str, Any]) -> list[str]:
        symptom_service = final_result.get("symptom_service") or final_result.get("root_cause") or "unknown"
        primary_root_cause = final_result.get("primary_root_cause") or final_result.get("root_cause") or "unknown"
        secondary_root_causes = final_result.get("secondary_root_causes") or final_result.get("secondary_causes") or []
        decision = final_result.get("decision") or "continue"
        confidence = final_result.get("confidence")
        secondary_text = "、".join(str(item) for item in secondary_root_causes) if secondary_root_causes else "暂无明确次级根因或放大点"
        return [
            f"- 用户当前关注的问题是：{state.user_input}。",
            f"- 表象服务更接近 `{symptom_service}`，主根因候选更接近 `{primary_root_cause}`。",
            f"- 次级根因或放大点候选：{secondary_text}。",
            f"- 当前决策为 `{decision}`，综合置信度为 `{confidence}`；结论仅基于已采集的指标、日志、调用链与知识命中整理。",
        ]

    def _build_cause_section_lines(self, final_result: dict[str, Any]) -> list[str]:
        primary_root_cause = final_result.get("primary_root_cause") or final_result.get("root_cause") or "unknown"
        secondary_root_causes = final_result.get("secondary_root_causes") or final_result.get("secondary_causes") or []
        ranked_services = final_result.get("ranked_services", [])
        if primary_root_cause == "unknown" or not ranked_services:
            return ["- 当前尚未形成足够稳定的因果归纳，只能确认存在异常而无法锁定起点。"]

        top_item = ranked_services[0]
        top_role = top_item.get("role", "candidate")
        lines = [
            f"- `{primary_root_cause}` 当前位于候选排序首位，角色判断偏向 `{top_role}`，因此被作为优先复核对象。"
        ]
        if secondary_root_causes:
            lines.append(
                f"- `{', '.join(map(str, secondary_root_causes))}` 同样存在较强异常，更像并发次因、传播放大点或下游症状服务。"
            )
        decision = final_result.get("decision") or "continue"
        confidence = final_result.get("confidence")
        if decision == "continue":
            lines.append(f"- 当前决策仍为 `{decision}`，说明现有证据虽已形成主候选，但置信度 `{confidence}` 还不足以完全终止排查。")
        else:
            lines.append(f"- 当前决策为 `{decision}`，说明现有证据已足以把 `{primary_root_cause}` 作为主根因结论输出，综合置信度 `{confidence}`。")
        return lines

    def _build_propagation_section_lines(self, final_result: dict[str, Any], evidence: dict[str, Any]) -> list[str]:
        propagation_summary = final_result.get("propagation_summary") or {}
        summary_lines = [f"- {item}" for item in propagation_summary.get("summary_lines", []) if str(item).strip()]
        path_lines = [f"- 样例路径：`{item}`" for item in propagation_summary.get("paths", []) if str(item).strip()]
        if summary_lines or path_lines:
            return summary_lines + path_lines

        trace_path_lines = [
            f"- {item.get('service')}: {item.get('propagation_paths', [])}"
            for item in evidence.get("traces", [])
            if item.get("service")
        ]
        if trace_path_lines:
            return trace_path_lines + self._build_evidence_link_lines(final_result)
        return ["- 当前没有可用的传播路径证据。"]

    def _build_exclusion_lines(self, final_result: dict[str, Any]) -> list[str]:
        excluded_hypotheses = final_result.get("excluded_hypotheses", [])
        if not excluded_hypotheses:
            return ["- 当前没有形成稳定的排除项，主要原因是候选之间仍需更多交叉验证。"]
        return [
            f"- 已暂不支持“{item.get('hypothesis', '-') }”这一假设，原因：{item.get('reason', '-') }。"
            for item in excluded_hypotheses
        ]

    def _build_recommendation_sections(self, final_result: dict[str, Any]) -> list[str]:
        tiers = final_result.get("recommendation_tiers") or {}
        immediate = tiers.get("immediate") or []
        verification = tiers.get("verification") or []
        hardening = tiers.get("hardening") or []
        lines: list[str] = []
        if immediate:
            lines.extend(["### 7.1 立即止血", *[f"- {item}" for item in immediate], ""])
        if verification:
            lines.extend(["### 7.2 补充验证", *[f"- {item}" for item in verification], ""])
        if hardening:
            lines.extend(["### 7.3 架构加固", *[f"- {item}" for item in hardening], ""])
        if lines:
            return lines[:-1] if lines[-1] == "" else lines
        return self._build_action_lines(final_result)

    def run(self, state: RCAState) -> dict[str, Any]:
        prompt = self.build_prompt(state)
        final_result = state.final_result
        evidence = state.evidence
        knowledge_hits = state.knowledge_hits
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        report_path = REPORTS_DIR / f"{DEFAULT_REPORT_PREFIX}_{timestamp}.md"
        report_header = self._build_header(state, generated_at)

        metric_rows = self._build_metric_rows(evidence.get("metrics", []))
        log_rows = self._build_log_rows(evidence.get("logs", []))
        trace_rows = self._build_trace_rows(evidence.get("traces", []))
        reasoning_lines = self._build_reasoning_lines(final_result)
        gap_lines = self._build_gap_lines(final_result)
        impact_lines = self._build_impact_lines(final_result, evidence)
        ranked_service_lines = self._build_ranked_service_lines(final_result)
        knowledge_lines = self._build_knowledge_lines(knowledge_hits)
        executive_summary_lines = self._build_executive_summary_lines(state, final_result)
        cause_section_lines = self._build_cause_section_lines(final_result)
        propagation_section_lines = self._build_propagation_section_lines(final_result, evidence)
        exclusion_lines = self._build_exclusion_lines(final_result)
        recommendation_lines = self._build_recommendation_sections(final_result)

        root_cause = final_result.get("root_cause") or "unknown"
        confidence = final_result.get("confidence")
        decision = final_result.get("decision") or "continue"

        header_lines = ["# AIOps 根因分析报告", ""]
        for field in REPORT_HEADER_FIELDS:
            header_lines.append(f"- {field}: {self._format_value(report_header.get(field))}")

        content = "\n".join(
            header_lines
            + [
                "",
                "---",
                "",
                "## 一、问题简述",
                *executive_summary_lines,
                "",
                "## 二、影响概述",
                *impact_lines,
                "",
                "## 三、问题原因",
                *cause_section_lines,
                "",
                "## 四、详细分析",
                "### 4.1 指标分析",
                "| 服务 | 指标 | 是否异常 | 峰值 | 异常点数量 |",
                "| --- | --- | --- | --- | --- |",
                *metric_rows,
                "",
                "### 4.2 日志分析",
                "| 服务 | 日志条数 | 代表模式 |",
                "| --- | --- | --- |",
                *log_rows,
                "",
                "### 4.3 调用链分析",
                "| 服务 | Trace 数量 | 样例传播路径 |",
                "| --- | --- | --- |",
                *trace_rows,
                "",
                "### 4.4 服务排序与角色判断",
                *ranked_service_lines,
                "",
                "### 4.5 根因推理链",
                *reasoning_lines,
                "",
                "### 4.6 排除项与反证",
                *exclusion_lines,
                "",
                "### 4.7 历史案例辅助参考",
                *knowledge_lines,
                "",
                "## 五、故障传播路径",
                *propagation_section_lines,
                "",
                "## 六、证据缺口与待验证项",
                *gap_lines,
                "",
                "## 七、优化建议",
                *recommendation_lines,
            ]
        )

        report_path.write_text(content, encoding="utf-8")
        return {
            "prompt": prompt,
            "report_path": str(report_path),
            "report_preview": content[:1200],
            "report_header": report_header,
            "root_cause": root_cause,
            "decision": decision,
            "confidence": confidence,
        }
