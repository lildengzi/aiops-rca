from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import streamlit as st


AGENT_NAMES = {
    "retrieve_knowledge": "知识检索",
    "master": "主控规划",
    "metric": "指标分析",
    "log": "日志分析",
    "trace": "调用链分析",
    "aggregate": "证据汇总",
    "analyst": "根因研判",
    "reporter": "报告生成",
    "unknown": "未知智能体",
}

PILLAR_LABELS = {
    "metric": "指标",
    "log": "日志",
    "trace": "调用链",
    "topology": "拓扑推断",
    "knowledge": "知识库",
}

SOURCE_LABELS = {
    "real": "有直接证据",
    "inferred": "推断依据",
    "support": "支持",
    "conflict": "冲突",
    "neutral": "中性",
    "none": "暂无",
    True: "有",
    False: "无",
}


def render_analysis_page() -> None:
    st.title("故障分析")
    st.caption("输入故障描述，补充语音或图片证据，然后运行多智能体 RCA 工作流。")

    _render_current_dataset_summary()
    _render_input_panel()
    _render_result_panel()


def _render_current_dataset_summary() -> None:
    csv_path = st.session_state.get("data_path") or st.session_state.get("csv_path", "")
    case_context = _current_case_context()
    evidence = case_context.get("evidence_availability") or {}
    col1, col2 = st.columns([3, 2])
    with col1:
        st.info(
            "当前数据："
            f"{case_context.get('dataset') or '-'} / "
            "匿名故障样本"
        )
    with col2:
        st.caption("case 标签已隐藏，仅评测脚本使用")
        st.caption(
            "证据源："
            f"指标{'有' if evidence.get('metrics') else '无'} / "
            f"日志{'有' if evidence.get('logs') else '无'} / "
            f"调用链{'有' if evidence.get('traces') else '无'}"
        )


def _render_input_panel() -> None:
    multimodal_text = _build_multimodal_context()
    default_input = st.session_state.get("analysis_input", "")
    placeholder = "例如：frontend 延迟升高，怀疑 cartservice 或其上游依赖异常"
    user_input = st.text_area(
        "故障描述",
        value=default_input,
        height=160,
        placeholder=placeholder,
        key="analysis_input",
    )

    if multimodal_text:
        st.caption("已检测到语音或图片补充内容，可一键合并到故障描述。")
        if st.button("将语音/OCR 结果追加到故障描述", key="merge_multimodal_context"):
            merged = _merge_user_input(user_input, multimodal_text)
            st.session_state.analysis_input = merged
            st.rerun()

    col1, col2 = st.columns(2)
    with col1:
        start_raw = st.text_input(
            "起始时间戳（可选）",
            value=st.session_state.get("analysis_start_raw", ""),
            key="analysis_start_raw",
        )
    with col2:
        end_raw = st.text_input(
            "结束时间戳（可选）",
            value=st.session_state.get("analysis_end_raw", ""),
            key="analysis_end_raw",
        )

    start = _parse_optional_int(start_raw)
    end = _parse_optional_int(end_raw)
    if start_raw.strip() and start is None:
        st.warning("起始时间戳需要是整数。")
    if end_raw.strip() and end is None:
        st.warning("结束时间戳需要是整数。")
    if start is not None and end is not None and start > end:
        st.warning("起始时间戳不能大于结束时间戳。")

    with st.expander("多模态补充输入", expanded=False):
        from ui.voice_input import render_voice_input
        from ui.image_input import render_image_input

        render_voice_input()
        _render_multimodal_result("voice_result", "语音转写")
        st.divider()
        render_image_input()
        _render_multimodal_result("image_result", "图片解析")

    if st.button("开始分析", type="primary"):
        _run_analysis(user_input=st.session_state.get("analysis_input", ""), start_raw=start_raw, end_raw=end_raw)


def _run_analysis(user_input: str, start_raw: str, end_raw: str) -> None:
    csv_path = st.session_state.get("data_path") or st.session_state.get("csv_path", "")
    selected_case = _current_case_context()
    if not csv_path:
        st.error("请先在侧边栏选择 RCAEval case。")
        return
    if not user_input.strip():
        st.error("请输入故障描述。")
        return

    start = _parse_optional_int(start_raw)
    end = _parse_optional_int(end_raw)
    if start_raw.strip() and start is None:
        st.error("起始时间戳必须是整数。")
        return
    if end_raw.strip() and end is None:
        st.error("结束时间戳必须是整数。")
        return
    if start is not None and end is not None and start > end:
        st.error("起始时间戳不能大于结束时间戳。")
        return

    with st.spinner("正在执行多智能体根因分析..."):
        from workflow.orchestrator import RCAOrchestrator

        orchestrator = RCAOrchestrator(csv_path=csv_path)
        state = orchestrator.run_investigation(user_input=user_input.strip(), start=start, end=end)
        st.session_state.analysis_result = {
            "user_input": state.user_input,
            "csv_path": state.csv_path,
            "data_path": state.csv_path,
            "selected_case": selected_case,
            "case_context": selected_case,
            "start": state.start,
            "end": state.end,
            "dataset_summary": state.dataset_summary,
            "detected_fault": state.detected_fault,
            "plan": state.plan,
            "evidence": state.evidence,
            "decisions": state.decisions,
            "final_result": state.final_result,
            "report_path": state.report_path,
            "think_log_path": state.think_log_path,
            "knowledge_hits": state.knowledge_hits,
            "node_history": _compact_node_history(state.node_history),
        }


