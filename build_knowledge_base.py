from __future__ import annotations

import argparse
import csv
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from config import BENCHMARK_DIR, FAISS_INDEX_PATH, KNOWLEDGE_DOCS_PATH
from knowledge_base.schemas import KnowledgeDocument
from knowledge_base.store import KnowledgeBaseStore
from tools.topology_tools import SERVICE_TOPOLOGY
from utils.anomaly_detection import detect_anomaly_zscore
from utils.data_loader import CSVDataLoader
from utils.service_parser import discover_service_metrics


DEFAULT_SOLUTIONS = {
    "cpu": "Check workload changes, hot requests, and CPU saturation for the service. Scale or roll back recent changes if current-case evidence supports it.",
    "memory": "Check heap growth, cache pressure, and memory limits for the service. Restart or tune memory only after current-case evidence confirms the service.",
    "mem": "Check heap growth, cache pressure, and memory limits for the service. Restart or tune memory only after current-case evidence confirms the service.",
    "load": "Check sudden traffic, retry storms, and dependency instability around the incident window.",
    "latency": "Check slow downstream calls, thread pool saturation, and request path changes using metrics, logs, and traces.",
    "error": "Check error-code distribution, recent deployments, and dependency availability for the affected service.",
    "network": "Check packet drops, connection churn, and service-to-service network paths around the incident window.",
}

METRIC_KEYWORDS = {
    "cpu": ("cpu", "quota", "usage"),
    "memory": ("memory", "mem", "rss", "working-set", "cache", "failures"),
    "latency": ("latency", "duration", "response"),
    "error": ("error", "errors", "status"),
    "network": ("network", "packets", "bytes", "dropped", "receive", "transmit"),
    "io": ("blkio", "fs-", "disk", "read", "write"),
    "load": ("request", "load", "traffic"),
}


def build_documents_from_csv(csv_path: str | Path) -> list[KnowledgeDocument]:
    loader = CSVDataLoader(csv_path)
    frame = loader.load()
    service_metrics = discover_service_metrics(frame.columns.tolist())
    timestamp_column = loader.timestamp_column
    documents: list[KnowledgeDocument] = []

    semantic_columns = {column.lower(): column for column in frame.columns}

    for service, metrics in service_metrics.items():
        semantic_service_rows = _lookup_semantic_rows(frame, semantic_columns, service)
        metric_evidence = _metric_evidence_from_flat_csv(frame, timestamp_column, service, metrics)
        if not metric_evidence:
            continue
        primary_metric = metric_evidence[0]["metric"]
        fault_type = normalize_fault_type(primary_metric)
        root_cause = infer_root_cause(service, semantic_service_rows)
        solution = infer_solution(fault_type, semantic_service_rows)
        upstreams, downstreams = service_neighbors(service)
        topology_context = build_topology_context(service, upstreams, downstreams)
        candidate_role = infer_candidate_role(fault_type, service, root_cause)
        evidence_pillars = ["metric", "topology"]
        content = build_document_content(
            service=service,
            fault_type=fault_type,
            root_cause=root_cause,
            solution=solution,
            evidence_pillars=evidence_pillars,
            metric_evidence=metric_evidence[:5],
            log_evidence=[],
            trace_evidence=[],
            topology_context=topology_context,
            candidate_role=candidate_role,
            source_case_id=Path(csv_path).stem,
            source_dataset="csv",
        )
        related_services = sorted({service, *upstreams, *downstreams})
        documents.append(
            KnowledgeDocument(
                title=f"{service} service incident: {fault_type}",
                content=content,
                service=service,
                fault_type=fault_type,
                root_cause_service=service,
                fault_code=fault_type if re.fullmatch(r"f\d+", fault_type, re.IGNORECASE) else None,
                root_cause=root_cause,
                solution=solution,
                source=str(csv_path),
                tags=[service, *related_services, fault_type, candidate_role, "service_incident"],
                metadata=service_incident_metadata(
                    evidence_pillars=evidence_pillars,
                    metric_evidence=metric_evidence[:5],
                    log_evidence=[],
                    trace_evidence=[],
                    topology_context=topology_context,
                    candidate_role=candidate_role,
                    source_case_id=Path(csv_path).stem,
                    source_dataset="csv",
                    upstreams=upstreams,
                    downstreams=downstreams,
                    related_services=related_services,
                    root_cause_service=service,
                    fault_code=fault_type if re.fullmatch(r"f\d+", fault_type, re.IGNORECASE) else None,
                    legacy_note="Flat CSV metric anomalies are stored as metric evidence, not as root causes.",
                ),
            )
        )

    if not documents:
        documents.append(
            KnowledgeDocument(
                title="dataset overview",
                content="No service-level anomaly document was generated. This overview is a placeholder for manual service incident curation.",
                source=str(csv_path),
                tags=["overview"],
                metadata={
                    "rows": int(len(frame)),
                    "evidence_pillars": [],
                    "metric_evidence": [],
                    "log_evidence": [],
                    "trace_evidence": [],
                    "topology_context": {},
                    "candidate_role": "unknown",
                    "source_case_id": Path(csv_path).stem,
                    "source_dataset": "csv",
                },
            )
        )
    return documents


