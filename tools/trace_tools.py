from __future__ import annotations

from typing import Any

from tools.log_tools import LogToolbox
from tools.metric_tools import MetricToolbox
from tools.topology_tools import TopologyToolbox
from utils.data_loader import CSVDataLoader


class TraceToolbox:
    def __init__(self, loader: CSVDataLoader):
        self.loader = loader
        self.metric_toolbox = MetricToolbox(loader)
        self.log_toolbox = LogToolbox(loader)
        self.topology_toolbox = TopologyToolbox(loader)

    def query_service_traces(
        self,
        service: str,
        start: int | None = None,
        end: int | None = None,
    ) -> list[dict[str, Any]]:
        topology = self.topology_toolbox.get_full_topology()
        topology_details = self.topology_toolbox.get_topology_details()
        reverse_topology = self.topology_toolbox.reverse_topology()
        try:
            latency_summary = self.metric_toolbox.summarize_metric(service, "latency", start=start, end=end)
        except KeyError:
            latency_summary = {
                "service": service,
                "metric": "latency",
                "stats": {},
                "is_anomalous": False,
                "anomaly_indices": [],
                "anomaly_timestamps": [],
                "peak_value": None,
            }
        log_summary = self.log_toolbox.summarize_logs(service, start=start, end=end)
        upstream = reverse_topology.get(service, [])
        downstream = topology.get(service, [])
        service_type = topology_details.get(service, {}).get("type", "application")

        traces: list[dict[str, Any]] = []
        root_candidates = upstream or [service]

        for source in root_candidates:
            path = [source] if source == service else [source, service]
            for dependency in downstream[:2]:
                if dependency not in path:
                    path.append(dependency)
            traces.append(
                {
                    "entry_service": path[0],
                    "suspect_service": service,
                    "path": path,
                    "observed_latency": latency_summary.get("peak_value"),
                    "log_count": log_summary.get("log_count"),
                    "service_type": service_type,
                    "upstream_services": upstream,
                    "downstream_services": downstream,
                }
            )

        return traces[:5]

    def summarize_traces(
        self,
        service: str,
        start: int | None = None,
        end: int | None = None,
    ) -> dict[str, Any]:
        traces = self.query_service_traces(service=service, start=start, end=end)
        propagation_paths = [" -> ".join(item["path"]) for item in traces]
        return {
            "service": service,
            "trace_count": len(traces),
            "propagation_paths": propagation_paths,
            "sample_traces": traces,
        }
