from __future__ import annotations

import argparse
import json
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas as pd

from benchmark_case_loader import filter_benchmark_cases, iter_benchmark_cases
from config import TEST_OUTPUTS_DIR
from utils.data_loader import CSVDataLoader


ERROR_KEYWORDS = (
    "error",
    "exception",
    "fail",
    "failed",
    "timeout",
    "warn",
    "refused",
    "denied",
    "unavailable",
    "unsupported",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a traditional non-agent RCA baseline on RCAEval-style cases.")
    parser.add_argument("--limit", type=int, default=180, help="Maximum number of cases to run.")
    parser.add_argument("--dataset", default="", help="Optional dataset filter, for example re3-tt.")
    parser.add_argument("--scenario", default="", help="Optional scenario filter.")
    parser.add_argument("--top-k", type=int, default=5, help="Top-K service hit threshold.")
    parser.add_argument(
        "--mode",
        choices=["simple", "enhanced"],
        default="simple",
        help="Baseline mode. enhanced filters infrastructure noise and normalizes service aliases.",
    )
    parser.add_argument(
        "--output",
        default=str(TEST_OUTPUTS_DIR / "traditional_baseline_full.json"),
        help="JSON output path.",
    )
    parser.add_argument(
        "--markdown-output",
        default="",
        help="Optional Markdown summary path. Defaults to the JSON path with .md suffix.",
    )
    return parser


def _strip_k8s_suffix(text: str) -> str:
    text = re.sub(r"-[0-9a-f]{6,}(?:-[a-z0-9]+)?$", "", text)
    text = re.sub(r"-(?=[a-z0-9]*\d)[a-z0-9]{5,}$", "", text)
    return text


def _normalize_service(value: str) -> str:
    text = str(value).strip()
    if not text:
        return ""
    text = text.split(".")[0]
    text = text.replace("_", "-")
    return _strip_k8s_suffix(text)


def _canonical_service(value: str) -> str:
    text = _normalize_service(value).lower()
    if not text:
        return ""
    if text.startswith("ts-") and not text.endswith("-service") and not any(
        token in text for token in ("-mongo", "-mysql", "-dashboard")
    ):
        text = f"{text}-service"
    return text


def _is_infrastructure_service(service: str) -> bool:
    text = service.lower()
    infrastructure_tokens = (
        "queue",
        "rabbitmq",
        "mongo",
        "mysql",
        "-db",
        "istio",
        "gke-",
        "ip-",
        "loadgenerator",
        "exporter",
        "dashboard",
    )
    return any(token in text for token in infrastructure_tokens)


def _metric_score(
    frame: pd.DataFrame,
    service_metrics: dict[str, list[str]],
    service: str,
    aliases: list[str] | None = None,
) -> tuple[float, dict[str, Any]]:
    metrics: list[str] = []
    for alias in [service, *(aliases or [])]:
        metrics.extend(service_metrics.get(alias) or [])
    metrics = list(dict.fromkeys(metrics))
    score = 0.0
    anomalous_columns = 0
    max_abs_z = 0.0
    for column in metrics:
        if column not in frame.columns:
            continue
        series = pd.to_numeric(frame[column], errors="coerce").dropna()
        if len(series) < 3:
            continue
        std = float(series.std(ddof=0))
        if std <= 1e-12:
            continue
        mean = float(series.mean())
        z_values = ((series - mean) / std).abs()
        column_max_z = float(z_values.max())
        anomaly_count = int((z_values >= 2.5).sum())
        if anomaly_count > 0:
            anomalous_columns += 1
        max_abs_z = max(max_abs_z, column_max_z)
        score += min(column_max_z, 8.0) + math.log1p(anomaly_count)
    return score, {
        "metric_score": round(score, 4),
        "anomalous_metric_columns": anomalous_columns,
        "max_abs_z": round(max_abs_z, 4),
    }


def _normalize_log_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    normalized = frame.copy()
    rename_map = {}
    for column in normalized.columns:
        lowered = column.lower()
        if lowered in {"time", "timestamp"} and "timestamp" not in rename_map.values():
            rename_map[column] = "timestamp"
        elif lowered in {"service", "container_name", "pod_name"} and "service" not in rename_map.values():
            rename_map[column] = "service"
        elif lowered in {"level", "severity"} and "level" not in rename_map.values():
            rename_map[column] = "level"
        elif lowered in {"msg", "content", "event", "message"} and "message" not in rename_map.values():
            rename_map[column] = "message"
    normalized = normalized.rename(columns=rename_map)
    if "service" not in normalized.columns:
        return normalized.iloc[0:0]
    if "message" not in normalized.columns:
        normalized["message"] = normalized.apply(lambda row: " ".join(str(value) for value in row.values), axis=1)
    if "level" not in normalized.columns:
        normalized["level"] = ""
    normalized["service"] = normalized["service"].astype(str).map(_normalize_service)
    return normalized


def _log_scores(frame: pd.DataFrame, *, enhanced: bool = False) -> dict[str, dict[str, Any]]:
    normalized = _normalize_log_frame(frame)
    if normalized.empty:
        return {}
    normalized["service"] = normalized["service"].astype(str).map(_canonical_service if enhanced else _normalize_service)
    scores: dict[str, dict[str, Any]] = {}
    for service, group in normalized.groupby("service"):
        if not service:
            continue
        messages = (
            group.get("message", pd.Series(dtype=str)).astype(str).str.lower()
            + " "
            + group.get("level", pd.Series(dtype=str)).astype(str).str.lower()
        )
        error_count = int(messages.map(lambda value: any(keyword in value for keyword in ERROR_KEYWORDS)).sum())
        log_count = int(len(group))
        score = math.log1p(log_count) + error_count * 2.0
        scores[str(service)] = {
            "log_score": round(score, 4),
            "log_count": log_count,
            "error_keyword_count": error_count,
        }
    return scores


def _normalize_trace_frame(frame: pd.DataFrame, *, enhanced: bool = False) -> pd.DataFrame:
    if frame.empty:
        return frame
    normalized = frame.copy()
    service_columns = [
        column
        for column in normalized.columns
        if column.lower() in {"service", "service_name", "operation", "caller", "callee", "source", "target"}
    ]
    if not service_columns:
        return normalized.iloc[0:0]
    rows: list[dict[str, str]] = []
    for _, row in normalized.iterrows():
        for column in service_columns:
            raw_service = str(row.get(column, ""))
            service = _canonical_service(raw_service) if enhanced else _normalize_service(raw_service)
            if service:
                rows.append({"service": service})
    return pd.DataFrame(rows)


def _trace_scores(frame: pd.DataFrame, *, enhanced: bool = False) -> dict[str, dict[str, Any]]:
    normalized = _normalize_trace_frame(frame, enhanced=enhanced)
    if normalized.empty:
        return {}
    scores: dict[str, dict[str, Any]] = {}
    for service, group in normalized.groupby("service"):
        count = int(len(group))
        scores[str(service)] = {
            "trace_score": round(math.log1p(count), 4),
            "trace_count": count,
        }
    return scores


def _service_aliases(services: list[str], enhanced: bool) -> dict[str, list[str]]:
    aliases: dict[str, list[str]] = defaultdict(list)
    for service in services:
        canonical = _canonical_service(service) if enhanced else _normalize_service(service)
        if canonical:
            aliases[canonical].append(service)
    return aliases


def _scenario_bonus(service: str, case: dict[str, Any], enhanced: bool) -> float:
    return 0.0


def _rank_case(case: dict[str, Any], *, mode: str = "simple") -> dict[str, Any]:
    enhanced = mode == "enhanced"
    loader = CSVDataLoader(case["data_path"])
    metrics = loader.load_metrics()
    metadata = loader.get_metadata()
    services = list(metadata.get("services") or [])
    service_metrics = metadata.get("service_metrics") or {}
    alias_map = _service_aliases(services, enhanced)
    log_scores = _log_scores(loader.load_logs(), enhanced=enhanced)
    trace_scores = _trace_scores(loader.load_traces(), enhanced=enhanced)

    all_services = set(alias_map) | set(log_scores) | set(trace_scores)
    ranked: list[dict[str, Any]] = []
    for service in sorted(all_services):
        if enhanced and _is_infrastructure_service(service):
            continue
        metric_score, metric_details = _metric_score(metrics, service_metrics, service, alias_map.get(service, []))
        log_details = log_scores.get(service, {"log_score": 0.0, "log_count": 0, "error_keyword_count": 0})
        trace_details = trace_scores.get(service, {"trace_score": 0.0, "trace_count": 0})
        bonus = _scenario_bonus(service, case, enhanced)
        total = metric_score + float(log_details["log_score"]) * 0.35 + float(trace_details["trace_score"]) * 0.25 + bonus
        ranked.append(
            {
                "service": service,
                "score": round(total, 4),
                "scenario_bonus": bonus,
                **metric_details,
                **log_details,
                **trace_details,
            }
        )
    ranked.sort(key=lambda item: (item["score"], item["metric_score"], item["error_keyword_count"]), reverse=True)
    return {
        "case_id": case["case_id"],
        "dataset": case.get("dataset"),
        "scenario": case.get("scenario"),
        "expected_root_cause": _canonical_service(str(case.get("root_cause") or "")) if enhanced else case.get("root_cause"),
        "raw_expected_root_cause": case.get("root_cause"),
        "ranked_services": [item["service"] for item in ranked],
        "ranked_details": ranked[:10],
    }


def _rank_of_expected(expected: str | None, ranked_services: list[str]) -> int | None:
    if not expected:
        return None
    for index, service in enumerate(ranked_services, start=1):
        if service == expected:
            return index
    return None


def _safe_rate(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return numerator / denominator


def _count_by(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = str(item.get(key) or "unknown")
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _summarize(results: list[dict[str, Any]], top_k: int) -> dict[str, Any]:
    labeled = [item for item in results if item.get("expected_root_cause")]
    top_1_hit_count = 0
    top_k_hit_count = 0
    reciprocal_ranks: list[float] = []
    for item in labeled:
        rank = item.get("expected_rank")
        if rank == 1:
            top_1_hit_count += 1
        if rank is not None and int(rank) <= top_k:
            top_k_hit_count += 1
        if rank:
            reciprocal_ranks.append(1 / int(rank))
    return {
        "case_count": len(results),
        "labeled_case_count": len(labeled),
        "top_1_hit_count": top_1_hit_count,
        "top_k_hit_count": top_k_hit_count,
        "top_1_accuracy": _safe_rate(top_1_hit_count, len(labeled)),
        "top_k_accuracy": _safe_rate(top_k_hit_count, len(labeled)),
        "mrr": sum(reciprocal_ranks) / len(labeled) if labeled else None,
    }


def _dataset_metrics(results: list[dict[str, Any]], top_k: int) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in results:
        grouped[str(item.get("dataset") or "unknown")].append(item)
    return {dataset: _summarize(items, top_k) for dataset, items in sorted(grouped.items())}


def _format_rate(value: Any) -> str:
    if value is None:
        return "-"
    return f"{float(value) * 100:.1f}%"


def _format_float(value: Any) -> str:
    if value is None:
        return "-"
    return f"{float(value):.3f}"


def _build_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    method_name = payload["config"]["method"]
    lines = [
        "# 传统规则基线结果摘要",
        "",
        "## 总体结果",
        "",
        "| 方法 | 案例数 | Top-1 | Top-K | MRR |",
        "| --- | ---: | ---: | ---: | ---: |",
        f"| {method_name} | {summary['case_count']} | {_format_rate(summary['top_1_accuracy'])} | {_format_rate(summary['top_k_accuracy'])} | {_format_float(summary['mrr'])} |",
        "",
        "## 分数据集结果",
        "",
        "| 数据集 | 案例数 | Top-1 | Top-K | MRR |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for dataset, item in payload["dataset_metrics"].items():
        lines.append(
            f"| {dataset} | {item['case_count']} | {_format_rate(item['top_1_accuracy'])} | "
            f"{_format_rate(item['top_k_accuracy'])} | {_format_float(item['mrr'])} |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    args = build_parser().parse_args()
    cases = filter_benchmark_cases(iter_benchmark_cases(), scenario=args.scenario, dataset=args.dataset)
    cases = cases[: args.limit]
    results: list[dict[str, Any]] = []
    for case in cases:
        result = _rank_case(case, mode=args.mode)
        rank = _rank_of_expected(result.get("expected_root_cause"), result["ranked_services"])
        result["expected_rank"] = rank
        result["top_1_hit"] = rank == 1
        result["top_k_hit"] = bool(rank is not None and rank <= args.top_k)
        results.append(result)

    payload = {
        "config": {
            "limit": args.limit,
            "dataset": args.dataset or None,
            "scenario": args.scenario or None,
            "top_k": args.top_k,
            "method": "traditional_enhanced_rule_baseline"
            if args.mode == "enhanced"
            else "traditional_metric_log_trace_rule_baseline",
            "mode": args.mode,
        },
        "case_count": len(results),
        "dataset_distribution": _count_by(results, "dataset"),
        "summary": _summarize(results, args.top_k),
        "dataset_metrics": _dataset_metrics(results, args.top_k),
        "results": results,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_output = Path(args.markdown_output) if args.markdown_output else output_path.with_suffix(".md")
    markdown_output.write_text(_build_markdown(payload), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
