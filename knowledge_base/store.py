from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from config import EMBEDDING_PROVIDER, FAISS_INDEX_PATH, KNOWLEDGE_DOCS_PATH
from knowledge_base.schemas import KnowledgeDocument

try:
    import faiss  # type: ignore
except ModuleNotFoundError:
    faiss = None


class KnowledgeBaseStore:
    def __init__(
        self,
        docs_path: str | Path = KNOWLEDGE_DOCS_PATH,
        index_path: str | Path = FAISS_INDEX_PATH,
        embedding_provider: str = EMBEDDING_PROVIDER,
    ):
        self.docs_path = Path(docs_path)
        self.index_path = Path(index_path)
        self.embedding_provider = embedding_provider
        self.docs_path.parent.mkdir(parents=True, exist_ok=True)
        self.index_path.mkdir(parents=True, exist_ok=True)
        self.index_file = self.index_path / "index.faiss"
        self.vocab_file = self.index_path / "vocab.json"
        self.mapping_file = self.index_path / "mapping.json"
        self.matrix_file = self.index_path / "matrix.npy"

    def list_documents(self) -> list[KnowledgeDocument]:
        if not self.docs_path.exists():
            return []
        payload = json.loads(self.docs_path.read_text(encoding="utf-8"))
        return [KnowledgeDocument.from_dict(item) for item in payload]

    def save_documents(self, documents: Iterable[KnowledgeDocument]) -> None:
        payload = [document.to_dict() for document in documents]
        self.docs_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def add_document(self, document: KnowledgeDocument) -> KnowledgeDocument:
        documents = self.list_documents()
        documents.append(document)
        self.save_documents(documents)
        return document

    def update_document(self, document_id: str, **updates: Any) -> KnowledgeDocument:
        documents = self.list_documents()
        for index, document in enumerate(documents):
            if document.document_id != document_id:
                continue
            payload = document.to_dict()
            payload.update(updates)
            updated = KnowledgeDocument.from_dict(payload)
            documents[index] = updated
            self.save_documents(documents)
            return updated
        raise KeyError(f"Knowledge document not found: {document_id}")

    def delete_document(self, document_id: str) -> None:
        documents = self.list_documents()
        filtered = [document for document in documents if document.document_id != document_id]
        if len(filtered) == len(documents):
            raise KeyError(f"Knowledge document not found: {document_id}")
        self.save_documents(filtered)

    def rebuild_index(self, documents: Iterable[KnowledgeDocument] | None = None) -> dict[str, Any]:
        docs = list(documents) if documents is not None else self.list_documents()
        if not docs:
            self._clear_index()
            return {"document_count": 0, "dimension": 0, "index_path": str(self.index_file)}

        texts = [self._document_text(document) for document in docs]
        vocabulary = self._build_vocabulary(texts)
        matrix = self._vectorize_texts(texts, vocabulary)
        backend = self._write_index(matrix)
        self.vocab_file.write_text(json.dumps(vocabulary, ensure_ascii=False, indent=2), encoding="utf-8")
        mapping = [document.to_dict() for document in docs]
        self.mapping_file.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
        return {
            "document_count": len(docs),
            "dimension": int(matrix.shape[1]),
            "index_path": str(self.index_file),
            "embedding_provider": self.embedding_provider,
            "index_backend": backend,
        }

    def load_index_bundle(self) -> tuple[Any, list[str], list[KnowledgeDocument], str]:
        if not self.vocab_file.exists() or not self.mapping_file.exists():
            raise FileNotFoundError("Knowledge index artifacts are missing. Run build_knowledge_base.py first.")
        if self.index_file.exists() and faiss is not None:
            index: Any = faiss.read_index(str(self.index_file))
            backend = "faiss"
        elif self.matrix_file.exists():
            index = np.load(self.matrix_file)
            backend = "numpy"
        else:
            raise FileNotFoundError("Knowledge index artifacts are missing. Run build_knowledge_base.py first.")
        vocabulary = json.loads(self.vocab_file.read_text(encoding="utf-8"))
        mapping_payload = json.loads(self.mapping_file.read_text(encoding="utf-8"))
        documents = [KnowledgeDocument.from_dict(item) for item in mapping_payload]
        return index, vocabulary, documents, backend

    def search(self, query: str, k: int) -> list[tuple[int, float]]:
        index, vocabulary, documents, backend = self.load_index_bundle()
        query_vector = self.vectorize_query(query, vocabulary)
        if query_vector.shape[1] == 0:
            return []
        limit = max(1, min(int(k), len(documents)))
        if backend == "faiss":
            scores, indices = index.search(query_vector, limit)
            return [
                (int(index_value), float(score))
                for score, index_value in zip(scores[0], indices[0])
                if int(index_value) >= 0
            ]
        scores = np.dot(index, query_vector[0])
        ranked_indices = np.argsort(scores)[::-1][:limit]
        return [(int(idx), float(scores[idx])) for idx in ranked_indices if scores[idx] > 0]

    def _write_index(self, matrix: np.ndarray) -> str:
        if faiss is not None:
            index = faiss.IndexFlatIP(matrix.shape[1])
            index.add(matrix)
            faiss.write_index(index, str(self.index_file))
            if self.matrix_file.exists():
                self.matrix_file.unlink()
            return "faiss"
        np.save(self.matrix_file, matrix)
        self.index_file.write_text("numpy-fallback", encoding="utf-8")
        return "numpy"

    def _clear_index(self) -> None:
        for path in [self.index_file, self.vocab_file, self.mapping_file, self.matrix_file]:
            if path.exists():
                path.unlink()

    def _document_text(self, document: KnowledgeDocument) -> str:
        return "\n".join(
            [
                document.title,
                document.content,
                document.service or "",
                document.fault_type or "",
                document.root_cause or "",
                document.solution or "",
                " ".join(document.tags),
            ]
        ).strip()

    def _build_vocabulary(self, texts: list[str]) -> list[str]:
        token_set: set[str] = set()
        for text in texts:
            token_set.update(self._tokenize(text))
        vocabulary = sorted(token_set)
        if not vocabulary:
            raise ValueError("No tokens available to build the knowledge index.")
        return vocabulary

    def _vectorize_texts(self, texts: list[str], vocabulary: list[str]) -> np.ndarray:
        matrix = np.zeros((len(texts), len(vocabulary)), dtype="float32")
        vocab_index = {token: idx for idx, token in enumerate(vocabulary)}
        for row_index, text in enumerate(texts):
            counts: dict[int, float] = {}
            for token in self._tokenize(text):
                token_index = vocab_index.get(token)
                if token_index is None:
                    continue
                counts[token_index] = counts.get(token_index, 0.0) + 1.0
            for token_index, value in counts.items():
                matrix[row_index, token_index] = value
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        matrix /= norms
        return matrix

    def vectorize_query(self, query: str, vocabulary: list[str]) -> np.ndarray:
        vector = np.zeros((1, len(vocabulary)), dtype="float32")
        vocab_index = {token: idx for idx, token in enumerate(vocabulary)}
        for token in self._tokenize(query):
            token_index = vocab_index.get(token)
            if token_index is None:
                continue
            vector[0, token_index] += 1.0
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector /= norm
        return vector

    def _tokenize(self, text: str) -> list[str]:
        normalized = []
        for char in text.lower():
            normalized.append(char if char.isalnum() else " ")
        return [token for token in "".join(normalized).split() if token]
