from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import uuid4

from utils.incident_contract import normalize_fault_code, normalize_service_name


@dataclass
class KnowledgeDocument:
    title: str
    content: str
    service: str | None = None
    fault_type: str | None = None
    root_cause_service: str | None = None
    fault_code: str | None = None
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
        metadata = dict(payload.get("metadata", {}))
        service = normalize_service_name(
            payload.get("root_cause_service")
            or metadata.get("root_cause_service")
            or payload.get("service")
        )
        fault_type = payload.get("fault_type")
        if not fault_type and payload.get("service") and not service:
            fault_type = str(payload.get("service"))
        fault_code = normalize_fault_code(
            payload.get("fault_code")
            or metadata.get("fault_code")
            or fault_type
        )
        root_cause_service = normalize_service_name(
            payload.get("root_cause_service")
            or metadata.get("root_cause_service")
            or service
        )
        if root_cause_service:
            metadata.setdefault("root_cause_service", root_cause_service)
        if fault_code:
            metadata.setdefault("fault_code", fault_code)
        metadata.setdefault("contract_schema_version", "service_fault_v1")
        return cls(
            title=str(payload.get("title", "")),
            content=str(payload.get("content", "")),
            service=service,
            fault_type=fault_type,
            root_cause_service=root_cause_service,
            fault_code=fault_code,
            root_cause=payload.get("root_cause"),
            solution=payload.get("solution"),
            source=str(payload.get("source", "generated")),
            tags=list(payload.get("tags", [])),
            metadata=metadata,
            document_id=str(payload.get("document_id") or uuid4()),
        )
