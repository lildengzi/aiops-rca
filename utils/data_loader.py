"""
数据加载与预处理工具
优先级：实时数据缓存 > 经验库 CSV

模块拆分：
- csv_processor.py: CSVProcessor - CSV处理、验证、故障类型推断
- service_parser.py: ServiceParser - 服务名与指标解析
- data_loader.py: 实时缓存管理 + 主入口函数
"""
import os
import pandas as pd
from typing import Optional
from config import FAULT_DATA_MAP

from .csv_processor import CSVProcessor
from .service_parser import ServiceParser, get_service_metrics


# ========= 实时数据缓存管理器 =========
class _RealtimeCacheManager:
    """管理实时数据缓存，封装全局状态"""

    def __init__(self):
        self._cache: dict[str, pd.DataFrame] = {}

    def set(self, fault_type: str, df: pd.DataFrame) -> None:
        """写入缓存"""
        self._cache[fault_type] = df

    def get(self, fault_type: str) -> Optional[pd.DataFrame]:
        """读取缓存"""
        return self._cache.get(fault_type)

    def pop(self, fault_type: str) -> Optional[pd.DataFrame]:
        """移除指定类型缓存"""
        return self._cache.pop(fault_type, None)

    def clear(self) -> None:
        """清空所有缓存"""
        self._cache.clear()

    def items(self):
        """返回缓存项"""
        return self._cache.items()

    def is_empty(self, fault_type: str) -> bool:
        """检查指定类型缓存是否为空"""
        df = self.get(fault_type)
        return df is None or df.empty


# 全局缓存管理器实例
_cache_manager = _RealtimeCacheManager()


# ========= 公开API函数 =========
def set_realtime_data(fault_type: str, df: pd.DataFrame) -> None:
    """\\brief 写入实时数据缓存（由 RCAAdapter.inject_into_tools() 调用）
    \\param fault_type 故障类型标签（用于缓存索引，不影响数据解析）
    \\param df 包含时序指标的 Pandas DataFrame"""
    _cache_manager.set(fault_type, df)


def get_realtime_data(fault_type: str) -> Optional[pd.DataFrame]:
    """\\brief 读取实时数据缓存
    \\param fault_type 故障类型
    \\return 缓存的 DataFrame，不存在则返回 None"""
    return _cache_manager.get(fault_type)


def inject_csv_as_realtime(file_path: str, fault_type: str = None) -> tuple[bool, str, Optional[pd.DataFrame]]:
    """\\brief 将CSV文件作为实时数据注入
    严格要求 time 列存在，不做 timestamp/ts 兼容
    \\param file_path CSV文件路径或文件对象
    \\param fault_type 指定故障类型标签（可选，不影响数据解析）
    \\return (成功标志, 消息, DataFrame)
    """
    try:
        if hasattr(file_path, 'read'):
            df = pd.read_csv(file_path)
        else:
            df = pd.read_csv(file_path)

        if df.empty:
            return False, "CSV文件为空", None

        # 验证CSV格式（严格要求 time 列，不兼容其他名称）
        is_valid, errors = CSVProcessor.validate_format(df)
        if not is_valid:
            return False, f"CSV格式验证失败: {'; '.join(errors)}", None

        # 严格要求 time 列存在（已由 validate_format 保证）
        df = CSVProcessor.preprocess(df)

        # fault_type 仅作为缓存标签，不影响数据解析
        if fault_type is None:
            fault_type = CSVProcessor.infer_fault_type(df)
            if fault_type == "unknown":
                fault_type = "unknown"

        set_realtime_data(fault_type, df)
        return True, f"成功注入{fault_type}类型数据，共{len(df)}行", df

    except Exception as e:
        return False, f"注入失败: {str(e)}", None


