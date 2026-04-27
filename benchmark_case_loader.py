from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from config import BENCHMARK_DIR

FAULT_TYPE_ALIASES = {
    "delay": "latency",
    "latency": "latency",
    "error": "error",
    "loss": "error",
    "cpu": "cpu",
    "mem": "memory",
    "memory": "memory",
    "load": "load",
    "disk": "disk",
}

FAULT_LABELS = {
    "latency": "延迟升高",
    "error": "错误升高",
    "cpu": "CPU 升高",
    "memory": "内存升高",
    "load": "负载升高",
    "disk": "磁盘异常",
}


def normalize_fault_type(value: str | None) -> str | None:
    if value is None:
        return None
    return FAULT_TYPE_ALIASES.get(value.strip().lower(), value.strip().lower())


def build_default_user_input(service: str, fault_type: str | None) -> str:
    normalized = normalize_fault_type(fault_type)
    label = FAULT_LABELS.get(normalized or "", f"{fault_type or '故障'}异常")
    return f"{service} {label}，请分析根因"


def _read_optional_int(file_path: Path) -> int | None:
    if not file_path.exists():
        return None
    content = file_path.read_text(encoding="utf-8").strip()
    if not content:
        return None
    try:
        return int(float(content))
    except ValueError:
        return None


def _read_optional_json(file_path: Path) -> dict[str, Any]:
    if not file_path.exists():
        return {}
    try:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _parse_scenario_name(scenario: str) -> tuple[str, str | None]:
    if "_" not in scenario:
        return scenario, None
    service, raw_fault_type = scenario.rsplit("_", 1)
    return service, normalize_fault_type(raw_fault_type)


def load_benchmark_case(case_dir: str | Path) -> dict[str, Any]:
    case_path = Path(case_dir)
    scenario = case_path.parent.name
    case_id = case_path.name
    service, fault_type = _parse_scenario_name(scenario)
    metadata = _read_optional_json(case_path / "meta.json")

    expected_root_cause = metadata.get("expected_root_cause") or service
    metadata_fault_type = metadata.get("fault_type")
    normalized_fault_type = normalize_fault_type(metadata_fault_type) or fault_type
    default_user_input = metadata.get("user_input") or build_default_user_input(expected_root_cause, normalized_fault_type)
    inject_time = metadata.get("inject_time")
    if inject_time is None:
        inject_time = _read_optional_int(case_path / "inject_time.txt")
    elif isinstance(inject_time, (int, float, str)):
        try:
            inject_time = int(float(inject_time))
        except ValueError:
            inject_time = None
    else:
        inject_time = None

    return {
        "scenario": scenario,
        "case_id": case_id,
        "case_dir": str(case_path.resolve()),
        "csv_path": str((case_path / "data.csv").resolve()),
        "inject_time": inject_time,
        "expected_root_cause": expected_root_cause,
        "fault_type": normalized_fault_type,
        "default_user_input": default_user_input,
        "metadata": metadata,
    }


def iter_benchmark_cases(benchmark_dir: str | Path = BENCHMARK_DIR) -> list[dict[str, Any]]:
    root = Path(benchmark_dir)
    if not root.exists():
        return []

    cases: list[dict[str, Any]] = []
    for scenario_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        for case_dir in sorted(path for path in scenario_dir.iterdir() if path.is_dir()):
            if not (case_dir / "data.csv").exists():
                continue
            cases.append(load_benchmark_case(case_dir))
    return cases


def has_benchmark_case_layout(benchmark_dir: str | Path = BENCHMARK_DIR) -> bool:
    return bool(iter_benchmark_cases(benchmark_dir))


def list_benchmark_scenarios(benchmark_dir: str | Path = BENCHMARK_DIR) -> list[str]:
    scenarios = {case["scenario"] for case in iter_benchmark_cases(benchmark_dir)}
    return sorted(scenarios)


def list_cases_for_scenario(scenario: str, benchmark_dir: str | Path = BENCHMARK_DIR) -> list[dict[str, Any]]:
    return [case for case in iter_benchmark_cases(benchmark_dir) if case["scenario"] == scenario]
