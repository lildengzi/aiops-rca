"""
日志查询工具 - 模拟 Log MCP / SLS 服务
基于指标异常数据生成模拟日志，适配动态服务集合
增强 RCA 支持：输出错误模式的根因/放大器/受害者分类
"""
import json
import random
import hashlib
import os
import glob
from datetime import datetime
from langchain_core.tools import tool
from utils.data_loader import load_fault_data, get_all_services
from utils.service_parser import ServiceParser
from utils.anomaly_detection import detect_anomalies_zscore


# 日志模板库（通用，不依赖固定故障类型）
ERROR_TEMPLATES_GENERIC = [
    "java.lang.OutOfMemoryError: {detail}",
    "High resource usage detected: {metric}={value}, threshold exceeded",
    "Request timeout after {duration}ms to {target_service}",
    "Connection refused: {host}:{port}",
    "HTTP 500 Internal Server Error: {path}",
    "Thread pool exhausted: active={active}, max={max}",
    "Circuit breaker triggered for {target_service}: failure rate={rate}%",
    "Process {pid} consuming excessive resources",
    "Latency spike detected: p99={duration}ms",
    "Error rate elevated: {rate}% on {metric}",
]

WARN_TEMPLATES = [
    "Connection pool nearing capacity: {current}/{max}",
    "Queue depth increasing: current={depth}, threshold={threshold}",
    "Response time SLA warning: p95={duration}ms > target 500ms",
    "Retry attempt {attempt}/{max_retries} for {operation}",
    "Health check degraded for upstream {target_service}",
]


def _generate_trace_id():
    """生成随机 Trace ID"""
    return hashlib.md5(str(random.random()).encode()).hexdigest()[:16]


def _infer_error_category(metric_name: str) -> str:
    """根据指标名推断可能的错误类别（用于日志生成参考，不用于分类逻辑）"""
    metric_lower = metric_name.lower()
    if "cpu" in metric_lower:
        return "cpu"
    if "mem" in metric_lower:
        return "mem"
    if "latency" in metric_lower or "delay" in metric_lower or "p50" in metric_lower or "p90" in metric_lower or "p99" in metric_lower:
        return "latency"
    if "error" in metric_lower or "fail" in metric_lower:
        return "error"
    if "disk" in metric_lower or "io" in metric_lower:
        return "disk"
    if "loss" in metric_lower or "packet" in metric_lower or "net" in metric_lower:
        return "network"
    return "generic"


def _generate_logs_for_service(
    service: str,
    anomalous_metrics: list[dict],
    timestamp_base: int,
    count: int = 5,
) -> list[dict]:
    """\\brief 根据异常指标为特定服务生成模拟日志
    \\param service 服务名称
    \\param anomalous_metrics 异常指标列表，每项含 metric 和 anomaly_score
    \\param timestamp_base 基础时间戳
    \\param count 期望生成的日志条数
    \\return 生成的模拟日志列表"""
    logs = []

    for i in range(min(count, 8)):
        ts = timestamp_base + random.randint(0, 300)

        if anomalous_metrics:
            primary = max(anomalous_metrics, key=lambda x: x.get("anomaly_score", 0))
            category = _infer_error_category(primary.get("metric", ""))
        else:
            category = "generic"

        template = random.choice(ERROR_TEMPLATES_GENERIC)

        metric_part = anomalous_metrics[0].get("metric", "unknown") if anomalous_metrics else "cpu"
        msg = template.format(
            detail="GC overhead limit exceeded" if category == "mem" else "resource limit exceeded",
            metric=metric_part,
            value=round(random.uniform(80, 99), 1),
            max=1024,
            queue=random.randint(100, 500),
            active=random.randint(50, 200),
            pid=random.randint(1000, 9999),
            duration=random.randint(500, 30000),
            target_service=random.choice(["redis", "database", "cartservice", "paymentservice"]),
            path=random.choice(["/api/cart", "/api/checkout", "/api/products"]),
            host=f"10.0.{random.randint(1,10)}.{random.randint(1,254)}",
            port=random.choice([3306, 6379, 8080, 9090]),
            rate=round(random.uniform(30, 80), 1),
            depth=random.randint(500, 2000),
            threshold=200,
            attempt=random.randint(1, 3),
            max_retries=3,
            operation=random.choice(["getCart", "processPayment", "getProduct"]),
        )

        level = "ERROR" if random.random() < 0.7 else "WARN"
        log_entry = {
            "timestamp": str(ts),
            "level": level,
            "message": msg,
            "source": {
                "__hostname__": f"{service}-pod-{random.randint(1,3)}",
                "_pod_name_": f"{service}-deployment-{hashlib.md5(str(i).encode()).hexdigest()[:8]}",
            },
            "fields": {
                "traceId": _generate_trace_id(),
                "service": service,
            },
        }
        logs.append(log_entry)

    return logs