def _render_result_panel() -> None:
    result = st.session_state.get("analysis_result")
    if not result:
        st.info("运行一次分析后，这里会显示结论摘要、证据覆盖、智能体执行过程、报告预览和 Think Log。")
        return

    final_result = result.get("final_result", {})
    ranked_services = final_result.get("ranked_services") or []
    knowledge_hits = result.get("knowledge_hits") or []
    evidence = result.get("evidence") or {}
    evidence_matrix = final_result.get("three_pillar_matrix") or final_result.get("evidence_matrix") or []
    primary_root_cause = final_result.get("primary_root_cause") or final_result.get("root_cause")
    symptom_service = final_result.get("symptom_service")
    recommendation_tiers = final_result.get("recommendation_tiers") or {}
    propagation_summary = final_result.get("propagation_summary") or {}
    excluded_hypotheses = final_result.get("excluded_hypotheses") or []
    trace_interpretation = final_result.get("trace_interpretation") or {}

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("主根因", _safe_text(primary_root_cause))
    col2.metric("表现服务", _safe_text(symptom_service))
    col3.metric("决策 / 置信度", f"{_safe_text(final_result.get('decision'))} / {_safe_text(final_result.get('confidence'))}")
    col4.metric("证据覆盖", _format_evidence_coverage(evidence_matrix, evidence))

    summary_tab, evidence_tab, process_tab, report_tab, detail_tab = st.tabs(
        ["结论摘要", "证据视图", "智能体过程", "报告预览", "技术细节"]
    )

    with summary_tab:
        _render_decision_summary(result, final_result, propagation_summary, excluded_hypotheses)
        if recommendation_tiers or final_result.get("recommended_actions"):
            st.subheader("建议动作")
            _render_recommendation_tiers(recommendation_tiers, final_result.get("recommended_actions") or [])

    with evidence_tab:
        _render_ranked_services(ranked_services)
        _render_three_pillar_matrix(evidence_matrix)
        _render_trace_interpretation(trace_interpretation)
        with st.expander("聚合证据 JSON 摘要", expanded=False):
            st.json(_compact_for_display(evidence))
        if knowledge_hits:
            with st.expander("知识库命中", expanded=False):
                st.dataframe(_compact_rows(knowledge_hits), width="stretch")

    with process_tab:
        st.subheader("每个智能体的 ReAct 过程")
        _render_node_history(result.get("node_history") or [])
        think_log_path = result.get("think_log_path")
        if think_log_path and st.checkbox("加载 Think Log 摘要", value=False):
            think_log_content = _read_text(think_log_path, max_chars=120_000)
            if think_log_content:
                st.subheader("Think Log 摘要")
                _render_think_log_summary(think_log_content)
                with st.expander("原始 Think Log 片段", expanded=False):
                    st.text_area("过程记录", value=think_log_content, height=360)

    with report_tab:
        st.subheader("报告预览")
        report_path = result.get("report_path")
        report_content = _read_text(report_path)
        if report_content:
            st.markdown(report_content)
        else:
            st.info("当前没有可预览的报告内容。")

    with detail_tab:
        with st.expander("结论 JSON 摘要", expanded=False):
            st.json(_compact_for_display(final_result))
        with st.expander("完整分析结果 JSON 摘要", expanded=False):
            st.json(_compact_for_display(result, max_depth=3))


