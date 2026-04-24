"""
测试 tools 模块的核心逻辑
覆盖：metric/log/trace 工具基本行为，RCA 分类
"""
import pytest
import json
import pandas as pd
from unittest.mock import patch, MagicMock


class TestMetricTools:
    """测试指标工具"""

    @patch("tools.metric_tools.load_fault_data")
    def test_query_service_metrics_valid(self, mock_load):
        """测试查询有效服务的指标"""
        # 模拟数据
        df = pd.DataFrame({
            "time": [1, 2, 3],
            "frontend_cpu": [1, 2, 3],
            "frontend_latency": [4, 5, 6],
        })
        mock_load.return_value = df

        from tools.metric_tools import query_service_metrics
        result_str = query_service_metrics.invoke({
            "fault_type": "unknown",
            "service_name": "frontend",
            "metric_type": "all",
        })
        result = json.loads(result_str)
        assert result["status"] == "success", f"查询失败: {result}"
        assert result["service"] == "frontend"
        assert len(result["metrics"]) == 2, "应返回2个指标"

    @patch("tools.metric_tools.load_fault_data")
    def test_query_service_metrics_invalid_service(self, mock_load):
        """测试查询无效服务"""
        df = pd.DataFrame({"time": [1], "frontend_cpu": [1]})
        mock_load.return_value = df

        from tools.metric_tools import query_service_metrics
        result_str = query_service_metrics.invoke({
            "fault_type": "unknown",
            "service_name": "unknown_service",
        })
        result = json.loads(result_str)
        assert result["status"] == "failure", "应返回失败"

    @patch("tools.metric_tools.load_fault_data")
    def test_rca_classification(self, mock_load):
        """测试 RCA 分类（根因/放大器/受害者）"""
        # 模拟高异常分数
        df = pd.DataFrame({
            "time": range(100),
            "frontend_cpu": [100] * 100,  # 异常值
        })
        mock_load.return_value = df

        from tools.metric_tools import query_service_metrics
        with patch("utils.anomaly_detection.detect_anomalies_zscore") as mock_anomaly:
            mock_anomaly.return_value = {"is_anomalous": True, "anomaly_score": 0.9}
            result_str = query_service_metrics.invoke({
                "fault_type": "unknown",
                "service_name": "frontend",
            })
            result = json.loads(result_str)
            assert result.get("rca_classification") == "root_cause_candidate", "高分数应为根因候选"


class TestLogTools:
    """测试日志工具"""

    @patch("tools.log_tools.load_fault_data")
    def test_query_service_logs_valid(self, mock_load):
        """测试查询有效服务的日志"""
        df = pd.DataFrame({
            "time": [1, 2, 3],
            "frontend_cpu": [1, 2, 3],
        })
        mock_load.return_value = df

        from tools.log_tools import query_service_logs
        result_str = query_service_logs.invoke({
            "fault_type": "unknown",
            "service_name": "frontend",
        })
        result = json.loads(result_str)
        assert result["status"] == "success", f"查询失败: {result}"
        assert result["agent_type"] == "log"

    @patch("tools.log_tools.load_fault_data")
    def test_rca_classification_logs(self, mock_load):
        """测试日志 RCA 分类"""
        df = pd.DataFrame({
            "time": range(100),
            "frontend_cpu": [100] * 100,
        })
        mock_load.return_value = df

        from tools.log_tools import query_service_logs
        with patch("utils.anomaly_detection.detect_anomalies_zscore") as mock_anomaly:
            mock_anomaly.return_value = {"is_anomalous": True, "anomaly_score": 0.9}
            result_str = query_service_logs.invoke({
                "fault_type": "unknown",
                "service_name": "frontend",
            })
            result = json.loads(result_str)
            assert result.get("rca_classification") == "root_cause_candidate", "高分数应为根因候选"


class TestTraceTools:
    """测试链路工具"""

    @patch("tools.trace_tools.load_fault_data")
    def test_analyze_call_chain_rca(self, mock_load):
        """测试分析调用链的 RCA 分类"""
        df = pd.DataFrame({
            "time": range(100),
            "frontend_cpu": [100] * 100,
            "cartservice_mem": [90] * 100,
        })
        mock_load.return_value = df

        from tools.trace_tools import analyze_call_chain
        with patch("utils.anomaly_detection.detect_anomalies_zscore") as mock_anomaly:
            mock_anomaly.return_value = {"is_anomalous": True, "anomaly_score": 0.9}
            result_str = analyze_call_chain.invoke({"fault_type": "unknown"})
            result = json.loads(result_str)
            assert result["status"] == "success"
            # 应返回 RCA 分类
            assert "rca_classification" in result, "应返回 RCA 分类"

    @patch("tools.trace_tools.load_fault_data")
    def test_query_service_traces_rca(self, mock_load):
        """测试查询调用链的 RCA 标记"""
        df = pd.DataFrame({
            "time": range(100),
            "frontend_cpu": [100] * 100,
        })
        mock_load.return_value = df

        from tools.trace_tools import query_service_traces
        with patch("utils.anomaly_detection.detect_anomalies_zscore") as mock_anomaly:
            mock_anomaly.return_value = {"is_anomalous": True, "anomaly_score": 0.9}
            result_str = query_service_traces.invoke({
                "fault_type": "unknown",
                "service_name": "frontend",
            })
            result = json.loads(result_str)
            assert result["status"] == "success"
            assert "rca_summary" in result, "应返回 RCA 汇总"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
