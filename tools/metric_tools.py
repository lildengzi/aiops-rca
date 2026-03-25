"""
指标查询工具 - 模拟 Metric MCP 服务
封装对时序指标数据的查询与异常检测能力
"""
import json
import pandas as pd
import numpy as np
from langchain_core.tools import tool
from utils.data_loader import load_fault_data, get_all_services
from utils.anomaly_detection import (
    detect_anomalies_zscore,
    detect_anomalies_sliding_window,
    detect_change_point,
    find_correlated_metrics,
)


def _get_data(fault_type: str) -> pd.DataFrame:
    """获取数据：优先实时缓存，回退经验库 CSV（由 data_loader 统一管理）"""
    return load_fault_data(fault_type)


@tool
def query_service_metrics(
    fault_type: str,
    service_name: str,
    metric_type: str = "all",
) -> str:
    """
    查询指定服务的监控指标数据并进行异常检测。

    Args:
        fault_type: 故障数据集类型 (cpu/delay/disk/loss/mem)
        service_name: 服务名称 (如 cartservice, frontend)
        metric_type: 指标类型 (cpu/mem/latency/load/error/all)

    Returns:
        JSON格式的指标数据与异常分析结果
    """
    try:
        df = _get_data(fault_type)
    except ValueError as e:
        return json.dumps({"status": "failure", "error_message": str(e)})

    # 筛选该服务相关列
    if metric_type == "all":
        cols = [c for c in df.columns if c.startswith(f"{service_name}_")]
    else:
        cols = [c for c in df.columns
                if c.startswith(f"{service_name}_") and metric_type in c]

    if not cols:
        return json.dumps({
            "status": "failure",
            "error_message": f"未找到服务 {service_name} 的 {metric_type} 指标",
            "available_services": get_all_services(df),
        })

    results = {"status": "success", "service": service_name, "metrics": []}

    for col in cols:
        series = df[col].dropna()
        # 统计摘要
        stats = {
            "mean": round(float(series.mean()), 4),
            "std": round(float(series.std()), 4),
            "min": round(float(series.min()), 4),
            "max": round(float(series.max()), 4),
            "p50": round(float(series.quantile(0.5)), 4),
            "p90": round(float(series.quantile(0.9)), 4),
            "p99": round(float(series.quantile(0.99)), 4),
        }
        # 异常检测
        anomaly = detect_anomalies_zscore(series)
        change = detect_change_point(series)

        # 采样数据点（首尾 + 异常点附近）
        sample_indices = list(range(min(3, len(series)))) + list(range(max(0, len(series)-3), len(series)))
        if anomaly["anomaly_indices"]:
            sample_indices.extend(anomaly["anomaly_indices"][:5])
        sample_indices = sorted(set(i for i in sample_indices if i < len(series)))

        sampled_values = []
        for idx in sample_indices:
            sampled_values.append({
                "timestamp": int(df["time"].iloc[idx]) if idx < len(df) else 0,
                "value": round(float(series.iloc[idx]), 4),
            })

        metric_result = {
            "metric_name": col,
            "stats": stats,
            "is_anomalous": anomaly["is_anomalous"],
            "anomaly_score": round(anomaly["anomaly_score"], 4),
            "anomaly_ratio": round(anomaly.get("anomaly_ratio", 0), 4),
            "max_z_score": round(anomaly["stats"].get("max_z_score", 0), 4),
            "has_change_point": change["has_change_point"],
            "change_point_index": change["change_point_index"],
            "sampled_values": sampled_values[:10],
        }
        results["metrics"].append(metric_result)

    return json.dumps(results, ensure_ascii=False)


@tool
def query_all_services_overview(fault_type: str) -> str:
    """
    查询所有服务的指标概览，用于全局扫描发现异常服务。

    Args:
        fault_type: 故障数据集类型 (cpu/delay/disk/loss/mem)

    Returns:
        JSON格式的全服务异常概览
    """
    try:
        df = _get_data(fault_type)
    except ValueError as e:
        return json.dumps({"status": "failure", "error_message": str(e)})

    services = get_all_services(df)
    overview = []

    for svc in services:
        svc_cols = [c for c in df.columns if c.startswith(f"{svc}_")]
        svc_anomalies = []
        for col in svc_cols:
            series = df[col].dropna()
            if len(series) < 10:
                continue
            anomaly = detect_anomalies_zscore(series)
            if anomaly["is_anomalous"]:
                svc_anomalies.append({
                    "metric": col,
                    "anomaly_score": round(anomaly["anomaly_score"], 4),
                    "max_z": round(anomaly["stats"].get("max_z_score", 0), 2),
                })

        overview.append({
            "service": svc,
            "total_metrics": len(svc_cols),
            "anomalous_metrics": len(svc_anomalies),
            "anomalies": sorted(svc_anomalies, key=lambda x: x["anomaly_score"], reverse=True),
        })

    # 按异常指标数排序
    overview.sort(key=lambda x: x["anomalous_metrics"], reverse=True)

    return json.dumps({
        "status": "success",
        "fault_type": fault_type,
        "total_services": len(services),
        "services": overview,
    }, ensure_ascii=False)


@tool
def query_metric_correlation(
    fault_type: str,
    target_metric: str,
    threshold: float = 0.7,
) -> str:
    """
    查询与目标指标高度相关的其他指标，用于故障传播链分析。

    Args:
        fault_type: 故障数据集类型
        target_metric: 目标指标列名 (如 cartservice_cpu)
        threshold: 相关性阈值 (0-1)

    Returns:
        JSON格式的相关指标列表
    """
    try:
        df = _get_data(fault_type)
    except ValueError as e:
        return json.dumps({"status": "failure", "error_message": str(e)})

    if target_metric not in df.columns:
        return json.dumps({
            "status": "failure",
            "error_message": f"指标 {target_metric} 不存在",
            "available_columns": [c for c in df.columns if c != "time"][:20],
        })

    correlated = find_correlated_metrics(df, target_metric, threshold)

    return json.dumps({
        "status": "success",
        "target_metric": target_metric,
        "correlated_metrics": correlated[:15],
    }, ensure_ascii=False)


# 导出所有工具
METRIC_TOOLS = [query_service_metrics, query_all_services_overview, query_metric_correlation]
