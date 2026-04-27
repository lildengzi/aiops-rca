from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from config import (
    ENABLE_LLM_REASONING,
    LLM_PROVIDER,
    MODEL_NAME,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_MAX_RETRIES,
    OPENAI_TIMEOUT,
)

try:
    from langchain_core.messages import BaseMessage
except ModuleNotFoundError:
    BaseMessage = Any

try:
    from langchain_openai import ChatOpenAI
except ModuleNotFoundError:
    ChatOpenAI = None


@dataclass
class LLMAdapter:
    provider: str
    model_name: str
    enabled: bool
    reason: str
    client: Any = None

    def invoke_messages(self, messages: list[tuple[str, str] | BaseMessage]) -> dict[str, Any]:
        if not self.enabled or self.client is None:
            raise RuntimeError(self.reason or "LLM adapter is unavailable.")
        response = self.client.invoke(messages)
        content = getattr(response, "content", response)
        if isinstance(content, list):
            content = "\n".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in content
            )
        if not isinstance(content, str):
            content = str(content)
        return {"raw_text": content}

    def invoke_json(self, system_prompt: str, user_payload: dict[str, Any]) -> dict[str, Any]:
        message = json.dumps(user_payload, ensure_ascii=False, indent=2)
        return self.invoke_messages(
            [
                ("system", system_prompt),
                ("human", message),
            ]
        )


def build_llm_adapter() -> LLMAdapter:
    provider = LLM_PROVIDER.strip().lower()
    model_name = MODEL_NAME.strip() or "offline-rule-engine"

    if not ENABLE_LLM_REASONING:
        return LLMAdapter(
            provider=provider,
            model_name=model_name,
            enabled=False,
            reason="ENABLE_LLM_REASONING is disabled.",
        )

    if provider in {"", "offline", "rule", "rule-engine"}:
        return LLMAdapter(
            provider=provider or "offline",
            model_name=model_name,
            enabled=False,
            reason="LLM provider is set to offline fallback.",
        )

    if provider != "openai":
        return LLMAdapter(
            provider=provider,
            model_name=model_name,
            enabled=False,
            reason=f"Unsupported LLM provider: {provider}",
        )

    if ChatOpenAI is None:
        return LLMAdapter(
            provider=provider,
            model_name=model_name,
            enabled=False,
            reason="langchain-openai is not installed.",
        )

    if not OPENAI_API_KEY:
        return LLMAdapter(
            provider=provider,
            model_name=model_name,
            enabled=False,
            reason="OPENAI_API_KEY is missing.",
        )

    client = ChatOpenAI(
        model=model_name,
        api_key=OPENAI_API_KEY,
        base_url=OPENAI_BASE_URL or None,
        timeout=OPENAI_TIMEOUT,
        max_retries=OPENAI_MAX_RETRIES,
        temperature=0,
    )
    return LLMAdapter(
        provider=provider,
        model_name=model_name,
        enabled=True,
        reason="",
        client=client,
    )
