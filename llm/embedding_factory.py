from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from config import EMBEDDING_BASE_URL, EMBEDDING_MODEL_NAME, EMBEDDING_PROVIDER, OPENAI_API_KEY

try:
    from langchain_openai import OpenAIEmbeddings
except ModuleNotFoundError:
    OpenAIEmbeddings = None


@dataclass
class EmbeddingAdapter:
    provider: str
    model_name: str
    enabled: bool
    reason: str
    client: Any = None


def build_embedding_adapter() -> EmbeddingAdapter:
    provider = EMBEDDING_PROVIDER.strip().lower()
    model_name = EMBEDDING_MODEL_NAME.strip()

    if provider in {"", "tfidf", "numpy", "local-fallback"}:
        return EmbeddingAdapter(
            provider=provider or "tfidf",
            model_name=model_name,
            enabled=False,
            reason="Embedding provider uses local fallback.",
        )

    if provider != "openai":
        return EmbeddingAdapter(
            provider=provider,
            model_name=model_name,
            enabled=False,
            reason=f"Unsupported embedding provider: {provider}",
        )

    if OpenAIEmbeddings is None:
        return EmbeddingAdapter(
            provider=provider,
            model_name=model_name,
            enabled=False,
            reason="langchain-openai is not installed.",
        )

    if not OPENAI_API_KEY:
        return EmbeddingAdapter(
            provider=provider,
            model_name=model_name,
            enabled=False,
            reason="OPENAI_API_KEY is missing.",
        )

    client = OpenAIEmbeddings(
        model=model_name or "text-embedding-3-small",
        api_key=OPENAI_API_KEY,
        base_url=EMBEDDING_BASE_URL or None,
    )
    return EmbeddingAdapter(
        provider=provider,
        model_name=model_name or "text-embedding-3-small",
        enabled=True,
        reason="",
        client=client,
    )
