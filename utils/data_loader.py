"""
数据加载与预处理工具
优先级：实时数据缓存 > 经验库 CSV
"""
import pandas as pd
import numpy as np
from typing import Optional
from config import FAULT_DATA_MAP, METRIC_CATEGORIES

# 实时数据缓存：由 simulator/rca_adapter 的 inject_into_tools() 写入
# 工具层所有函数通过 load_fault_data() 自动获取实时数据
_realtime_cache: dict[str, pd.DataFrame] = {}


def set_realtime_data(fault_type: str, df: pd.DataFrame) -> None:
    """写入实时数据缓存（由 RCAAdapter.inject_into_tools() 调用）"""
    _realtime_cache[fault_type] = df


def get_realtime_data(fault_type: str) -> Optional[pd.DataFrame]:
    """读取实时数据缓存"""
    return _realtime_cache.get(fault_type)


def load_fault_data(fault_type: str) -> pd.DataFrame:
    """
    加载指定故障类型的数据。
    优先使用实时注入的数据；
    若无实时数据，则回退到经验库 CSV。
    """
    # 优先：实时数据缓存
    if fault_type in _realtime_cache and not _realtime_cache[fault_type].empty:
        return _realtime_cache[fault_type]

    # 回退：经验库 CSV
    path = FAULT_DATA_MAP.get(fault_type)
    if path is None:
        raise ValueError(f"未知故障类型: {fault_type}，可选: {list(FAULT_DATA_MAP.keys())}")
    df = pd.read_csv(path)
    # 有些数据集有两列 time，去重
    if df.columns.duplicated().any():
        df = df.loc[:, ~df.columns.duplicated()]
    return df


def parse_columns(df: pd.DataFrame) -> dict:
    """
    解析 DataFrame 列名，按服务和指标类型分组。
    返回: {service_name: {metric_type: [column_names]}}
    """
    result = {}
    for col in df.columns:
        if col == "time":
            continue
        parts = col.rsplit("_", 1)
        if len(parts) == 2:
            service, metric_suffix = parts
            metric_type = _classify_metric(metric_suffix, col)
            if service not in result:
                result[service] = {}
            if metric_type not in result[service]:
                result[service][metric_type] = []
            result[service][metric_type].append(col)
        else:
            for cat_type, suffixes in METRIC_CATEGORIES.items():
                for suffix in suffixes:
                    if col.endswith(f"_{suffix}"):
                        service = col[:col.rfind(f"_{suffix}")]
                        if service not in result:
                            result[service] = {}
                        if cat_type not in result[service]:
                            result[service][cat_type] = []
                        result[service][cat_type].append(col)
                        break
    return result


def _classify_metric(suffix: str, full_col: str) -> str:
    """对指标后缀进行分类"""
    suffix_lower = suffix.lower()
    if suffix_lower in ("cpu",):
        return "resource_cpu"
    elif suffix_lower in ("mem",):
        return "resource_mem"
    elif "latency" in suffix_lower:
        return "performance"
    elif suffix_lower in ("load", "workload"):
        return "traffic"
    elif suffix_lower in ("error",):
        return "error"
    else:
        return "other"


def get_service_metrics(
    df: pd.DataFrame,
    service: str,
    start_time: Optional[int] = None,
    end_time: Optional[int] = None,
) -> pd.DataFrame:
    """获取指定服务在指定时间范围内的所有指标"""
    cols = ["time"] + [c for c in df.columns if c.startswith(f"{service}_")]
    sub = df[cols].copy()
    if start_time is not None:
        sub = sub[sub["time"] >= start_time]
    if end_time is not None:
        sub = sub[sub["time"] <= end_time]
    return sub


def get_all_services(df: pd.DataFrame) -> list[str]:
    """提取数据中所有服务名"""
    services = set()
    for col in df.columns:
        if col == "time":
            continue
        for cat_suffixes in METRIC_CATEGORIES.values():
            for suffix in cat_suffixes:
                if col.endswith(f"_{suffix}"):
                    svc = col[:col.rfind(f"_{suffix}")]
                    services.add(svc)
                    break
        if "-" in col:
            base = col.split("_")
            if len(base) >= 2:
                svc_name = "_".join(base[:-1])
                if base[-1].startswith("latency"):
                    services.add(svc_name)
    for col in df.columns:
        for suf in ["_cpu", "_mem", "_error"]:
            if col.endswith(suf):
                services.add(col[: -len(suf)])
    services.discard("time")
    return sorted(services)

