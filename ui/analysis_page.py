from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st

from ui.image_input import render_image_input
from ui.voice_input import render_voice_input
from workflow.orchestrator import RCAOrchestrator


def render_analysis_page() -> None:
    st.title("故障分析")
    st.caption("输入故障描述、补充语音或图片证据，并直接调用现有 RCA 工作流。")

    _render_current_dataset_summary()
    _render_input_panel()
    _render_result_panel()


def _render_current_dataset_summary() -> None:
    csv_path = st.session_state.get("csv_path", "")
    uploaded_name = st.session_state.get("uploaded_csv_name")
    col1, col2 = st.columns([3, 2])
    with col1:
        st.info(f"当前数据集：{csv_path or '未选择'}")
    with col2:
        label = uploaded_name or (Path(csv_path).name if csv_path else "-")
        st.caption(f"当前文件：{label}")


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
        st.caption("已检测到多模态补充内容，可一键并入故障描述。")
        if st.button("将语音/OCR 结果追加到故障描述", key="merge_multimodal_context"):
            merged = _merge_user_input(user_input, multimodal_text)
            st.session_state.analysis_input = merged
            st.rerun()

    col1, col2 = st.columns(2)
    with col1:
        start_raw = st.text_input("起始时间戳（可选）", value=st.session_state.get("analysis_start_raw", ""), key="analysis_start_raw")
    with col2:
        end_raw = st.text_input("结束时间戳（可选）", value=st.session_state.get("analysis_end_raw", ""), key="analysis_end_raw")

    start = _parse_optional_int(start_raw)
    end = _parse_optional_int(end_raw)
    if start_raw.strip() and start is None:
        st.warning("起始时间戳需为整数。")
    if end_raw.strip() and end is None:
        st.warning("结束时间戳需为整数。")
    if start is not None and end is not None and start > end:
        st.warning("起始时间戳不能大于结束时间戳。")

    with st.expander("多模态补充输入", expanded=False):
        render_voice_input()
        _render_multimodal_result("voice_result", "语音转写")
        st.divider()
        render_image_input()
        _render_multimodal_result("image_result", "图片解析")

    if st.button("开始分析", type="primary"):
        _run_analysis(user_input=st.session_state.get("analysis_input", ""), start_raw=start_raw, end_raw=end_raw)


def _run_analysis(user_input: str, start_raw: str, end_raw: str) -> None:
    csv_path = st.session_state.get("csv_path", "")
    if not csv_path:
        st.error("请先在侧边栏填写或上传 CSV 文件。")
        return
    if not user_input.strip():
        st.error("请输入故障描述。")
        return

    start = _parse_optional_int(start_raw)
    end = _parse_optional_int(end_raw)
    if start_raw.strip() and start is None:
        st.error("起始时间戳必须为整数。")
        return
    if end_raw.strip() and end is None:
        st.error("结束时间戳必须为整数。")
        return
    if start is not None and end is not None and start > end:
        st.error("起始时间戳不能大于结束时间戳。")
        return

    with st.spinner("正在执行多 Agent 根因分析..."):
        orchestrator = RCAOrchestrator(csv_path=csv_path)
        state = orchestrator.run_investigation(user_input=user_input.strip(), start=start, end=end)
        st.session_state.analysis_result = {
            "user_input": state.user_input,
            "csv_path": state.csv_path,
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
            "node_history": state.node_history,
        }


