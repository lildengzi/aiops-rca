from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st

from config import REPORTS_DIR


HEADER_PREFIXES = {
    "fault_type": "- fault_type:",
    "analysis_question": "- analysis_question:",
    "generated_at": "- generated_at:",
    "root_cause": "- root_cause:",
    "decision": "- decision:",
    "confidence": "- confidence:",
    "affected_services": "- affected_services:",
    "report_version": "- report_version:",
}


def render_dashboard_page() -> None:
    st.title("故障趋势")
    reports = _load_report_rows()
    if not reports:
        st.info("reports/ 目录下暂无报告，先在“故障分析”页面运行一次分析。")
        return

    dataframe = pd.DataFrame(reports)
    display_columns = [
        "generated_at",
        "report_name",
        "fault_type",
        "root_cause",
        "decision",
        "confidence",
        "service_count",
        "analysis_question",
    ]

    overview = {
        "报告总数": len(dataframe),
        "唯一根因候选数": int(dataframe["root_cause"].fillna("unknown").nunique()),
        "覆盖服务数": int(len({service for services in dataframe["services"] for service in services})),
        "平均置信度": _format_confidence(dataframe["confidence_value"].dropna().mean()),
    }
    cols = st.columns(len(overview))
    for index, (label, value) in enumerate(overview.items()):
        cols[index].metric(label, value)

    st.subheader("历史报告总览")
    st.dataframe(dataframe[display_columns], use_container_width=True)

    root_cause_counts = dataframe["root_cause"].fillna("unknown").value_counts()
    decision_counts = dataframe["decision"].fillna("unknown").value_counts()
    fault_type_counts = dataframe["fault_type"].fillna("unknown").value_counts()

    col1, col2 = st.columns(2)
    with col1:
        st.caption("根因候选频次")
        st.bar_chart(root_cause_counts)
    with col2:
        st.caption("故障类型频次")
        st.bar_chart(fault_type_counts)

    col1, col2 = st.columns(2)
    with col1:
        st.caption("决策分布")
        st.bar_chart(decision_counts)
    with col2:
        confidence_chart = _build_confidence_chart(dataframe)
        if confidence_chart is not None:
            st.caption("各报告置信度")
            st.line_chart(confidence_chart)

    service_counter = Counter()
    for services in dataframe["services"].tolist():
        for service in services:
            service_counter[service] += 1
    if service_counter:
        st.caption("报告涉及服务频次")
        service_df = pd.DataFrame(
            [{"service": service, "count": count} for service, count in service_counter.most_common()]
        ).set_index("service")
        st.bar_chart(service_df)

    recent_rows = dataframe.head(8).copy()
    recent_rows["summary"] = recent_rows.apply(_build_recent_summary, axis=1)
    st.subheader("最近报告时间线")
    for _, row in recent_rows.iterrows():
        title = row["generated_at"] or row["report_name"]
        with st.expander(title, expanded=False):
            st.write(row["summary"])
            st.caption(f"版本：{row.get('report_version') or '-'}")
            if row["services"]:
                st.write(f"涉及服务：{', '.join(row['services'])}")



def _load_report_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(REPORTS_DIR.glob("*.md"), key=lambda item: item.stat().st_mtime, reverse=True):
        content = path.read_text(encoding="utf-8")
        header = _extract_header(content)
        services = _extract_services(content, header)
        confidence_value = _coerce_float(header.get("confidence"))
        rows.append(
            {
                "report_name": path.name,
                "generated_at": _normalize_generated_at(header.get("generated_at"), path),
                "analysis_question": header.get("analysis_question") or "-",
                "root_cause": header.get("root_cause") or "unknown",
                "decision": header.get("decision") or "unknown",
                "confidence": header.get("confidence") or "-",
                "confidence_value": confidence_value,
                "fault_type": header.get("fault_type") or "unknown",
                "services": services,
                "service_count": len(services),
                "report_version": header.get("report_version") or "-",
            }
        )
    return rows



def _extract_header(content: str) -> dict[str, Any]:
    header: dict[str, Any] = {}
    for key, prefix in HEADER_PREFIXES.items():
        value = _extract_line_value(content, prefix)
        if value is None:
            continue
        header[key] = _parse_header_value(value)
    return header



def _extract_line_value(content: str, prefix: str) -> str | None:
    for line in content.splitlines():
        if line.strip().startswith(prefix):
            value = line.split(":", 1)[1].strip()
            return value or None
    return None



def _parse_header_value(value: str) -> Any:
    if not value:
        return None
    if value.startswith("[") or value.startswith("{"):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value



def _extract_services(content: str, header: dict[str, Any]) -> list[str]:
    affected_services = header.get("affected_services")
    if isinstance(affected_services, list):
        return sorted(str(item) for item in affected_services if item)

    services: set[str] = set()
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        parts = [part.strip() for part in stripped.strip("|").split("|")]
        if len(parts) < 2:
            continue
        if parts[0] in {"服务", "Service", "---", "-"} or not parts[0]:
            continue
        services.add(parts[0])
    return sorted(services)



def _coerce_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None



def _normalize_generated_at(value: Any, path: Any) -> str:
    if value:
        return str(value)
    timestamp = datetime.fromtimestamp(path.stat().st_mtime)
    return timestamp.strftime("%Y-%m-%d %H:%M:%S")



def _format_confidence(value: Any) -> str:
    if value is None or pd.isna(value):
        return "-"
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return str(value)



def _build_confidence_chart(dataframe: pd.DataFrame) -> pd.DataFrame | None:
    subset = dataframe[["generated_at", "confidence_value"]].dropna()
    if subset.empty:
        return None
    return subset.set_index("generated_at")



def _build_recent_summary(row: pd.Series) -> str:
    services = row.get("services") or []
    services_text = ", ".join(services[:4]) if services else "-"
    return (
        f"根因候选：{row.get('root_cause') or '-'}；"
        f"决策：{row.get('decision') or '-'}；"
        f"置信度：{row.get('confidence') or '-'}；"
        f"故障类型：{row.get('fault_type') or '-'}；"
        f"涉及服务：{services_text}"
    )
