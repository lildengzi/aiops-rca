from __future__ import annotations

import re
from typing import Any


CODE_FAULT_RE = re.compile(r"^f\d+$", re.IGNORECASE)
LEGACY_METRIC_FAULT_TYPES = {
    "cpu",
    "memory",
    "mem",
    "disk",
    "network",
    "latency",
    "delay",
    "loss",
    "error",
    "load",
}


def is_fault_code(value: Any) -> bool:
    return bool(CODE_FAULT_RE.fullmatch(str(value or "").strip()))


def is_fault_type_label(value: Any) -> bool:
    text = str(value or "").strip().lower()
    return bool(text and (is_fault_code(text) or text in LEGACY_METRIC_FAULT_TYPES))


def normalize_fault_code(value: Any) -> str | None:
    text = str(value or "").strip()
    return text.lower() if is_fault_code(text) else None


def normalize_service_name(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text or is_fault_type_label(text):
        return None
    return text


def normalize_service_list(values: Any) -> list[str]:
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, list):
        return []
    normalized = {
        service
        for item in values
        if (service := normalize_service_name(item))
    }
    return sorted(normalized)


def report_header_contract(header: dict[str, Any]) -> dict[str, Any]:
    root_cause = header.get("root_cause")
    root_cause_service = (
        normalize_service_name(header.get("root_cause_service"))
        or normalize_service_name(root_cause)
    )
    fault_type = str(header.get("fault_type") or "unknown").strip() or "unknown"
    fault_code = normalize_fault_code(header.get("fault_code")) or normalize_fault_code(fault_type)
    affected_services = normalize_service_list(
        header.get("affected_services") or header.get("services") or []
    )
    if root_cause_service and root_cause_service not in affected_services:
        affected_services = sorted({*affected_services, root_cause_service})
    return {
        "root_cause_service": root_cause_service,
        "fault_type": fault_type,
        "fault_code": fault_code,
        "affected_services": affected_services,
    }
