from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st

from ui.dashboard_page import _extract_header, _extract_services, load_report_rows, read_report_text
from utils.incident_contract import report_header_contract


@st.cache_data(show_spinner=False)
def _list_report_paths() -> list[str]:
    return [row["report_path"] for row in load_report_rows()]


@st.cache_data(show_spinner=False)
def _read_think_log_text(path_value: str) -> str:
    return Path(path_value).read_text(encoding="utf-8")


def render_history_page() -> None:
    st.title("历史报告")
    report_path_values = _list_report_paths()
    if not report_path_values:
        st.info("reports/ 目录下暂无报告。")
        return

    report_paths = [Path(value) for value in report_path_values]
    options = {_build_report_label(path): path for path in report_paths}
    selected_label = st.selectbox("选择报告", list(options.keys()))
    selected_path = options[selected_label]
    content = read_report_text(str(selected_path))
    header = _extract_header(content)
    contract = report_header_contract(header)
    services = _extract_services(content, header) or contract["affected_services"]

    _render_report_summary(selected_path, header, services, contract)

    st.caption(f"文件路径：{selected_path}")
    st.download_button(
        "下载报告",
        data=content,
        file_name=selected_path.name,
        mime="text/markdown",
    )
    st.markdown(content)

    think_log_path = _find_matching_think_log(selected_path)
    with st.expander("关联 Think Log", expanded=False):
        if think_log_path is None:
            st.info("未找到同一时间戳的 Think Log。")
        else:
            st.caption(str(think_log_path))
            st.text_area("Think Log", value=_read_think_log_text(str(think_log_path)), height=360)


def _render_report_summary(
    report_path: Path,
    header: dict[str, Any],
    services: list[str],
    contract: dict[str, Any],
) -> None:
    generated_at = header.get("generated_at") or _guess_generated_at(report_path)
    root_cause_service = contract.get("root_cause_service") or header.get("root_cause")
    fault_type = contract.get("fault_type") or header.get("fault_type")
    fault_code = contract.get("fault_code")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("故障模式", _safe_text(fault_type))
    col2.metric("根因服务", _safe_text(root_cause_service))
    col3.metric("决策", _safe_text(header.get("decision")))
    col4.metric("置信度", _safe_text(header.get("confidence")))

    if fault_code:
        st.caption(f"代码级故障标签：{fault_code}。该标签用于区分故障模式，不计入服务覆盖统计。")

    st.subheader("报告摘要")
    left, right = st.columns([2, 1])
    with left:
        st.write(f"**分析问题**：{_safe_text(header.get('analysis_question'))}")
        st.write(f"**生成时间**：{generated_at}")
        st.write(f"**报告版本**：{_safe_text(header.get('report_version'))}")
    with right:
        st.write(f"**受影响服务**：{', '.join(services) if services else '-'}")
        secondary = header.get("secondary_causes")
        if isinstance(secondary, list) and secondary:
            st.write(f"**次级根因/放大点**：{', '.join(map(str, secondary))}")
        else:
            st.write("**次级根因/放大点**：-")


def _build_report_label(path: Path) -> str:
    content = read_report_text(str(path))
    header = _extract_header(content)
    contract = report_header_contract(header)
    root_cause = contract.get("root_cause_service") or header.get("root_cause") or "unknown"
    generated_at = header.get("generated_at") or _guess_generated_at(path)
    fault_type = contract.get("fault_type") or header.get("fault_type") or "unknown"
    return f"{generated_at} | {root_cause} | {fault_type} | {path.name}"


def _guess_generated_at(report_path: Path) -> str:
    parts = report_path.stem.replace("rca_report_", "")
    if len(parts) >= 15 and "_" in parts:
        date_part, time_part = parts.split("_", 1)
        if len(date_part) == 8 and len(time_part) >= 6:
            return f"{date_part[:4]}-{date_part[4:6]}-{date_part[6:8]} {time_part[:2]}:{time_part[2:4]}:{time_part[4:6]}"
    return report_path.name


def _find_matching_think_log(report_path: Path) -> Path | None:
    suffix = report_path.stem.replace("rca_report_", "")
    think_log_dir = report_path.parent.parent / "think_log"
    matches = sorted(think_log_dir.glob(f"*{suffix}.md"))
    return matches[0] if matches else None


def _safe_text(value: Any) -> str:
    if value is None or value == "":
        return "-"
    return str(value)
