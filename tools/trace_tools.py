"""
链路追踪查询工具 - 模拟 Trace MCP / ARMS 服务
基于服务拓扑和指标异常模拟调用链数据，适配动态服务集合
增强 RCA 支持：明确标记根因/放大器/枢纽/受害者
"""
import json
import random
import hashlib
from langchain_core.tools import tool
from utils.data_loader import load_fault_data, get_all_services
from utils.anomaly_detection import detect_anomalies_zscore
from config import SERVICE_TOPOLOGY


def _gen_id(seed: str, length: int = 16) -> str:
    """根据种子生成固定长度的 MD5 哈希 ID"""
    return hashlib.md5(seed.encode()).hexdigest()[:length]


def _get_rca_role(service: str, anomaly_score: float = 0.0) -> str:
    """根据异常分数和服务类型确定 RCA 角色"""
    if anomaly_score > 0.8:
        return "root_cause"
    elif anomaly_score > 0.5:
        return "amplifier"
    elif service in SERVICE_TOPOLOGY and SERVICE_TOPOLOGY[service].get("type") == "infrastructure":
        return "propagation_hub"
    else:
        return "victim"


def _build_trace(entry_service: str, anomalous_services: list, base_ts: int) -> dict:
    """根据拓扑关系和异常服务构建一条模拟调用链（增强 RCA 标记）"""
    trace_id = _gen_id(f"{entry_service}-{base_ts}-{random.random()}", 32)
    spans = []
    span_idx = 0

    anomalous_svc_set = {a["service"] for a in anomalous_services}
    anomalous_svc_map = {a["service"]: a for a in anomalous_services}

    def add_span(svc, operation, parent_id, is_error, latency_ms, anomaly_score=0.0):
        nonlocal span_idx
        span_idx += 1
        sid = _gen_id(f"{trace_id}-{span_idx}")
        tags = {
            "http.method": "POST" if "checkout" in operation else "GET",
            "http.url": f"/{svc}/api/{operation}",
            "http.status_code": "500" if is_error else "200",
        }
        rca_role = _get_rca_role(svc, anomaly_score)
        span = {
            "operation_name": f"{svc}/{operation}",
            "service_name": svc,
            "span_id": sid,
            "parent_span_id": parent_id,
            "start_time": f"{base_ts + span_idx}",
            "duration": f"{latency_ms}ms",
            "rca_role": rca_role,  # RCA 角色标记
            "tags": tags,
        }
        if is_error:
            category = "generic"
            if svc in anomalous_svc_map:
                metric = anomalous_svc_map[svc].get("metric", "")
                metric_lower = metric.lower()
                if "cpu" in metric_lower:
                    category = "cpu"
                elif "mem" in metric_lower or "memory" in metric_lower:
                    category = "mem"
                elif "latency" in metric_lower or "delay" in metric_lower:
                    category = "delay"

            error_msgs = {
                "cpu": f"java.lang.RuntimeException: Thread pool exhausted in {svc}",
                "mem": f"java.lang.OutOfMemoryError: Java heap space in {svc}",
                "delay": f"io.grpc.StatusRuntimeException: DEADLINE_EXCEEDED in {svc}",
                "generic": f"java.lang.RuntimeException: Service {svc} experiencing issues",
            }
            span["error_type"] = "RuntimeException"
            span["error_message"] = error_msgs.get(category, error_msgs["generic"])
            span["tags"]["error"] = "true"
            span["tags"]["exception.type"] = span["error_type"]
            span["tags"]["exception.message"] = span["error_message"]
        return span, sid

    # 入口 span
    is_entry_error = entry_service in anomalous_svc_set
    entry_score = anomalous_svc_map.get(entry_service, {}).get("anomaly_score", 0.0) if entry_service in anomalous_svc_set else 0.0
    entry_span, entry_id = add_span(
        entry_service, "handleRequest", "",
        is_error=is_entry_error,
        latency_ms=random.randint(500, 5000) if is_entry_error else random.randint(10, 100),
        anomaly_score=entry_score,
    )
    if entry_span["rca_role"] == "root_cause":
        entry_span["error_message"] = f"[根因] {entry_span.get('error_message', '')}"
    elif entry_span["rca_role"] == "amplifier":
        entry_span["error_message"] = f"[放大器] {entry_span.get('error_message', '')}"
    spans.append(entry_span)

    # 下游调用（仅使用在当前数据中存在的依赖）
    deps = SERVICE_TOPOLOGY.get(entry_service, {}).get("dependencies", [])
    for dep in deps:
        if dep in anomalous_svc_set:
            dep_info = anomalous_svc_map.get(dep, {})
            dep_score = dep_info.get("anomaly_score", 0.5)
            latency = int(200 + dep_score * 5000)
            dep_span, dep_id = add_span(dep, "process", entry_id, is_error=True, latency_ms=latency, anomaly_score=dep_score)
            if dep_span["rca_role"] == "root_cause":
                dep_span["error_message"] = f"[根因] {dep_span.get('error_message', '')}"
            elif dep_span["rca_role"] == "amplifier":
                dep_span["error_message"] = f"[放大器] {dep_span.get('error_message', '')}"
            spans.append(dep_span)

            sub_deps = SERVICE_TOPOLOGY.get(dep, {}).get("dependencies", [])
            for sub in sub_deps[:2]:
                sub_is_anomalous = sub in anomalous_svc_set
                sub_score = anomalous_svc_map.get(sub, {}).get("anomaly_score", 0.0) if sub_is_anomalous else 0.0
                sub_span, _ = add_span(
                    sub, "query", dep_id,
                    is_error=sub_is_anomalous,
                    latency_ms=random.randint(500, 3000) if sub_is_anomalous else random.randint(1, 50),
                    anomaly_score=sub_score,
                )
                if sub_span["rca_role"] in ["root_cause", "amplifier"]:
                    tag = "[根因]" if sub_span["rca_role"] == "root_cause" else "[放大器]"
                    sub_span["error_message"] = f"{tag} {sub_span.get('error_message', '')}"
                spans.append(sub_span)
        else:
            dep_span, _ = add_span(dep, "process", entry_id, is_error=False, latency_ms=random.randint(1, 50))
            spans.append(dep_span)

    return {"trace_id": trace_id, "spans": spans, "rca_summary": {
        "root_causes": [s["service_name"] for s in spans if s.get("rca_role") == "root_cause"],
        "amplifiers": [s["service_name"] for s in spans if s.get("rca_role") == "amplifier"],
        "hubs": [s["service_name"] for s in spans if s.get("rca_role") == "propagation_hub"],
        "victims": [s["service_name"] for s in spans if s.get("rca_role") == "victim"],
    }}