def build_documents_from_case_dir(
    case_dir: str | Path,
    *,
    dataset: str = "",
    limit: int | None = None,
) -> list[KnowledgeDocument]:
    root = Path(case_dir)
    case_dirs = discover_rcaeval_case_dirs(root)
    if dataset:
        dataset_key = dataset.strip().lower()
        case_dirs = [path for path in case_dirs if infer_dataset(path).lower() == dataset_key]
    if limit is not None:
        case_dirs = case_dirs[: max(0, limit)]

    documents: list[KnowledgeDocument] = []
    for path in case_dirs:
        documents.append(build_document_from_rcaeval_case(path, dataset_override=dataset))
    return documents


def discover_rcaeval_case_dirs(root: Path) -> list[Path]:
    metric_files = ("metrics.csv", "metrics.json", "simple_metrics.csv")
    if not root.exists():
        raise FileNotFoundError(f"Case directory not found: {root}")
    candidates = [
        path
        for path in root.rglob("*")
        if path.is_dir() and any((path / filename).exists() for filename in metric_files)
    ]
    priority = {"re3-ob": 0, "re3-tt": 1}
    return sorted(candidates, key=lambda path: (priority.get(infer_dataset(path), 9), str(path).lower()))


def build_document_from_rcaeval_case(case_dir: Path, *, dataset_override: str = "") -> KnowledgeDocument:
    scenario = infer_scenario(case_dir)
    service = normalize_service_name(infer_root_service(case_dir, scenario))
    fault_type = normalize_fault_type(infer_fault_type(scenario))
    root_cause = read_root_cause(case_dir) or service
    root_cause = normalize_root_cause(root_cause, fallback_service=service)
    dataset = dataset_override.strip() or infer_dataset(case_dir)
    source_case_id = f"{scenario}_{case_dir.name}" if scenario else case_dir.name

    metric_evidence = summarize_metric_evidence(case_dir, service)
    log_evidence = summarize_log_evidence(case_dir, service)
    trace_evidence = summarize_trace_evidence(case_dir, service)
    upstreams, downstreams = service_neighbors(service)
    topology_context = build_topology_context(service, upstreams, downstreams)
    evidence_pillars = sorted(
        pillar
        for pillar, evidence in {
            "metric": metric_evidence,
            "log": log_evidence,
            "trace": trace_evidence,
            "topology": [topology_context] if topology_context else [],
        }.items()
        if evidence
    )
    candidate_role = infer_candidate_role(fault_type, service, root_cause)
    solution = DEFAULT_SOLUTIONS.get(fault_type, "Use the historical case only as auxiliary evidence; verify the current case with metrics, logs, and traces.")
    related_services = sorted({service, *upstreams, *downstreams, *extract_trace_neighbors(trace_evidence, service)})

    content = build_document_content(
        service=service,
        fault_type=fault_type,
        root_cause=root_cause,
        solution=solution,
        evidence_pillars=evidence_pillars,
        metric_evidence=metric_evidence,
        log_evidence=log_evidence,
        trace_evidence=trace_evidence,
        topology_context=topology_context,
        candidate_role=candidate_role,
        source_case_id=source_case_id,
        source_dataset=dataset,
    )
    return KnowledgeDocument(
        title=f"{source_case_id}: {service} service incident ({fault_type})",
        content=content,
        service=service,
        fault_type=fault_type,
        root_cause_service=service,
        fault_code=fault_type if re.fullmatch(r"f\d+", fault_type, re.IGNORECASE) else None,
        root_cause=root_cause,
        solution=solution,
        source=str(case_dir),
        tags=[service, fault_type, candidate_role, dataset, "service_incident", *related_services],
        metadata=service_incident_metadata(
            evidence_pillars=evidence_pillars,
            metric_evidence=metric_evidence,
            log_evidence=log_evidence,
            trace_evidence=trace_evidence,
            topology_context=topology_context,
            candidate_role=candidate_role,
            source_case_id=source_case_id,
            source_dataset=dataset,
            upstreams=upstreams,
            downstreams=downstreams,
            related_services=related_services,
            root_cause_service=service,
            fault_code=fault_type if re.fullmatch(r"f\d+", fault_type, re.IGNORECASE) else None,
            scenario=scenario,
            case_dir=str(case_dir),
            evidence_availability={
                "metrics": bool(metric_evidence),
                "logs": (case_dir / "logs.csv").exists(),
                "traces": (case_dir / "traces.csv").exists(),
            },
            evidence_source_files={
                "metrics": first_existing_name(case_dir, ["metrics.csv", "metrics.json", "simple_metrics.csv"]),
                "logs": "logs.csv" if (case_dir / "logs.csv").exists() else None,
                "traces": "traces.csv" if (case_dir / "traces.csv").exists() else None,
            },
        ),
    )


