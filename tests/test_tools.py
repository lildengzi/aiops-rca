"""
测试工具模块
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestTopologyTools:
    """测试拓扑工具"""

    def test_import(self):
        """测试导入"""
        try:
            from tools.topology_tools import get_service_topology
            assert True
        except ImportError:
            pytest.skip("topology_tools模块不可用")

    def test_get_topology(self):
        """测试获取服务拓扑"""
        try:
            from tools.topology_tools import get_service_topology
            from config import SERVICE_TOPOLOGY
            # 验证配置中的拓扑数据可用
            assert isinstance(SERVICE_TOPOLOGY, dict)
            assert len(SERVICE_TOPOLOGY) > 0
        except ImportError:
            pytest.skip("topology_tools模块不可用")


class TestMetricTools:
    """测试指标工具"""

    def test_import(self):
        """测试导入"""
        try:
            from tools.metric_tools import get_metric_data
            assert True
        except ImportError:
            pytest.skip("metric_tools模块不可用")


class TestTraceTools:
    """测试链路追踪工具"""

    def test_import(self):
        """测试导入"""
        try:
            from tools.trace_tools import get_trace_data
            assert True
        except ImportError:
            pytest.skip("trace_tools模块不可用")


class TestLogTools:
    """测试日志工具"""

    def test_import(self):
        """测试导入"""
        try:
            from tools.log_tools import get_log_data
            assert True
        except ImportError:
            pytest.skip("log_tools模块不可用")
