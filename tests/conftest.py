"""
测试配置和公共fixtures
"""
import sys
import os
import pytest

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

@pytest.fixture
def fault_types():
    """支持的故障类型"""
    return ["cpu", "mem", "delay", "disk", "loss"]

@pytest.fixture
def sample_fault_type():
    """示例故障类型"""
    return "cpu"
