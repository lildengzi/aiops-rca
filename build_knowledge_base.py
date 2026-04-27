from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import pandas as pd

from config import BENCHMARK_DIR
from knowledge_base.schemas import KnowledgeDocument
from knowledge_base.store import KnowledgeBaseStore
from utils.anomaly_detection import detect_anomaly_zscore
from utils.data_loader import CSVDataLoader
from utils.service_parser import discover_service_metrics


DEFAULT_SOLUTIONS = {
    "cpu": "检查异常流量、热点请求和服务实例 CPU 饱和情况，必要时扩容或回滚最近变更。",
    "mem": "检查对象堆积、缓存膨胀和内存泄漏迹象，必要时重启并分析内存占用。",
    "load": "检查突发请求、上游重试和依赖抖动，评估限流与扩容方案。",
    "latency": "检查慢调用、下游依赖延迟和线程池阻塞，必要时做链路回放分析。",
    "error": "检查错误码分布、发布变更和依赖可用性，必要时回滚并修复异常路径。",
}


def build_documents_from_csv(csv_path: str | Path) -> list[KnowledgeDocument]:
    loader = CSVDataLoader(csv_path)
    frame = loader.load()
    service_metrics = discover_service_metrics(frame.columns.tolist())
    timestamp_column = loader.timestamp_column
    documents: list[KnowledgeDocument] = []

    semantic_columns = {
        column.lower(): column
        for column in frame.columns
    }

    for service, metrics in service_metrics.items():
        semantic_service_rows = _lookup_semantic_rows(frame, semantic_columns, service)
        for metric in metrics:
            metric_column = f"{service}_{metric}"
            if metric_column not in frame.columns:
                continue
            series = frame[metric_column]
            anomaly_indices = detect_anomaly_zscore(series, threshold=2.5)
            if not anomaly_indices:
                continue
            anomaly_frame = frame.iloc[anomaly_indices]
            peak_value = float(pd.to_numeric(series, errors="coerce").max())
            window_start = int(anomaly_frame[timestamp_column].min())
            window_end = int(anomaly_frame[timestamp_column].max())
            fault_type = normalize_fault_type(metric)
            root_cause = infer_root_cause(service, metric, semantic_service_rows)
            solution = infer_solution(metric, semantic_service_rows)
            candidate_role = infer_candidate_role(metric)
            symptom_summary = build_symptom_summary(service, metric, peak_value, window_start, window_end)
            title = f"{service} {fault_type} anomaly"
            content = build_document_content(
                service=service,
                metric=metric,
                fault_type=fault_type,
                root_cause=root_cause,
                solution=solution,
                peak_value=peak_value,
                window_start=window_start,
                window_end=window_end,
                symptom_summary=symptom_summary,
                candidate_role=candidate_role,
            )
            documents.append(
                KnowledgeDocument(
                    title=title,
                    content=content,
                    service=service,
                    fault_type=fault_type,
                    root_cause=root_cause,
                    solution=solution,
                    source=str(csv_path),
                    tags=[service, metric, fault_type, candidate_role],
                    metadata={
                        "metric": metric,
                        "peak_value": peak_value,
                        "window_start": window_start,
                        "window_end": window_end,
                        "anomaly_count": len(anomaly_indices),
                        "symptom_summary": symptom_summary,
                        "evidence_type": "metric_pattern",
                        "candidate_role": candidate_role,
                    },
                )
            )

    if not documents:
        documents.append(
            KnowledgeDocument(
                title="dataset overview",
                content="未检测到显著异常，保留数据集概要知识条目供后续人工补充。",
                source=str(csv_path),
                tags=["overview"],
                metadata={"rows": int(len(frame))},
            )
        )
    return documents


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


def build_document_content(
    *,
    service: str,
    metric: str,
    fault_type: str,
    root_cause: str,
    solution: str,
    peak_value: float,
    window_start: int,
    window_end: int,
    symptom_summary: str,
    candidate_role: str,
) -> str:
    return (
        f"故障案例：服务 {service} 出现 {fault_type} 异常。\n"
        f"症状摘要：{symptom_summary}\n"
        f"关键指标：{metric}，峰值 {peak_value:.6f}，异常窗口 {window_start}~{window_end}。\n"
        f"候选角色：{candidate_role}。\n"
        f"历史推断根因：{root_cause}。\n"
        f"建议动作：{solution}"
    )


def build_symptom_summary(service: str, metric: str, peak_value: float, window_start: int, window_end: int) -> str:
    return (
        f"{service} 在 {window_start}~{window_end} 期间 {metric} 指标显著异常，"
        f"峰值达到 {peak_value:.6f}，疑似存在与当前时间窗重合的资源或依赖故障信号"
    )


def normalize_fault_type(metric: str) -> str:
    if metric == "mem":
        return "memory"
    return metric


def infer_root_cause(service: str, metric: str, semantic_rows: pd.DataFrame) -> str:
    semantic_root_cause = _first_non_empty(semantic_rows, ["root_cause", "error_type"])
    if semantic_root_cause:
        return semantic_root_cause
    if metric == "cpu":
        return f"{service} CPU saturation"
    if metric == "mem":
        return f"{service} memory pressure"
    if metric == "latency":
        return f"{service} request latency spike"
    if metric == "error":
        return f"{service} application error surge"
    if metric == "load":
        return f"{service} traffic load spike"
    return f"{service} anomaly"


def infer_solution(metric: str, semantic_rows: pd.DataFrame) -> str:
    semantic_solution = _first_non_empty(semantic_rows, ["solution"])
    if semantic_solution:
        return semantic_solution
    return DEFAULT_SOLUTIONS.get(metric, "结合服务指标与近期变更继续排查。")


def infer_candidate_role(metric: str) -> str:
    if metric in {"latency", "error"}:
        return "symptom_or_propagated"
    return "origin_candidate"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build FAISS knowledge base from RCA benchmark data")
    parser.add_argument(
        "--csv",
        default=str(BENCHMARK_DIR / "data_with_error.csv"),
        help="Path to the labeled or semi-structured benchmark CSV",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    documents = build_documents_from_csv(args.csv)
    store = KnowledgeBaseStore()
    store.save_documents(documents)
    result = store.rebuild_index(documents)
    print(
        {
            "document_count": result["document_count"],
            "dimension": result["dimension"],
            "index_path": result["index_path"],
            "docs_path": str(store.docs_path),
        }
    )


if __name__ == "__main__":
    main()