@tool
def query_service_logs(
    fault_type: str,
    service_name: str,
    log_level: str = "ERROR",
    max_logs: int = 8,
) -> str:
    """\\brief 查询指定服务的日志数据，基于指标异常自动生成模拟日志（支持动态服务）
    只对当前数据中实际存在的服务做分析
    \\param fault_type 缓存标签（仅用于数据索引，不驱动分析）
    \\param service_name 服务名称
    \\param log_level 日志级别过滤 (ERROR/WARN/ALL)
    \\param max_logs 最大返回条数
    \\return JSON格式的日志数据，包含:
        - logs 列表（含 RCA 分类：root_cause/amplifier/victim）
        - error_patterns: 错误模式汇总
        - rca_classification: 该服务的日志异常 RCA 分类
        - survey_summary 摘要"""
    try:
        df = load_fault_data(fault_type)
    except ValueError as e:
        return json.dumps({"agent_type": "log", "status": "failure",
                          "error_message": str(e)})

    services_in_data = set(get_all_services(df))
    if service_name not in services_in_data:
        return json.dumps({
            "agent_type": "log",
            "status": "failure",
            "error_message": f"服务 {service_name} 在当前数据中未找到相关指标列",
            "available_services": sorted(services_in_data),
        })

    svc_cols = [c for c in df.columns if c.startswith(f"{service_name}_")]

    anomalies = []
    max_score = 0.0
    for col in svc_cols:
        result = detect_anomalies_zscore(df[col])
        if result["is_anomalous"]:
            anomalies.append({
                "metric": col,
                "anomaly_score": result["anomaly_score"],
            })
            max_score = max(max_score, result["anomaly_score"])

    # RCA 分类：根据异常分数和服务角色
    from config import SERVICE_TOPOLOGY
    svc_info = SERVICE_TOPOLOGY.get(service_name, {})
    svc_type = svc_info.get("type", "application")
    
    rca_classification = "victim"  # 默认受害者
    if max_score > 0.8:
        rca_classification = "root_cause_candidate"
    elif max_score > 0.5:
        rca_classification = "amplifier"
    elif svc_type == "infrastructure":
        rca_classification = "potential_hub"  # 基础设施可能是传播枢纽

    saved_logs, saved_path = _load_latest_saved_logs(service_name, fault_type)
    base_ts = int(df["time"].iloc[len(df) // 2])

    if saved_logs:
        logs = saved_logs
        summary = f"已加载先前保存的日志文件: {os.path.basename(saved_path)}，共 {len(logs)} 条。"
    else:
        if anomalies:
            logs = _generate_logs_for_service(
                service_name, anomalies, base_ts, max_logs
            )
            primary = max(anomalies, key=lambda x: x["anomaly_score"])
            summary = (
                f"服务 {service_name} 发现 {len(anomalies)} 个异常指标，"
                f"主要异常: {primary['metric']}（异常分数: {primary['anomaly_score']:.2f}）。"
                f"日志中发现相关错误模式，建议结合指标数据进一步确认根因。"
            )
        else:
            logs = _generate_logs_for_service(
                service_name, [], base_ts, 2
            )
            summary = f"服务 {service_name} 指标未见明显异常，日志中少量 WARN 信息，暂无关键性错误。"

        try:
            saved = _save_logs_to_file(service_name, fault_type, logs)
            if saved:
                summary += f" 已将生成的日志保存至 {os.path.relpath(saved, PROJECT_ROOT)}。"
        except Exception:
            pass

    if log_level != "ALL":
        logs = [l for l in logs if l["level"] == log_level]

    # 为日志添加 RCA 分类标记
    for log in logs:
        log["rca_role"] = rca_classification
        log["anomaly_score"] = round(max_score, 4)

    # 错误模式汇总（增强 RCA）
    error_patterns = []
    if anomalies:
        error_patterns.append({
            "pattern": f"服务 {service_name} 异常（分数: {max_score:.2f}）",
            "count": len(logs),
            "severity": "HIGH" if max_score > 0.8 else "MEDIUM",
            "rca_role": rca_classification,
        })

    return json.dumps({
        "agent_type": "log",
        "status": "success",
        "data": {"logs": logs[:max_logs]},
        "error_patterns": error_patterns,
        "rca_classification": rca_classification,
        "max_anomaly_score": round(max_score, 4),
        "survey_summary": summary,
    }, ensure_ascii=False)


@tool
def search_error_patterns(fault_type: str, keyword: str = "") -> str:
    """\\brief 在所有服务中搜索错误模式，用于全局日志扫描（增强 RCA 分类）
    仅基于当前数据中实际存在的服务进行分析
    \\param fault_type 缓存标签（仅用于数据索引，不驱动分析）
    \\param keyword 搜索关键词(可选)
    \\return JSON格式的错误模式汇总，包含:
        - total_error_patterns 总数
        - patterns 列表（含 RCA 分类：root_cause/amplifier/hub/victim）
        - candidate_roots: 候选根因服务列表
        - propagation_hubs: 传播枢纽候选列表"""
    try:
        df = load_fault_data(fault_type)
    except ValueError as e:
        return json.dumps({"status": "failure", "error_message": str(e)})

    services = get_all_services(df)
    error_summary = []
    candidate_roots = []
    propagation_hubs = []

    for svc in services:
        svc_cols = [c for c in df.columns if c.startswith(f"{svc}_")]
        svc_max_score = 0.0
        for col in svc_cols:
            result = detect_anomalies_zscore(df[col])
            if result["is_anomalous"] and result["anomaly_score"] > 0.5:
                svc_max_score = max(svc_max_score, result["anomaly_score"])
                error_summary.append({
                    "service": svc,
                    "metric": col,
                    "severity": "HIGH" if result["anomaly_score"] > 0.8 else "MEDIUM",
                    "anomaly_score": round(result["anomaly_score"], 4),
                })
        
        # RCA 分类
        if svc_max_score > 0.8:
            candidate_roots.append(svc)
        elif svc_max_score > 0.5:
            propagation_hubs.append(svc)

    error_summary.sort(key=lambda x: x["anomaly_score"], reverse=True)

    return json.dumps({
        "status": "success",
        "total_error_patterns": len(error_summary),
        "patterns": error_summary[:15],
        "candidate_roots": candidate_roots,
        "propagation_hubs": propagation_hubs,
    }, ensure_ascii=False)


LOG_TOOLS = [query_service_logs, search_error_patterns]

# Logs save directory (project_root/logs)
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
LOG_SAVE_DIR = os.path.join(PROJECT_ROOT, "logs")
os.makedirs(LOG_SAVE_DIR, exist_ok=True)


def _save_logs_to_file(service: str, fault_type: str, logs: list[dict]) -> str:
    """\\brief 将生成的日志保存为 JSON 文件
    \\param service 服务名称
    \\param fault_type 缓存标签
    \\param logs 日志列表
    \\return 保存的文件路径，失败返回空字符串"""
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    rand = hashlib.md5(str(random.random()).encode()).hexdigest()[:8]
    filename = f"{service}_{fault_type}_{ts}_{rand}.json"
    path = os.path.join(LOG_SAVE_DIR, filename)
    payload = {
        "saved_at": datetime.utcnow().isoformat() + "Z",
        "service": service,
        "fault_type_label": fault_type,
        "log_count": len(logs),
        "logs": logs,
    }
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception:
        return ""
    return path


def _load_latest_saved_logs(service: str, fault_type: str) -> tuple[list[dict], str] | tuple[None, None]:
    """\\brief 加载指定服务的最新已保存日志文件
    \\param service 服务名称
    \\param fault_type 缓存标签
    \\return 元组 (日志列表, 文件路径)，若不存在则返回 (None, None)"""
    pattern = os.path.join(LOG_SAVE_DIR, f"{service}_{fault_type}_*.json")
    files = glob.glob(pattern)
    if not files:
        return None, None
    files.sort()
    latest = files[-1]
    try:
        with open(latest, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("logs", []), latest
    except Exception:
        return None, None
