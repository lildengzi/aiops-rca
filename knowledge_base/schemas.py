from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import uuid4


@dataclass
class KnowledgeDocument:
    title: str
    content: str
    service: str | None = None
    fault_type: str | None = None
    root_cause: str | None = None
    solution: str | None = None
    source: str = "generated"
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    document_id: str = field(default_factory=lambda: str(uuid4()))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "KnowledgeDocument":
        return cls(
            title=str(payload.get("title", "")),
            content=str(payload.get("content", "")),
            service=payload.get("service"),
            fault_type=payload.get("fault_type"),
            root_cause=payload.get("root_cause"),
            solution=payload.get("solution"),
            source=str(payload.get("source", "generated")),
            tags=list(payload.get("tags", [])),
            metadata=dict(payload.get("metadata", {})),
            document_id=str(payload.get("document_id") or uuid4()),
        )
