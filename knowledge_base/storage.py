"""
知识库持久化存储模块
负责学习到的故障模式的加载和保存
"""
import json
import os
from typing import Dict

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
KNOWLEDGE_BASE_DIR = os.path.join(PROJECT_ROOT, "knowledge_base")
FAULT_PATTERNS_FILE = os.path.join(KNOWLEDGE_BASE_DIR, "fault_patterns.json")


class KnowledgeStorage:
    """知识库存储管理器"""
    
    @staticmethod
    def load_learned_patterns() -> Dict:
        """加载已学习的故障模式"""
        if os.path.exists(FAULT_PATTERNS_FILE):
            try:
                with open(FAULT_PATTERNS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {}
    
    @staticmethod
    def save_learned_patterns(patterns: Dict) -> None:
        """保存学习到的故障模式"""
        os.makedirs(KNOWLEDGE_BASE_DIR, exist_ok=True)
        with open(FAULT_PATTERNS_FILE, 'w', encoding='utf-8') as f:
            json.dump(patterns, f, ensure_ascii=False, indent=2)