def _render_decision_summary(
    result: dict[str, Any],
    final_result: dict[str, Any],
    propagation_summary: dict[str, Any],
    excluded_hypotheses: list[Any],
) -> None:
    primary_root_cause = final_result.get("primary_root_cause") or final_result.get("root_cause")
    symptom_service = final_result.get("symptom_service")
    secondary_root_causes = final_result.get("secondary_root_causes") or final_result.get("secondary_causes") or []

    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("根因判断")
        st.write(f"- 主根因候选：`{_safe_text(primary_root_cause)}`")
        st.write(f"- 用户看到异常的服务：`{_safe_text(symptom_service)}`")
        st.write(f"- 次级根因/放大点：{_format_list(secondary_root_causes)}")
        reasoning = final_result.get("reasoning") or []
        if reasoning:
            st.markdown("**关键理由**")
            for line in reasoning[:5]:
                st.write(f"- {line}")
        propagation_lines = propagation_summary.get("summary_lines") or []
        if propagation_lines:
            st.markdown("**传播判断**")
            for line in propagation_lines[:3]:
                st.write(f"- {line}")
        if excluded_hypotheses:
            st.markdown("**已排除假设**")
            for item in excluded_hypotheses[:3]:
                if isinstance(item, dict):
                    st.write(f"- {item.get('hypothesis', '-')}：{item.get('reason', '-')}")
                else:
                    st.write(f"- {item}")
    with col2:
        st.subheader("分析上下文")
        case_context = result.get("selected_case") or result.get("case_context") or {}
        evidence_availability = case_context.get("evidence_availability") if isinstance(case_context, dict) else {}
        st.write(f"**数据集**：`{case_context.get('dataset') if isinstance(case_context, dict) else '-'}`")
        st.write("**场景 / Case**：`匿名展示`")
        st.write("**标注根因**：`已隐藏，仅用于评测统计`")
        st.write(f"**证据源**：{_format_case_evidence(evidence_availability if isinstance(evidence_availability, dict) else {})}")
        st.write("**数据路径**：`已隐藏，避免暴露目录标签`")
        st.write(f"**时间范围**：{_format_time_range(result.get('start'), result.get('end'))}")
        fault_types = (result.get("detected_fault") or {}).get("fault_types") or []
        st.write(f"**检测到的故障类型**：{', '.join(map(str, fault_types)) if fault_types else '-'}")


def _render_ranked_services(ranked_services: list[Any]) -> None:
    st.subheader("服务排序与角色判断")
    rows = []
    for index, item in enumerate(ranked_services, start=1):
        if not isinstance(item, dict):
            rows.append({"排名": index, "服务": str(item), "角色": "-", "得分": "-", "证据": "-"})
            continue
        rows.append(
            {
                "排名": index,
                "服务": item.get("service") or item.get("name") or "-",
                "角色": item.get("role") or "-",
                "得分": item.get("score") if item.get("score") is not None else "-",
                "证据": _format_list([PILLAR_LABELS.get(str(v), str(v)) for v in item.get("evidence_pillars") or []]),
                "说明": item.get("reason") or item.get("summary") or "",
            }
        )
    if rows:
        st.dataframe(rows, width="stretch", hide_index=True)
    else:
        st.info("当前没有服务排序结果。")


def _render_three_pillar_matrix(matrix: list[Any]) -> None:
    st.subheader("证据覆盖矩阵")
    if not matrix:
        st.info("当前没有三支柱证据矩阵。")
        return
    rows = []
    for item in matrix:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "服务": item.get("service") or "-",
                "角色": item.get("role") or "-",
                "指标": _source_label(item.get("metric")),
                "日志": _source_label(item.get("log")),
                "调用链": _source_label(item.get("trace")),
                "拓扑": _source_label(item.get("topology")),
                "知识库": _source_label(item.get("knowledge")),
                "备注": _format_list(item.get("notes") or []),
            }
        )
    if rows:
        st.dataframe(rows, width="stretch", hide_index=True)
        st.caption("直接证据比拓扑推断更可靠；知识库用于辅助解释，不应单独决定根因。")


def _render_trace_interpretation(trace_interpretation: dict[str, Any]) -> None:
    st.subheader("调用链证据解释")
    if not trace_interpretation:
        st.info("当前没有调用链解释信息。")
        return
    real_trace = trace_interpretation.get("real_trace_available")
    topology_used = trace_interpretation.get("topology_inference_used")
    col1, col2 = st.columns(2)
    col1.metric("真实调用链", "可用" if real_trace else "不可用")
    col2.metric("拓扑推断", "已使用" if topology_used else "未使用")
    limitations = trace_interpretation.get("trace_limitations") or []
    if limitations:
        st.markdown("**使用限制**")
        for item in limitations:
            st.write(f"- {item}")


def _render_multimodal_result(session_key: str, title: str) -> None:
    result = st.session_state.get(session_key)
    if not result:
        return
    st.caption(title)
    col1, col2 = st.columns([3, 1])
    with col1:
        st.info(result.get("message") or "")
        if result.get("provider"):
            st.caption(f"来源：{result['provider']}")
    with col2:
        if st.button("写入描述", key=f"append_{session_key}"):
            merged = _merge_user_input(st.session_state.get("analysis_input", ""), result.get("text", ""))
            st.session_state.analysis_input = merged
            st.rerun()
    if result.get("text"):
        st.text_area(f"{title}内容", value=result["text"], height=120, key=f"{session_key}_text")


def _render_think_log_summary(think_log_content: str) -> None:
    sections = _parse_think_log_sections(think_log_content)
    if not sections:
        st.info("当前 Think Log 无法结构化解析，请展开查看原始日志。")
        return

    lines = _summarize_think_log_sections(sections)
    if lines:
        for line in lines:
            st.write(f"- {line}")
    else:
        st.info("当前 Think Log 暂无可提炼的结构化摘要，请展开查看原始日志。")

    section_names = [AGENT_NAMES.get(section["node"], section["node"]) for section in sections if section.get("node")]
    if section_names:
        suffix = " ..." if len(section_names) > 8 else ""
        st.caption(f"覆盖节点：{' -> '.join(section_names[:8])}{suffix}")


