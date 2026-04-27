from __future__ import annotations

from typing import Any

from agents.prompts import trace_prompt
from tools.trace_tools import TraceToolbox
from workflow.state import RCAState


class TraceAgent:
    name = "trace"

    def __init__(self, trace_toolbox: TraceToolbox):
        self.trace_toolbox = trace_toolbox

    def build_prompt(self, state: RCAState) -> dict[str, Any]:
        return trace_prompt(
            state.plan,
            {"start": state.start, "end": state.end},
        )

    def run(self, state: RCAState) -> dict[str, Any]:
        prompt = self.build_prompt(state)
        services = []
        seen = set()
        for action in state.plan.get("actions", []):
            if action.get("tool") != "trace":
                continue
            service = action["service"]
            if service not in seen:
                seen.add(service)
                services.append(service)
        return {
            "prompt": prompt,
            "traces": [
                self.trace_toolbox.summarize_traces(service=service, start=state.start, end=state.end)
                for service in services
            ],
        }
