from __future__ import annotations

from agents.analyst_agent import AnalystAgent
from agents.log_agent import LogAgent
from agents.master_agent import MasterAgent
from agents.metric_agent import MetricAgent
from agents.reporter_agent import ReporterAgent
from agents.trace_agent import TraceAgent
from knowledge_base.retriever import KnowledgeRetriever
from llm.embedding_factory import build_embedding_adapter
from llm.model_factory import build_llm_adapter
from tools.log_tools import LogToolbox
from tools.metric_tools import MetricToolbox
from tools.topology_tools import TopologyToolbox
from tools.trace_tools import TraceToolbox
from utils.data_loader import CSVDataLoader
from workflow.builder import WorkflowBuilder, WorkflowRuntime
from workflow.state import RCAState


class RCAOrchestrator:
    def __init__(self, csv_path: str):
        self.loader = CSVDataLoader(csv_path)
        self.metric_toolbox = MetricToolbox(self.loader)
        self.log_toolbox = LogToolbox(self.loader)
        self.trace_toolbox = TraceToolbox(self.loader)
        self.topology_toolbox = TopologyToolbox(self.loader)
        self.knowledge_retriever = KnowledgeRetriever()
        self.llm_adapter = build_llm_adapter()
        self.embedding_adapter = build_embedding_adapter()
        self.master_agent = MasterAgent(
            self.metric_toolbox,
            knowledge_retriever=self.knowledge_retriever,
            llm_adapter=self.llm_adapter,
        )
        self.metric_agent = MetricAgent(self.metric_toolbox)
        self.log_agent = LogAgent(self.log_toolbox)
        self.trace_agent = TraceAgent(self.trace_toolbox)
        self.analyst_agent = AnalystAgent(
            knowledge_retriever=self.knowledge_retriever,
            llm_adapter=self.llm_adapter,
        )
        self.reporter_agent = ReporterAgent()
        self.runtime = WorkflowRuntime(
            loader=self.loader,
            metric_toolbox=self.metric_toolbox,
            log_toolbox=self.log_toolbox,
            trace_toolbox=self.trace_toolbox,
            knowledge_retriever=self.knowledge_retriever,
            llm_adapter=self.llm_adapter,
            embedding_adapter=self.embedding_adapter,
            master_agent=self.master_agent,
            metric_agent=self.metric_agent,
            log_agent=self.log_agent,
            trace_agent=self.trace_agent,
            analyst_agent=self.analyst_agent,
            reporter_agent=self.reporter_agent,
        )
        self.builder = WorkflowBuilder(self.runtime)

    def run_investigation(
        self,
        user_input: str,
        start: int | None = None,
        end: int | None = None,
    ) -> RCAState:
        state = self.builder.initialize_state(user_input=user_input, start=start, end=end)
        return self.builder.run(state)