def service_incident_metadata(**kwargs: Any) -> dict[str, Any]:
    metadata = dict(kwargs)
    metadata.setdefault("evidence_pillars", [])
    metadata.setdefault("metric_evidence", [])
    metadata.setdefault("log_evidence", [])
    metadata.setdefault("trace_evidence", [])
    metadata.setdefault("topology_context", {})
    metadata.setdefault("candidate_role", "unknown")
    metadata.setdefault("source_case_id", "unknown")
    metadata.setdefault("source_dataset", "unknown")
    metadata.setdefault("root_cause_service", metadata.get("service"))
    if not metadata.get("fault_code"):
        fault_type = str(metadata.get("fault_type") or "").strip()
        if re.fullmatch(r"f\d+", fault_type, re.IGNORECASE):
            metadata["fault_code"] = fault_type.lower()
    metadata["contract_schema_version"] = "service_fault_v1"
    metadata["evidence_type"] = "service_incident_case"
    return metadata


def summarize_metric_evidence(case_dir: Path, service: str) -> list[dict[str, Any]]:
    metrics_path = first_existing_path(case_dir, ["simple_metrics.csv", "metrics.csv"])
    if not metrics_path:
        return []
    try:
        frame = pd.read_csv(metrics_path, nrows=250)
    except Exception as exc:
        return [{"service": service, "pillar": "metric", "source_type": "real", "summary": f"metric file could not be parsed: {exc}"}]

    service_columns = [
        column
        for column in frame.columns
        if column != "time" and service_token_matches_column(service, column)
    ]
    if not service_columns:
        service_columns = [column for column in frame.columns if column != "time" and service.split("-")[0] in column.lower()]
    scored: list[tuple[float, str, str]] = []
    for column in service_columns[:200]:
        series = pd.to_numeric(frame[column], errors="coerce").dropna()
        if series.empty:
            continue
        spread = float(series.max() - series.min())
        std = float(series.std()) if not math.isnan(float(series.std())) else 0.0
        score = spread + std
        if score <= 0:
            continue
        scored.append((score, column, classify_metric_name(column)))
    scored.sort(reverse=True, key=lambda item: item[0])

    evidence: list[dict[str, Any]] = []
    for score, column, metric_type in scored[:5]:
        series = pd.to_numeric(frame[column], errors="coerce")
        evidence.append(
            {
                "service": service,
                "pillar": "metric",
                "source_type": "real",
                "metric": metric_type,
                "metric_name": column,
                "strength": "medium" if score > 0 else "weak",
                "summary": f"{service} has {metric_type} metric movement in {column}.",
                "details": {
                    "min": safe_float(series.min()),
                    "max": safe_float(series.max()),
                    "std": safe_float(series.std()),
                },
            }
        )
    return evidence


