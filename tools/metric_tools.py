"""
指标查询工具 - 模拟 Metric MCP 服务
封装对时序指标数据的查询与异常检测能力
动态模式：
  - 指标名不固定，支持任意 {service}_{metric} 格式
  - 基于实际存在的列工作，而非预设指标类别
  - 增强 RCA 支持：输出指标异常的根因/放大器/受害者分类
"""
import json
import pandas as pd
import numpy as np
from langchain_core.tools import tool
from utils.data_loader import load_fault_data, get_all_services
from utils.service_parser import ServiceParser
from utils.anomaly_detection import (
    detect_anomalies_zscore,
    detect_anomalies_sliding_window,
    detect_change_point,
    find_correlated_metrics,
)


def _get_data(fault_type: str) -> pd.DataFrame:
    """\\brief 获取指标数据（实时缓存优先，CSV 回退）
    \\param fault_type 缓存标签（仅用于数据索引，不驱动分析）
    \\return 指标数据 DataFrame"""
    return load_fault_data(fault_type)


def _get_service_columns(df: pd.DataFrame, service_name: str, metric_type: str = "all") -> list[str]:
    """获取指定服务的指标列名
    \\param df 数据 DataFrame
    \\param service_name 服务名
    \\param metric_type 指标类型过滤（"all" 或具体 metric 名称）
    \\return 匹配的列名列表
    """
    prefix = f"{service_name}_"
    cols = [c for c in df.columns if c.startswith(prefix) and c != "time"]

    if metric_type == "all":
        return cols

    # 精确匹配：metric 部分与 metric_type 完全一致
    matched = []
    for c in cols:
        metric_part = c[len(prefix):]
        if metric_part == metric_type:
            matched.append(c)
    return matched


@tool
def query_service_metrics(
    fault_type: str,
    service_name: str,
    metric_type: str = "all",
) -> str:
    """\\brief 查询指定服务的监控指标数据并进行异常检测（支持动态指标）
    \\param fault_type 缓存标签（仅用于数据索引，不驱动分析）
    \\param service_name 服务名称 (如 cartservice, frontend)
    \\param metric_type 指标名过滤 ("all" 返回所有指标，或指定具体指标名如 "cpu"、"latency_p99")
    \\return JSON 字符串，包含:
        - metrics 列表，每项含统计信息、异常标记、采样值
        - rca_classification: 尝试对指标异常做 RCA 分类（根因/放大器/受害者）
        - 或错误信息（当服务/指标不存在时）"""
    try:
        df = _get_data(fault_type)
    except ValueError as e:
        return json.dumps({"status": "failure", "error_message": str(e)})

    # 获取该服务的所有列
    all_cols = _get_service_columns(df, service_name, metric_type="all")

    if not all_cols:
        return json.dumps({
            "status": "failure",
            "error_message": f"未找到服务 {service_name} 的任何指标列",
            "available_services": get_all_services(df),
        })

    # 按 metric_type 过滤
    if metric_type == "all":
        cols = all_cols
    else:
        cols = _get_service_columns(df, service_name, metric_type=metric_type)
        if not cols:
            return json.dumps({
                "status": "failure",
                "error_message": f"未找到服务 {service_name} 的指标 '{metric_type}'",
                "available_metrics": [c[len(f"{service_name}_"):] for c in all_cols],
                "available_columns": all_cols,
            })

    results = {
        "status": "success", 
        "service": service_name, 
        "metrics": [],
        "rca_classification": "victim",  # 默认受害者，根据异常分数调整
        "anomaly_severity": "low",
    }

    max_anomaly_score = 0.0
    anomalous_metrics = []

    for col in cols:
        series = df[col].dropna()
        if len(series) == 0:
            continue

        stats = {
            "mean": round(float(series.mean()), 4),
            "std": round(float(series.std()), 4),
            "min": round(float(series.min()), 4),
            "max": round(float(series.max()), 4),
            "p50": round(float(series.quantile(0.5)), 4),
            "p90": round(float(series.quantile(0.9)), 4),
            "p99": round(float(series.quantile(0.99)), 4),
        }
        anomaly = detect_anomalies_zscore(series)
        change = detect_change_point(series)

        if anomaly["is_anomalous"]:
            anomalous_metrics.append({
                "metric": col,
                "score": anomaly["anomaly_score"],
            })
            max_anomaly_score = max(max_anomaly_score, anomaly["anomaly_score"])

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
            "metric_short_name": col[len(f"{service_name}_"):],
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

    # RCA 分类：根据异常严重度分类
    if max_anomaly_score > 0.8:
        results["rca_classification"] = "root_cause_candidate"
        results["anomaly_severity"] = "high"
    elif max_anomaly_score > 0.5:
        results["rca_classification"] = "amplifier"
        results["anomaly_severity"] = "medium"
    else:
        results["rca_classification"] = "victim"
        results["anomaly_severity"] = "low"

    results["max_anomaly_score"] = round(max_anomaly_score, 4)
    results["anomalous_metric_count"] = len(anomalous_metrics)

    return json.dumps(results, ensure_ascii=False)


