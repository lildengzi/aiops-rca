from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from statistics import mean
from typing import Any

from benchmark_case_loader import has_benchmark_case_layout, iter_benchmark_cases
from config import BENCHMARK_DIR
from utils.anomaly_detection import detect_anomaly_zscore
from utils.data_loader import CSVDataLoader
from utils.service_parser import discover_service_metrics, find_metric_column
from workflow.orchestrator import RCAOrchestrator
from workflow.summary import build_investigation_summary

DEFAULT_CSV_PATH = str(BENCHMARK_DIR / "data_with_error.csv")
DEFAULT_SAMPLE_COUNT = 8
DEFAULT_WINDOW_SIZE = 30
BASELINE_THRESHOLD = 3.0
FAULT_METRICS = ("latency", "error", "load", "cpu", "mem")
FAULT_TYPE_BY_METRIC = {
    "latency": "latency",
    "error": "error",
    "load": "load",
    "cpu": "cpu",
    "mem": "memory",
}
FAULT_TYPE_ALIASES = {
    "mem": "memory",
    "memory": "memory",
    "latency": "latency",
    "error": "error",
    "load": "load",
    "cpu": "cpu",
    "delay": "latency",
    "loss": "error",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Benchmark the RCA workflow against a simple baseline")
    parser.add_argument("--csv", default=DEFAULT_CSV_PATH, help="Path to the telemetry CSV file")
    parser.add_argument(
        "--benchmark-dir",
        default=str(BENCHMARK_DIR),
        help="Path to the benchmark directory containing scenario/case folders",
    )
    parser.add_argument(
        "--mode",
        choices=("auto", "csv", "cases"),
        default="auto",
        help="Benchmark mode: single CSV windows or benchmark cases",
    )
    parser.add_argument("--sample-count", type=int, default=DEFAULT_SAMPLE_COUNT, help="Number of windows or cases to evaluate")
    parser.add_argument("--window-size", type=int, default=DEFAULT_WINDOW_SIZE, help="Window size in rows")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducible sampling")
    parser.add_argument(
        "--output",
        default=str(Path("benchmark_results.json")),
        help="Path to write JSON benchmark results",
    )
    return parser


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _safe_mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(mean(values))


def _build_prompt(service: str, fault_type: str) -> str:
    fault_label = {
        "latency": "延迟升高",
        "error": "错误升高",
        "load": "负载升高",
        "cpu": "CPU 升高",
        "mem": "内存升高",
        "memory": "内存升高",
    }.get(fault_type, f"{fault_type} 异常")
    return f"{service} {fault_label}，请分析根因"


def _window_bounds(frame, timestamp_column: str, start_index: int, window_size: int) -> tuple[int, int]:
    end_index = min(start_index + window_size - 1, len(frame) - 1)
    start_ts = int(frame.iloc[start_index][timestamp_column])
    end_ts = int(frame.iloc[end_index][timestamp_column])
    return start_ts, end_ts


def _normalize_fault_type(value: str | None) -> str | None:
    if value is None:
        return None
    return FAULT_TYPE_ALIASES.get(value.lower(), value.lower())


def _score_window(series, threshold: float) -> tuple[int, float]:
    anomaly_indices = detect_anomaly_zscore(series, threshold=threshold)
    if series.empty:
        return 0, 0.0
    numeric = series.astype(float)
    peak = float(numeric.max()) if len(numeric) else 0.0
    return len(anomaly_indices), peak


def _build_candidates(loader: CSVDataLoader, window_size: int) -> list[dict[str, Any]]:
    frame = loader.load()
    timestamp_column = loader.timestamp_column
    service_metrics = discover_service_metrics(frame.columns.tolist())
    candidates: list[dict[str, Any]] = []
    max_start = max(len(frame) - window_size + 1, 0)

    for start_index in range(max_start):
        end_index = start_index + window_size
        window = frame.iloc[start_index:end_index].reset_index(drop=True)
        if window.empty:
            continue
        best: dict[str, Any] | None = None
        for service, metrics in service_metrics.items():
            for metric in metrics:
                if metric not in FAULT_METRICS:
                    continue
                column = find_metric_column(window.columns.tolist(), service, metric)
                anomaly_count, peak = _score_window(window[column], threshold=BASELINE_THRESHOLD)
                if anomaly_count <= 0:
                    continue
                candidate = {
                    "service": service,
                    "metric": metric,
                    "fault_type": FAULT_TYPE_BY_METRIC.get(metric, metric),
                    "anomaly_count": anomaly_count,
                    "peak": peak,
                    "start": int(window.iloc[0][timestamp_column]),
                    "end": int(window.iloc[-1][timestamp_column]),
                    "start_index": start_index,
                }
                if best is None or (candidate["anomaly_count"], candidate["peak"]) > (best["anomaly_count"], best["peak"]):
                    best = candidate
        if best is not None:
            candidates.append(best)
    return candidates


def _sample_candidates(candidates: list[dict[str, Any]], sample_count: int, seed: int) -> list[dict[str, Any]]:
    if len(candidates) <= sample_count:
        return candidates
    rng = random.Random(seed)
    return sorted(rng.sample(candidates, sample_count), key=lambda item: item["start"])


def _baseline_predict(loader: CSVDataLoader, start: int | None, end: int | None) -> dict[str, Any]:
    frame = loader.filter_by_time(start=start, end=end)
    service_metrics = discover_service_metrics(frame.columns.tolist())
    best: dict[str, Any] | None = None
    for service, metrics in service_metrics.items():
        for metric in metrics:
            if metric not in FAULT_METRICS:
                continue
            column = find_metric_column(frame.columns.tolist(), service, metric)
            anomaly_count, peak = _score_window(frame[column], threshold=BASELINE_THRESHOLD)
            if anomaly_count <= 0:
                continue
            candidate = {
                "service": service,
                "fault_type": FAULT_TYPE_BY_METRIC.get(metric, metric),
                "metric": metric,
                "anomaly_count": anomaly_count,
                "peak": peak,
            }
            if best is None or (candidate["anomaly_count"], candidate["peak"]) > (best["anomaly_count"], best["peak"]):
                best = candidate
    return best or {
        "service": None,
        "fault_type": None,
        "metric": None,
        "anomaly_count": 0,
        "peak": 0.0,
    }


def _evaluate_hits(predicted_service: str | None, predicted_fault_type: str | None, truth: dict[str, Any]) -> dict[str, bool]:
    return {
        "service_hit": predicted_service == truth.get("service"),
        "fault_type_hit": _normalize_fault_type(predicted_fault_type) == _normalize_fault_type(truth.get("fault_type")),
    }


def _aggregate_metrics(samples: list[dict[str, Any]], model_key: str) -> dict[str, Any]:
    total = len(samples)
    service_hits = sum(1 for item in samples if item[model_key]["hits"]["service_hit"])
    fault_type_hits = sum(1 for item in samples if item[model_key]["hits"]["fault_type_hit"])
    confidences = [
        float(item[model_key].get("confidence"))
        for item in samples
        if item[model_key].get("confidence") is not None
    ]
    stop_count = sum(1 for item in samples if item[model_key].get("decision") == "stop")
    return {
        "samples": total,
        "service_hit_rate": round(service_hits / total, 4) if total else 0.0,
        "fault_type_hit_rate": round(fault_type_hits / total, 4) if total else 0.0,
        "avg_confidence": round(_safe_mean(confidences), 4) if confidences else None,
        "decision_stop_rate": round(stop_count / total, 4) if total else 0.0,
        "accuracy": round(service_hits / total, 4) if total else 0.0,
        "precision": round(service_hits / total, 4) if total else 0.0,
        "recall": round(service_hits / total, 4) if total else 0.0,
        "f1": round(service_hits / total, 4) if total else 0.0,
    }


def run_window_benchmark(csv_path: str, sample_count: int, window_size: int, seed: int) -> dict[str, Any]:
    loader = CSVDataLoader(csv_path)
    candidates = _build_candidates(loader, window_size=window_size)
    sampled = _sample_candidates(candidates, sample_count=sample_count, seed=seed)
    orchestrator = RCAOrchestrator(csv_path=csv_path)
    samples: list[dict[str, Any]] = []

    for index, truth in enumerate(sampled, start=1):
        prompt = _build_prompt(truth["service"], truth["fault_type"])
        baseline = _baseline_predict(loader, truth["start"], truth["end"])
        state = orchestrator.run_investigation(
            user_input=prompt,
            start=truth["start"],
            end=truth["end"],
        )
        summary = build_investigation_summary(state)
        decision_summary = summary.get("decision_summary", {})
        report_header = summary.get("report_header", {})
        rca_prediction = {
            "service": decision_summary.get("root_cause"),
            "fault_type": report_header.get("fault_type"),
            "decision": decision_summary.get("decision"),
            "confidence": decision_summary.get("confidence"),
        }
        baseline_hits = _evaluate_hits(baseline.get("service"), baseline.get("fault_type"), truth)
        rca_hits = _evaluate_hits(rca_prediction.get("service"), rca_prediction.get("fault_type"), truth)
        samples.append(
            {
                "sample_id": index,
                "window": {
                    "start": truth["start"],
                    "end": truth["end"],
                    "start_index": truth["start_index"],
                    "window_size": window_size,
                },
                "prompt": prompt,
                "pseudo_ground_truth": {
                    "service": truth["service"],
                    "fault_type": truth["fault_type"],
                    "metric": truth["metric"],
                    "anomaly_count": truth["anomaly_count"],
                    "peak": truth["peak"],
                },
                "baseline": {
                    **baseline,
                    "hits": baseline_hits,
                    "decision": "stop" if baseline.get("service") else "continue",
                    "confidence": None,
                },
                "rca": {
                    **rca_prediction,
                    "hits": rca_hits,
                    "report_path": summary.get("artifacts", {}).get("report_path"),
                    "think_log_path": summary.get("artifacts", {}).get("think_log_path"),
                },
            }
        )

    return {
        "benchmark_config": {
            "mode": "csv",
            "csv_path": csv_path,
            "sample_count": sample_count,
            "window_size": window_size,
            "seed": seed,
            "baseline_threshold": BASELINE_THRESHOLD,
            "candidate_windows": len(candidates),
            "evaluated_windows": len(samples),
        },
        "aggregate": {
            "baseline": _aggregate_metrics(samples, "baseline"),
            "rca": _aggregate_metrics(samples, "rca"),
        },
        "samples": samples,
    }


def run_case_benchmark(benchmark_dir: str, sample_count: int, seed: int) -> dict[str, Any]:
    cases = iter_benchmark_cases(benchmark_dir)
    if len(cases) > sample_count:
        rng = random.Random(seed)
        selected_cases = sorted(rng.sample(cases, sample_count), key=lambda item: (item["scenario"], item["case_id"]))
    else:
        selected_cases = cases

    samples: list[dict[str, Any]] = []
    for index, case in enumerate(selected_cases, start=1):
        loader = CSVDataLoader(case["csv_path"])
        baseline = _baseline_predict(loader, case.get("inject_time"), None)
        orchestrator = RCAOrchestrator(csv_path=case["csv_path"])
        state = orchestrator.run_investigation(
            user_input=case["default_user_input"],
            start=case.get("inject_time"),
            end=None,
        )
        summary = build_investigation_summary(state)
        decision_summary = summary.get("decision_summary", {})
        report_header = summary.get("report_header", {})
        truth = {
            "service": case.get("expected_root_cause"),
            "fault_type": case.get("fault_type"),
        }
        rca_prediction = {
            "service": decision_summary.get("root_cause"),
            "fault_type": report_header.get("fault_type"),
            "decision": decision_summary.get("decision"),
            "confidence": decision_summary.get("confidence"),
        }
        baseline_hits = _evaluate_hits(baseline.get("service"), baseline.get("fault_type"), truth)
        rca_hits = _evaluate_hits(rca_prediction.get("service"), rca_prediction.get("fault_type"), truth)
        samples.append(
            {
                "sample_id": index,
                "case": {
                    "scenario": case.get("scenario"),
                    "case_id": case.get("case_id"),
                    "case_dir": case.get("case_dir"),
                    "csv_path": case.get("csv_path"),
                    "inject_time": case.get("inject_time"),
                },
                "prompt": case.get("default_user_input"),
                "ground_truth": truth,
                "baseline": {
                    **baseline,
                    "hits": baseline_hits,
                    "decision": "stop" if baseline.get("service") else "continue",
                    "confidence": None,
                },
                "rca": {
                    **rca_prediction,
                    "hits": rca_hits,
                    "report_path": summary.get("artifacts", {}).get("report_path"),
                    "think_log_path": summary.get("artifacts", {}).get("think_log_path"),
                },
            }
        )

    return {
        "benchmark_config": {
            "mode": "cases",
            "benchmark_dir": benchmark_dir,
            "sample_count": sample_count,
            "seed": seed,
            "discovered_cases": len(cases),
            "evaluated_cases": len(samples),
        },
        "aggregate": {
            "baseline": _aggregate_metrics(samples, "baseline"),
            "rca": _aggregate_metrics(samples, "rca"),
        },
        "samples": samples,
    }


def run_benchmark(
    csv_path: str,
    benchmark_dir: str,
    sample_count: int,
    window_size: int,
    seed: int,
    mode: str = "auto",
) -> dict[str, Any]:
    resolved_mode = mode
    if resolved_mode == "auto":
        resolved_mode = "cases" if has_benchmark_case_layout(benchmark_dir) else "csv"
    if resolved_mode == "cases":
        return run_case_benchmark(benchmark_dir=benchmark_dir, sample_count=sample_count, seed=seed)
    return run_window_benchmark(csv_path=csv_path, sample_count=sample_count, window_size=window_size, seed=seed)


def _print_console_summary(results: dict[str, Any]) -> None:
    config = results.get("benchmark_config", {})
    aggregate = results.get("aggregate", {})
    print("=== RCA Benchmark Summary ===")
    print(f"mode: {config.get('mode')}")
    if config.get("csv_path"):
        print(f"csv_path: {config.get('csv_path')}")
    if config.get("benchmark_dir"):
        print(f"benchmark_dir: {config.get('benchmark_dir')}")
    print(f"sample_count: {config.get('sample_count')}")
    if config.get("window_size") is not None:
        print(f"window_size: {config.get('window_size')}")
    print(f"seed: {config.get('seed')}")
    if config.get("candidate_windows") is not None:
        print(f"candidate_windows: {config.get('candidate_windows')}")
    if config.get("evaluated_windows") is not None:
        print(f"evaluated_windows: {config.get('evaluated_windows')}")
    if config.get("discovered_cases") is not None:
        print(f"discovered_cases: {config.get('discovered_cases')}")
    if config.get("evaluated_cases") is not None:
        print(f"evaluated_cases: {config.get('evaluated_cases')}")
    print()
    print("baseline:")
    print(_json_dumps(aggregate.get("baseline", {})))
    print()
    print("rca:")
    print(_json_dumps(aggregate.get("rca", {})))


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    results = run_benchmark(
        csv_path=args.csv,
        benchmark_dir=args.benchmark_dir,
        sample_count=max(1, args.sample_count),
        window_size=max(5, args.window_size),
        seed=args.seed,
        mode=args.mode,
    )
    output_path = Path(args.output)
    output_path.write_text(_json_dumps(results), encoding="utf-8")
    _print_console_summary(results)
    print()
    print(f"results_path: {output_path}")


if __name__ == "__main__":
    main()