def summarize_log_evidence(case_dir: Path, service: str) -> list[dict[str, Any]]:
    logs_path = case_dir / "logs.csv"
    if not logs_path.exists():
        return []
    counts: Counter[str] = Counter()
    examples: list[str] = []
    try:
        with logs_path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                row_service = str(row.get("container_name") or row.get("service") or row.get("serviceName") or "").strip()
                if normalize_service_name(row_service) != service:
                    continue
                message = str(row.get("message") or row.get("log") or "").strip()
                severity = classify_log_message(message)
                counts[severity] += 1
                if message and len(examples) < 3:
                    examples.append(message[:180])
                if sum(counts.values()) >= 500:
                    break
    except Exception as exc:
        return [{"service": service, "pillar": "log", "source_type": "real", "summary": f"log file could not be parsed: {exc}"}]
    total = sum(counts.values())
    if total == 0:
        return []
    severity = "error" if counts["error"] else "warning" if counts["warning"] else "activity"
    return [
        {
            "service": service,
            "pillar": "log",
            "source_type": "real",
            "strength": "strong" if counts["error"] else "medium",
            "summary": f"{service} has {total} log records in the incident window; dominant class: {severity}.",
            "details": {"counts": dict(counts), "examples": examples},
        }
    ]


def summarize_trace_evidence(case_dir: Path, service: str) -> list[dict[str, Any]]:
    traces_path = case_dir / "traces.csv"
    if not traces_path.exists():
        return []
    service_counts: Counter[str] = Counter()
    operations: Counter[str] = Counter()
    durations: list[float] = []
    parent_links: dict[str, str] = {}
    span_services: dict[str, str] = {}
    try:
        with traces_path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                row_service = normalize_service_name(str(row.get("serviceName") or row.get("service") or "").strip())
                span_id = str(row.get("spanID") or "").strip()
                parent_id = str(row.get("parentSpanID") or "").strip()
                if row_service:
                    service_counts[row_service] += 1
                if span_id and row_service:
                    span_services[span_id] = row_service
                if span_id and parent_id:
                    parent_links[span_id] = parent_id
                if row_service == service:
                    operation = str(row.get("operationName") or row.get("methodName") or "").strip()
                    if operation:
                        operations[operation] += 1
                    duration = safe_float(row.get("duration"))
                    if duration is not None:
                        durations.append(duration)
    except Exception as exc:
        return [{"service": service, "pillar": "trace", "source_type": "real", "summary": f"trace file could not be parsed: {exc}"}]

    if service_counts.get(service, 0) == 0:
        return []
    neighbors: set[str] = set()
    for span_id, parent_id in parent_links.items():
        child_service = span_services.get(span_id)
        parent_service = span_services.get(parent_id)
        if child_service == service and parent_service:
            neighbors.add(parent_service)
        if parent_service == service and child_service:
            neighbors.add(child_service)
    return [
        {
            "service": service,
            "pillar": "trace",
            "source_type": "real",
            "strength": "medium",
            "summary": f"{service} appears in {service_counts[service]} trace spans with real trace data.",
            "details": {
                "span_count": service_counts[service],
                "top_operations": dict(operations.most_common(5)),
                "neighbor_services": sorted(neighbors),
                "duration_max": max(durations) if durations else None,
            },
        }
    ]


def _metric_evidence_from_flat_csv(
    frame: pd.DataFrame,
    timestamp_column: str,
    service: str,
    metrics: Iterable[str],
) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for metric in metrics:
        metric_column = f"{service}_{metric}"
        if metric_column not in frame.columns:
            continue
        series = frame[metric_column]
        anomaly_indices = detect_anomaly_zscore(series, threshold=2.5)
        if not anomaly_indices:
            continue
        anomaly_frame = frame.iloc[anomaly_indices]
        evidence.append(
            {
                "service": service,
                "pillar": "metric",
                "source_type": "real",
                "metric": normalize_fault_type(metric),
                "metric_name": metric_column,
                "strength": "medium",
                "summary": f"{service} {metric} anomaly is observed in the source CSV.",
                "details": {
                    "peak_value": safe_float(pd.to_numeric(series, errors="coerce").max()),
                    "window_start": safe_int(anomaly_frame[timestamp_column].min()),
                    "window_end": safe_int(anomaly_frame[timestamp_column].max()),
                    "anomaly_count": len(anomaly_indices),
                },
            }
        )
    evidence.sort(key=lambda item: int(item.get("details", {}).get("anomaly_count") or 0), reverse=True)
    return evidence


