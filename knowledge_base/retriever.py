from __future__ import annotations

from typing import Any

from config import KB_TOP_K
from knowledge_base.store import KnowledgeBaseStore


class KnowledgeRetriever:
    def __init__(self, store: KnowledgeBaseStore | None = None):
        self.store = store or KnowledgeBaseStore()

    def retrieve_knowledge(self, query: str, k: int = KB_TOP_K) -> list[dict[str, Any]]:
        documents = self.store.list_documents()
        return [
            self._build_hit(documents[int(index_value)], score, retrieval_stage="direct")
            for index_value, score in self.store.search(query, k)
        ]

    def retrieve_for_context(self, query_payload: dict[str, Any], k: int = KB_TOP_K) -> list[dict[str, Any]]:
        documents = self.store.list_documents()
        scored_hits: dict[str, dict[str, Any]] = {}

        global_query = str(query_payload.get("global_query", "")).strip()
        if global_query:
            for index_value, score in self.store.search(global_query, k):
                document = documents[int(index_value)]
                scored_hits[document.document_id] = self._build_hit(document, score, retrieval_stage="global")

        for service_query in query_payload.get("service_queries", []):
            if not isinstance(service_query, dict):
                continue
            service = str(service_query.get("service", "")).strip()
            query = str(service_query.get("query", "")).strip()
            if not service or not query:
                continue
            for index_value, score in self.store.search(query, max(k, 2)):
                document = documents[int(index_value)]
                hit = self._build_hit(document, score, retrieval_stage="service-observability")
                hit["matched_service"] = service
                self._merge_hit(scored_hits, hit)

        ranked_hits = [self._rerank_hit(hit, query_payload) for hit in scored_hits.values()]
        ranked_hits.sort(key=lambda item: item["score"], reverse=True)
        return ranked_hits[:k]

    def _build_hit(self, document: Any, score: float, retrieval_stage: str) -> dict[str, Any]:
        metadata = document.metadata or {}
        evidence_pillars = self._metadata_list(metadata, "evidence_pillars")
        return {
            "document_id": document.document_id,
            "title": document.title,
            "service": document.service,
            "fault_type": document.fault_type,
            "root_cause": document.root_cause,
            "solution": document.solution,
            "score": round(float(score), 4),
            "content": document.content,
            "tags": document.tags,
            "metadata": document.metadata,
            "match_reasons": [],
            "alignment": "neutral",
            "alignment_reasons": [],
            "evidence_pillars": evidence_pillars,
            "matched_service": document.service,
            "matched_fault_type": document.fault_type,
            "retrieval_stage": retrieval_stage,
        }

    def _merge_hit(self, scored_hits: dict[str, dict[str, Any]], new_hit: dict[str, Any]) -> None:
        existing = scored_hits.get(new_hit["document_id"])
        if not existing:
            scored_hits[new_hit["document_id"]] = new_hit
            return
        existing["score"] = round(max(float(existing.get("score", 0.0)), float(new_hit.get("score", 0.0))), 4)
        stages = {str(existing.get("retrieval_stage", "")), str(new_hit.get("retrieval_stage", ""))}
        existing["retrieval_stage"] = "+".join(sorted(stage for stage in stages if stage))
        if not existing.get("matched_service") and new_hit.get("matched_service"):
            existing["matched_service"] = new_hit["matched_service"]

    def _rerank_hit(self, hit: dict[str, Any], query_payload: dict[str, Any]) -> dict[str, Any]:
        score = float(hit.get("score", 0.0))
        match_reasons: list[str] = []
        service = str(hit.get("service") or "").strip()
        fault_type = str(hit.get("fault_type") or "").strip()
        tags = {str(item).strip() for item in hit.get("tags", []) if str(item).strip()}
        metadata = hit.get("metadata") or {}
        metric = str(metadata.get("metric") or "").strip()
        metric_names = self._evidence_values(metadata, "metric_evidence", ["metric", "metric_name"])
        role = str(metadata.get("candidate_role") or metadata.get("chain_role") or "").strip()
        related_services = self._metadata_set(metadata, "related_services")
        downstreams = self._metadata_set(metadata, "downstreams")
        upstreams = self._metadata_set(metadata, "upstreams")
        evidence_pillars = set(self._metadata_list(metadata, "evidence_pillars"))

        candidate_services = self._payload_set(query_payload, "candidate_services")
        fault_types = self._payload_set(query_payload, "fault_types")
        candidate_metrics = self._payload_set(query_payload, "candidate_metrics")
        graph_neighbors = self._graph_neighbors(query_payload.get("service_graph") or {}, candidate_services)
        alignment_reasons: list[str] = []
        service_match = bool(service and service in candidate_services)
        service_scope_match = bool(related_services.intersection(candidate_services) or tags.intersection(candidate_services))
        fault_type_match = bool(fault_type and fault_type in fault_types)
        metric_match = bool(
            (metric and metric in candidate_metrics)
            or metric_names.intersection(candidate_metrics)
            or any(self._loose_metric_match(item, candidate_metrics) for item in metric_names)
        )

        if service_match:
            score += 0.18
            match_reasons.append(f"service match: {service}")
            alignment_reasons.append(f"historical service matches current candidate: {service}")
        if related_services.intersection(candidate_services):
            score += 0.12
            match_reasons.append("same service incident scope")
            alignment_reasons.append("current candidates overlap the historical incident service scope")
        if service and service in graph_neighbors:
            score += 0.08
            match_reasons.append(f"topology neighbor: {service}")
            alignment_reasons.append("historical service is a topology neighbor of a current candidate")
        if downstreams.intersection(candidate_services) or upstreams.intersection(candidate_services):
            score += 0.08
            match_reasons.append("upstream/downstream overlap")
            alignment_reasons.append("current candidates overlap historical upstream/downstream context")
        if fault_type_match:
            score += 0.08
            match_reasons.append(f"fault type match: {fault_type}")
            alignment_reasons.append(f"fault type matches: {fault_type}")
        if metric_match:
            score += 0.08
            match_reasons.append("metric evidence match")
            alignment_reasons.append("metric evidence overlaps current metric signals")
        if role in {"origin", "origin_candidate", "root_service"}:
            score += 0.04
            match_reasons.append("historical role: root candidate")
        if tags.intersection(candidate_services):
            score += 0.06
            match_reasons.append("tag matches candidate service")
        if tags.intersection(fault_types):
            score += 0.05
            match_reasons.append("tag matches fault type")
        if metric_match and not (service_match or service_scope_match):
            score = min(score, 0.42)
            match_reasons.append("metric-only hit capped because service does not match")
            alignment_reasons.append("metric overlaps, but historical service does not match current candidate services")
        if service and candidate_services and not service_match and service not in graph_neighbors and not related_services.intersection(candidate_services):
            if fault_type_match or metric_match:
                score = min(score, 0.55)
                alignment_reasons.append("historical evidence is only partially aligned because the service differs")
        if not match_reasons:
            match_reasons.append("semantic similarity")

        hit["score"] = round(score, 4)
        hit["match_reasons"] = match_reasons
        hit["matched_fault_type"] = fault_type or None
        hit["evidence_pillars"] = sorted(evidence_pillars)
        hit["alignment"], hit["alignment_reasons"] = self._alignment(
            service_match=service_match,
            service_scope_match=service_scope_match,
            fault_type_match=fault_type_match,
            metric_match=metric_match,
            candidate_services=bool(candidate_services),
            reasons=alignment_reasons,
        )
        return hit

    @staticmethod
    def _payload_set(payload: dict[str, Any], key: str) -> set[str]:
        value = payload.get(key, [])
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, list):
            return set()
        return {str(item).strip() for item in value if str(item).strip()}

    @staticmethod
    def _metadata_set(metadata: dict[str, Any], key: str) -> set[str]:
        value = metadata.get(key, [])
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, list):
            return set()
        return {str(item).strip() for item in value if str(item).strip()}

    @staticmethod
    def _metadata_list(metadata: dict[str, Any], key: str) -> list[str]:
        value = metadata.get(key, [])
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, list):
            return []
        return sorted({str(item).strip() for item in value if str(item).strip()})

    @staticmethod
    def _evidence_values(metadata: dict[str, Any], key: str, fields: list[str]) -> set[str]:
        values: set[str] = set()
        items = metadata.get(key, [])
        if not isinstance(items, list):
            return values
        for item in items:
            if not isinstance(item, dict):
                continue
            for field in fields:
                value = str(item.get(field) or "").strip()
                if value:
                    values.add(value)
        return values

    @staticmethod
    def _loose_metric_match(metric: str, candidate_metrics: set[str]) -> bool:
        lowered = metric.lower()
        for candidate in candidate_metrics:
            candidate_lower = candidate.lower()
            if candidate_lower and (candidate_lower in lowered or lowered in candidate_lower):
                return True
        return False

    @staticmethod
    def _alignment(
        *,
        service_match: bool,
        service_scope_match: bool,
        fault_type_match: bool,
        metric_match: bool,
        candidate_services: bool,
        reasons: list[str],
    ) -> tuple[str, list[str]]:
        if service_match and (fault_type_match or metric_match or service_scope_match):
            return "support", reasons or ["historical service-level case supports the current candidate"]
        if service_scope_match and (fault_type_match or metric_match):
            return "support", reasons or ["historical service scope supports the current candidate"]
        if candidate_services and metric_match and not (service_match or service_scope_match):
            return "conflict", reasons or ["metric evidence overlaps but the service differs"]
        if candidate_services and fault_type_match and not (service_match or service_scope_match):
            return "neutral", reasons or ["fault type matches, but service evidence is not aligned"]
        return "neutral", reasons or ["retrieved as auxiliary historical context"]

    @staticmethod
    def _graph_neighbors(service_graph: dict[str, Any], candidate_services: set[str]) -> set[str]:
        neighbors: set[str] = set()
        for candidate in candidate_services:
            details = service_graph.get(candidate, {})
            neighbors.update(str(item).strip() for item in details.get("upstreams", []) if str(item).strip())
            neighbors.update(str(item).strip() for item in details.get("downstreams", []) if str(item).strip())
        return neighbors

    def has_index(self) -> bool:
        return self.store.mapping_file.exists() and self.store.vocab_file.exists() and (
            self.store.index_file.exists() or self.store.matrix_file.exists()
        )
