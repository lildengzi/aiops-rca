"""
测试数据加载模块
"""
import pytest
from utils.data_loader import load_fault_data, get_all_services


class TestLoadFaultData:
    """测试故障数据加载"""

    def test_load_cpu_data(self):
        """测试加载CPU故障数据"""
        df = load_fault_data("cpu")
        assert df is not None
        assert len(df) > 0
        assert "time" in df.columns

    def test_load_all_fault_types(self, fault_types):
        """测试加载所有类型的故障数据"""
        for ft in fault_types:
            df = load_fault_data(ft)
            assert df is not None
            assert len(df) > 0

    def test_load_nonexistent_data(self):
        """测试加载不存在的数据"""
        with pytest.raises(Exception):
            load_fault_data("nonexistent")


class TestGetAllServices:
    """测试获取服务列表"""

    def test_get_services_from_cpu(self):
        """测试从CPU数据获取服务列表"""
        df = load_fault_data("cpu")
        services = get_all_services(df)
        assert isinstance(services, list)
        assert len(services) > 0

    def test_services_not_empty(self):
        """测试服务列表不为空"""
        df = load_fault_data("cpu")
        services = get_all_services(df)
        assert all(isinstance(s, str) for s in services)
        assert all(len(s) > 0 for s in services)

    def test_service_columns_exist(self):
        """测试服务对应的列存在"""
        df = load_fault_data("cpu")
        services = get_all_services(df)
        for svc in services:
            cols = [c for c in df.columns if c.startswith(f"{svc}_")]
            assert len(cols) > 0