def build_document_content(
    *,
    service: str,
    fault_type: str,
    root_cause: str,
    solution: str,
    evidence_pillars: list[str],
    metric_evidence: list[dict[str, Any]],
    log_evidence: list[dict[str, Any]],
    trace_evidence: list[dict[str, Any]],
    topology_context: dict[str, Any],
    candidate_role: str,
    source_case_id: str,
    source_dataset: str,
) -> str:
    metric_text = "; ".join(item.get("summary", "") for item in metric_evidence[:3]) or "no metric evidence captured"
    log_text = "; ".join(item.get("summary", "") for item in log_evidence[:2]) or "no log evidence captured"
    trace_text = "; ".join(item.get("summary", "") for item in trace_evidence[:2]) or "no trace evidence captured"
    upstream_text = ", ".join(topology_context.get("upstreams", [])) or "none"
    downstream_text = ", ".join(topology_context.get("downstreams", [])) or "none"
    return "\n".join(
        [
            f"Service incident case: {service} is the service-level root cause candidate for {fault_type}.",
            f"Root cause service/text: {root_cause}. This is not a metric-name root cause.",
            f"Evidence pillars: {', '.join(evidence_pillars) if evidence_pillars else 'none'}.",
            f"Metric evidence: {metric_text}.",
            f"Log evidence: {log_text}.",
            f"Trace evidence: {trace_text}.",
            f"Topology context: upstreams={upstream_text}; downstreams={downstream_text}.",
            f"Historical role: {candidate_role}.",
            f"Source: dataset={source_dataset}; case={source_case_id}.",
            f"Suggested action: {solution}",
        ]
    )


def _lookup_semantic_rows(frame: pd.DataFrame, semantic_columns: dict[str, str], service: str) -> pd.DataFrame:
    service_column = semantic_columns.get("service")
    if not service_column:
        return frame.iloc[0:0]
    return frame.loc[frame[service_column].astype(str).str.lower() == service.lower()]


def _first_non_empty(frame: pd.DataFrame, columns: list[str]) -> str | None:
    for column in columns:
        if column not in frame.columns:
            continue
        values = frame[column].dropna().astype(str)
        values = values[values.str.strip() != ""]
        if not values.empty:
            return values.iloc[0].strip()
    return None


def normalize_fault_type(value: str | None) -> str:
    text = str(value or "").strip().lower()
    if text in {"mem", "memory"}:
        return "memory"
    if text.startswith("f") and text[1:].isdigit():
        return text
    for fault_type, keywords in METRIC_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return fault_type
    return text or "unknown"


def classify_metric_name(column: str) -> str:
    lowered = column.lower()
    for metric_type, keywords in METRIC_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return metric_type
    return "metric"


def infer_root_cause(service: str, semantic_rows: pd.DataFrame) -> str:
    semantic_root_cause = _first_non_empty(semantic_rows, ["root_cause", "service", "root_service"])
    if semantic_root_cause:
        return normalize_root_cause(semantic_root_cause, fallback_service=service)
    return service


def infer_solution(fault_type: str, semantic_rows: pd.DataFrame) -> str:
    semantic_solution = _first_non_empty(semantic_rows, ["solution"])
    if semantic_solution:
        return semantic_solution
    return DEFAULT_SOLUTIONS.get(fault_type, "Verify the service-level hypothesis with current metrics, logs, and traces before acting.")


def infer_candidate_role(fault_type: str, service: str = "", root_cause: str = "") -> str:
    if service and root_cause and normalize_service_name(service) == normalize_service_name(root_cause):
        return "origin_candidate"
    if fault_type in {"latency", "error"}:
        return "origin_or_propagated"
    return "origin_candidate"


def service_neighbors(service: str) -> tuple[list[str], list[str]]:
    details = SERVICE_TOPOLOGY.get(service, {})
    downstreams = sorted(str(item) for item in details.get("dependencies", []))
    upstreams = sorted(
        source
        for source, source_details in SERVICE_TOPOLOGY.items()
        if service in source_details.get("dependencies", [])
    )
    return upstreams, downstreams


def build_topology_context(service: str, upstreams: list[str], downstreams: list[str]) -> dict[str, Any]:
    return {
        "service": service,
        "upstreams": upstreams,
        "downstreams": downstreams,
        "source_type": "inferred" if upstreams or downstreams else "none",
        "summary": f"{service} topology context: upstreams={upstreams or ['none']}, downstreams={downstreams or ['none']}.",
    }


def infer_scenario(case_dir: Path) -> str:
    parent = case_dir.parent.name
    return parent if "_" in parent else case_dir.name


