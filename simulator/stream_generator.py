"""
实时数据流生成器
模拟真实的微服务指标波动，支持故障注入
"""
import numpy as np
import pandas as pd
import time
import random
from dataclasses import dataclass
from typing import Optional

# 所有服务列表（与 config.py 中保持一致）
SERVICES = [
    "frontend", "cartservice", "checkoutservice", "recommendationservice",
    "productcatalogservice", "currencyservice", "paymentservice",
    "shippingservice", "emailservice", "adservice", "redis", "main",
]

# 每个服务的基线指标（正常状态）
BASELINE = {
    "frontend":              {"cpu": 25, "mem": 40, "latency": 80,  "load": 500, "error": 0.01},
    "cartservice":           {"cpu": 15, "mem": 30, "latency": 20,  "load": 200, "error": 0.005},
    "checkoutservice":       {"cpu": 20, "mem": 35, "latency": 150, "load": 100, "error": 0.01},
    "recommendationservice": {"cpu": 10, "mem": 25, "latency": 30,  "load": 300, "error": 0.005},
    "productcatalogservice": {"cpu": 12, "mem": 28, "latency": 15,  "load": 600, "error": 0.003},
    "currencyservice":       {"cpu": 5,  "mem": 15, "latency": 5,   "load": 400, "error": 0.001},
    "paymentservice":        {"cpu": 8,  "mem": 20, "latency": 50,  "load": 80,  "error": 0.005},
    "shippingservice":       {"cpu": 7,  "mem": 18, "latency": 25,  "load": 150, "error": 0.003},
    "emailservice":          {"cpu": 3,  "mem": 12, "latency": 100, "load": 50,  "error": 0.002},
    "adservice":             {"cpu": 18, "mem": 35, "latency": 40,  "load": 800, "error": 0.01},
    "redis":                 {"cpu": 10, "mem": 60, "latency": 2,   "load": 1000,"error": 0.001},
    "main":                  {"cpu": 30, "mem": 50, "latency": 10,  "load": 200, "error": 0.0},
}

# 故障类型对应的注入参数
FAULT_PROFILES = {
    "cpu": {
        "description": "CPU 资源耗尽故障",
        "root_cause_service": "adservice",
        "affected_services": ["adservice", "frontend", "recommendationservice"],
        "metric_overrides": {
            "adservice":             {"cpu": (92, 99), "latency": (800, 3000), "error": (0.3, 0.8)},
            "frontend":              {"cpu": (60, 80), "latency": (500, 1500), "error": (0.1, 0.3)},
            "recommendationservice": {"cpu": (50, 70), "latency": (300, 800),  "error": (0.05, 0.2)},
        },
    },
    "delay": {
        "description": "服务延迟异常故障",
        "root_cause_service": "productcatalogservice",
        "affected_services": ["productcatalogservice", "checkoutservice", "recommendationservice", "frontend"],
        "metric_overrides": {
            "productcatalogservice": {"latency": (2000, 8000), "cpu": (60, 80), "error": (0.1, 0.4)},
            "checkoutservice":       {"latency": (1500, 5000), "error": (0.15, 0.5)},
            "recommendationservice": {"latency": (1000, 3000), "error": (0.05, 0.2)},
            "frontend":              {"latency": (800, 2000),  "error": (0.05, 0.15)},
        },
    },
    "disk": {
        "description": "磁盘 I/O 异常故障",
        "root_cause_service": "main",
        "affected_services": ["main", "redis", "cartservice"],
        "metric_overrides": {
            "main":        {"cpu": (70, 90), "latency": (500, 2000), "error": (0.2, 0.6)},
            "redis":       {"latency": (100, 800),  "cpu": (40, 70),  "error": (0.1, 0.3)},
            "cartservice": {"latency": (200, 1000), "error": (0.1, 0.4)},
        },
    },
    "loss": {
        "description": "网络丢包故障",
        "root_cause_service": "main",
        "affected_services": ["main", "frontend", "checkoutservice", "paymentservice"],
        "metric_overrides": {
            "main":            {"error": (0.3, 0.7), "latency": (200, 1000)},
            "frontend":        {"error": (0.2, 0.5), "latency": (300, 1200), "load": (50, 150)},
            "checkoutservice": {"error": (0.25, 0.6), "latency": (400, 1500)},
            "paymentservice":  {"error": (0.2, 0.5), "latency": (300, 1000)},
        },
    },
    "mem": {
        "description": "内存泄漏 / OOM 故障",
        "root_cause_service": "checkoutservice",
        "affected_services": ["checkoutservice", "cartservice", "paymentservice", "frontend"],
        "metric_overrides": {
            "checkoutservice": {"mem": (88, 99), "cpu": (70, 90), "latency": (1000, 4000), "error": (0.2, 0.6)},
            "cartservice":     {"mem": (80, 95), "latency": (500, 2000), "error": (0.1, 0.3)},
            "paymentservice":  {"mem": (70, 90), "latency": (400, 1500), "error": (0.1, 0.25)},
            "frontend":        {"latency": (300, 1000), "error": (0.05, 0.15)},
        },
    },
}


