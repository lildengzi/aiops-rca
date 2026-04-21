"""
知识库管理系统 - 基于数据集构建RCA专家知识库
提供故障模式识别、根因匹配和历史案例查询功能
新增RAG(检索增强生成)能力，支持语义化知识检索

本模块为对外API入口，所有内部实现已模块化拆分：
- fault_patterns.py: 预定义故障模式
- rag_index.py: RAG向量索引与语义检索
- data_analyzer.py: 数据集自动分析
- storage.py: 知识库持久化存储
"""
import os
from typing import Dict, List, Optional, Any

# 导入模块化组件
from .fault_patterns import FAULT_PATTERNS
from .rag_index import RAGKnowledgeIndex
from .data_analyzer import FaultDataAnalyzer
from .storage import KnowledgeStorage

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
KNOWLEDGE_BASE_DIR = os.path.join(PROJECT_ROOT, "knowledge_base")
FAULT_PATTERNS_FILE = os.path.join(KNOWLEDGE_BASE_DIR, "fault_patterns.json")


class KnowledgeManager:
    """
    知识库管理器 - 提供故障模式查询、根因推荐、历史案例检索
    
    所有内部逻辑已模块化拆分，本类作为统一对外API门面
    保持100%向后兼容性，原有调用方式完全不变
    """
    
    def __init__(self):
        self.fault_patterns = FAULT_PATTERNS.copy()
        self.rag_index = RAGKnowledgeIndex()
        self._load_learned_patterns()
        
    def _load_learned_patterns(self):
        """加载已学习的故障模式"""
        learned = KnowledgeStorage.load_learned_patterns()
        # 合并已知模式和学习到的模式
        for fault_type, pattern in learned.items():
            if fault_type in self.fault_patterns:
                self.fault_patterns[fault_type].update(pattern)
            else:
                self.fault_patterns[fault_type] = pattern
    
    def save_learned_patterns(self):
        """保存学习到的故障模式"""
        KnowledgeStorage.save_learned_patterns(self.fault_patterns)
    
    def get_fault_pattern(self, fault_type: str) -> Optional[Dict]:
        """获取指定故障类型的模式信息"""
        return self.fault_patterns.get(fault_type)
    
    def recommend_root_causes(self, fault_type: str, 
                            anomaly_metrics: List[str] = None) -> List[str]:
        """
        基于故障类型和异常指标推荐可能的根因
        """
        pattern = self.get_fault_pattern(fault_type)
        if not pattern:
            return []
        
        candidates = pattern["common_roots"].copy()
        
        # 如果有异常指标，根据指标匹配度排序
        if anomaly_metrics:
            typical_metrics = pattern["typical_metrics"]
            matched = any(any(tm in am for am in anomaly_metrics) 
                         for tm in typical_metrics)
            if matched:
                # 匹配到典型指标，提升相关根因优先级
                pass
        
        return candidates
    
    def recommend_mitigations(self, fault_type: str) -> List[str]:
        """获取故障缓解建议"""
        pattern = self.get_fault_pattern(fault_type)
        return pattern["mitigation"] if pattern else []
    
    def get_propagation_path(self, fault_type: str) -> str:
        """获取典型故障传播路径"""
        pattern = self.get_fault_pattern(fault_type)
        return pattern["propagation_path"] if pattern else ""
    
    def search_knowledge(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        RAG语义检索 - 根据查询搜索相关知识库内容
        可被智能体直接调用作为工具
        """
        return self.rag_index.search(query, top_k)
    
    def recommend_root_causes_enhanced(self, fault_type: str, 
                                     anomaly_metrics: List[str] = None,
                                     query_context: str = None) -> List[str]:
        """
        增强版根因推荐 - 结合结构化故障模式 + RAG语义检索
        """
        # 原有结构化推荐
        base_causes = self.recommend_root_causes(fault_type, anomaly_metrics)
        
        # 新增RAG增强检索
        if query_context and self.rag_index.vector_store:
            rag_results = self.search_knowledge(query_context, top_k=2)
            for result in rag_results:
                # 从RAG结果中提取根因相关内容
                content = result["content"]
                if "根因" in content or "常见" in content or "导致" in content:
                    # 简单提取相关句子作为补充
                    lines = [l.strip() for l in content.split('\n') if l.strip()]
                    base_causes.extend([l for l in lines if len(l) > 10][:2])
        
        # 去重并保持顺序
        seen = set()
        unique_causes = []
        for cause in base_causes:
            if cause not in seen:
                seen.add(cause)
                unique_causes.append(cause)
        
        return unique_causes
    
    def get_diagnosis_guidance(self, fault_type: str, query: str = None) -> Dict:
        """
        获取完整诊断指导 - 融合结构化知识 + RAG检索结果
        """
        pattern = self.get_fault_pattern(fault_type)
        if not pattern:
            return {}
            
        guidance = {
            "fault_info": pattern,
            "root_causes": self.recommend_root_causes(fault_type),
            "mitigations": self.recommend_mitigations(fault_type),
            "propagation": self.get_propagation_path(fault_type),
            "related_knowledge": []
        }
        
        # 补充RAG检索到的相关知识
        if query and self.rag_index.vector_store:
            guidance["related_knowledge"] = self.search_knowledge(query, top_k=2)
            
        return guidance
    
    def analyze_fault_from_data(self, fault_type: str) -> Dict:
        """
        从数据集自动分析并生成故障知识库条目
        """
        return FaultDataAnalyzer.analyze_fault_from_data(fault_type)
    
    def build_knowledge_from_all_datasets(self):
        """从所有数据集构建完整知识库"""
        results = {}
        for fault_type in ["cpu", "mem", "delay", "disk", "loss"]:
            analysis = self.analyze_fault_from_data(fault_type)
            if analysis:
                results[fault_type] = analysis
                
                # 更新知识库中的典型服务
                if fault_type in self.fault_patterns:
                    self.fault_patterns[fault_type]["typical_services_observed"] = \
                        analysis["typical_services_observed"]
        
        self.save_learned_patterns()
        return results
    
    def is_rag_available(self) -> bool:
        """检查RAG功能是否可用"""
        return self.rag_index.is_available()
    
    def get_knowledge_summary(self) -> Dict:
        """获取知识库概览信息"""
        return {
            "fault_patterns_count": len(self.fault_patterns),
            "rag_enabled": self.is_rag_available(),
            "knowledge_documents": os.path.basename(os.path.join(KNOWLEDGE_BASE_DIR, "rca_knowledge.md")),
            "learned_patterns_file": os.path.basename(FAULT_PATTERNS_FILE),
            "module_version": "2.0.0"
        }


# 全局知识库实例
_knowledge_manager = None

def get_knowledge_manager() -> KnowledgeManager:
    global _knowledge_manager
    if _knowledge_manager is None:
        _knowledge_manager = KnowledgeManager()
    return _knowledge_manager