@tool
def query_service_traces(fault_type: str, service_name: str, include_errors_only: bool = True, max_traces: int = 3) -> str:
    """查询指定服务的调用链数据，分析故障传播路径（增强 RCA 分类）
    \\param fault_type 缓存标签（仅用于数据索引，不驱动分析）
    \\return JSON 包含:
        - traces: 调用链列表（含 rca_role 标记）
        - rca_summary: RCA 分类汇总（根因/放大器/枢纽/受害者）
        - propagation_path: 传播路径列表"""
    try:
        df = load_fault_data(fault_type)
    except ValueError as e:
        return json.dumps({"agent_type": "trace", "status": "failure", "error_message": str(e)})

    services_in_data = set(get_all_services(df))
    if service_name not in services_in_data:
        return json.dumps({
            "agent_type": "trace", "status": "failure",
            "error_message": f"服务 {service_name} 在当前数据中未找到相关指标列",
            "available_services": sorted(services_in_data),
        })

    anomalous = []
    for svc in services_in_data:
        cols = [c for c in df.columns if c.startswith(f"{svc}_")]
        for col in cols:
            res = detect_anomalies_zscore(df[col])
            if res["is_anomalous"]:
                anomalous.append({"service": svc, "metric": col, "anomaly_score": res["anomaly_score"]})

    svc_scores = {}
    for a in anomalous:
        if a["service"] not in svc_scores or a["anomaly_score"] > svc_scores[a["service"]]["anomaly_score"]:
            svc_scores[a["service"]] = a
    anomalous_list = list(svc_scores.values())

    base_ts = int(df["time"].iloc[len(df) // 2])
    traces = []
    for i in range(min(max_traces, 3)):
        trace = _build_trace(service_name, anomalous_list, base_ts + i * 100)
        traces.append(trace)

    # 汇总 RCA 分类
    all_roots = set()
    all_amplifiers = set()
    all_hubs = set()
    all_victims = set()
    propagation_path = []

    for trace in traces:
        summary = trace.get("rca_summary", {})
        all_roots.update(summary.get("root_causes", []))
        all_amplifiers.update(summary.get("amplifiers", []))
        all_hubs.update(summary.get("hubs", []))
        all_victims.update(summary.get("victims", []))
        # 构建传播路径
        if summary.get("root_causes"):
            propagation_path.append(f"根因: {summary['root_causes']}")
        if summary.get("amplifiers"):
            propagation_path.append(f"放大: {summary['amplifiers']}")
        if summary.get("hubs"):
            propagation_path.append(f"传播枢纽: {summary['hubs']}")
        propagation_path.append(f"影响: {summary.get('victims', [])}")

    summary_text = f"从 {service_name} 出发的调用链中，发现 {len(all_roots)} 个根因候选。"
    if all_roots:
        summary_text += f" 根因候选: {list(all_roots)}"

    return json.dumps({
        "agent_type": "trace", "status": "success",
        "summary": summary_text,
        "data": {"traces": traces},
        "rca_summary": {
            "root_causes": list(all_roots),
            "amplifiers": list(all_amplifiers),
            "propagation_hubs": list(all_hubs),
            "victims": list(all_victims),
        },
        "propagation_path": propagation_path,
    }, ensure_ascii=False)


@tool
def analyze_call_chain(fault_type: str) -> str:
    """分析完整的服务调用链，识别故障传播路径（增强 RCA 分类）
    \\param fault_type 缓存标签（仅用于数据索引，不驱动分析）
    \\return JSON 包含:
        - service_health: 各服务健康度
        - rca_classification: 每个服务的 RCA 角色（根因/放大器/枢纽/受害者）
        - fault_propagation: 传播路径（按异常分数排序）
        - candidate_roots: 候选根因服务列表
        - propagation_hubs: 传播枢纽列表"""
    try:
        df = load_fault_data(fault_type)
    except ValueError as e:
        return json.dumps({"status": "failure", "error_message": str(e)})

    services_in_data = get_all_services(df)
    service_health = {}
    candidate_roots = []
    propagation_hubs = []

    for svc in services_in_data:
        cols = [c for c in df.columns if c.startswith(f"{svc}_")]
        max_score = 0.0
        anomalous_metrics = []
        for col in cols:
            res = detect_anomalies_zscore(df[col])
            if res["is_anomalous"]:
                anomalous_metrics.append(col)
                max_score = max(max_score, res["anomaly_score"])
        rca_role = _get_rca_role(svc, max_score)
        service_health[svc] = {
            "service": svc,
            "health_score": round(1 - max_score, 2),
            "anomalous_metrics": anomalous_metrics,
            "max_anomaly_score": round(max_score, 4),
            "rca_role": rca_role,  # 新增 RCA 角色
        }
        if rca_role == "root_cause":
            candidate_roots.append(svc)
        elif rca_role == "propagation_hub":
            propagation_hubs.append(svc)

    propagation = []
    for svc, info in sorted(service_health.items(), key=lambda x: x[1]["max_anomaly_score"], reverse=True):
        if info["max_anomaly_score"] > 0:
            deps = SERVICE_TOPOLOGY.get(svc, {}).get("dependencies", [])
            affected_deps = [d for d in deps if d in services_in_data and service_health.get(d, {}).get("max_anomaly_score",0) > 0]
            propagation.append({
                "service": svc,
                "anomaly_score": info["max_anomaly_score"],
                "rca_role": info["rca_role"],
                "anomalous_metrics": info["anomalous_metrics"],
                "affected_dependencies": affected_deps,
            })

    return json.dumps({
        "status": "success",
        "service_health": service_health,
        "rca_classification": {svc: info["rca_role"] for svc, info in service_health.items()},
        "fault_propagation": propagation[:10],
        "candidate_roots": candidate_roots,
        "propagation_hubs": propagation_hubs,
    }, ensure_ascii=False)


TRACE_TOOLS = [query_service_traces, analyze_call_chain]
