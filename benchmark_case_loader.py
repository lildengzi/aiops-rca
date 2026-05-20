from __future__ import annotations

from pathlib import Path
from typing import Any

from config import BENCHMARK_DIR


RCAEVAL_CASE_FILES = ("metrics.json", "metrics.csv", "simple_metrics.csv")
RCAEVAL_DATASET_KEYS = {
    "RE1-OB": "re1-ob",
    "RE1-SS": "re1-ss",
    "RE1-TT": "re1-tt",
    "RE2-OB": "re2-ob",
    "RE2-SS": "re2-ss",
    "RE2-TT": "re2-tt",
    "RE3-OB": "re3-ob",
    "RE3-SS": "re3-ss",
    "RE3-TT": "re3-tt",
}


def _case_directories() -> list[Path]:
    if not BENCHMARK_DIR.exists():
        return []
    candidates = [
        path
        for path in BENCHMARK_DIR.rglob("*")
        if path.is_dir() and any((path / filename).exists() for filename in RCAEVAL_CASE_FILES)
    ]
    return sorted(candidates, key=lambda path: (str(path.parent), path.name))


def iter_benchmark_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for case_dir in _case_directories():
        scenario_id = _scenario_id_for_case_dir(case_dir)
        case_id = f"{scenario_id}_{case_dir.name}" if scenario_id else case_dir.name
        inject_time = _read_optional_int(case_dir / "inject_time.txt")
        root_cause_text = _read_optional_text(case_dir / "root_cause.txt")
        root_cause = _infer_root_cause(scenario_id or case_id, root_cause_text)
        fault_type = _infer_fault_type(scenario_id or case_id)
        dataset = _infer_dataset(case_dir)
        evidence_availability = _evidence_availability(case_dir)
        evidence_source_files = _evidence_source_files(case_dir)
        cases.append(
            {
                "case_id": case_id,
                "scenario": _infer_scenario(scenario_id or case_id),
                "dataset": dataset,
                "case_dir": str(case_dir),
                "data_path": str(case_dir),
                "inject_time": inject_time,
                "root_cause": root_cause,
                "root_cause_text": root_cause_text,
                "fault_type": fault_type,
                "has_metrics": evidence_availability["metrics"],
                "has_logs": evidence_availability["logs"],
                "has_traces": evidence_availability["traces"],
                "evidence_availability": evidence_availability,
                "evidence_source_files": evidence_source_files,
                "default_user_input": _default_user_input(case_id, root_cause, fault_type),
            }
        )
    if not cases:
        cases.extend(_legacy_flat_cases())
    return cases


def filter_benchmark_cases(
    cases: list[dict[str, Any]],
    *,
    scenario: str = "",
    dataset: str = "",
) -> list[dict[str, Any]]:
    filtered = cases
    if scenario:
        scenario_key = scenario.strip().lower()
        filtered = [case for case in filtered if str(case.get("scenario", "")).lower() == scenario_key]
    if dataset:
        dataset_key = dataset.strip().lower()
        filtered = [case for case in filtered if str(case.get("dataset", "")).lower() == dataset_key]
    return filtered


def list_benchmark_scenarios() -> list[str]:
    scenarios = {case["scenario"] for case in iter_benchmark_cases()}
    return sorted(scenarios)


def list_benchmark_datasets() -> list[str]:
    datasets = {str(case.get("dataset", "")) for case in iter_benchmark_cases() if case.get("dataset")}
    return sorted(datasets)


def case_context_for_path(data_path: str | Path) -> dict[str, Any]:
    target = _resolve_path(data_path)
    for case in iter_benchmark_cases():
        case_path = _resolve_path(case.get("data_path") or case.get("case_dir") or "")
        if case_path == target:
            return build_case_context(case)
    return {
        "dataset": "unknown",
        "scenario": "unknown",
        "case_id": target.name if target else "",
        "case_dir": str(target) if target else "",
        "data_path": str(target) if target else str(data_path),
        "inject_time": None,
        "root_cause": None,
        "fault_type": None,
        "evidence_availability": {
            "metrics": False,
            "logs": False,
            "traces": False,
        },
        "evidence_source_files": {},
    }


