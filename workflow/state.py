from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from config import MAX_ITERATIONS, THINK_LOG_DIR
from workflow.graph_state import GraphState


@dataclass
class RCAState:
    user_input: str
    csv_path: str
    start: int | None = None
    end: int | None = None
    iteration: int = 0
    max_iter: int = MAX_ITERATIONS
    dataset_summary: dict[str, Any] = field(default_factory=dict)
    detected_fault: dict[str, Any] = field(default_factory=dict)
    plan: dict[str, Any] = field(default_factory=dict)
    evidence: dict[str, Any] = field(default_factory=dict)
    decisions: list[dict[str, Any]] = field(default_factory=list)
    final_result: dict[str, Any] = field(default_factory=dict)
    report_path: str | None = None
    report_header: dict[str, Any] = field(default_factory=dict)
    think_log_path: str | None = None
    knowledge_hits: list[dict[str, Any]] = field(default_factory=list)
    llm_enabled: bool = False
    llm_reason: str = ""
    node_history: list[dict[str, Any]] = field(default_factory=list)
    topology_details: dict[str, dict[str, Any]] = field(default_factory=dict)

    def ensure_think_log_path(self) -> Path:
        if self.think_log_path:
            return Path(self.think_log_path)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = Path(self.csv_path).stem.replace(" ", "_")
        path = THINK_LOG_DIR / f"think_log_{safe_name}_{timestamp}.md"
        self.think_log_path = str(path)
        return path

    def to_graph_state(self) -> GraphState:
        return GraphState(**asdict(self))

    @classmethod
    def from_graph_state(cls, graph_state: GraphState) -> "RCAState":
        return cls(**graph_state)
