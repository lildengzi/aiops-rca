"""
日志查询工具 - 模拟 Log MCP / SLS 服务
基于指标异常数据生成模拟日志，模拟真实运维场景
"""
import json
import random
import hashlib
import os
import glob
from datetime import datetime
from langchain_core.tools import tool
from utils.data_loader import load_fault_data, get_all_services
from utils.anomaly_detection import detect_anomalies_zscore


# 日志模板库
ERROR_TEMPLATES = {
    "cpu": [
        "java.lang.OutOfMemoryError: GC overhead limit exceeded",
        "Thread pool exhausted: active={active}, max={max}, queue={queue}",
        "High CPU detected: usage={value}%, threshold=80%",
        "Process {pid} consuming excessive CPU resources",
        "Scheduler thread blocked for {duration}ms, possible deadlock",
    ],
    "mem": [
        "java.lang.OutOfMemoryError: Java heap space",
        "Memory usage critical: {value}MB used / {max}MB total ({percent}%)",
        "GC pause time exceeded threshold: {duration}ms",
        "Off-heap memory leak detected in {component}",
        "Container OOMKilled: memory limit exceeded",
    ],
    "latency": [
        "Request timeout after {duration}ms to {target_service}",
        "Slow query detected: {duration}ms, SQL: SELECT * FROM {table}...",
        "Connection pool wait timeout: {duration}ms",
        "Upstream service {target_service} response time degraded: p99={duration}ms",
        "Circuit breaker triggered for {target_service}: failure rate={rate}%",
    ],
    "error": [
        "HTTP 500 Internal Server Error: {path}",
        "Connection refused: {host}:{port}",
        "java.net.SocketTimeoutException: connect timed out",
        "Service {target_service} returned error code {code}",
        "Retry exhausted after {retries} attempts for {operation}",
    ],
    "disk": [
        "Disk usage critical: {value}% on /data partition",
        "Write failed: No space left on device",
        "I/O wait time elevated: {value}%",
        "Log rotation failed: insufficient disk space",
    ],
    "network": [
        "Packet loss detected: {value}% on interface eth0",
        "TCP connection reset by peer: {host}:{port}",
        "DNS resolution timeout for {hostname}",
        "Network latency spike: {value}ms to {target}",
    ],
}

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


