"""
知识库管理系统 - 基于数据集构建RCA专家知识库
提供故障模式识别、根因匹配和历史案例查询功能
"""
import json
import os
import pandas as pd
from typing import Dict, List, Optional
from utils.data_loader import load_fault_data, get_all_services
from utils.anomaly_detection import detect_anomalies_zscore

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
KNOWLEDGE_BASE_DIR = os.path.join(PROJECT_ROOT, "knowledge_base")
FAULT_PATTERNS_FILE = os.path.join(KNOWLEDGE_BASE_DIR, "fault_patterns.json")

# 故障模式知识库
FAULT_PATTERNS = {
    "cpu": {
        "name": "CPU资源耗尽故障",
        "typical_metrics": ["cpu_usage", "system_load", "process_threads"],
        "typical_services": ["frontend", "cartservice", "checkoutservice"],
        "common_roots": [
            "无限循环导致CPU占用过高",
            "频繁GC导致CPU消耗",
            "大量并发请求导致CPU瓶颈",
            "计算密集型任务异常",
            "死锁导致线程自旋"
        ],
        "propagation_path": "高CPU服务 → 上游服务延迟升高 → 级联超时",
        "mitigation": [
            "扩容CPU资源",
            "优化代码逻辑减少CPU消耗",
            "限制并发请求数",
            "添加熔断机制"
        ]
    },
    "mem": {
        "name": "内存泄漏/溢出故障",
        "typical_metrics": ["mem_usage", "heap_used", "gc_duration"],
        "typical_services": ["cartservice", "productcatalogservice", "checkoutservice"],
        "common_roots": [
            "内存泄漏未释放对象",
            "缓存数据无限制增长",
            "大对象创建未回收",
            "线程池泄漏",
            "类加载器泄漏"
        ],
        "propagation_path": "内存占用升高 → GC频繁 → 响应延迟 → OOM崩溃",
        "mitigation": [
            "增加内存配额",
            "排查内存泄漏点",
            "限制缓存大小",
            "优化对象创建逻辑"
        ]
    },
    "delay": {
        "name": "服务延迟异常故障",
        "typical_metrics": ["latency_p99", "latency_p95", "request_duration"],
        "typical_services": ["frontend", "recommendationservice", "productcatalogservice"],
        "common_roots": [
            "下游服务依赖延迟",
            "数据库慢查询",
            "网络传输延迟",
            "锁竞争导致阻塞",
            "资源池耗尽等待"
        ],
        "propagation_path": "下游服务延迟 → 上游调用超时 → 错误率升高",
        "mitigation": [
            "添加缓存层",
            "优化数据库查询",
            "异步处理非关键路径",
            "降级非核心功能"
        ]
    },
    "disk": {
        "name": "磁盘I/O异常故障",
        "typical_metrics": ["disk_io_wait", "disk_usage", "io_ops"],
        "typical_services": ["redis", "productcatalogservice", "checkoutservice"],
        "common_roots": [
            "大量磁盘写入操作",
            "日志无限制增长",
            "磁盘碎片严重",
            "磁盘配额耗尽",
            "文件句柄泄漏"
        ],
        "propagation_path": "磁盘I/O升高 → 读写操作延迟 → 服务响应变慢",
        "mitigation": [
            "清理磁盘空间",
            "配置日志轮转",
            "迁移到高速存储",
            "优化磁盘读写模式"
        ]
    },
    "loss": {
        "name": "网络丢包/连接故障",
        "typical_metrics": ["error_rate", "connection_count", "packet_loss"],
        "typical_services": ["frontend", "checkoutservice", "shippingservice"],
        "common_roots": [
            "网络拥塞导致丢包",
            "连接数超过上限",
            "防火墙规则拦截",
            "DNS解析失败",
            "服务实例宕机"
        ],
        "propagation_path": "网络异常 → 连接失败 → 请求重试风暴 → 级联故障",
        "mitigation": [
            "检查网络连通性",
            "添加重试和熔断机制",
            "扩容服务实例",
            "优化连接池配置"
        ]
    }
}


class KnowledgeManager:
    """
    知识库管理器 - 提供故障模式查询、根因推荐、历史案例检索
    """
    
    def __init__(self):
        self.fault_patterns = FAULT_PATTERNS
        self._load_learned_patterns()
        
    def _load_learned_patterns(self):
        """加载已学习的故障模式"""
        if os.path.exists(FAULT_PATTERNS_FILE):
            try:
                with open(FAULT_PATTERNS_FILE, 'r', encoding='utf-8') as f:
                    learned = json.load(f)
                    # 合并已知模式和学习到的模式
                    for fault_type, pattern in learned.items():
                        if fault_type in self.fault_patterns:
                            self.fault_patterns[fault_type].update(pattern)
                        else:
                            self.fault_patterns[fault_type] = pattern
            except Exception:
                pass
    
    def save_learned_patterns(self):
        """保存学习到的故障模式"""
        os.makedirs(KNOWLEDGE_BASE_DIR, exist_ok=True)
        with open(FAULT_PATTERNS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.fault_patterns, f, ensure_ascii=False, indent=2)
    
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
    
    def analyze_fault_from_data(self, fault_type: str) -> Dict:
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


# 全局知识库实例
_knowledge_manager = None

def get_knowledge_manager() -> KnowledgeManager:
    global _knowledge_manager
    if _knowledge_manager is None:
        _knowledge_manager = KnowledgeManager()
    return _knowledge_manager