@dataclass
class MetricSnapshot:
    """一个时间点的所有服务指标快照"""
    timestamp: float
    metrics: dict  # {service: {metric: value}}
    fault_active: bool = False
    fault_type: Optional[str] = None
    fault_progress: float = 0.0  # 0~1，故障发展进度


class RealtimeStreamGenerator:
    """
    实时数据流生成器
    - 正常状态：基线 + 随机高斯抖动
    - 故障状态：渐进式异常注入（模拟真实故障发展）
    """

    def __init__(self, fault_type: str = "cpu", fault_delay: float = 15.0, tick_interval: float = 1.0):
        """
        Args:
            fault_type: 要注入的故障类型
            fault_delay: 正常运行多少秒后开始注入故障
            tick_interval: 每次采样间隔秒数
        """
        self.fault_type = fault_type
        self.fault_delay = fault_delay
        self.tick_interval = tick_interval
        self.start_time = time.time()
        self.tick_count = 0
        self._noise_seeds = {
            svc: np.random.RandomState(abs(hash(svc)) % (2**31))
            for svc in SERVICES
        }

    @property
    def elapsed(self) -> float:
        return time.time() - self.start_time

    @property
    def fault_active(self) -> bool:
        return self.elapsed >= self.fault_delay

    @property
    def fault_progress(self) -> float:
        """故障发展进度（0~1），10秒内从0爬升到1"""
        if not self.fault_active:
            return 0.0
        return min(1.0, (self.elapsed - self.fault_delay) / 10.0)

    def _base_noise(self, service: str, base_val: float, noise_ratio: float = 0.05) -> float:
        """为指定服务生成带噪声的基线值"""
        rng = self._noise_seeds[service]
        noise = float(rng.normal(0, base_val * noise_ratio + 0.001))
        t = self.elapsed
        wave = base_val * 0.08 * np.sin(2 * np.pi * t / 60)
        return max(0.0, base_val + noise + wave)

    def _get_metric_value(self, service: str, metric: str) -> float:
        """计算当前时刻某服务某指标的值"""
        base = BASELINE[service][metric]
        normal_val = self._base_noise(service, base)

        if not self.fault_active:
            return normal_val

        profile = FAULT_PROFILES[self.fault_type]
        overrides = profile["metric_overrides"]

        if service not in overrides or metric not in overrides[service]:
            return normal_val

        lo, hi = overrides[service][metric]
        target = random.uniform(lo, hi)
        progress = self.fault_progress
        jitter = random.uniform(-0.03, 0.03) * target
        anomalous_val = normal_val + (target - normal_val) * progress + jitter

        if metric in ("cpu", "mem"):
            return min(100.0, max(0.0, anomalous_val))
        elif metric == "error":
            return min(1.0, max(0.0, anomalous_val))
        else:
            return max(0.0, anomalous_val)

    def next_snapshot(self) -> MetricSnapshot:
        """生成下一个时间点的快照"""
        self.tick_count += 1
        metrics = {}
        for svc in SERVICES:
            metrics[svc] = {}
            for m in BASELINE[svc]:
                metrics[svc][m] = round(self._get_metric_value(svc, m), 3)

        return MetricSnapshot(
            timestamp=time.time(),
            metrics=metrics,
            fault_active=self.fault_active,
            fault_type=self.fault_type if self.fault_active else None,
            fault_progress=self.fault_progress,
        )

    def to_dataframe(self, snapshots: list) -> pd.DataFrame:
        """
        将一批快照转换为 DataFrame，格式与原始 data/*.csv 一致
        供工具层直接使用
        """
        rows = []
        for snap in snapshots:
            row = {"time": int(snap.timestamp)}
            for svc in SERVICES:
                for m, v in snap.metrics[svc].items():
                    row[f"{svc}_{m}"] = v
            rows.append(row)
        return pd.DataFrame(rows)

    def get_alert_services(self, snapshot: MetricSnapshot, threshold_cpu=80, threshold_error=0.1) -> list:
        """从快照中提取告警服务列表"""
        alerts = []
        for svc, m in snapshot.metrics.items():
            reasons = []
            if m["cpu"] > threshold_cpu:
                reasons.append(f"CPU {m['cpu']:.1f}%")
            if m["error"] > threshold_error:
                reasons.append(f"错误率 {m['error']*100:.1f}%")
            if m["latency"] > 1000:
                reasons.append(f"延迟 {m['latency']:.0f}ms")
            if m["mem"] > 85:
                reasons.append(f"内存 {m['mem']:.1f}%")
            if reasons:
                alerts.append({"service": svc, "reasons": reasons})
        return alerts
