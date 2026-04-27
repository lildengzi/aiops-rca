from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from workflow.state import RCAState


def append_think_log(state: RCAState, agent_name: str, payload: dict[str, Any]) -> None:
    path = state.ensure_think_log_path()
    lines = [
        f"## {datetime.now().isoformat()} [{agent_name}]",
        "```json",
        json.dumps(payload, ensure_ascii=False, indent=2),
        "```",
        "",
    ]
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines))


def record_node_event(state: RCAState, node_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    entry = {
        "timestamp": datetime.now().isoformat(),
        "node": node_name,
        "iteration": state.iteration,
        "payload": payload,
    }
    state.node_history.append(entry)
    append_think_log(state, node_name, payload)
    return payload
