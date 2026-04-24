"""
测试异常检测模块
"""
import pytest
import pandas as pd
import numpy as np
from utils.anomaly_detection import (
    detect_anomalies_zscore,
    detect_anomalies_sliding_window,
    detect_change_point,
    find_correlated_metrics,
    rank_root_causes,
)


class TestDetectAnomaliesZScore:
    """测试Z-Score异常检测"""

    def test_normal_series(self):
        """测试正常序列"""
        series = pd.Series(np.random.normal(0, 1, 100))
        result = detect_anomalies_zscore(series)
        assert "is_anomalous" in result
        assert "anomaly_score" in result
        assert "stats" in result

    def test_anomalous_series(self):
        """测试包含异常的序列"""
        series = pd.Series(np.random.normal(0, 1, 100))
        series.iloc[50:55] = 10  # 注入异常
        result = detect_anomalies_zscore(series)
        assert isinstance(result["is_anomalous"], bool)
        assert 0 <= result["anomaly_score"] <= 1

    def test_empty_series(self):
        """测试空序列"""
        series = pd.Series([], dtype=float)
        result = detect_anomalies_zscore(series)
        assert result["is_anomalous"] is False


class TestDetectChangePoint:
    """测试变化点检测"""

    def test_series_with_change(self):
        """测试包含变化点的序列"""
        series = pd.Series(np.concatenate([np.ones(50), np.ones(50) * 3]))
        result = detect_change_point(series)
        assert "has_change_point" in result
        assert "change_point_index" in result

    def test_normal_series(self):
        """测试正常序列"""
        series = pd.Series(np.random.normal(0, 1, 100))
        result = detect_change_point(series)
        assert "has_change_point" in result


class TestFindCorrelatedMetrics:
    """测试相关性分析"""

    def test_correlated_metrics(self):
        """测试查找相关指标"""
        np.random.seed(42)
        df = pd.DataFrame({
            "time": range(100),
            "svc1_cpu": np.random.normal(0, 1, 100),
            "svc1_mem": np.random.normal(0, 1, 100),
            "svc2_cpu": np.random.normal(0, 1, 100),
        })
        # 制造相关性
        df["svc1_cpu_corr"] = df["svc1_cpu"] + np.random.normal(0, 0.1, 100)

        result = find_correlated_metrics(df, "svc1_cpu", threshold=0.5)
        assert isinstance(result, list)

    def test_no_correlation(self):
        """测试无相关指标"""
        np.random.seed(42)
        df = pd.DataFrame({
            "time": range(100),
            "svc1_cpu": np.random.normal(0, 1, 100),
            "svc1_mem": np.random.normal(0, 1, 100),
        })
        result = find_correlated_metrics(df, "svc1_cpu", threshold=0.9)
        assert isinstance(result, list)


class TestRankRootCauses:
    """测试根因排序"""

    def test_rank_anomalies(self):
        """测试异常排序"""
        anomalies = {
            "svc1_cpu": {
                "is_anomalous": True,
                "anomaly_score": 0.9,
                "stats": {"mean": 80, "max": 95}
            },
            "svc2_mem": {
                "is_anomalous": True,
                "anomaly_score": 0.7,
                "stats": {"mean": 70, "max": 85}
            }
        }
        result = rank_root_causes(anomalies)
        assert isinstance(result, list)
        assert len(result) > 0
        # 验证按分数降序排列
        if len(result) > 1:
            assert result[0]["anomaly_score"] >= result[1]["anomaly_score"]

    def test_empty_anomalies(self):
        """测试空异常字典"""
        result = rank_root_causes({})
        assert result == []