def infer_root_service(case_dir: Path, scenario: str) -> str:
    root_text = read_root_cause(case_dir)
    if root_text:
        return root_text
    return scenario.split("_")[0] if "_" in scenario else scenario


def infer_fault_type(scenario: str) -> str:
    parts = scenario.split("_", 1)
    return parts[1] if len(parts) > 1 else "unknown"


def read_root_cause(case_dir: Path) -> str:
    path = case_dir / "root_cause.txt"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace").strip()


def normalize_root_cause(value: str, *, fallback_service: str) -> str:
    text = str(value or "").strip()
    if not text:
        return fallback_service
    tokens = re.split(r"[\s,;:()\[\]{}]+", text)
    ignored = {"root", "cause", "root_cause", "metric", "metrics", "error", "latency", "cpu", "memory", "mem"}
    for token in tokens:
        cleaned = normalize_service_name(token)
        if not cleaned or cleaned in ignored:
            continue
        if any(ch.isdigit() for ch in cleaned) and "-" not in cleaned:
            continue
        if len(cleaned) <= 80:
            return cleaned
    return normalize_service_name(fallback_service)


def normalize_service_name(value: str) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("_", "-")
    text = re.sub(r"[^a-z0-9.-]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text


def service_token_matches_column(service: str, column: str) -> bool:
    lowered = column.lower()
    service = normalize_service_name(service)
    variants = {service, service.replace("-", ""), service.replace("-", "_")}
    return any(lowered.startswith(f"{variant}_") or lowered.startswith(f"{variant}-") for variant in variants)


def classify_log_message(message: str) -> str:
    lowered = message.lower()
    if any(token in lowered for token in ["error", "exception", "failed", "failure", "timeout", "unavailable"]):
        return "error"
    if any(token in lowered for token in ["warn", "retry", "slow", "latency"]):
        return "warning"
    return "info"


def extract_trace_neighbors(trace_evidence: list[dict[str, Any]], service: str) -> set[str]:
    neighbors: set[str] = set()
    for item in trace_evidence:
        details = item.get("details") or {}
        for neighbor in details.get("neighbor_services", []) or []:
            normalized = normalize_service_name(neighbor)
            if normalized and normalized != service:
                neighbors.add(normalized)
    return neighbors


def infer_dataset(case_dir: Path) -> str:
    for part in case_dir.parts:
        lowered = part.lower()
        if re.fullmatch(r"re\d-[a-z]{2}", lowered):
            return lowered
        upper = part.upper()
        if re.fullmatch(r"RE\d-[A-Z]{2}", upper):
            return upper.lower()
    return "local"


def first_existing_path(root: Path, names: list[str]) -> Path | None:
    for name in names:
        path = root / name
        if path.exists():
            return path
    return None


def first_existing_name(root: Path, names: list[str]) -> str | None:
    path = first_existing_path(root, names)
    return path.name if path else None


def safe_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(result) or math.isinf(result):
        return None
    return result


def safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build service-level RCA knowledge base documents and index")
    parser.add_argument(
        "--csv",
        default="",
        help="Path to the labeled or semi-structured benchmark CSV. Kept for legacy flat CSV builds.",
    )
    parser.add_argument("--case-dir", default="", help="Directory containing RCAEval case folders.")
    parser.add_argument("--dataset", default="", help="Optional dataset filter or metadata override, e.g. re3-ob.")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of RCAEval case documents to build.")
    parser.add_argument("--output-docs", default=str(KNOWLEDGE_DOCS_PATH), help="Output documents.json path.")
    parser.add_argument("--index-dir", default=str(FAISS_INDEX_PATH), help="Output index directory.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.case_dir:
        documents = build_documents_from_case_dir(args.case_dir, dataset=args.dataset, limit=args.limit)
    else:
        csv_path = args.csv or str(BENCHMARK_DIR / "data_with_error.csv")
        documents = build_documents_from_csv(csv_path)

    store = KnowledgeBaseStore(docs_path=args.output_docs, index_path=args.index_dir)
    store.save_documents(documents)
    result = store.rebuild_index(documents)
    print(
        {
            "document_count": result["document_count"],
            "dimension": result["dimension"],
            "index_path": result["index_path"],
            "docs_path": str(store.docs_path),
            "index_backend": result.get("index_backend"),
        }
    )


if __name__ == "__main__":
    main()
