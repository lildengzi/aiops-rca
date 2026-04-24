"""
故障自动检测节点 - 增强版，返回候选异常模式而非固定类型
基于指标异常分布扫描数据集，给出可疑异常模式参考。
不强制分类，证据不足时返回 unknown。
"""
import json
from datetime import datetime
from typing import Dict, List, Any

from tools.metric_tools import query_all_services_overview
from workflow.state import RCAState


# 判定阈值
SCORE_DIFF_RATIO = 0.15
MIN_ANOMALOUS_METRICS = 2
MIN_ANOMALOUS_SERVICES = 1


def _extract_anomaly_patterns(overview: Dict[str, Any]) -> List[str]:
    """从概览中提取异常模式（基于实际指标名，不固定类型）"""
    patterns = []
    services = overview.get("services", [])
    
    # 收集所有异常指标名
    anomalous_metrics = []
    for svc in services:
        for anomaly in (svc.get("anomalies", []) or []):
            metric_short = anomaly.get("metric_short_name", "")
            if metric_short:
                anomalous_metrics.append(metric_short)
    
    # 基于实际指标名推断模式（仅供参考）
    metric_str = " ".join(anomalous_metrics).lower()
    
    if any(k in metric_str for k in ["cpu", "processor"]):
        patterns.append("cpu_spike")
    if any(k in metric_str for k in ["mem", "memory", "heap", "gc"]):
        patterns.append("memory_pressure")
    if any(k in metric_str for k in ["latency", "delay", "p50", "p90", "p99"]):
        patterns.append("high_latency")
    if any(k in metric_str for k in ["disk", "io", "storage"]):
        patterns.append("disk_issue")
    if any(k in metric_str for k in ["loss", "packet", "net", "timeout"]):
        patterns.append("network_issue")
    if any(k in metric_str for k in ["error", "fail", "exception"]):
        patterns.append("error_spike")
    
    return patterns if patterns else ["unknown_pattern"]


def detect_fault_node(state: RCAState) -> dict:
    """
    故障检测节点：扫描数据集给出可疑异常模式参考（不固定类型）。
    - 若用户已显式指定，则透传（作为参考标签）
    - 否则扫描数据集，提取实际异常模式，证据不足时返回 unknown
    """
    ts = datetime.now().strftime("%H:%M:%S")
    specified_fault_type = state.get("fault_type", "unknown")

    # 用户指定了类型，仅作参考标签透传
    if specified_fault_type != "unknown":
        return {
            "detected_fault_type": specified_fault_type,
            "thinking_log": [f"[{ts}] 用户指定参考标签: {specified_fault_type}（仅供参考，不驱动分析）"],
        }

    # 扫描数据集获取概览
    try:
        # 使用默认标签扫描（实际数据不依赖fault_type）
        raw = query_all_services_overview.invoke({"fault_type": "unknown"})
        overview = json.loads(raw)
        
        if overview.get("status") == "failure":
            return {
                "detected_fault_type": "unknown",
                "thinking_log": [f"[{ts}] 数据扫描失败: {overview.get('error_message', '未知错误')}"],
            }
        
        services = overview.get("services", [])
        anomalous_services = [s for s in services if s.get("anomalous_metrics", 0) > 0]
        
        # 证据不足判断
        total_anomalous_metrics = sum(s.get("anomalous_metrics", 0) for s in anomalous_services)
        if len(anomalous_services) < MIN_ANOMALOUS_SERVICES or total_anomalous_metrics < MIN_ANOMALOUS_METRICS:
            return {
                "detected_fault_type": "unknown",
                "thinking_log": [f"[{ts}] 证据不足: 仅发现 {len(anomalous_services)} 个异常服务，{total_anomalous_metrics} 个异常指标，记为 unknown"],
            }
        
        # 提取候选异常模式
        candidate_patterns = _extract_anomaly_patterns(overview)
        primary_pattern = candidate_patterns[0] if candidate_patterns else "unknown"
        
        # 构建日志
        svc_summary = ", ".join([f"{s['service']}({s['anomalous_metrics']}指标异常)" for s in anomalous_services[:3]])
        log_entry = (
            f"[{ts}] 候选异常模式: {candidate_patterns}\n"
            f"异常服务: {svc_summary}\n"
            f"注意: 该结果为参考模式，分析应基于实际观测证据，而非预设标签"
        )
        
        return {
            "detected_fault_type": primary_pattern,  # 仅作参考标签
            "thinking_log": [log_entry],
        }
        
    except Exception as e:
        return {
            "detected_fault_type": "unknown",
            "thinking_log": [f"[{ts}] 自动检测异常: {str(e)}，记为 unknown"],
        }
