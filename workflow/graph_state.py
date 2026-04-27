from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict


def merge_evidence(
    left: dict[str, Any] | None,
    right: dict[str, Any] | None,
) -> dict[str, Any]:
    merged = dict(left or {})
    merged.update(right or {})
    return merged


def keep_existing_or_latest(
    left: str | None,
    right: str | None,
) -> str | None:
    return right or left


class GraphState(TypedDict, total=False):
    user_input: str
    csv_path: str
    start: int | None
    end: int | None
    iteration: int
    max_iter: int
    dataset_summary: dict[str, Any]
    detected_fault: dict[str, Any]
    plan: dict[str, Any]
    evidence: Annotated[dict[str, Any], merge_evidence]
    decisions: list[dict[str, Any]]
    final_result: dict[str, Any]
    report_path: str | None
    report_header: dict[str, Any]
    think_log_path: Annotated[str | None, keep_existing_or_latest]
    knowledge_hits: list[dict[str, Any]]
    llm_enabled: bool
    llm_reason: str
    node_history: Annotated[list[dict[str, Any]], add]
    topology_details: dict[str, dict[str, Any]]
