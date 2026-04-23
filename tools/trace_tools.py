"""
链路追踪查询工具 - 模拟 Trace MCP / ARMS 服务
基于服务拓扑和指标异常模拟调用链数据
"""
import json
import random
import hashlib
from langchain_core.tools import tool
from utils.data_loader import load_fault_data, get_all_services
from utils.anomaly_detection import detect_anomalies_zscore
from config import SERVICE_TOPOLOGY


def _gen_id(seed: str, length: int = 16) -> str:
    """\brief 根据种子生成固定长度的 MD5 哈希 ID
    \param seed 随机种子字符串
    \param length 截取长度（默认 16）
    \return 十六进制 ID 字符串"""
    return hashlib.md5(seed.encode()).hexdigest()[:length]


def _build_trace(
    entry_service: str,
    fault_type: str,
    anomalous_services: list[dict],
    base_ts: int,
) -> dict:
    """\brief 根据拓扑关系和异常服务构建一条模拟调用链
    \param entry_service 入口服务名
    \param fault_type 故障类型
    \param anomalous_services 异常服务列表（含 anomaly_score）
    \param base_ts 基础时间戳
    \return 调用链字典，包含 trace_id 和 spans 列表"""
    trace_id = _gen_id(f"{entry_service}-{base_ts}-{random.random()}", 32)
    spans = []
    span_idx = 0

    def add_span(svc, operation, parent_id, is_error, latency_ms):
        nonlocal span_idx
        span_idx += 1
        sid = _gen_id(f"{trace_id}-{span_idx}")
        tags = {
            "http.method": "POST" if "checkout" in operation else "GET",
            "http.url": f"/{svc}/api/{operation}",
            "http.status_code": "500" if is_error else "200",
        }
        span = {
            "operation_name": f"{svc}/{operation}",
            "service_name": svc,
            "span_id": sid,
            "parent_span_id": parent_id,
            "start_time": f"{base_ts + span_idx}",
            "duration": f"{latency_ms}ms",
            "tags": tags,
        }
        if is_error:
            error_msgs = {
                "cpu": f"java.lang.RuntimeException: Thread pool exhausted in {svc}, active threads at maximum",
                "mem": f"java.lang.OutOfMemoryError: Java heap space in {svc}",
                "delay": f"io.grpc.StatusRuntimeException: DEADLINE_EXCEEDED: deadline exceeded after {latency_ms}ms",
                "disk": f"java.io.IOException: No space left on device in {svc}",
                "loss": f"java.net.SocketException: Connection reset by peer from {svc}",
            }
            span["error_type"] = "RuntimeException"
            span["error_message"] = error_msgs.get(fault_type, f"Unknown error in {svc}")
            span["tags"]["error"] = "true"
            span["tags"]["exception.type"] = span["error_type"]
            span["tags"]["exception.message"] = span["error_message"]
        return span, sid

    # 入口 span
    anomalous_svc_names = {a["service"] for a in anomalous_services}
    is_entry_error = entry_service in anomalous_svc_names
    entry_span, entry_id = add_span(
        entry_service, "handleRequest", "",
        is_error=is_entry_error,
        latency_ms=random.randint(500, 5000) if is_entry_error else random.randint(10, 100),
    )
    if is_entry_error:
        entry_span["error_message"] = f"[根因] {entry_span.get('error_message', '')}"
    spans.append(entry_span)

    # 下游调用
    deps = SERVICE_TOPOLOGY.get(entry_service, {}).get("dependencies", [])
    for dep in deps:
        if dep in anomalous_svc_names:
            dep_info = next((a for a in anomalous_services if a["service"] == dep), {})
            dep_score = dep_info.get("anomaly_score", 0.5)
            latency = int(200 + dep_score * 5000)
            dep_span, dep_id = add_span(dep, "process", entry_id, is_error=True, latency_ms=latency)
            dep_span["error_message"] = f"[根因] {dep_span.get('error_message', '')}"
            spans.append(dep_span)

            # 该服务自身的下游
            sub_deps = SERVICE_TOPOLOGY.get(dep, {}).get("dependencies", [])
            for sub in sub_deps[:2]:
                sub_is_anomalous = sub in anomalous_svc_names
                sub_span, _ = add_span(
                    sub, "query", dep_id,
                    is_error=sub_is_anomalous,
                    latency_ms=random.randint(500, 3000) if sub_is_anomalous else random.randint(1, 50),
                )
                if sub_is_anomalous:
                    sub_span["error_message"] = f"[根因] {sub_span.get('error_message', '')}"
                spans.append(sub_span)
        else:
            dep_span, _ = add_span(dep, "process", entry_id, is_error=False, latency_ms=random.randint(1, 50))
            spans.append(dep_span)

    return {"trace_id": trace_id, "spans": spans}


