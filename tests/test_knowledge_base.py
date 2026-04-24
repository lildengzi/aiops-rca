"""
测试知识库模块 - 重点测试基于知识库的工作流
"""
import pytest
import os
import json
from knowledge_base.knowledge_manager import KnowledgeManager, get_knowledge_manager
from knowledge_base.fault_patterns import FAULT_PATTERNS


class TestKnowledgeManagerInit:
    """测试知识库管理器初始化"""

    def test_init(self):
        """测试初始化"""
        km = KnowledgeManager()
        assert km is not None
        assert hasattr(km, 'fault_patterns')
        assert hasattr(km, 'rag_index')

    def test_fault_patterns_loaded(self):
        """测试故障模式已加载"""
        km = KnowledgeManager()
        assert len(km.fault_patterns) > 0

    def test_singleton(self):
        """测试单例模式"""
        km1 = get_knowledge_manager()
        km2 = get_knowledge_manager()
        assert km1 is km2


class TestGetFaultPattern:
    """测试获取故障模式"""

    def test_get_existing_pattern(self):
        """测试获取已存在的故障模式"""
        km = KnowledgeManager()
        pattern = km.get_fault_pattern("cpu")
        assert pattern is not None
        assert "name" in pattern
        assert "typical_metrics" in pattern
        assert "common_roots" in pattern
        assert "mitigation" in pattern

    def test_get_nonexistent_pattern(self):
        """测试获取不存在的故障模式"""
        km = KnowledgeManager()
        pattern = km.get_fault_pattern("nonexistent")
        assert pattern is None


class TestRecommendRootCauses:
    """测试根因推荐"""

    def test_recommend_cpu(self):
        """测试CPU故障根因推荐"""
        km = KnowledgeManager()
        causes = km.recommend_root_causes("cpu")
        assert isinstance(causes, list)
        assert len(causes) > 0

    def test_recommend_with_metrics(self):
        """测试带异常指标的根因推荐"""
        km = KnowledgeManager()
        anomaly_metrics = ["adservice_cpu", "frontend_cpu"]
        causes = km.recommend_root_causes("cpu", anomaly_metrics)
        assert isinstance(causes, list)

    def test_recommend_nonexistent(self):
        """测试不存在故障类型的推荐"""
        km = KnowledgeManager()
        causes = km.recommend_root_causes("nonexistent")
        assert causes == []


class TestRecommendMitigations:
    """测试缓解建议"""

    def test_mitigation_cpu(self):
        """测试CPU故障缓解建议"""
        km = KnowledgeManager()
        mitigations = km.recommend_mitigations("cpu")
        assert isinstance(mitigations, list)
        assert len(mitigations) > 0

    def test_mitigation_nonexistent(self):
        """测试不存在故障类型的缓解建议"""
        km = KnowledgeManager()
        mitigations = km.recommend_mitigations("nonexistent")
        assert mitigations == []


class TestGetPropagationPath:
    """测试传播路径"""

    def test_propagation_path(self):
        """测试获取传播路径"""
        km = KnowledgeManager()
        path = km.get_propagation_path("cpu")
        assert isinstance(path, str)


class TestRAGSearch:
    """测试RAG语义检索"""

    def test_search_availability(self):
        """测试RAG功能可用性"""
        km = KnowledgeManager()
        available = km.is_rag_available()
        assert isinstance(available, bool)

    def test_search_knowledge(self):
        """测试知识检索"""
        km = KnowledgeManager()
        if km.is_rag_available():
            results = km.search_knowledge("CPU故障", top_k=3)
            assert isinstance(results, list)
        else:
            results = km.search_knowledge("CPU故障")
            assert results == []


class TestEnhancedRootCauses:
    """测试增强版根因推荐"""

    def test_enhanced_recommend(self):
        """测试增强版推荐"""
        km = KnowledgeManager()
        causes = km.recommend_root_causes_enhanced("cpu", ["adservice_cpu"])
        assert isinstance(causes, list)

    def test_enhanced_with_context(self):
        """测试带上下文的增强推荐"""
        km = KnowledgeManager()
        causes = km.recommend_root_causes_enhanced(
            "cpu",
            ["adservice_cpu"],
            query_context="CPU使用率过高"
        )
        assert isinstance(causes, list)


class TestDiagnosisGuidance:
    """测试诊断指导"""

    def test_get_guidance(self):
        """测试获取诊断指导"""
        km = KnowledgeManager()
        guidance = km.get_diagnosis_guidance("cpu")
        assert isinstance(guidance, dict)
        assert "fault_info" in guidance or "root_causes" in guidance

    def test_get_guidance_nonexistent(self):
        """测试不存在故障的诊断指导"""
        km = KnowledgeManager()
        guidance = km.get_diagnosis_guidance("nonexistent")
        assert guidance == {}


class TestAnalyzeFaultFromData:
    """测试从数据分析故障"""

    def test_analyze_cpu(self):
        """测试分析CPU故障数据"""
        km = KnowledgeManager()
        result = km.analyze_fault_from_data("cpu")
        assert isinstance(result, dict)

    def test_analyze_nonexistent(self):
        """测试分析不存在的故障类型"""
        km = KnowledgeManager()
        result = km.analyze_fault_from_data("nonexistent")
        assert isinstance(result, dict)
        assert len(result) == 0 or "error" in result


class TestBuildKnowledgeFromDatasets:
    """测试从数据集构建知识库"""

    def test_build_knowledge(self):
        """测试构建知识库"""
        km = KnowledgeManager()
        results = km.build_knowledge_from_all_datasets()
        assert isinstance(results, dict)


class TestKnowledgeSummary:
    """测试知识库概览"""

    def test_get_summary(self):
        """测试获取知识库概览"""
        km = KnowledgeManager()
        summary = km.get_knowledge_summary()
        assert isinstance(summary, dict)
        assert "fault_patterns_count" in summary
        assert "rag_enabled" in summary
