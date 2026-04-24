"""
知识库管理系统 - 基于异常模式模板的RCA参考知识库（仅作参考，不覆盖观测证据）
提供异常模式查询、根因候选推荐、历史案例检索功能
新增RAG(检索增强生成)能力，支持语义化知识检索

本模块为对外API入口，所有内部实现已模块化拆分：
- fault_patterns.py: 预定义异常模式参考模板（仅参考）
- rag_index.py: RAG向量索引与语义检索
- data_analyzer.py: 数据集自动分析
- storage.py: 知识库持久化存储

注意：知识库返回的所有信息仅作为参考，观测证据优先级高于知识库
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
    知识库管理器 - 提供异常模式查询、根因候选推荐、历史案例检索（仅作参考）
    
    所有内部逻辑已模块化拆分，本类作为统一对外API门面
    保持100%向后兼容性，原有调用方式完全不变
    
    重要：知识库仅为参考信息，实际分析必须以观测证据为准
    当知识库与观测证据冲突时，以观测证据为准
    """
    
    def __init__(self):
        # fault_patterns 中的 key（cpu/mem/delay/disk/loss）为异常模式标识符，非固定故障标签
        self.fault_patterns = FAULT_PATTERNS.copy()
        self.rag_index = RAGKnowledgeIndex()
        self._load_learned_patterns()
        
    def _load_learned_patterns(self):
        """加载已学习的异常模式（仅作参考）"""
        learned = KnowledgeStorage.load_learned_patterns()
        # 合并已知模式和学到的模式
        for pattern_key, pattern in learned.items():
            if pattern_key in self.fault_patterns:
                self.fault_patterns[pattern_key].update(pattern)
            else:
                self.fault_patterns[pattern_key] = pattern
    
    def save_learned_patterns(self):
        """保存学习到的异常模式"""
        KnowledgeStorage.save_learned_patterns(self.fault_patterns)
    
    def get_fault_pattern(self, pattern_key: str) -> Optional[Dict]:
        """
        获取指定异常模式标识符的参考信息（仅作参考）
        注意：返回的pattern为参考模板，不代表先验真值标签，不驱动分析
        """
        return self.fault_patterns.get(pattern_key)
    
    def recommend_root_causes(self, pattern_key: str, 
                            anomaly_metrics: List[str] = None) -> List[str]:
        """
        基于异常模式推荐可能的根因候选（仅作参考，需结合观测证据判断）
        注意：result为常见候选根因，观测证据冲突时以观测为准
        """
        pattern = self.get_fault_pattern(pattern_key)
        if not pattern:
            return []
        
        # 返回常见根因候选，但不覆盖观测证据
        return pattern.get("common_roots", []).copy()
    
    def recommend_mitigations(self, pattern_key: str) -> List[str]:
        """获取该异常模式下常见缓解建议（仅供参考，不驱动决策）"""
        pattern = self.get_fault_pattern(pattern_key)
        return pattern.get("mitigation", []) if pattern else []
    
    def get_propagation_path(self, pattern_key: str) -> str:
        """获取该异常模式下常见传播路径参考（经验性参考，非唯一因果链）"""
        pattern = self.get_fault_pattern(pattern_key)
        return pattern.get("propagation_path", "") if pattern else ""
    
    def search_knowledge(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        RAG语义检索 - 根据查询搜索相关知识库内容（仅作参考）
        可被智能体直接调用作为工具，但结果不覆盖观测证据
        """
        if not self.rag_index.vector_store:
            return []
        return self.rag_index.search(query, top_k)
    
    def recommend_root_causes_enhanced(self, pattern_key: str, 
                                     anomaly_metrics: List[str] = None,
                                     query_context: str = None) -> List[str]:
        """
        增强版根因候选推荐 - 结合结构化异常模式 + RAG语义检索（仅作参考）
        注意：结果为候选参考，需结合实际观测证据确认，不覆盖证据
        """
        # 原有结构化推荐（仅参考）
        base_causes = self.recommend_root_causes(pattern_key, anomaly_metrics)
        
        # 新增RAG增强检索（仅补充参考，不覆盖证据）
        if query_context and self.rag_index.vector_store:
            rag_results = self.search_knowledge(query_context, top_k=2)
            for result in rag_results:
                content = result.get("content", "")
                if "根因" in content or "常见" in content or "导致" in content:
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
    
    def get_diagnosis_guidance(self, pattern_key: str, query: str = None) -> Dict:
        """
        获取完整诊断参考 - 融合结构化知识 + RAG检索结果（仅作参考）
        注意：所有信息均为参考，实际诊断必须以观测证据为准
        """
        pattern = self.get_fault_pattern(pattern_key)
        if not pattern:
            return {}
            
        guidance = {
            "fault_info": pattern,  # 仅参考，不驱动分析
            "root_causes": self.recommend_root_causes(pattern_key),
            "mitigations": self.recommend_mitigations(pattern_key),
            "propagation": self.get_propagation_path(pattern_key),
            "related_knowledge": []
        }
        
        # 补充RAG检索到的相关知识（仅参考）
        if query and self.rag_index.vector_store:
            guidance["related_knowledge"] = self.search_knowledge(query, top_k=2)
            
        return guidance
    
    def analyze_fault_from_data(self, pattern_key: str) -> Dict:
        """
        从数据集自动分析并生成异常模式参考条目（仅作参考）
        注意：分析的为异常特征模板，非固定故障标签，不驱动核心分析
        """
        return FaultDataAnalyzer.analyze_fault_from_data(pattern_key)
    
    def build_knowledge_from_all_datasets(self):
        """从所有数据集构建完整异常模式参考库（仅作参考）"""
        results = {}
        for pattern_key in ["cpu", "mem", "delay", "disk", "loss"]:
            analysis = self.analyze_fault_from_data(pattern_key)
            if analysis:
                results[pattern_key] = analysis
                if pattern_key in self.fault_patterns:
                    self.fault_patterns[pattern_key]["typical_services_observed"] = \
                        analysis.get("typical_services_observed", [])
        
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
            "module_version": "2.1.0 (参考版，不覆盖观测证据)",
            "note": "所有知识库信息仅作参考，观测证据优先级最高"
        }
    


# 全局知识库实例
_knowledge_manager = None

def get_knowledge_manager() -> KnowledgeManager:
    """获取知识库管理器实例（返回的知识库仅作参考）"""
    global _knowledge_manager
    if _knowledge_manager is None:
        _knowledge_manager = KnowledgeManager()
    return _knowledge_manager
