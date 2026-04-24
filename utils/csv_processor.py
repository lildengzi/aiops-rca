"""
CSV 处理器 - 封装CSV相关的处理、验证和推断逻辑
严格模式：
  - 时间列固定为 `time`，不兼容 timestamp/ts 等别名
  - 指标列必须遵循 {service}_{metric} 格式
  - service 必须存在于 config.SERVICE_TOPOLOGY
  - metric 只需非空，不做固定枚举
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


class CSVProcessor:
    """封装CSV相关的处理、验证和推断逻辑"""

    @staticmethod
    def preprocess(df: pd.DataFrame) -> pd.DataFrame:
        """预处理CSV数据：去重、确保 time 列为数值型"""
        df = df.copy()

        if df.columns.duplicated().any():
            df = df.loc[:, ~df.columns.duplicated()]

        if "time" in df.columns and not pd.api.types.is_numeric_dtype(df["time"]):
            try:
                df["time"] = pd.to_numeric(df["time"])
            except Exception:
                pass

        return df

    @staticmethod
    def infer_fault_type(df: pd.DataFrame) -> str:
        """从数据列名推断故障类型（兼容逻辑，已降级）
        不再用于核心分析，仅作为缓存标签参考，无法可靠推断时返回 "unknown"
        """
        # 仅做简单关键词匹配作为缓存标签，不驱动核心逻辑
        columns_str = " ".join(df.columns).lower()
        for keyword, ftype in [
            ("cpu", "cpu"), ("mem", "mem"), ("memory", "mem"),
            ("latency", "delay"), ("delay", "delay"),
            ("disk", "disk"), ("io", "disk"),
            ("loss", "loss"), ("packet", "loss"), ("net", "loss"),
        ]:
            if keyword in columns_str:
                return ftype
        return "unknown"

    @staticmethod
    def validate_format(df: pd.DataFrame) -> tuple[bool, list[str]]:
        """验证CSV格式是否符合要求
        \\param df 待验证的 DataFrame
        \\return (是否有效, 错误信息列表)
        """
        errors = []

        if df.columns.duplicated().any():
            df = df.loc[:, ~df.columns.duplicated()]

        if "time" not in df.columns:
            errors.append("缺少必需列: time")
            return False, errors

        try:
            pd.to_numeric(df["time"])
        except Exception:
            errors.append("time 列无法转换为数值型时间戳")

        metric_cols = [c for c in df.columns if c != "time"]
        if not metric_cols:
            errors.append("没有找到任何服务指标列（除 time 外至少应有 1 个指标列）")
            return False, errors

        invalid_cols = []
        invalid_services = []

        for col in metric_cols:
            parsed = _parse_column(col)
            if parsed is None:
                invalid_cols.append(f"{col}（无法解析为 {{service}}_{{metric}} 格式，或 service 不在 SERVICE_TOPOLOGY 中）")
                continue
            service, metric = parsed
            if not metric or not metric.strip():
                invalid_cols.append(f"{col}（metric 部分不能为空）")

        if invalid_cols:
            errors.append(f"以下列名格式不正确（前5个）: {', '.join(invalid_cols[:5])}")

        return len(errors) == 0, errors