def _generate_logs_for_service(
    service: str,
    fault_type: str,
    anomaly_info: dict,
    timestamp_base: int,
    count: int = 5,
) -> list[dict]:
    """\brief 根据异常信息为特定服务生成模拟日志
    \param service 服务名称
    \param fault_type 故障类型 (cpu/delay/disk/loss/mem)
    \param anomaly_info 异常信息字典，包含 metric 和 anomaly_score
    \param timestamp_base 基础时间戳
    \param count 期望生成的日志条数
    \return 生成的模拟日志列表"""
    logs = []
    # 选择合适的模板
    category = fault_type
    if "latency" in anomaly_info.get("metric", ""):
        category = "latency"
    elif "error" in anomaly_info.get("metric", ""):
        category = "error"
    elif "cpu" in anomaly_info.get("metric", ""):
        category = "cpu"
    elif "mem" in anomaly_info.get("metric", ""):
        category = "mem"

    templates = ERROR_TEMPLATES.get(category, ERROR_TEMPLATES["error"])
    score = anomaly_info.get("anomaly_score", 0.5)

    for i in range(min(count, 8)):
        ts = timestamp_base + random.randint(0, 300)
        template = random.choice(templates)
        # 填充模板变量
        msg = template.format(
            value=round(random.uniform(80, 99), 1),
            max=1024,
            queue=random.randint(100, 500),
            active=random.randint(50, 200),
            pid=random.randint(1000, 9999),
            duration=random.randint(500, 30000),
            target_service=random.choice(["redis", "database", "cartservice", "paymentservice"]),
            table=random.choice(["orders", "products", "users"]),
            component=random.choice(["Netty", "gRPC", "HttpClient"]),
            path=random.choice(["/api/cart", "/api/checkout", "/api/products"]),
            host=f"10.0.{random.randint(1,10)}.{random.randint(1,254)}",
            port=random.choice([3306, 6379, 8080, 9090]),
            code=random.choice([500, 502, 503, 504]),
            retries=3,
            operation=random.choice(["getCart", "processPayment", "getProduct"]),
            rate=round(random.uniform(30, 80), 1),
            hostname=f"{service}.svc.cluster.local",
            target=f"10.0.{random.randint(1,5)}.{random.randint(1,254)}",
            percent=round(random.uniform(85, 99), 1),
            current=random.randint(80, 100),
            depth=random.randint(500, 2000),
            threshold=200,
            attempt=random.randint(1, 3),
            max_retries=3,
        )

        level = "ERROR" if random.random() < 0.7 + score * 0.2 else "WARN"
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
    """\brief 查询指定服务的日志数据，基于指标异常自动生成模拟日志
    \param fault_type 故障数据集类型 (cpu/delay/disk/loss/mem)
    \param service_name 服务名称
    \param log_level 日志级别过滤 (ERROR/WARN/ALL)
    \param max_logs 最大返回条数
    \return JSON格式的日志数据，包含 logs 列表和 survey_summary 摘要"""
    try:
        df = load_fault_data(fault_type)
    except ValueError as e:
        return json.dumps({"agent_type": "log", "status": "failure",
                          "error_message": str(e)})

    # 找出该服务的异常指标
    svc_cols = [c for c in df.columns if c.startswith(f"{service_name}_")]
    if not svc_cols:
        return json.dumps({
            "agent_type": "log",
            "status": "failure",
            "error_message": f"未找到服务 {service_name} 的相关数据",
            "available_services": get_all_services(df),
        })

    # 检测异常
    anomalies = []
    for col in svc_cols:
        result = detect_anomalies_zscore(df[col])
        if result["is_anomalous"]:
            anomalies.append({
                "metric": col,
                "anomaly_score": result["anomaly_score"],
            })
    # 先尝试加载已有保存的日志（优先使用已保存文件）
    saved_logs, saved_path = _load_latest_saved_logs(service_name, fault_type)
    base_ts = int(df["time"].iloc[len(df) // 2])
    if saved_logs:
        logs = saved_logs
        summary = f"已加载先前保存的日志文件: {os.path.basename(saved_path)}，共 {len(logs)} 条。"
    else:
        # 生成日志
        if anomalies:
            primary_anomaly = max(anomalies, key=lambda x: x["anomaly_score"])
            logs = _generate_logs_for_service(
                service_name, fault_type, primary_anomaly, base_ts, max_logs
            )
            summary = (
                f"服务 {service_name} 发现 {len(anomalies)} 个异常指标，"
                f"主要异常: {primary_anomaly['metric']}（异常分数: {primary_anomaly['anomaly_score']:.2f}）。"
                f"日志中发现相关错误模式，建议结合指标数据进一步确认根因。"
            )
        else:
            logs = _generate_logs_for_service(
                service_name, fault_type, {"metric": "", "anomaly_score": 0.1}, base_ts, 2
            )
            summary = f"服务 {service_name} 指标未见明显异常，日志中少量 WARN 信息，暂无关键性错误。"

        # 保存生成的日志到专属目录
        try:
            saved = _save_logs_to_file(service_name, fault_type, logs)
            if saved:
                summary += f" 已将生成的日志保存至 {os.path.relpath(saved, PROJECT_ROOT)}。"
        except Exception:
            pass

    if log_level != "ALL":
        logs = [l for l in logs if l["level"] == log_level]

    return json.dumps({
        "agent_type": "log",
        "status": "success",
        "data": {"logs": logs[:max_logs]},
        "survey_summary": summary,
    }, ensure_ascii=False)


@tool
def search_error_patterns(fault_type: str, keyword: str = "") -> str:
    """\brief 在所有服务中搜索错误模式，用于全局日志扫描
    \param fault_type 故障数据集类型
    \param keyword 搜索关键词(可选)
    \return JSON格式的错误模式汇总，包含 total_error_patterns 和 patterns 列表"""
    try:
        df = load_fault_data(fault_type)
    except ValueError as e:
        return json.dumps({"status": "failure", "error_message": str(e)})

    services = get_all_services(df)
    error_summary = []

    for svc in services:
        svc_cols = [c for c in df.columns if c.startswith(f"{svc}_")]
        for col in svc_cols:
            result = detect_anomalies_zscore(df[col])
            if result["is_anomalous"] and result["anomaly_score"] > 0.5:
                error_summary.append({
                    "service": svc,
                    "metric": col,
                    "severity": "HIGH" if result["anomaly_score"] > 0.8 else "MEDIUM",
                    "anomaly_score": round(result["anomaly_score"], 4),
                })

    error_summary.sort(key=lambda x: x["anomaly_score"], reverse=True)

    return json.dumps({
        "status": "success",
        "total_error_patterns": len(error_summary),
        "patterns": error_summary[:15],
    }, ensure_ascii=False)


LOG_TOOLS = [query_service_logs, search_error_patterns]

# Logs save directory (project_root/logs)
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
LOG_SAVE_DIR = os.path.join(PROJECT_ROOT, "logs")
os.makedirs(LOG_SAVE_DIR, exist_ok=True)


def _save_logs_to_file(service: str, fault_type: str, logs: list[dict]) -> str:
    """\brief 将生成的日志保存为 JSON 文件
    \param service 服务名称
    \param fault_type 故障类型
    \param logs 日志列表
    \return 保存的文件路径，失败返回空字符串"""
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    rand = hashlib.md5(str(random.random()).encode()).hexdigest()[:8]
    filename = f"{service}_{fault_type}_{ts}_{rand}.json"
    path = os.path.join(LOG_SAVE_DIR, filename)
    payload = {
        "saved_at": datetime.utcnow().isoformat() + "Z",
        "service": service,
        "fault_type": fault_type,
        "log_count": len(logs),
        "logs": logs,
    }
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception:
        # 忽略写入错误（保持向后兼容）
        return ""
    return path


def _load_latest_saved_logs(service: str, fault_type: str) -> tuple[list[dict], str] | tuple[None, None]:
    """\brief 加载指定服务的最新已保存日志文件
    \param service 服务名称
    \param fault_type 故障类型
    \return 元组 (日志列表, 文件路径)，若不存在则返回 (None, None)"""
    pattern = os.path.join(LOG_SAVE_DIR, f"{service}_{fault_type}_*.json")
    files = glob.glob(pattern)
    if not files:
        return None, None
    # 按文件名（包含时间戳）排序，取最新
    files.sort()
    latest = files[-1]
    try:
        with open(latest, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("logs", []), latest
    except Exception:
        return None, None
