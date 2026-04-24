"""
异常检测工具 - 基于统计方法的时序数据异常检测
实现多种检测方法：Z-Score、滑动窗口、相关性分析
"""
import numpy as np
import pandas as pd
from config import ANOMALY_CONFIG


def detect_anomalies_zscore(
    series: pd.Series,
    threshold: float = None,
) -> dict:
    """\brief 基于 Z-Score 的时序数据异常检测
    \details 计算每个数据点与均值的偏离标准差倍数，超过阈值的点标记为异常。
    异常分数 = max_z_score / threshold，最大为 1.0。
    \param series 时序数据序列（Pandas Series）
    \param threshold Z-Score 阈值，默认从配置读取
    \return 字典包含:
        - is_anomalous: 是否存在异常
        - anomaly_score: 整体异常分数 [0,1]
        - anomaly_indices: 异常点索引列表
        - anomaly_ratio: 异常点比例
        - stats: 统计信息（均值、标准差、最值、最大Z分数）"""
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
    """\brief 基于滑动窗口的异常检测
    \details 将序列分为前半基线、后半近期窗口，比较两部分的均值偏离。
    适用于检测趋势性漂移或突变。
    \param series 时序数据序列
    \param window_size 窗口大小（默认从配置读取，实际以 half-length 为准）
    \param threshold Z-Score 阈值
    \return 字典包含:
        - is_anomalous
        - anomaly_score
        - anomaly_indices
        - baseline_mean: 基线均值
        - recent_mean: 近期均值
        - deviation: 偏离度"""
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
    """\brief CUSUM 变化点检测
    \details 使用累积和（CUSUM）方法检测时序数据的突变点。
    分别计算正向和负向累积和，取最大偏离点作为候选变化点。
    \param series 时序数据序列
    \return 字典包含:
        - has_change_point: 是否存在显著变化点
        - change_point_index: 变化点索引
        - cusum_max: 正向 CUSUM 最大值
        - cusum_min: 负向 CUSUM 最小值"""
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
    """\brief 计算指定指标列间的 Pearson 相关系数矩阵
    \param df 指标数据 DataFrame
    \param columns 需要分析的列名列表（None 表示所有数值列）
    \return 相关系数矩阵 DataFrame"""
    if columns:
        df = df[columns]
    # Use min_periods=1 to avoid NaN when std=0, then fill NaN with 0
    corr = df.corr(min_periods=1)
    return corr.fillna(0.0)


def find_correlated_metrics(
    df: pd.DataFrame,
    target_col: str,
    threshold: float = None,
) -> list[dict]:
    """\brief 找出与目标指标高度相关的其他指标
    \details 计算目标列与所有数值列的 Pearson 相关系数，
    返回绝对值超过阈值的指标列表，用于故障传播分析。
    \param df 指标数据 DataFrame
    \param target_col 目标指标列名
    \param threshold 相关性阈值 (0-1)，默认从配置读取
    \return 相关指标列表，每项含 metric、correlation、direction"""
    if threshold is None:
        threshold = ANOMALY_CONFIG["correlation_threshold"]

    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if target_col not in numeric_cols:
        return []

    correlations = []
    for col in numeric_cols:
        if col == target_col or col == "time":
            continue
        try:
            # Check if either column has zero variance
            if df[target_col].std() == 0 or df[col].std() == 0:
                corr = 0.0
            else:
                corr = df[target_col].corr(df[col])
                if pd.isna(corr):
                    corr = 0.0
        except Exception:
            corr = 0.0
        if abs(corr) >= threshold:
            correlations.append({
                "metric": col,
                "correlation": round(float(corr), 4),
                "direction": "positive" if corr > 0 else "negative",
            })

    correlations.sort(key=lambda x: abs(x["correlation"]), reverse=True)
    return correlations


def rank_root_causes(anomaly_results: dict) -> list[dict]:
    """\brief 根据异常检测结果对可能的根因进行排序
    \details 采用 BARO（基于异常分数）思路，按 anomaly_score 降序排列。
    \param anomaly_results 异常检测结果字典 {metric_name: result_dict}
    \return 排序后的根因列表，每项含 metric、anomaly_score、stats"""
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
