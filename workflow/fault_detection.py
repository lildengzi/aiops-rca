from __future__ import annotations


KEYWORDS: dict[str, list[str]] = {
    "f1": ["f1"],
    "f2": ["f2"],
    "f3": ["f3"],
    "f4": ["f4"],
    "f5": ["f5"],
    "latency": ["延迟", "时延", "响应慢", "耗时", "latency", "slow", "timeout"],
    "cpu": ["cpu", "负载", "高负载", "load", "usage"],
    "memory": ["内存", "mem", "memory", "oom"],
    "error": ["错误", "异常", "失败", "报错", "error", "failure", "fail"],
    "network": ["网络", "丢包", "吞吐", "连接", "network", "drop", "throughput", "socket"],
}


def _merge_fault_types(values: list[str]) -> list[str]:
    merged: list[str] = []
    for value in values:
        if not value or value == "unknown":
            continue
        if value not in merged:
            merged.append(value)
    return merged or ["unknown"]


def detect_fault_types(user_input: str) -> list[str]:
    lowered = user_input.lower()
    matched = [
        fault_type
        for fault_type, candidates in KEYWORDS.items()
        if any(token in lowered for token in candidates)
    ]
    return _merge_fault_types(matched)


def build_detected_fault(user_input: str, case_context: dict | None = None) -> dict[str, list[str]]:
    detected = detect_fault_types(user_input)
    context_fault_type = ""
    if isinstance(case_context, dict):
        context_fault_type = str(case_context.get("fault_type") or "").strip().lower()
    return {"fault_types": _merge_fault_types([*detected, context_fault_type])}
