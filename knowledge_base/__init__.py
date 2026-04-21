"""
知识库模块对外API
所有内部模块均通过本文件导出，保持接口稳定性
"""
from .knowledge_manager import KnowledgeManager, get_knowledge_manager
from .fault_patterns import FAULT_PATTERNS
from .rag_index import RAGKnowledgeIndex
from .data_analyzer import FaultDataAnalyzer
from .storage import KnowledgeStorage

__all__ = [
    "KnowledgeManager", 
    "get_knowledge_manager", 
    "FAULT_PATTERNS",
    "RAGKnowledgeIndex",
    "FaultDataAnalyzer",
    "KnowledgeStorage"
]
