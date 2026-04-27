from __future__ import annotations

from typing import Any

from agents.prompts import metric_prompt
from tools.metric_tools import MetricToolbox
from workflow.state import RCAState


class MetricAgent:
    name = "metric"

    def __init__(self, metric_toolbox: MetricToolbox):
        self.metric_toolbox = metric_toolbox

    def build_prompt(self, state: RCAState) -> dict[str, Any]:
        return metric_prompt(
            state.plan,
            {"start": state.start, "end": state.end},
        )

    def run(self, state: RCAState) -> dict[str, Any]:
        prompt = self.build_prompt(state)
        results: list[dict[str, Any]] = []
        for action in state.plan.get("actions", []):
            if action.get("tool") != "metric":
                continue
            results.append(
                self.metric_toolbox.summarize_metric(
                    service=action["service"],
                    metric=action["metric"],
                    start=state.start,
                    end=state.end,
                )
            )
        return {"prompt": prompt, "metrics": results}
