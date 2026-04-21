"""
数据集分析模块
从故障数据集中自动分析并生成知识库条目
"""
import pandas as pd
from typing import Dict, List
from utils.data_loader import load_fault_data, get_all_services
from utils.anomaly_detection import detect_anomalies_zscore


class FaultDataAnalyzer:
    """故障数据集分析器"""
    
    @staticmethod
    def analyze_fault_from_data(fault_type: str) -> Dict:
        """
        从数据集自动分析并生成故障知识库条目
        """
        try:
            df = load_fault_data(fault_type)
        except ValueError:
            return {}
            
        services = get_all_services(df)
        anomaly_summary = {}
        
        # 分析每个服务的异常情况
        for svc in services:
            cols = [c for c in df.columns if c.startswith(f"{svc}_")]
            anomalies = []
            max_score = 0
            
            for col in cols:
                res = detect_anomalies_zscore(df[col])
                if res["is_anomalous"]:
                    anomalies.append({
                        "metric": col,
                        "score": res["anomaly_score"],
                        "max_z": res["stats"]["max_z_score"]
                    })
                    max_score = max(max_score, res["anomaly_score"])
            
            if anomalies:
                anomaly_summary[svc] = {
                    "max_anomaly_score": max_score,
                    "anomalous_metrics": [a["metric"] for a in anomalies],
                    "severity": "HIGH" if max_score > 0.8 else "MEDIUM"
                }
        
        # 按严重程度排序
        sorted_services = sorted(
            anomaly_summary.items(), 
            key=lambda x: x[1]["max_anomaly_score"], 
            reverse=True
        )
        
        return {
            "fault_type": fault_type,
            "typical_services_observed": [s[0] for s in sorted_services[:3]],
            "anomaly_distribution": anomaly_summary,
            "total_services_analyzed": len(services)
        }
    
    @staticmethod
    def analyze_all_fault_types() -> Dict[str, Dict]:
        """分析所有已知故障类型"""
        results = {}
        for fault_type in ["cpu", "mem", "delay", "disk", "loss"]:
            analysis = FaultDataAnalyzer.analyze_fault_from_data(fault_type)
            if analysis:
                results[fault_type] = analysis
        return results