@tool
def query_service_traces(
    fault_type: str,
    service_name: str,
    include_errors_only: bool = True,
    max_traces: int = 3,
) -> str:
    """\brief 查询指定服务的调用链数据，分析故障传播路径
    \param fault_type 故障数据集类型 (cpu/delay/disk/loss/mem)
    \param service_name 要分析的服务名称
    \param include_errors_only 是否仅返回包含错误的 Trace
    \param max_traces 最大返回 Trace 数量
    \return JSON 格式的调用链数据，包含 summary 和 traces"""
    try:
        df = load_fault_data(fault_type)
    except ValueError as e:
        return json.dumps({"agent_type": "trace", "status": "failure",
                          "error_message": str(e)})

    services = get_all_services(df)
    if service_name not in services and service_name not in SERVICE_TOPOLOGY:
        return json.dumps({
            "agent_type": "trace", "status": "failure",
            "error_message": f"服务 {service_name} 不存在",
            "available_services": services,
        })

    # 检测所有服务异常
    anomalous = []
    for svc in services:
        cols = [c for c in df.columns if c.startswith(f"{svc}_")]
        for col in cols:
            res = detect_anomalies_zscore(df[col])
            if res["is_anomalous"]:
                anomalous.append({
                    "service": svc,
                    "metric": col,
                    "anomaly_score": res["anomaly_score"],
                })

    # 去重取最高分
    svc_scores = {}
    for a in anomalous:
        if a["service"] not in svc_scores or a["anomaly_score"] > svc_scores[a["service"]]["anomaly_score"]:
            svc_scores[a["service"]] = a
    anomalous_list = list(svc_scores.values())

    base_ts = int(df["time"].iloc[len(df) // 2])
    traces = []
    for i in range(min(max_traces, 3)):
        trace = _build_trace(service_name, fault_type, anomalous_list, base_ts + i * 100)
        traces.append(trace)

    # 生成摘要
    anomalous_in_trace = [a["service"] for a in anomalous_list
                          if a["service"] in SERVICE_TOPOLOGY.get(service_name, {}).get("dependencies", [])
                          or a["service"] == service_name]
    summary = (
        f"从 {service_name} 出发的调用链中，"
        f"发现 {len(anomalous_in_trace)} 个异常服务: {anomalous_in_trace}。"
        f"主要错误类型与 {fault_type} 故障特征一致。"
    )

    return json.dumps({
        "agent_type": "trace",
        "status": "success",
        "summary": summary,
        "data": {"traces": traces},
    }, ensure_ascii=False)


@tool
def analyze_call_chain(fault_type: str) -> str:
    """\brief 分析完整的服务调用链，识别故障传播路径
    \param fault_type 故障数据集类型
    \return JSON 格式的调用链分析结果，包含:
        - service_health: 各服务健康度及异常指标
        - fault_propagation: 故障传播链（按异常分数排序）"""
    try:
        df = load_fault_data(fault_type)
    except ValueError as e:
        return json.dumps({"status": "failure", "error_message": str(e)})

    services = get_all_services(df)

    # 分析每个服务的异常程度
    service_health = {}
    for svc in services:
        cols = [c for c in df.columns if c.startswith(f"{svc}_")]
        max_score = 0.0
        anomalous_metrics = []
        for col in cols:
            res = detect_anomalies_zscore(df[col])
            if res["is_anomalous"]:
                anomalous_metrics.append(col)
                max_score = max(max_score, res["anomaly_score"])
        service_health[svc] = {
            "service": svc,
            "health_score": round(1 - max_score, 2),
            "anomalous_metrics": anomalous_metrics,
            "max_anomaly_score": round(max_score, 4),
        }

    # 按拓扑关系构建传播链
    propagation = []
    for svc, info in sorted(service_health.items(), key=lambda x: x[1]["max_anomaly_score"], reverse=True):
        if info["max_anomaly_score"] > 0:
            deps = SERVICE_TOPOLOGY.get(svc, {}).get("dependencies", [])
            affected_deps = [d for d in deps if service_health.get(d, {}).get("max_anomaly_score", 0) > 0]
            propagation.append({
                "service": svc,
                "anomaly_score": info["max_anomaly_score"],
                "anomalous_metrics": info["anomalous_metrics"],
                "affected_dependencies": affected_deps,
            })

    return json.dumps({
        "status": "success",
        "service_health": service_health,
        "fault_propagation": propagation[:10],
    }, ensure_ascii=False)


TRACE_TOOLS = [query_service_traces, analyze_call_chain]