@tool
def query_all_services_overview(fault_type: str) -> str:
    """\\brief 查询所有服务的指标概览，全局扫描发现异常服务（动态指标适配）
    基于实际存在的指标列工作，不依赖固定指标类别
    \\param fault_type 缓存标签（仅用于数据索引，不驱动分析）
    \\return JSON 字符串，包含:
        - services 列表，每项含异常指标数、异常列表（按分数排序）、RCA 分类
        - total_services 服务总数
        - candidate_roots: 候选根因服务列表（高异常分数）
        - propagation_hubs: 传播枢纽候选（中异常分数）"""
    try:
        df = _get_data(fault_type)
    except ValueError as e:
        return json.dumps({"status": "failure", "error_message": str(e)})

    services = get_all_services(df)
    overview = []
    candidate_roots = []
    propagation_hubs = []

    for svc in services:
        svc_cols = [c for c in df.columns if c.startswith(f"{svc}_")]
        svc_anomalies = []
        max_score = 0.0
        for col in svc_cols:
            series = df[col].dropna()
            if len(series) < 10:
                continue
            anomaly = detect_anomalies_zscore(series)
            if anomaly["is_anomalous"]:
                metric_short = col[len(f"{svc}_"):]
                score = round(anomaly["anomaly_score"], 4)
                svc_anomalies.append({
                    "metric": col,
                    "metric_short_name": metric_short,
                    "anomaly_score": score,
                    "max_z": round(anomaly["stats"].get("max_z_score", 0), 2),
                })
                max_score = max(max_score, score)

        # RCA 分类
        rca_class = "victim"
        if max_score > 0.8:
            rca_class = "root_cause_candidate"
            candidate_roots.append(svc)
        elif max_score > 0.5:
            rca_class = "amplifier"
            propagation_hubs.append(svc)

        overview.append({
            "service": svc,
            "total_metrics": len(svc_cols),
            "metric_columns": svc_cols,
            "anomalous_metrics": len(svc_anomalies),
            "anomalies": sorted(svc_anomalies, key=lambda x: x["anomaly_score"], reverse=True),
            "max_anomaly_score": round(max_score, 4),
            "rca_classification": rca_class,
        })

    overview.sort(key=lambda x: x["max_anomaly_score"], reverse=True)

    return json.dumps({
        "status": "success",
        "fault_type_label": fault_type,  # 仅作参考标签
        "total_services": len(services),
        "services": overview,
        "candidate_roots": candidate_roots,
        "propagation_hubs": propagation_hubs,
    }, ensure_ascii=False)


@tool
def query_metric_correlation(
    fault_type: str,
    target_metric: str,
    threshold: float = 0.7,
) -> str:
    """\\brief 查询与目标指标高度相关的其他指标（用于故障传播链分析）
    基于真实存在的数值列工作
    \\param fault_type 缓存标签（仅用于数据索引，不驱动分析）
    \\param target_metric 目标指标列名（如 cartservice_cpu）
    \\param threshold 相关性阈值 [0-1]
    \\return JSON 字符串，包含 correlated_metrics 列表（含 correlation、direction、服务分类）"""
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

    # 为相关指标添加服务分类
    for item in correlated:
        metric_col = item["metric"]
        if "_" in metric_col:
            svc = metric_col.split("_")[0]
            item["service"] = svc
            item["rca_role"] = "unknown"  # 可进一步分类

    return json.dumps({
        "status": "success",
        "target_metric": target_metric,
        "correlated_metrics": correlated[:15],
    }, ensure_ascii=False)


# 导出所有工具
METRIC_TOOLS = [query_service_metrics, query_all_services_overview, query_metric_correlation]
