"""
服务解析器 - 封装服务名和指标解析逻辑
动态模式：
  - 不依赖固定指标名白名单
  - 列名遵循 {service}_{metric} 格式
  - service 必须存在于 config.SERVICE_TOPOLOGY
  - metric 可为任意非空字符串
"""
import pandas as pd
from typing import Optional
from config import SERVICE_TOPOLOGY


def _parse_column(col: str) -> tuple[str, str] | None:
    """尝试解析列名为 (service, metric) 对
    从列名开头匹配已知服务名，剩余部分作为 metric
    """
    valid_services = set(SERVICE_TOPOLOGY.keys())
    for svc in valid_services:
        prefix = f"{svc}_"
        if col.startswith(prefix):
            metric = col[len(prefix):]
            if metric:
                return (svc, metric)
    return None


class ServiceParser:
    """封装服务名和指标解析逻辑"""

    @staticmethod
    def parse_columns(df: pd.DataFrame) -> dict:
        """解析 DataFrame 列名，按服务和指标分组
        支持任意指标名，只要符合 {service}_{metric} 格式且 service 合法
        \\param df 包含时序指标数据的 DataFrame
        \\return 嵌套字典 {service_name: {metric_name: [column_names]}}
        """
        result = {}

        for col in df.columns:
            if col == "time":
                continue

            parsed = _parse_column(col)
            if parsed is None:
                continue

            service, metric = parsed
            if service not in result:
                result[service] = {}
            if metric not in result[service]:
                result[service][metric] = []
            result[service][metric].append(col)

        return result

    @staticmethod
    def get_all_services(df: pd.DataFrame) -> list[str]:
        """从 DataFrame 列名中提取实际出现的服务名
        \\param df 指标数据 DataFrame
        \\return 排序后的服务名列表（仅包含 SERVICE_TOPOLOGY 中的合法节点）
        """
        services = set()

        for col in df.columns:
            if col == "time":
                continue

            parsed = _parse_column(col)
            if parsed is not None:
                service, _ = parsed
                services.add(service)

        return sorted(services)

    @staticmethod
    def get_service_metrics_detail(df: pd.DataFrame, service: str) -> dict:
        """获取指定服务的所有指标详细信息
        \\param df 指标数据 DataFrame
        \\param service 服务名
        \\return {metric_name: [column_names], ...}
        """
        parsed = ServiceParser.parse_columns(df)
        return parsed.get(service, {})

    @staticmethod
    def get_metrics_for_service(df: pd.DataFrame, service: str) -> list[str]:
        """获取指定服务的所有指标列名
        \\param df 指标数据 DataFrame
        \\param service 服务名
        \\return 该服务的所有指标列名列表
        """
        return [c for c in df.columns if c.startswith(f"{service}_") and c != "time"]


def get_service_metrics(
    df: pd.DataFrame,
    service: str,
    start_time: Optional[int] = None,
    end_time: Optional[int] = None,
) -> pd.DataFrame:
    """获取指定服务在指定时间范围内的所有指标
    \\param df 指标数据 DataFrame
    \\param service 目标服务名
    \\param start_time 起始时间戳（可选）
    \\param end_time 结束时间戳（可选）
    \\return 筛选后的服务指标子集 DataFrame
    """
    cols = ["time"] + [c for c in df.columns if c.startswith(f"{service}_")]
    sub = df[cols].copy()
    if start_time is not None:
        sub = sub[sub["time"] >= start_time]
    if end_time is not None:
        sub = sub[sub["time"] <= end_time]
    return sub