def _parse_think_log_sections(think_log_content: str) -> list[dict[str, Any]]:
    pattern = re.compile(
        r"##\s+(?P<timestamp>[^\[]+)\[(?P<node>[^\]]+)\]\s*\n```json\s*\n(?P<body>[\s\S]*?)\n```",
        re.MULTILINE,
    )
    sections: list[dict[str, Any]] = []
    for match in pattern.finditer(think_log_content):
        body = match.group("body").strip()
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = {"raw": body}
        sections.append(
            {
                "timestamp": match.group("timestamp").strip(),
                "node": match.group("node").strip(),
                "payload": payload,
            }
        )
    return sections


def _summarize_think_log_sections(sections: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    dataset_payload = _find_section_payload(sections, "dataset_summary")
    knowledge_payload = _find_section_payload(sections, "retrieve_knowledge")
    master_payload = _find_section_payload(sections, "master")
    analyst_payload = _find_section_payload(sections, "analyst")
    reporter_payload = _find_section_payload(sections, "reporter")

    for builder, payloads in (
        (_build_dataset_summary_line, (dataset_payload,)),
        (_build_fault_summary_line, (knowledge_payload,)),
        (_build_knowledge_summary_line, (knowledge_payload,)),
        (_build_master_summary_line, (master_payload,)),
        (_build_analyst_summary_line, (analyst_payload, reporter_payload)),
    ):
        line = builder(*payloads)
        if line:
            lines.append(line)
    return lines


def _find_section_payload(sections: list[dict[str, Any]], node_name: str) -> dict[str, Any]:
    for section in reversed(sections):
        if section.get("node") == node_name:
            payload = section.get("payload")
            if isinstance(payload, dict):
                return payload
    return {}


def _build_dataset_summary_line(payload: dict[str, Any]) -> str:
    if not payload:
        return ""
    rows = payload.get("window_rows") or payload.get("rows")
    services = payload.get("services") or []
    start = payload.get("window_start") or payload.get("start_time")
    end = payload.get("window_end") or payload.get("end_time")
    metrics = payload.get("service_metrics") or {}
    metric_names: set[str] = set()
    if isinstance(metrics, dict):
        for values in metrics.values():
            if isinstance(values, list):
                metric_names.update(str(item) for item in values if item)
    segments: list[str] = []
    if rows is not None:
        segments.append(f"读取了 {rows} 条窗口数据")
    if services:
        segments.append(f"覆盖 {len(services)} 个服务")
    if metric_names:
        segments.append(f"主要指标类型包括 {', '.join(sorted(metric_names))}")
    if start is not None or end is not None:
        segments.append(f"时间范围为 {_format_time_range(start, end)}")
    return f"本次分析先完成数据集扫描：{'；'.join(segments)}。" if segments else ""


def _build_fault_summary_line(payload: dict[str, Any]) -> str:
    fault_types = payload.get("fault_types") if isinstance(payload, dict) else []
    return f"系统先将故障模式识别为：{_format_list(fault_types)}。" if fault_types else ""


def _build_knowledge_summary_line(payload: dict[str, Any]) -> str:
    if not payload:
        return ""
    hit_count = payload.get("hit_count")
    top_hits = payload.get("top_hits") or []
    services = payload.get("candidate_services") or []
    pieces: list[str] = []
    if hit_count is not None:
        pieces.append(f"命中 {hit_count} 条知识")
    if services:
        pieces.append(f"重点检索服务为 {_format_list(services[:5])}")
    if top_hits:
        top_titles = [str(item.get("title") or item.get("service") or "") for item in top_hits[:3] if isinstance(item, dict)]
        top_titles = [title for title in top_titles if title]
        if top_titles:
            pieces.append(f"高相关条目包括 {_format_list(top_titles)}")
    return f"知识库检索阶段：{'；'.join(pieces)}。" if pieces else ""


def _build_master_summary_line(payload: dict[str, Any]) -> str:
    if not payload:
        return ""
    objective = _extract_prompt_value(payload, "objective")
    user_input = _extract_prompt_input(payload, "user_input")
    services = _extract_prompt_input(payload, "services") or payload.get("selected_services") or []
    candidate_metrics = payload.get("candidate_metrics") or _extract_prompt_input(payload, "candidate_metrics") or []
    pieces: list[str] = []
    if user_input:
        pieces.append(f"围绕“{user_input}”组织调查")
    if services:
        pieces.append(f"初始关注服务为 {_format_list(list(services)[:5])}")
    if candidate_metrics:
        pieces.append(f"优先关注指标 {_format_list(list(candidate_metrics)[:5])}")
    if objective:
        pieces.append(f"阶段目标是 {objective}")
    return f"主控规划阶段：{'；'.join(pieces)}。" if pieces else ""


def _build_analyst_summary_line(analyst_payload: dict[str, Any], reporter_payload: dict[str, Any]) -> str:
    payload = analyst_payload or reporter_payload
    if not payload:
        return ""
    root_cause = payload.get("root_cause") or payload.get("primary_root_cause")
    decision = payload.get("decision")
    confidence = payload.get("confidence")
    services = payload.get("selected_services") or payload.get("ranked_services") or []
    pieces: list[str] = []
    if root_cause:
        pieces.append(f"最终收敛到主根因候选 {root_cause}")
    if decision:
        pieces.append(f"结论决策为 {decision}")
    if confidence is not None:
        pieces.append(f"置信度为 {confidence}")
    service_names = _extract_service_names(services)
    if service_names:
        pieces.append(f"重点分析服务包括 {_format_list(service_names[:5])}")
    return f"综合判断阶段：{'；'.join(pieces)}。" if pieces else ""


def _extract_prompt_value(payload: dict[str, Any], key: str) -> Any:
    prompt = payload.get("prompt")
    if isinstance(prompt, dict):
        return prompt.get(key)
    return None


def _extract_prompt_input(payload: dict[str, Any], key: str) -> Any:
    prompt = payload.get("prompt")
    if isinstance(prompt, dict):
        inputs = prompt.get("inputs")
        if isinstance(inputs, dict):
            return inputs.get(key)
    return None


def _extract_service_names(services: Any) -> list[str]:
    if not isinstance(services, list):
        return []
    names: list[str] = []
    for item in services:
        if isinstance(item, str):
            names.append(item)
        elif isinstance(item, dict):
            name = item.get("service") or item.get("name")
            if name:
                names.append(str(name))
    return names


def _render_node_history(entries: list[dict[str, Any]]) -> None:
    if not entries:
        st.info("当前没有节点执行记录。")
        return

    for index, entry in enumerate(entries, start=1):
        node = str(entry.get("node") or "unknown")
        iteration = entry.get("iteration")
        timestamp = entry.get("timestamp") or "-"
        payload = entry.get("payload") or {}
        readable = _entry_readable_react(entry, node, payload)
        agent_name = readable.get("agent") or AGENT_NAMES.get(node, node)
        status = readable.get("status") or "已完成"
        title = f"{index}. {agent_name} | {status}"
        if iteration is not None:
            title += f" | 第 {iteration} 轮"

        with st.container(border=True):
            top_left, top_right = st.columns([3, 2])
            top_left.markdown(f"**{title}**")
            top_right.caption(f"节点：{node} ｜ 时间：{timestamp}")
            st.write(f"**这一步目标**：{readable.get('goal') or '-'}")
            st.write(f"**为什么做**：{readable.get('why') or '-'}")

            thought_tab, action_tab, observation_tab, result_tab = st.tabs(["想法", "动作", "观察", "结果"])
            with thought_tab:
                _write_lines(readable.get("thought"))
            with action_tab:
                _write_lines(readable.get("action"))
            with observation_tab:
                _write_lines(readable.get("observation"))
            with result_tab:
                _write_lines(readable.get("result"))

            with st.expander("技术细节：原始 JSON", expanded=False):
                st.json(_compact_for_display(payload))


def _compact_node_history(entries: list[dict[str, Any]], limit: int = 80) -> list[dict[str, Any]]:
    compacted: list[dict[str, Any]] = []
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        key = (
            str(entry.get("timestamp") or ""),
            str(entry.get("node") or ""),
            str(entry.get("iteration") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(entry)

    for entry in deduped[-limit:]:
        payload = entry.get("payload") if isinstance(entry.get("payload"), dict) else {}
        compacted.append(
            {
                "timestamp": entry.get("timestamp"),
                "node": entry.get("node"),
                "iteration": entry.get("iteration"),
                "payload": _compact_for_display(payload, max_depth=3),
                "readable_react": entry.get("readable_react"),
                "display": entry.get("display"),
            }
        )
    return compacted


def _entry_readable_react(entry: dict[str, Any], node: str, payload: Any) -> dict[str, Any]:
    readable = entry.get("readable_react")
    if not isinstance(readable, dict):
        display = entry.get("display")
        if isinstance(display, dict):
            readable = display.get("readable_react")
    if isinstance(readable, dict):
        return {
            "agent": readable.get("agent_label") or readable.get("agent") or AGENT_NAMES.get(node, node),
            "status": _status_label(readable.get("status")),
            "goal": readable.get("plain_goal") or readable.get("goal") or readable.get("objective"),
            "why": readable.get("why") or readable.get("rationale") or readable.get("thought"),
            "thought": readable.get("thought"),
            "action": readable.get("action"),
            "observation": readable.get("observation"),
            "result": readable.get("result") or readable.get("next_step") or readable.get("conclusion"),
        }
    return _build_readable_react(node, payload)


def _status_label(value: Any) -> str:
    labels = {
        "success": "已完成",
        "warning": "需复核",
        "info": "已记录",
    }
    return labels.get(str(value), str(value or "已完成"))


def _build_readable_react(node: str, payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        readable = payload.get("readable_react")
        if isinstance(readable, dict):
            return {
                "agent": readable.get("agent") or AGENT_NAMES.get(node, node),
                "status": readable.get("status") or "已完成",
                "goal": readable.get("goal") or readable.get("objective"),
                "why": readable.get("why") or readable.get("rationale"),
                "thought": readable.get("thought") or readable.get("think") or readable.get("reasoning"),
                "action": readable.get("action") or readable.get("actions"),
                "observation": readable.get("observation") or readable.get("observations"),
                "result": readable.get("result") or readable.get("next_step") or readable.get("conclusion"),
            }
    payload = payload if isinstance(payload, dict) else {"raw": payload}
    builders = {
        "retrieve_knowledge": _react_retrieve_knowledge,
        "master": _react_master,
        "metric": _react_metric,
        "log": _react_log,
        "trace": _react_trace,
        "aggregate": _react_aggregate,
        "analyst": _react_analyst,
        "reporter": _react_reporter,
    }
    return builders.get(node, _react_generic)(node, payload)


def _react_retrieve_knowledge(node: str, payload: dict[str, Any]) -> dict[str, Any]:
    services = payload.get("candidate_services") or []
    metrics = payload.get("candidate_metrics") or []
    hit_count = payload.get("hit_count")
    return _react(
        node,
        "查找历史经验和知识库线索。",
        "知识库可以提示常见故障模式，但只作为辅助证据。",
        [
            f"检索候选服务：{_format_list(services[:6])}",
            f"检索候选指标：{_format_list(metrics[:6])}",
        ],
        f"命中 {hit_count if hit_count is not None else 0} 条知识记录。",
        "把高相关知识交给后续研判，避免只凭经验下结论。",
    )


def _react_master(node: str, payload: dict[str, Any]) -> dict[str, Any]:
    services = payload.get("selected_services") or _extract_prompt_input(payload, "services") or []
    metrics = payload.get("candidate_metrics") or _extract_prompt_input(payload, "candidate_metrics") or []
    objective = _extract_prompt_value(payload, "objective") or "制定调查计划"
    return _react(
        node,
        objective,
        "需要先缩小调查范围，再并行收集指标、日志和调用链证据。",
        [
            f"选择重点服务：{_format_list(list(services)[:6])}",
            f"选择重点指标：{_format_list(list(metrics)[:6])}",
        ],
        _summarize_payload(payload) or "已生成调查计划。",
        "进入指标、日志和调用链分析。",
    )


def _react_metric(node: str, payload: dict[str, Any]) -> dict[str, Any]:
    metrics = payload.get("metrics") or []
    services = _extract_service_names(metrics)
    return _react(
        node,
        "从指标数据里寻找异常服务和异常指标。",
        "延迟、错误率、资源使用率等指标能提供直接的时间序列证据。",
        f"检查 {len(metrics)} 条指标证据，涉及服务：{_format_list(services[:6])}。",
        _summarize_evidence_items(metrics),
        "把指标异常交给证据汇总和根因研判。",
    )


def _react_log(node: str, payload: dict[str, Any]) -> dict[str, Any]:
    logs = payload.get("logs") or []
    services = _extract_service_names(logs)
    return _react(
        node,
        "从日志中查找错误、异常和关键事件。",
        "日志能解释指标变化背后的具体失败信息。",
        f"检查 {len(logs)} 条日志证据，涉及服务：{_format_list(services[:6])}。",
        _summarize_evidence_items(logs),
        "把日志异常交给证据汇总和根因研判。",
    )


def _react_trace(node: str, payload: dict[str, Any]) -> dict[str, Any]:
    traces = payload.get("traces") or []
    services = _extract_service_names(traces)
    return _react(
        node,
        "从调用链或拓扑关系中判断故障传播路径。",
        "调用关系能区分用户看到的异常服务和真正拖慢链路的上游服务。",
        f"检查 {len(traces)} 条调用链/拓扑证据，涉及服务：{_format_list(services[:6])}。",
        _summarize_evidence_items(traces),
        "把调用链证据交给证据汇总和根因研判。",
    )


def _react_aggregate(node: str, payload: dict[str, Any]) -> dict[str, Any]:
    metric_count = payload.get("metric_count", 0)
    log_count = payload.get("log_count", 0)
    trace_count = payload.get("trace_count", 0)
    return _react(
        node,
        "把不同来源的证据合并到同一视图。",
        "单一证据容易误判，指标、日志、调用链要一起看。",
        f"汇总指标 {metric_count} 条、日志 {log_count} 条、调用链 {trace_count} 条。",
        f"当前证据覆盖：{_format_evidence_coverage([], {'metrics': [1] * int(metric_count or 0), 'logs': [1] * int(log_count or 0), 'traces': [1] * int(trace_count or 0)})}。",
        "进入最终根因研判。",
    )


def _react_analyst(node: str, payload: dict[str, Any]) -> dict[str, Any]:
    root_cause = payload.get("primary_root_cause") or payload.get("root_cause")
    decision = payload.get("decision")
    confidence = payload.get("confidence")
    ranked = payload.get("ranked_services") or []
    return _react(
        node,
        "基于全部证据给出根因判断。",
        "需要把候选服务排序，并说明证据是否足够支持结论。",
        f"比较候选服务：{_format_list(_extract_service_names(ranked)[:6])}。",
        [
            f"主根因候选：{_safe_text(root_cause)}",
            f"决策：{_safe_text(decision)}",
            f"置信度：{_safe_text(confidence)}",
        ],
        "生成建议动作和报告所需结论。",
    )


def _react_reporter(node: str, payload: dict[str, Any]) -> dict[str, Any]:
    return _react(
        node,
        "把分析结论整理成可读报告。",
        "报告需要让排障人员快速看到根因、证据和下一步动作。",
        f"生成报告文件：{_safe_text(payload.get('report_path'))}。",
        "报告头和正文已生成。" if payload.get("report_path") else "报告生成结果未返回文件路径。",
        "用户可以在报告预览中查看完整内容。",
    )


def _react_generic(node: str, payload: dict[str, Any]) -> dict[str, Any]:
    return _react(
        node,
        "执行工作流中的一个分析步骤。",
        "该步骤为后续判断提供中间结果。",
        _summarize_payload(payload) or "已处理当前节点输入。",
        _summarize_payload(payload) or "已产出结构化结果。",
        "继续交给后续节点处理。",
    )


def _react(node: str, goal: Any, why: Any, action: Any, observation: Any, result: Any) -> dict[str, Any]:
    return {
        "agent": AGENT_NAMES.get(node, node),
        "status": "已完成",
        "goal": goal,
        "why": why,
        "thought": why,
        "action": action,
        "observation": observation,
        "result": result,
    }


def _summarize_payload(payload: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    if payload.get("root_cause") or payload.get("primary_root_cause"):
        lines.append(f"根因候选：{payload.get('primary_root_cause') or payload.get('root_cause')}")
    if payload.get("decision"):
        lines.append(f"决策：{payload['decision']}")
    if payload.get("confidence") is not None:
        lines.append(f"置信度：{payload['confidence']}")
    if payload.get("metric_count") is not None:
        lines.append(f"指标证据数：{payload['metric_count']}")
    if payload.get("log_count") is not None:
        lines.append(f"日志证据数：{payload['log_count']}")
    if payload.get("trace_count") is not None:
        lines.append(f"调用链证据数：{payload['trace_count']}")
    if payload.get("selected_services"):
        lines.append(f"聚焦服务：{', '.join(map(str, payload['selected_services']))}")
    return lines


def _summarize_evidence_items(items: list[Any]) -> list[str]:
    if not items:
        return ["没有找到明确证据。"]
    lines: list[str] = []
    for item in items[:5]:
        if not isinstance(item, dict):
            lines.append(str(item))
            continue
        service = item.get("service") or item.get("name") or "未知服务"
        summary = item.get("summary") or item.get("reason") or item.get("message") or item.get("evidence") or ""
        score = item.get("score")
        prefix = f"{service}"
        if score is not None:
            prefix += f"（得分 {score}）"
        lines.append(f"{prefix}：{summary or '发现一条相关证据'}")
    return lines


def _write_lines(value: Any) -> None:
    values = _as_display_lines(value)
    if not values:
        st.write("-")
        return
    for line in values:
        st.write(f"- {line}")


def _as_display_lines(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        lines: list[str] = []
        for item in value:
            if isinstance(item, dict):
                lines.append(json.dumps(item, ensure_ascii=False))
            else:
                lines.append(str(item))
        return [line for line in lines if line.strip()]
    if isinstance(value, dict):
        return [json.dumps(value, ensure_ascii=False)]
    return [str(value)]


def _build_multimodal_context() -> str:
    parts: list[str] = []
    for key, label in (("voice_result", "语音转写"), ("image_result", "图片解析")):
        result = st.session_state.get(key) or {}
        text = str(result.get("text") or "").strip()
        if text:
            parts.append(f"[{label}]\n{text}")
    return "\n\n".join(parts)


def _current_case_context() -> dict[str, Any]:
    context = st.session_state.get("selected_benchmark_case_metadata")
    if isinstance(context, dict) and context:
        return context
    data_path = st.session_state.get("data_path") or st.session_state.get("csv_path", "")
    return {
        "dataset": st.session_state.get("selected_benchmark_dataset") or "unknown",
        "scenario": st.session_state.get("selected_benchmark_scenario") or "unknown",
        "case_id": st.session_state.get("selected_benchmark_case") or (Path(data_path).name if data_path else ""),
        "case_dir": st.session_state.get("selected_benchmark_case_dir") or data_path,
        "data_path": data_path,
        "inject_time": _parse_optional_int(st.session_state.get("analysis_start_raw", "")),
        "root_cause": None,
        "fault_type": None,
        "evidence_availability": {
            "metrics": bool(data_path),
            "logs": False,
            "traces": False,
        },
        "evidence_source_files": {},
    }


def _format_case_evidence(evidence: dict[str, Any]) -> str:
    labels = [
        ("指标", evidence.get("metrics")),
        ("日志", evidence.get("logs")),
        ("调用链", evidence.get("traces")),
    ]
    return " / ".join(f"{label}{'有' if available else '无'}" for label, available in labels)


def _merge_user_input(user_input: str, addition: str) -> str:
    base = user_input.strip()
    extra = addition.strip()
    if not extra:
        return base
    if not base:
        return extra
    if extra in base:
        return base
    return f"{base}\n\n补充证据：\n{extra}"


def _format_time_range(start: Any, end: Any) -> str:
    if start is None and end is None:
        return "全量时间窗口"
    return f"{start if start is not None else '-'} ~ {end if end is not None else '-'}"


def _parse_optional_int(value: str) -> int | None:
    stripped = value.strip()
    if not stripped:
        return None
    try:
        return int(stripped)
    except ValueError:
        return None


def _safe_text(value: Any) -> str:
    if value is None or value == "":
        return "-"
    return str(value)


def _format_list(items: Any) -> str:
    if not isinstance(items, list):
        items = [items] if items not in (None, "") else []
    values = [str(item) for item in items if str(item).strip()]
    return ", ".join(values) if values else "-"


def _source_label(value: Any) -> str:
    return SOURCE_LABELS.get(value, SOURCE_LABELS.get(str(value), str(value) if value not in (None, "") else "暂无"))


def _format_evidence_coverage(evidence_matrix: list[Any], evidence: dict[str, Any]) -> str:
    dimensions: list[str] = []
    if any(bool(item.get("metric")) and item.get("metric") != "none" for item in evidence_matrix if isinstance(item, dict)) or evidence.get("metrics"):
        dimensions.append("指标")
    if any(bool(item.get("log")) and item.get("log") != "none" for item in evidence_matrix if isinstance(item, dict)) or evidence.get("logs"):
        dimensions.append("日志")
    if any(bool(item.get("trace")) and item.get("trace") != "none" for item in evidence_matrix if isinstance(item, dict)) or evidence.get("traces"):
        dimensions.append("调用链")
    if any(item.get("topology") == "inferred" for item in evidence_matrix if isinstance(item, dict)):
        dimensions.append("拓扑")
    return f"{len(dimensions)} 类（{'/'.join(dimensions)}）" if dimensions else "0 类"


def _render_recommendation_tiers(recommendation_tiers: dict[str, Any], fallback_actions: list[str]) -> None:
    tiers = [
        ("立即止血", recommendation_tiers.get("immediate") or []),
        ("补充验证", recommendation_tiers.get("verification") or []),
        ("长期加固", recommendation_tiers.get("hardening") or []),
    ]
    rendered = False
    for title, items in tiers:
        if not items:
            continue
        rendered = True
        st.markdown(f"**{title}**")
        for item in items:
            st.write(f"- {item}")
    if not rendered:
        for item in fallback_actions:
            st.write(f"- {item}")


def _compact_rows(rows: list[Any], limit: int = 20) -> list[Any]:
    compacted = [_compact_for_display(row, max_depth=2) for row in rows[:limit]]
    if len(rows) > limit:
        compacted.append({"omitted": len(rows) - limit})
    return compacted


def _compact_for_display(value: Any, max_depth: int = 4, max_items: int = 12, max_text: int = 500) -> Any:
    if max_depth <= 0:
        if isinstance(value, (dict, list)):
            return f"<{type(value).__name__}: {len(value)} items>"
        return _clip(str(value), max_text)
    if isinstance(value, dict):
        items = list(value.items())
        compacted = {
            str(key): _compact_for_display(item, max_depth=max_depth - 1, max_items=max_items, max_text=max_text)
            for key, item in items[:max_items]
        }
        if len(items) > max_items:
            compacted["<omitted_keys>"] = len(items) - max_items
        return compacted
    if isinstance(value, list):
        compacted = [
            _compact_for_display(item, max_depth=max_depth - 1, max_items=max_items, max_text=max_text)
            for item in value[:max_items]
        ]
        if len(value) > max_items:
            compacted.append(f"<omitted_items: {len(value) - max_items}>")
        return compacted
    if isinstance(value, str):
        return _clip(value, max_text)
    return value


def _clip(value: str, limit: int) -> str:
    text = " ".join(str(value).split())
    return text if len(text) <= limit else f"{text[:limit - 3]}..."


def _read_text(path_value: str | None, max_chars: int | None = None) -> str:
    if not path_value:
        return ""
    path = Path(path_value)
    if not path.exists():
        return ""
    content = path.read_text(encoding="utf-8")
    if max_chars is not None and len(content) > max_chars:
        return content[:max_chars] + "\n\n... 内容过长，已截断展示 ..."
    return content
