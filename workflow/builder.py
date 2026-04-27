from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langgraph.graph import END, START, StateGraph

from agents.analyst_agent import AnalystAgent
from agents.log_agent import LogAgent
from agents.master_agent import MasterAgent
from agents.metric_agent import MetricAgent
from agents.reporter_agent import ReporterAgent
from agents.trace_agent import TraceAgent
from knowledge_base.retriever import KnowledgeRetriever
from llm.embedding_factory import EmbeddingAdapter
from llm.model_factory import LLMAdapter
from tools.log_tools import LogToolbox
from tools.metric_tools import MetricToolbox
from tools.trace_tools import TraceToolbox
from utils.csv_processor import build_dataset_summary
from utils.data_loader import CSVDataLoader
from workflow.graph_state import GraphState
from workflow.nodes.aggregate_node import aggregate_graph_node
from workflow.nodes.analyst_node import analyst_graph_node
from workflow.nodes.detect_fault_node import detect_fault_graph_node
from workflow.nodes.log_node import log_graph_node
from workflow.nodes.master_node import master_graph_node
from workflow.nodes.metric_node import metric_graph_node
from workflow.nodes.reporter_node import reporter_graph_node
from workflow.nodes.retrieve_knowledge_node import retrieve_knowledge_graph_node
from workflow.nodes.trace_node import trace_graph_node
from workflow.state import RCAState
from workflow.utils import record_node_event


@dataclass
class WorkflowRuntime:
    loader: CSVDataLoader
    metric_toolbox: MetricToolbox
    log_toolbox: LogToolbox
    trace_toolbox: TraceToolbox
    knowledge_retriever: KnowledgeRetriever | None
    llm_adapter: LLMAdapter | None
    embedding_adapter: EmbeddingAdapter | None
    master_agent: MasterAgent
    metric_agent: MetricAgent
    log_agent: LogAgent
    trace_agent: TraceAgent
    analyst_agent: AnalystAgent
    reporter_agent: ReporterAgent


class WorkflowBuilder:
    def __init__(self, runtime: WorkflowRuntime):
        self.runtime = runtime
        self.graph = self._build_graph()

    def initialize_state(
        self,
        user_input: str,
        start: int | None = None,
        end: int | None = None,
    ) -> RCAState:
        state = RCAState(
            user_input=user_input,
            csv_path=str(self.runtime.loader.csv_path),
            start=start,
            end=end,
            topology_details=self.runtime.trace_toolbox.topology_toolbox.get_topology_details(),
        )
        dataset_summary = build_dataset_summary(self.runtime.loader, start=start, end=end)
        state.dataset_summary = dataset_summary
        record_node_event(state, "dataset_summary", dataset_summary)
        return state

    def run(self, state: RCAState) -> RCAState:
        final_graph_state = self.graph.invoke(state.to_graph_state())
        return RCAState.from_graph_state(final_graph_state)

    def _build_graph(self):
        graph = StateGraph(GraphState)
        graph.add_node("detect_fault", detect_fault_graph_node)
        graph.add_node("retrieve_knowledge", lambda graph_state: retrieve_knowledge_graph_node(graph_state, self.runtime))
        graph.add_node("master", lambda graph_state: master_graph_node(graph_state, self.runtime.master_agent))
        graph.add_node("metric", lambda graph_state: metric_graph_node(graph_state, self.runtime.metric_agent))
        graph.add_node("log", lambda graph_state: log_graph_node(graph_state, self.runtime.log_agent))
        graph.add_node("trace", lambda graph_state: trace_graph_node(graph_state, self.runtime.trace_agent))
        graph.add_node("aggregate", aggregate_graph_node)
        graph.add_node("analyst", lambda graph_state: analyst_graph_node(graph_state, self.runtime.analyst_agent))
        graph.add_node("reporter", lambda graph_state: reporter_graph_node(graph_state, self.runtime.reporter_agent))

        graph.add_edge(START, "detect_fault")
        graph.add_edge("detect_fault", "retrieve_knowledge")
        graph.add_edge("retrieve_knowledge", "master")
        graph.add_edge("master", "metric")
        graph.add_edge("master", "log")
        graph.add_edge("master", "trace")
        graph.add_edge("metric", "aggregate")
        graph.add_edge("log", "aggregate")
        graph.add_edge("trace", "aggregate")
        graph.add_edge("aggregate", "analyst")
        graph.add_conditional_edges(
            "analyst",
            self._route_after_analyst,
            {
                "master": "master",
                "reporter": "reporter",
            },
        )
        graph.add_edge("reporter", END)
        return graph.compile()

    @staticmethod
    def _route_after_analyst(graph_state: GraphState) -> str:
        final_result = graph_state.get("final_result", {})
        iteration = graph_state.get("iteration", 0)
        max_iter = graph_state.get("max_iter", 0)
        if final_result.get("decision") == "stop" or iteration >= max_iter:
            return "reporter"
        return "master"
