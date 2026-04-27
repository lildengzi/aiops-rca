from __future__ import annotations

from typing import Any

from config import KB_TOP_K
from knowledge_base.store import KnowledgeBaseStore


class KnowledgeRetriever:
    def __init__(self, store: KnowledgeBaseStore | None = None):
        self.store = store or KnowledgeBaseStore()

    def retrieve_knowledge(self, query: str, k: int = KB_TOP_K) -> list[dict[str, Any]]:
        index_hits = self.store.search(query, k)
        documents = self.store.list_documents()
        results: list[dict[str, Any]] = []
        for index_value, score in index_hits:
            document = documents[int(index_value)]
            results.append(
                {
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
                }
            )
        return results

    def retrieve_for_context(self, query_payload: dict[str, Any], k: int = KB_TOP_K) -> list[dict[str, Any]]:
        documents = self.store.list_documents()
        scored_hits: dict[str, dict[str, Any]] = {}

        global_query = str(query_payload.get("global_query", "")).strip()
        if global_query:
            for index_value, score in self.store.search(global_query, k):
                document = documents[int(index_value)]
                hit = self._build_hit(document, score, retrieval_stage="global")
                scored_hits[document.document_id] = hit

        for service_query in query_payload.get("service_queries", []):
            if not isinstance(service_query, dict):
                continue
            service = str(service_query.get("service", "")).strip()
            query = str(service_query.get("query", "")).strip()
            if not service or not query:
                continue
            for index_value, score in self.store.search(query, max(k, 2)):
                document = documents[int(index_value)]
                hit = self._build_hit(document, score, retrieval_stage="service-focused")
                hit["matched_service"] = service
                self._merge_hit(scored_hits, hit)

        ranked_hits = [
            self._rerank_hit(hit, query_payload)
            for hit in scored_hits.values()
        ]
        ranked_hits.sort(key=lambda item: item["score"], reverse=True)
        return ranked_hits[:k]

    def _build_hit(self, document: Any, score: float, retrieval_stage: str) -> dict[str, Any]:
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

        candidate_services = {str(item).strip() for item in query_payload.get("candidate_services", []) if str(item).strip()}
        fault_types = {str(item).strip() for item in query_payload.get("fault_types", []) if str(item).strip()}
        candidate_metrics = {str(item).strip() for item in query_payload.get("candidate_metrics", []) if str(item).strip()}

        if service and service in candidate_services:
            score += 0.18
            match_reasons.append(f"服务命中 {service}")
        if fault_type and fault_type in fault_types:
            score += 0.12
            match_reasons.append(f"故障类型命中 {fault_type}")
        if metric and metric in candidate_metrics:
            score += 0.1
            match_reasons.append(f"关键指标命中 {metric}")
        if tags.intersection(candidate_services):
            score += 0.06
            match_reasons.append("标签与候选服务对齐")
        if tags.intersection(fault_types):
            score += 0.05
            match_reasons.append("标签与故障类型对齐")
        if not match_reasons:
            match_reasons.append("来自基础语义相似度召回")

        hit["score"] = round(score, 4)
        hit["match_reasons"] = match_reasons
        hit["matched_fault_type"] = fault_type or None
        return hit

    def has_index(self) -> bool:
        return self.store.mapping_file.exists() and self.store.vocab_file.exists() and (
            self.store.index_file.exists() or self.store.matrix_file.exists()
        )