def build_case_context(case: dict[str, Any]) -> dict[str, Any]:
    evidence_availability = case.get("evidence_availability")
    if not isinstance(evidence_availability, dict):
        evidence_availability = {
            "metrics": bool(case.get("has_metrics")),
            "logs": bool(case.get("has_logs")),
            "traces": bool(case.get("has_traces")),
        }
    evidence_source_files = case.get("evidence_source_files")
    if not isinstance(evidence_source_files, dict):
        evidence_source_files = {}
    return {
        "dataset": case.get("dataset") or "unknown",
        "scenario": case.get("scenario") or "unknown",
        "case_id": case.get("case_id") or "",
        "case_dir": case.get("case_dir") or case.get("data_path") or "",
        "data_path": case.get("data_path") or case.get("case_dir") or "",
        "csv_path": case.get("data_path") or case.get("case_dir") or "",
        "inject_time": case.get("inject_time"),
        "root_cause": case.get("root_cause"),
        "fault_type": case.get("fault_type"),
        "evidence_availability": {
            "metrics": bool(evidence_availability.get("metrics")),
            "logs": bool(evidence_availability.get("logs")),
            "traces": bool(evidence_availability.get("traces")),
        },
        "evidence_source_files": {
            str(key): str(value) for key, value in evidence_source_files.items() if value
        },
    }


def _read_optional_int(path: Path) -> int | None:
    if not path.exists():
        return None
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except ValueError:
        return None


def _read_optional_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace").strip()


def _infer_scenario(case_id: str) -> str:
    parts = case_id.split("_")
    return parts[0].lower() if parts else "unknown"


def _scenario_id_for_case_dir(case_dir: Path) -> str:
    parent = case_dir.parent.name
    if "_" in parent:
        return parent
    return ""


def _infer_root_cause(case_id: str, root_cause_text: str = "") -> str | None:
    parts = case_id.split("_")
    inferred_from_id = parts[0] if len(parts) >= 2 else None
    if inferred_from_id and root_cause_text and inferred_from_id.lower() in root_cause_text.lower():
        return inferred_from_id
    if root_cause_text:
        tokens = root_cause_text.replace(",", " ").split()
        ignored = {"root", "cause", "root_cause", "time", "timestamp", "warn", "error", "info"}
        for token in tokens:
            cleaned = token.strip(":：,，;；[]()").strip()
            if not cleaned or cleaned.lower() in ignored:
                continue
            if cleaned.isdigit() or ":" in cleaned:
                continue
            if len(cleaned) > 64:
                continue
            return cleaned
    return inferred_from_id


def _infer_fault_type(case_id: str) -> str | None:
    parts = case_id.split("_")
    return parts[1] if len(parts) >= 2 else None


def _evidence_availability(case_dir: Path) -> dict[str, bool]:
    return {
        "metrics": any((case_dir / filename).exists() for filename in RCAEVAL_CASE_FILES),
        "logs": (case_dir / "logs.csv").exists(),
        "traces": (case_dir / "traces.csv").exists(),
    }


def _evidence_source_files(case_dir: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    for filename in RCAEVAL_CASE_FILES:
        path = case_dir / filename
        if path.exists():
            files["metrics"] = str(path)
            break
    for key, filename in (("logs", "logs.csv"), ("traces", "traces.csv")):
        path = case_dir / filename
        if path.exists():
            files[key] = str(path)
    return files


def _default_user_input(case_id: str, root_cause: str | None, fault_type: str | None) -> str:
    if root_cause and fault_type:
        return f"{case_id}: {root_cause} shows {fault_type} anomaly. Please analyze the root cause."
    return f"{case_id}: please analyze the root cause."


def _infer_dataset(case_dir: Path) -> str:
    for part in case_dir.parts:
        dataset = RCAEVAL_DATASET_KEYS.get(part.upper())
        if dataset:
            return dataset
    for part in case_dir.parts:
        lowered = part.lower()
        if lowered in set(RCAEVAL_DATASET_KEYS.values()):
            return lowered
    return "local"


def _resolve_path(value: Any) -> Path:
    return Path(str(value)).expanduser().resolve()


def _legacy_flat_cases() -> list[dict[str, Any]]:
    if not (BENCHMARK_DIR / "simple_metrics.csv").exists():
        return []
    return [
        {
            "case_id": "local_flat_case",
            "scenario": "local",
            "dataset": "local",
            "case_dir": str(BENCHMARK_DIR),
            "data_path": str(BENCHMARK_DIR),
            "inject_time": None,
            "root_cause": None,
            "root_cause_text": "",
            "fault_type": None,
            "has_metrics": True,
            "has_logs": (BENCHMARK_DIR / "logs.csv").exists(),
            "has_traces": (BENCHMARK_DIR / "traces.csv").exists(),
            "evidence_availability": {
                "metrics": True,
                "logs": (BENCHMARK_DIR / "logs.csv").exists(),
                "traces": (BENCHMARK_DIR / "traces.csv").exists(),
            },
            "evidence_source_files": _evidence_source_files(BENCHMARK_DIR),
            "default_user_input": "Local multi-source telemetry case. Please analyze the root cause.",
        }
    ]
