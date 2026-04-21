"""
工作流通用工具函数
"""
import psutil
from langchain_openai import ChatOpenAI

from config import LLM_CONFIG


def _create_llm() -> ChatOpenAI:
    """创建 LLM 实例"""
    return ChatOpenAI(
        model=LLM_CONFIG["model"],
        api_key=LLM_CONFIG["api_key"],
        base_url=LLM_CONFIG["base_url"],
        temperature=LLM_CONFIG["temperature"],
        max_tokens=LLM_CONFIG["max_tokens"],
    )


def _calculate_optimal_parallel_degree() -> int:
    """
    根据系统资源计算最优并行度
    """
    # 获取CPU核心数
    cpu_count = psutil.cpu_count(logical=True)
    # 获取可用内存比例
    memory = psutil.virtual_memory()
    memory_available_percent = memory.available / memory.total
    
    # 基于系统资源计算并行度
    # 保守策略：最多使用一半的CPU核心
    max_parallel = max(1, cpu_count // 2)
    
    # 根据内存可用性调整
    if memory_available_percent < 0.2:
        # 内存不足，降低并行度
        return max(1, max_parallel // 2)
    elif memory_available_percent < 0.5:
        # 内存紧张，保持保守并行度
        return max(1, max_parallel)
    else:
        # 内存充足，可以增加并行度
        return min(3, max_parallel)  # 最多并行3个智能体
