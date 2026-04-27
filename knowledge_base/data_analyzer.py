"""
数据集分析模块
从实验数据中自动分析提取故障模式特征
"""
import os
import pandas as pd
import numpy as np
from typing import Dict, List, Optional

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
KNOWLEDGE_BASE_DIR = os.path.join(PROJECT_ROOT, "knowledge_base")


class FaultDataAnalyzer:
    """故障数据自动分析器"""
    
    FAULT_TYPES = ["cpu", "mem", "delay", "disk", "loss"]
    
    @classmethod
    def analyze_fault_from_data(cls, pattern_key: str) -> Dict:
        """
        从数据集自动分析并生成异常模式参考条目
        注意：分析的为异常特征模板，非固定故障标签
        
        Args:
            pattern_key: 故障类型标识符 (cpu/mem/delay/disk/loss)
            
        Returns:
            包含分析结果的字典
        """
        if pattern_key not in cls.FAULT_TYPES:
            return {}
        
        # 查找对应类型的数据目录
        data_dir = cls._find_fault_type_dirs(pattern_key)
        if not data_dir:
            return {}
        
        # 收集所有相关CSV文件
        csv_files = cls._collect_csv_files(data_dir)
        if not csv_files:
            return {}
        
        # 分析所有文件
        all_error_counts = {}
        all_services = set()
        file_count = 0
        
        for csv_file in csv_files:
            try:
                df = pd.read_csv(csv_file)
                file_count += 1
                
                # 找出所有 error 列
                error_cols = [c for c in df.columns if '_error' in c.lower()]
                
                for col in error_cols:
                    # 提取服务名
                    service_name = col.replace('_error', '')
                    if service_name and not service_name.startswith('frontend-external'):
                        all_services.add(service_name)
                    
                    # 统计非零错误数
                    non_zero = (df[col] > 0).sum()
                    if non_zero > 0:
                        all_error_counts[col] = all_error_counts.get(col, 0) + non_zero
            except Exception:
                continue
        
        # 获取已存在的模板作为基础
        from .fault_patterns import FAULT_PATTERNS
        base_pattern = FAULT_PATTERNS.get(pattern_key, {})
        
        # 合并典型服务
        existing_services = set(base_pattern.get("typical_services", []))
        all_services.update(existing_services)
        
        return {
            "name": base_pattern.get("name", f"{pattern_key}异常模式"),
            "pattern_type": "anomaly_pattern",
            "usage_note": base_pattern.get("usage_note", "从数据集自动学习的异常模式参考"),
            "typical_metrics": base_pattern.get("typical_metrics", []),
            "typical_services": sorted(list(all_services)),
            "typical_services_observed": sorted(list(all_services)),
            "common_roots": base_pattern.get("common_roots", []),
            "propagation_path": base_pattern.get("propagation_path", ""),
            "mitigation": base_pattern.get("mitigation", []),
            "learned_from_files": file_count,
            "error_columns_detected": all_error_counts
        }
    
    @staticmethod
    def _find_fault_type_dirs(pattern_key: str) -> List[str]:
        """查找对应故障类型的所有数据目录"""
        dirs = []
        if not os.path.exists(DATA_DIR):
            return dirs
        
        for item in os.listdir(DATA_DIR):
            item_path = os.path.join(DATA_DIR, item)
            if os.path.isdir(item_path) and item.endswith(f"_{pattern_key}"):
                dirs.append(item_path)
        
        return dirs
    
    @staticmethod
    def _collect_csv_files(data_dirs: List[str]) -> List[str]:
        """收集所有CSV文件"""
        csv_files = []
        for data_dir in data_dirs:
            if not os.path.isdir(data_dir):
                continue
            for run_id in os.listdir(data_dir):
                run_dir = os.path.join(data_dir, run_id)
                if os.path.isdir(run_dir):
                    csv_file = os.path.join(run_dir, "data.csv")
                    if os.path.exists(csv_file):
                        csv_files.append(csv_file)
        return csv_files
