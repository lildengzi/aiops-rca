"""
异常检测工具 - 基于统计方法的时序数据异常检测
实现多种检测方法：Z-Score、滑动窗口、相关性分析
"""
import numpy as np
import pandas as pd
from typing import Optional
from scipy import stats
from config import ANOMALY_CONFIG


def detect_anomalies_zscore(
    series: pd.Series,
    threshold: float = None,
) -> dict:
    """
    基于 Z-Score 的异常检测
    返回: {is_anomalous, anomaly_score, anomaly_indices, stats}
    """
    if threshold is None:
        threshold = ANOMALY_CONFIG["z_score_threshold"]

    clean = series.dropna()
    if len(clean) < 10:
        return {"is_anomalous": False, "anomaly_score": 0.0,
                "anomaly_indices": [], "stats": {}}

    mean = clean.mean()
    std = clean.std()
    if std == 0:
        return {"is_anomalous": False, "anomaly_score": 0.0,
                "anomaly_indices": [], "stats": {"mean": mean, "std": 0}}

    z_scores = np.abs((clean - mean) / std)
    anomaly_mask = z_scores > threshold
    anomaly_indices = clean.index[anomaly_mask].tolist()
    anomaly_ratio = anomaly_mask.sum() / len(clean)
    max_z = float(z_scores.max())

    return {
        "is_anomalous": len(anomaly_indices) > 0,
        "anomaly_score": min(max_z / threshold, 1.0) if max_z > 0 else 0.0,
        "anomaly_indices": anomaly_indices,
        "anomaly_ratio": float(anomaly_ratio),
        "stats": {
            "mean": float(mean),
            "std": float(std),
            "max": float(clean.max()),
            "min": float(clean.min()),
            "max_z_score": float(max_z),
        },
    }


def detect_anomalies_sliding_window(
    series: pd.Series,
    window_size: int = None,
    threshold: float = None,
) -> dict:
    """
    基于滑动窗口的异常检测
    对比当前窗口与历史基线的偏离
    """
    if window_size is None:
        window_size = ANOMALY_CONFIG["window_size"]
    if threshold is None:
        threshold = ANOMALY_CONFIG["z_score_threshold"]

    clean = series.dropna()
    if len(clean) < window_size * 2:
        return detect_anomalies_zscore(clean, threshold)

    # 前半部分作为基线
    baseline = clean.iloc[:len(clean) // 2]
    recent = clean.iloc[len(clean) // 2:]
    baseline_mean = baseline.mean()
    baseline_std = baseline.std()

    if baseline_std == 0:
        baseline_std = 1e-10

    recent_z = np.abs((recent - baseline_mean) / baseline_std)
    anomaly_mask = recent_z > threshold
    anomaly_indices = recent.index[anomaly_mask].tolist()

    # 计算偏离度
    deviation = abs(recent.mean() - baseline_mean) / baseline_std if baseline_std > 0 else 0

    return {
        "is_anomalous": len(anomaly_indices) > 0,
        "anomaly_score": min(float(deviation) / threshold, 1.0),
        "anomaly_indices": anomaly_indices,
        "baseline_mean": float(baseline_mean),
        "recent_mean": float(recent.mean()),
        "deviation": float(deviation),
    }


def detect_change_point(series: pd.Series) -> dict:
    """
    变化点检测 - 找到时序数据中的突变点
    使用 CUSUM (Cumulative Sum) 方法
    """
    clean = series.dropna().values
    if len(clean) < 20:
        return {"has_change_point": False, "change_point_index": -1}

    mean = np.mean(clean)
    cusum_pos = np.zeros(len(clean))
    cusum_neg = np.zeros(len(clean))

    for i in range(1, len(clean)):
        cusum_pos[i] = max(0, cusum_pos[i - 1] + clean[i] - mean - 0.5 * np.std(clean))
        cusum_neg[i] = min(0, cusum_neg[i - 1] + clean[i] - mean + 0.5 * np.std(clean))

    max_idx = int(np.argmax(cusum_pos))
    min_idx = int(np.argmin(cusum_neg))
    change_idx = max_idx if cusum_pos[max_idx] > abs(cusum_neg[min_idx]) else min_idx

    return {
        "has_change_point": True if max(cusum_pos[max_idx], abs(cusum_neg[min_idx])) > 5 * np.std(clean) else False,
        "change_point_index": change_idx,
        "cusum_max": float(cusum_pos[max_idx]),
        "cusum_min": float(cusum_neg[min_idx]),
    }


def compute_correlation_matrix(df: pd.DataFrame, columns: list[str] = None) -> pd.DataFrame:
    """计算指标间的相关性矩阵"""
    if columns:
        df = df[columns]
    return df.corr()


def find_correlated_metrics(
    df: pd.DataFrame,
    target_col: str,
    threshold: float = None,
) -> list[dict]:
    """
    找到与目标指标高相关的其他指标
    用于故障传播链分析
    """
    if threshold is None:
        threshold = ANOMALY_CONFIG["correlation_threshold"]

    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if target_col not in numeric_cols:
        return []

    correlations = []
    for col in numeric_cols:
        if col == target_col or col == "time":
            continue
        corr = df[target_col].corr(df[col])
        if abs(corr) >= threshold:
            correlations.append({
                "metric": col,
                "correlation": round(float(corr), 4),
                "direction": "positive" if corr > 0 else "negative",
            })

    correlations.sort(key=lambda x: abs(x["correlation"]), reverse=True)
    return correlations


def rank_root_causes(anomaly_results: dict) -> list[dict]:
    """
    根据异常检测结果对可能的根因进行排序
    采用 BARO 思路：基于异常分数进行排序
    """
    ranked = []
    for metric_name, result in anomaly_results.items():
        if result.get("is_anomalous"):
            ranked.append({
                "metric": metric_name,
                "anomaly_score": result.get("anomaly_score", 0),
                "stats": result.get("stats", {}),
            })

    ranked.sort(key=lambda x: x["anomaly_score"], reverse=True)
    return ranked