def list_realtime_data() -> dict[str, dict]:
    """\\brief 列出所有实时缓存数据的信息
    \\return {fault_type: {"rows": 行数, "columns": 列数, "time_range": (start, end), "services": {...}}}
    """
    result = {}
    for fault_type, df in _cache_manager.items():
        if df.empty:
            continue

        services = ServiceParser.get_all_services(df)
        service_stats = {}
        for svc in services:
            svc_cols = [c for c in df.columns if c.startswith(f"{svc}_")]
            service_stats[svc] = {
                "metric_count": len(svc_cols),
                "columns": svc_cols,
            }

        result[fault_type] = {
            "rows": len(df),
            "columns": len(df.columns),
            "time_range": (
                int(df["time"].min()) if "time" in df.columns else None,
                int(df["time"].max()) if "time" in df.columns else None,
            ),
            "services": service_stats,
        }
    return result


def clear_realtime_cache(fault_type: str = None) -> None:
    """\\brief 清理实时数据缓存
    \\param fault_type 指定故障类型，为None则清理所有"""
    if fault_type:
        _cache_manager.pop(fault_type)
    else:
        _cache_manager.clear()


def load_fault_data(fault_type: str) -> pd.DataFrame:
    """\\brief 加载指定标签的数据（优先级：实时缓存 > CSV 文件 > 自动扫描）
    \\param fault_type 数据标签或文件路径
    \\return 包含指标数据的 Pandas DataFrame
    \\throw ValueError 当所有加载方式都失败时"""
    # 优先：实时数据缓存
    if not _cache_manager.is_empty(fault_type):
        return _cache_manager.get(fault_type)

    # 尝试1：经验库 CSV（fault_type 作为键）
    path = FAULT_DATA_MAP.get(fault_type)
    if path is not None:
        df = pd.read_csv(path)
        if df.columns.duplicated().any():
            df = df.loc[:, ~df.columns.duplicated()]
        return df

    # 尝试2：fault_type 作为文件路径直接加载
    if os.path.exists(fault_type):
        df = pd.read_csv(fault_type)
        if df.columns.duplicated().any():
            df = df.loc[:, ~df.columns.duplicated()]
        return df

    # 尝试3：自动扫描 data/ 目录，加载第一个可用的 CSV
    data_dir = DATA_DIR
    if os.path.isdir(data_dir):
        csv_files = [f for f in os.listdir(data_dir) if f.endswith('.csv')]
        if csv_files:
            # 优先使用与 fault_type 相关的文件，否则用第一个
            matched = [f for f in csv_files if fault_type.lower() in f.lower()]
            target = matched[0] if matched else csv_files[0]
            path = os.path.join(data_dir, target)
            df = pd.read_csv(path)
            if df.columns.duplicated().any():
                df = df.loc[:, ~df.columns.duplicated()]
            return df

    # 所有尝试都失败，抛出友好错误
    available = list(FAULT_DATA_MAP.keys()) + [f for f in os.listdir(data_dir) if f.endswith('.csv')] if os.path.isdir(data_dir) else []
    raise ValueError(
        f"无法加载数据: '{fault_type}'。可用选项: {available}。"
        f"请使用 --fault 参数指定（如 cpu/delay/disk/loss/mem），或确保 data/ 目录有 CSV 文件。"
    )


def parse_columns(df: pd.DataFrame) -> dict:
    """\\brief 解析 DataFrame 列名，按服务和指标分组（委托给 ServiceParser）
    \\param df 包含时序指标数据的 DataFrame
    \\return 嵌套字典 {service_name: {metric_name: [column_names]}}"""
    return ServiceParser.parse_columns(df)


def get_all_services(df: pd.DataFrame) -> list[str]:
    """\\brief 从 DataFrame 列名中提取所有服务名（委托给 ServiceParser）
    \\param df 指标数据 DataFrame
    \\return 排序后的服务名列表"""
    return ServiceParser.get_all_services(df)


# get_service_metrics 直接从 service_parser 导入
# 已通过: from .service_parser import get_service_metrics
