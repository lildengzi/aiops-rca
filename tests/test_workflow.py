"""
测试工作流模块 - 重点测试基于知识库的工作流能否跑通
注意：不测试需要LLM的节点，只测试结构和无LLM依赖的部分
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from workflow.state import RCAState
from workflow.builder import build_rca_workflow, run_rca
from config import WORKFLOW_CONFIG


class TestWorkflowState:
    """测试工作流状态定义"""

    def test_state_structure(self):
        """测试状态结构"""
        state: RCAState = {
            "user_query": "测试查询",
            "fault_type": "cpu",
            "detected_fault_type": "",
            "full_analysis": True,
            "iteration": 0,
            "max_iterations": 5,
            "should_stop": False,
            "parallel_degree": 3,
            "master_plan": "",
            "metric_results": [],
            "log_results": [],
            "trace_results": [],
            "analyst_decision": "",
            "final_report": "",
            "thinking_log": [],
        }
        assert state["user_query"] == "测试查询"
        assert state["fault_type"] == "cpu"
        assert state["iteration"] == 0

    def test_state_with_all_fields(self):
        """测试包含所有字段的状态"""
        state: RCAState = {
            "user_query": "CPU使用率过高",
            "fault_type": "cpu",
            "detected_fault_type": "cpu",
            "full_analysis": True,
            "iteration": 1,
            "max_iterations": 5,
            "should_stop": False,
            "parallel_degree": 3,
            "master_plan": "分析CPU指标",
            "metric_results": ["指标正常"],
            "log_results": ["日志正常"],
            "trace_results": ["链路正常"],
            "analyst_decision": "继续分析",
            "final_report": "",
            "thinking_log": ["开始分析"],
        }
        assert len(state) == 15


class TestBuildRCAWorkflow:
    """测试构建RCA工作流"""

    def test_workflow_structure(self):
        """测试工作流结构定义"""
        # 测试RCAState结构是否正常
        from workflow.state import RCAState
        assert RCAState is not None

    def test_import_builder(self):
        """测试导入工作流构建器"""
        # 只测试导入，不实际构建工作流（避免LLM连接）
        assert callable(build_rca_workflow)
        assert callable(run_rca)


class TestRunRCA:
    """测试运行RCA - 跳过需要LLM的测试"""

    @pytest.mark.skip(reason="需要LLM连接，单独测试")
    def test_run_rca_basic(self):
        """测试基本RCA运行"""
        result = run_rca(
            user_query="测试查询",
            fault_type="cpu",
            max_iterations=1,
            full_analysis=False
        )
        assert isinstance(result, dict)
        assert "iteration" in result

    @pytest.mark.skip(reason="需要LLM连接，单独测试")
    def test_run_rca_with_progress(self):
        """测试带进度回调的RCA运行"""
        progress_events = []

        def progress_callback(node_name, status):
            progress_events.append((node_name, status))

        result = run_rca(
            user_query="CPU过高",
            fault_type="cpu",
            max_iterations=1,
            full_analysis=False,
            progress_callback=progress_callback
        )
        assert isinstance(result, dict)


class TestWorkflowIntegration:
    """测试工作流集成 - 重点测试知识库工作流"""

    def test_knowledge_base_in_workflow(self):
        """测试知识库在工作流中的使用"""
        from knowledge_base.knowledge_manager import get_knowledge_manager

        km = get_knowledge_manager()
        # 验证知识库可在工作流前获取
        pattern = km.get_fault_pattern("cpu")
        assert pattern is not None

        # 验证工作流可以使用知识库
        state = {
            "user_query": "CPU故障",
            "fault_type": "cpu",
            "detected_fault_type": "",
            "full_analysis": True,
            "iteration": 0,
            "max_iterations": 1,
            "should_stop": False,
            "parallel_degree": 3,
            "master_plan": "",
            "metric_results": [],
            "log_results": [],
            "trace_results": [],
            "analyst_decision": "",
            "final_report": "",
            "thinking_log": [],
        }

        # 在工作流执行前，知识库应该能给出建议
        causes = km.recommend_root_causes("cpu")
        assert len(causes) > 0

    def test_workflow_uses_knowledge(self):
        """测试工作流使用知识库"""
        from knowledge_base.knowledge_manager import get_knowledge_manager

        km = get_knowledge_manager()

        # 模拟工作流节点调用知识库
        for fault_type in ["cpu", "mem", "delay", "disk", "loss"]:
            pattern = km.get_fault_pattern(fault_type)
            if pattern:
                assert "typical_metrics" in pattern
                assert "common_roots" in pattern

                # 验证推荐功能
                causes = km.recommend_root_causes(fault_type)
                assert isinstance(causes, list)


class TestWorkflowConfig:
    """测试工作流配置"""

    def test_workflow_config_exists(self):
        """测试工作流配置存在"""
        assert "max_iterations" in WORKFLOW_CONFIG
        assert "convergence_threshold" in WORKFLOW_CONFIG

    def test_max_iterations_value(self):
        """测试最大迭代次数配置"""
        assert WORKFLOW_CONFIG["max_iterations"] > 0
