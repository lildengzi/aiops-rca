from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from workflow.state import RCAState


AGENT_LABELS = {
    "dataset_summary": "数据扫描",
    "retrieve_knowledge": "知识检索",
    "master": "主控规划智能体",
    "metric": "指标分析智能体",
    "log": "日志分析智能体",
    "trace": "链路分析智能体",
    "aggregate": "证据汇总",
    "analyst": "综合判断",
    "reporter": "报告生成",
}

EVIDENCE_LABELS = {
    "metric": "指标",
    "metrics": "指标",
    "log": "日志",
    "logs": "日志",
    "trace": "真实调用链",
    "traces": "真实调用链",
    "topology": "拓扑推断",
    "knowledge": "历史知识",
}


def append_think_log(state: RCAState, agent_name: str, payload: dict[str, Any]) -> None:
    path = state.ensure_think_log_path()
    lines = [
        f"## {datetime.now().isoformat()} [{agent_name}]",
        "```json",
        json.dumps(payload, ensure_ascii=False, indent=2),
        "```",
        "",
    ]
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines))


def record_node_event(state: RCAState, node_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    readable_react = build_readable_react(node_name, payload, state)
    entry = {
        "timestamp": datetime.now().isoformat(),
        "node": node_name,
        "iteration": state.iteration,
        "payload": payload,
        "readable_react": readable_react,
        "display": {
            "readable_react": readable_react,
        },
    }
    state.node_history.append(entry)
    append_think_log(state, node_name, payload)
    return payload


def build_readable_react(node_name: str, payload: dict[str, Any], state: RCAState) -> dict[str, Any]:
    builder = {
        "dataset_summary": _dataset_summary_react,
        "retrieve_knowledge": _retrieve_knowledge_react,
        "master": _master_react,
        "metric": _metric_react,
        "log": _log_react,
        "trace": _trace_react,
        "aggregate": _aggregate_react,
        "analyst": _analyst_react,
        "reporter": _reporter_react,
    }.get(node_name, _default_react)
    react = builder(payload, state)
    return _normalize_react(node_name, react)


def _normalize_react(node_name: str, react: dict[str, Any]) -> dict[str, Any]:
    return {
        "agent_label": react.get("agent_label") or AGENT_LABELS.get(node_name, node_name),
        "plain_goal": _clean_text(react.get("plain_goal") or "完成当前分析步骤。"),
        "thought": _clean_text(react.get("thought") or "根据当前状态选择下一步检查。"),
        "action": _clean_text(react.get("action") or "读取输入并整理结果。"),
        "observation": _short_lines(react.get("observation"), fallback="当前步骤没有产生可展示的关键观察。", limit=3),
        "result": _clean_text(react.get("result") or "结果已写入工作流状态，供后续步骤使用。"),
        "next_step": _clean_text(react.get("next_step") or "交给下一个节点继续分析。"),
        "status": react.get("status") if react.get("status") in {"success", "warning", "info"} else "info",
    }


def _dataset_summary_react(payload: dict[str, Any], state: RCAState) -> dict[str, Any]:
    services = _as_list(payload.get("services"))
    rows = payload.get("window_rows") or payload.get("rows")
    metric_names = _collect_metric_names(payload.get("service_metrics"))
    window = _format_range(payload.get("window_start") or payload.get("start_time"), payload.get("window_end") or payload.get("end_time"))
    return {
        "plain_goal": "先确认这次分析能看到哪些服务、指标和时间窗口。",
        "thought": "根因分析需要先知道数据覆盖范围，否则后面的异常判断没有上下文。",
        "action": "扫描数据集摘要，统计服务、指标和窗口行数。",
        "observation": [
            f"数据窗口包含 {rows} 行记录。" if rows is not None else "数据窗口行数未在摘要中给出。",
            f"覆盖 {len(services)} 个服务：{_join_preview(services)}。" if services else "没有识别到明确的服务列表。",
            f"可用指标包括：{_join_preview(metric_names)}。" if metric_names else "没有识别到明确的指标列表。",
            f"时间范围：{window}。" if window else "",
        ],
        "result": "已形成数据集背景，后续智能体只能基于这些服务和观测数据排查。",
        "next_step": "交给知识检索节点查找相似历史案例。",
        "status": "success" if services else "warning",
    }


def _retrieve_knowledge_react(payload: dict[str, Any], state: RCAState) -> dict[str, Any]:
    hit_count = int(payload.get("hit_count", 0) or 0)
    candidates = _as_list(payload.get("candidate_services"))
    top_hits = [item for item in _as_list(payload.get("top_hits")) if isinstance(item, dict)]
    status_text = str(payload.get("status") or "")
    return {
        "agent_label": AGENT_LABELS["retrieve_knowledge"],
        "plain_goal": "查找历史知识中有没有相似故障，可作为排查参考。",
        "thought": "历史知识只能辅助排序和解释，不能替代当前这次事故的指标、日志和调用链证据。",
        "action": "用用户问题、候选服务和故障类型构造检索条件，查询知识库。",
        "observation": [
            f"历史知识命中 {hit_count} 条。",
            f"重点候选服务：{_join_preview(candidates)}。" if candidates else "没有明确的候选服务用于检索。",
            f"高相关条目：{_join_preview([hit.get('title') or hit.get('service') for hit in top_hits])}。" if top_hits else "没有可展示的高相关历史条目。",
            f"检索状态：{status_text}。" if status_text and status_text != "ok" else "",
        ],
        "result": "历史知识已作为参考信号保存，后续会和当前证据做支持、冲突或中性对齐。",
        "next_step": "交给主控规划智能体决定先检查哪些服务和证据维度。",
        "status": "success" if hit_count > 0 else "info",
    }


def _master_react(payload: dict[str, Any], state: RCAState) -> dict[str, Any]:
    actions = [item for item in _as_list(payload.get("actions")) if isinstance(item, dict)]
    hypotheses = [item for item in _as_list(payload.get("hypotheses")) if isinstance(item, dict)]
    services = _as_list(payload.get("selected_services"))
    tool_counts = _count_by(actions, "tool")
    return {
        "plain_goal": "把当前问题拆成可执行的检查计划。",
        "thought": "需要让指标、日志和真实调用链互相验证，避免只凭单一信号下结论。",
        "action": f"生成 {len(actions)} 个检查动作：{_format_tool_counts(tool_counts)}。",
        "observation": [
            f"优先关注服务：{_join_preview(services)}。" if services else "没有选出明确的优先服务。",
            f"主要假设：{_join_preview([item.get('hypothesis') or item.get('service') for item in hypotheses], limit=2)}。" if hypotheses else "没有形成明确假设。",
            f"计划覆盖证据：{_join_preview([_evidence_label(tool) for tool in tool_counts])}。" if tool_counts else "计划中没有可执行工具。",
        ],
        "result": "检查计划已生成，后续三个专业智能体会按计划并行取证。",
        "next_step": "交给指标、日志和链路分析智能体执行对应检查。",
        "status": "success" if actions else "warning",
    }


def _metric_react(payload: dict[str, Any], state: RCAState) -> dict[str, Any]:
    metrics = [item for item in _as_list(payload.get("metrics")) if isinstance(item, dict)]
    anomalies = [item for item in metrics if item.get("is_anomalous")]
    return {
        "plain_goal": "查看候选服务的指标是否真的异常。",
        "thought": "指标能说明某个服务是否出现资源、延迟或错误率异常，但还需要和日志、调用链互相印证。",
        "action": f"调用指标工具检查 {len(metrics)} 个服务/指标组合。",
        "observation": _metric_observations(metrics, anomalies),
        "result": f"产出 {len(metrics)} 条指标证据，其中 {len(anomalies)} 条显示异常。",
        "next_step": "把指标证据交给汇总节点，并等待日志和调用链证据一起判断。",
        "status": "success" if anomalies else "info",
    }


def _log_react(payload: dict[str, Any], state: RCAState) -> dict[str, Any]:
    logs = [item for item in _as_list(payload.get("logs")) if isinstance(item, dict)]
    active = [item for item in logs if int(item.get("log_count", 0) or 0) > 0]
    return {
        "plain_goal": "查看候选服务在故障窗口内有没有异常日志模式。",
        "thought": "日志可以补充本地错误、重试、资源争用等信号，用来确认异常是否发生在服务内部。",
        "action": f"调用日志工具检查 {len(logs)} 个服务。",
        "observation": _log_observations(logs, active),
        "result": f"产出 {len(logs)} 条日志证据，其中 {len(active)} 个服务有日志事件。",
        "next_step": "把日志证据交给汇总节点，与指标和调用链一起对齐。",
        "status": "success" if active else "info",
    }


def _trace_react(payload: dict[str, Any], state: RCAState) -> dict[str, Any]:
    traces = [item for item in _as_list(payload.get("traces")) if isinstance(item, dict)]
    real = [item for item in traces if item.get("source_type") == "real" and int(item.get("trace_count", 0) or 0) > 0]
    inferred = [item for item in traces if item.get("source_type") == "inferred" or item.get("pillar") == "topology"]
    observations = _trace_observations(traces, real, inferred)
    return {
        "plain_goal": "查看候选服务在调用关系中处于什么位置。",
        "thought": "真实调用链可以帮助区分首发服务、传播影响和表象服务；拓扑推断只能作为弱参考。",
        "action": f"调用链路工具检查 {len(traces)} 个服务。",
        "observation": observations,
        "result": f"产出 {len(real)} 条真实调用链证据和 {len(inferred)} 条拓扑推断参考。",
        "next_step": "把链路证据交给汇总节点，综合判断时会降低拓扑推断的权重。",
        "status": "warning" if inferred and not real else "success" if real else "info",
    }


def _aggregate_react(payload: dict[str, Any], state: RCAState) -> dict[str, Any]:
    metric_count = int(payload.get("metric_count", 0) or 0)
    log_count = int(payload.get("log_count", 0) or 0)
    trace_count = int(payload.get("trace_count", 0) or 0)
    return {
        "plain_goal": "把各专业智能体拿到的证据放到同一个证据包里。",
        "thought": "综合判断前，需要先确认指标、日志、真实调用链或拓扑推断分别有多少证据。",
        "action": "合并指标、日志和链路分析结果。",
        "observation": [
            f"指标证据 {_count_text(metric_count)}。",
            f"日志证据 {_count_text(log_count)}。",
            f"真实调用链/拓扑证据 {_count_text(trace_count)}。",
        ],
        "result": "证据包已更新，综合判断节点可以开始交叉验证。",
        "next_step": "交给综合判断节点排序候选根因并决定是否继续迭代。",
        "status": "success" if metric_count or log_count or trace_count else "warning",
    }


def _analyst_react(payload: dict[str, Any], state: RCAState) -> dict[str, Any]:
    ranked = [item for item in _as_list(payload.get("ranked_services")) if isinstance(item, dict)]
    root = payload.get("primary_root_cause") or payload.get("root_cause") or "unknown"
    decision = payload.get("decision") or "continue"
    confidence = payload.get("confidence")
    pillars = _translated_pillars(ranked[0].get("evidence_pillars", [])) if ranked else []
    gaps = _as_list(payload.get("evidence_gaps"))
    return {
        "plain_goal": "把所有证据合并成根因候选排序和下一步决策。",
        "thought": "需要比较指标、日志、真实调用链、拓扑推断和历史知识是否互相支持，证据不足时不能过早停止。",
        "action": "计算候选服务排序、证据覆盖、置信度和是否继续排查。",
        "observation": [
            f"当前首要根因候选：{root}，置信度 {confidence}。",
            f"Top 候选证据来源：{_join_preview(pillars)}。" if pillars else "Top 候选缺少清晰的证据来源。",
            f"决策：{decision}。",
            f"主要缺口：{_join_preview(gaps, limit=2)}。" if gaps else "",
        ],
        "result": f"综合结论已形成：{root}；工作流决策为 {decision}。",
        "next_step": "如果结论足够稳定则生成报告，否则回到主控规划智能体继续补证。",
        "status": "success" if decision == "stop" else "warning",
    }


def _reporter_react(payload: dict[str, Any], state: RCAState) -> dict[str, Any]:
    path = payload.get("report_path")
    root = payload.get("root_cause") or (payload.get("report_header") or {}).get("root_cause")
    decision = payload.get("decision") or (payload.get("report_header") or {}).get("decision")
    return {
        "plain_goal": "把机器分析结果整理成用户可读的 RCA 报告。",
        "thought": "报告需要同时保留结论、证据、缺口和建议，便于人工复核和后续处置。",
        "action": "生成 Markdown 报告和稳定的报告头字段。",
        "observation": [
            f"报告路径：{path}。" if path else "报告路径未生成。",
            f"报告中的根因候选：{root}。" if root else "报告中没有明确根因候选。",
            f"报告决策：{decision}。" if decision else "",
        ],
        "result": "报告已写入文件路径，并同步到工作流状态。",
        "next_step": "前端可以展示报告预览、原始 JSON 和可读 ReAct 过程。",
        "status": "success" if path else "warning",
    }


def _default_react(payload: dict[str, Any], state: RCAState) -> dict[str, Any]:
    return {
        "plain_goal": "执行一个工作流节点。",
        "thought": "该节点产生了结构化输出，需要记录到执行历史中。",
        "action": "保存节点 payload，并追加 think log。",
        "observation": [f"输出字段包括：{_join_preview(list(payload.keys()))}。" if payload else "节点没有输出字段。"],
        "result": "节点输出已保留。",
        "next_step": "继续执行后续节点。",
        "status": "info",
    }


def _metric_observations(metrics: list[dict[str, Any]], anomalies: list[dict[str, Any]]) -> list[str]:
    if not metrics:
        return ["没有返回指标证据。"]
    lines = [f"检查了 {len(metrics)} 条指标证据，异常 {len(anomalies)} 条。"]
    for item in anomalies[:2]:
        lines.append(
            f"{item.get('service', '-')} 的 {item.get('metric', '-')} 异常，峰值 {item.get('peak_value', '-')}。"
        )
    if not anomalies:
        lines.append("当前指标没有显示明显异常。")
    return lines


def _log_observations(logs: list[dict[str, Any]], active: list[dict[str, Any]]) -> list[str]:
    if not logs:
        return ["没有返回日志证据。"]
    lines = [f"检查了 {len(logs)} 个服务，{len(active)} 个服务有日志事件。"]
    for item in active[:2]:
        patterns = item.get("top_patterns") or []
        pattern = patterns[0].get("pattern") if patterns and isinstance(patterns[0], dict) else "未归纳模式"
        lines.append(f"{item.get('service', '-')} 有 {item.get('log_count', 0)} 条日志，代表模式：{pattern}。")
    if not active:
        lines.append("当前日志没有显示明显事件。")
    return lines


def _trace_observations(
    traces: list[dict[str, Any]],
    real: list[dict[str, Any]],
    inferred: list[dict[str, Any]],
) -> list[str]:
    if not traces:
        return ["没有返回调用链证据。"]
    lines = [f"检查了 {len(traces)} 个服务，真实调用链证据 {len(real)} 条，拓扑推断 {len(inferred)} 条。"]
    if inferred:
        lines.append("存在 topology inferred：这不是采集到的真实调用链，只能作为弱参考。")
    samples = real or inferred
    for item in samples[:1]:
        paths = _as_list(item.get("propagation_paths"))
        if paths:
            lines.append(f"{item.get('service', '-')} 的样例路径：{_clip(str(paths[0]), 100)}。")
    return lines


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [value]


def _short_lines(value: Any, fallback: str, limit: int = 3) -> list[str]:
    lines = [_clean_text(item) for item in _as_list(value)]
    lines = [line for line in lines if line]
    if not lines:
        lines = [fallback]
    return [_clip(line, 140) for line in lines[:limit]]


def _clean_text(value: Any) -> str:
    return " ".join(str(value).split()) if value not in (None, "") else ""


def _clip(value: str, limit: int) -> str:
    text = _clean_text(value)
    return text if len(text) <= limit else f"{text[:limit - 1]}…"


def _join_preview(items: list[Any], limit: int = 5) -> str:
    values = [_clean_text(item) for item in items if _clean_text(item)]
    if not values:
        return "-"
    suffix = f" 等 {len(values)} 项" if len(values) > limit else ""
    return "、".join(values[:limit]) + suffix


def _collect_metric_names(service_metrics: Any) -> list[str]:
    names: set[str] = set()
    if isinstance(service_metrics, dict):
        for metrics in service_metrics.values():
            for metric in _as_list(metrics):
                if metric:
                    names.add(str(metric))
    return sorted(names)


def _format_range(start: Any, end: Any) -> str:
    if start is None and end is None:
        return ""
    return f"{start if start is not None else '-'} ~ {end if end is not None else '-'}"


def _count_by(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = str(item.get(key) or "")
        if value:
            counts[value] = counts.get(value, 0) + 1
    return counts


def _format_tool_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "没有工具调用"
    return "、".join(f"{_evidence_label(tool)} {count} 次" for tool, count in sorted(counts.items()))


def _evidence_label(value: Any) -> str:
    return EVIDENCE_LABELS.get(str(value), str(value))


def _translated_pillars(pillars: Any) -> list[str]:
    return [_evidence_label(item) for item in _as_list(pillars)]


def _count_text(count: int) -> str:
    return f"{count} 条" if count else "0 条"