def _render_result_panel() -> None:
    result = st.session_state.get("analysis_result")
    if not result:
        st.info("运行一次分析后，这里会显示结论摘要、服务证据、报告预览和 think log。")
        return

    final_result = result.get("final_result", {})
    ranked_services = final_result.get("ranked_services") or []
    knowledge_hits = result.get("knowledge_hits") or []
    evidence = result.get("evidence") or {}
    evidence_matrix = final_result.get("evidence_matrix") or []
    primary_root_cause = final_result.get("primary_root_cause") or final_result.get("root_cause")
    symptom_service = final_result.get("symptom_service")
    recommendation_tiers = final_result.get("recommendation_tiers") or {}
    propagation_summary = final_result.get("propagation_summary") or {}
    excluded_hypotheses = final_result.get("excluded_hypotheses") or []

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("主根因", _safe_text(primary_root_cause))
    col2.metric("表象服务", _safe_text(symptom_service))
    col3.metric("决策 / 置信度", f"{_safe_text(final_result.get('decision'))} / {_safe_text(final_result.get('confidence'))}")
    col4.metric("证据覆盖", _format_evidence_coverage(evidence_matrix, evidence))

    st.subheader("结论摘要")
    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown("**主根因判断**")
        st.write(f"- 主根因候选：`{_safe_text(primary_root_cause)}`")
        st.write(f"- 表象服务：`{_safe_text(symptom_service)}`")
        secondary_root_causes = final_result.get("secondary_root_causes") or final_result.get("secondary_causes") or []
        st.write(f"- 次级根因/放大点：{_format_list(secondary_root_causes)}")
        propagation_lines = propagation_summary.get("summary_lines") or []
        if propagation_lines:
            st.markdown("**传播判断**")
            for line in propagation_lines[:3]:
                st.write(f"- {line}")
        if excluded_hypotheses:
            st.markdown("**排除项与反证**")
            for item in excluded_hypotheses[:3]:
                st.write(f"- {item.get('hypothesis', '-')}：{item.get('reason', '-')}")
    with col2:
        st.subheader("分析上下文")
        st.write(f"**数据集**：`{result.get('csv_path') or '-'}`")
        st.write(f"**时间范围**：{_format_time_range(result.get('start'), result.get('end'))}")
        fault_types = (result.get("detected_fault") or {}).get("fault_types") or []
        st.write(f"**检测故障类型**：{', '.join(map(str, fault_types)) if fault_types else '-'}")

    st.subheader("报告预览")
    report_path = result.get("report_path")
    report_content = _read_text(report_path)
    if report_content:
        st.markdown(report_content)
    else:
        st.info("当前没有可预览的报告内容。")

    if recommendation_tiers or final_result.get("recommended_actions"):
        st.subheader("建议动作")
        _render_recommendation_tiers(recommendation_tiers, final_result.get("recommended_actions") or [])

    if ranked_services:
        st.subheader("服务排序与角色判断")
        st.dataframe(ranked_services, use_container_width=True)

    st.subheader("节点执行过程")
    _render_node_history(result.get("node_history") or [])

    with st.expander("查看原始结论 JSON", expanded=False):
        st.json(final_result)

    if knowledge_hits:
        with st.expander("知识库命中", expanded=False):
            st.dataframe(knowledge_hits, use_container_width=True)

    think_log_path = result.get("think_log_path")
    think_log_content = _read_text(think_log_path)
    if think_log_content:
        with st.expander("Think Log", expanded=False):
            st.text_area("过程记录", value=think_log_content, height=360)

    with st.expander("聚合证据", expanded=False):
        st.json(evidence)



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
        if st.button(f"写入描述", key=f"append_{session_key}"):
            merged = _merge_user_input(st.session_state.get("analysis_input", ""), result.get("text", ""))
            st.session_state.analysis_input = merged
            st.rerun()
    if result.get("text"):
        st.text_area(f"{title}内容", value=result["text"], height=120, key=f"{session_key}_text")



def _render_node_history(entries: list[dict[str, Any]]) -> None:
    if not entries:
        st.info("当前没有节点执行记录。")
        return

    for entry in entries:
        node = entry.get("node") or "unknown"
        iteration = entry.get("iteration")
        timestamp = entry.get("timestamp") or "-"
        payload = entry.get("payload") or {}
        label = f"[{timestamp}] {node}"
        if iteration is not None:
            label += f" · iteration {iteration}"
        with st.expander(label, expanded=node in {"analyst", "reporter"}):
            if isinstance(payload, dict):
                summary = _summarize_payload(payload)
                if summary:
                    for line in summary:
                        st.write(f"- {line}")
            st.json(payload)



def _summarize_payload(payload: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    if payload.get("root_cause"):
        lines.append(f"根因候选：{payload['root_cause']}")
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



def _build_multimodal_context() -> str:
    parts: list[str] = []
    for key, label in (("voice_result", "语音转写"), ("image_result", "图片解析")):
        result = st.session_state.get(key) or {}
        text = str(result.get("text") or "").strip()
        if text:
            parts.append(f"[{label}]\n{text}")
    return "\n\n".join(parts)



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



def _format_list(items: list[Any]) -> str:
    values = [str(item) for item in items if str(item).strip()]
    return ", ".join(values) if values else "-"



def _format_evidence_coverage(evidence_matrix: list[dict[str, Any]], evidence: dict[str, Any]) -> str:
    dimensions: list[str] = []
    if any(bool(item.get("metric")) for item in evidence_matrix if isinstance(item, dict)) or evidence.get("metrics"):
        dimensions.append("metric")
    if any(bool(item.get("log")) for item in evidence_matrix if isinstance(item, dict)) or evidence.get("logs"):
        dimensions.append("log")
    if any(bool(item.get("trace")) for item in evidence_matrix if isinstance(item, dict)) or evidence.get("traces"):
        dimensions.append("trace")
    return f"{len(dimensions)} 维 ({'/'.join(dimensions)})" if dimensions else "0 维"



def _render_recommendation_tiers(recommendation_tiers: dict[str, Any], fallback_actions: list[str]) -> None:
    immediate = recommendation_tiers.get("immediate") or []
    verification = recommendation_tiers.get("verification") or []
    hardening = recommendation_tiers.get("hardening") or []
    if immediate:
        st.markdown("**立即止血**")
        for item in immediate:
            st.write(f"- {item}")
    if verification:
        st.markdown("**补充验证**")
        for item in verification:
            st.write(f"- {item}")
    if hardening:
        st.markdown("**架构加固**")
        for item in hardening:
            st.write(f"- {item}")
    if not (immediate or verification or hardening):
        for item in fallback_actions:
            st.write(f"- {item}")



def _read_text(path_value: str | None) -> str:
    if not path_value:
        return ""
    path = Path(path_value)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")
