from __future__ import annotations

from typing import Any

from agents.prompts import log_prompt
from tools.log_tools import LogToolbox
from workflow.state import RCAState


class LogAgent:
    name = "log"

    def __init__(self, log_toolbox: LogToolbox):
        self.log_toolbox = log_toolbox

    def build_prompt(self, state: RCAState) -> dict[str, Any]:
        return log_prompt(
            state.plan,
            {"start": state.start, "end": state.end},
        )

    def run(self, state: RCAState) -> dict[str, Any]:
        prompt = self.build_prompt(state)
        services = []
        seen = set()
        for action in state.plan.get("actions", []):
            if action.get("tool") != "log":
                continue
            service = action["service"]
            if service not in seen:
                seen.add(service)
                services.append(service)
        return {
            "prompt": prompt,
            "logs": [
                self.log_toolbox.summarize_logs(service=service, start=state.start, end=state.end)
                for service in services
            ],
        }
