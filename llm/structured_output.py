from __future__ import annotations

import json
import re
from typing import Any


JSON_BLOCK_PATTERN = re.compile(r"```json\s*(\{[\s\S]*?\})\s*```", re.IGNORECASE)


def extract_json_object(text: str) -> dict[str, Any]:
    candidate = text.strip()
    block_match = JSON_BLOCK_PATTERN.search(candidate)
    if block_match:
        candidate = block_match.group(1).strip()

    if candidate.startswith("{") and candidate.endswith("}"):
        return json.loads(candidate)

    start = candidate.find("{")
    end = candidate.rfind("}")
    if start >= 0 and end > start:
        return json.loads(candidate[start : end + 1])

    raise ValueError("No JSON object found in LLM response.")
