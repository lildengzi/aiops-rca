"""
故障类型自动检测节点
基于真实指标异常扫描 5 类数据集，确定最可能的故障类型。
"""
import json
from datetime import datetime

from tools.metric_tools import query_all_services_overview
from workflow.state import RCAState


FAULT_TYPES = ["cpu", "delay", "disk", "loss", "mem"]


def _score_overview(overview: dict) -> tuple[float, dict]:
    """基于异常数量和严重程度为数据集打分。"""
    services = overview.get("services", [])
    anomalous_services = 0
    anomalous_metrics = 0
    total_score = 0.0
    max_score = 0.0

    for svc in services:
        svc_anomalies = svc.get("anomalies", []) or []
        if svc_anomalies:
            anomalous_services += 1
        anomalous_metrics += len(svc_anomalies)

        for anomaly in svc_anomalies:
            score = float(anomaly.get("anomaly_score", 0.0) or 0.0)
            total_score += score
            max_score = max(max_score, score)

    final_score = anomalous_metrics * 10 + anomalous_services * 3 + total_score + max_score * 2
    stats = {
        "anomalous_services": anomalous_services,
        "anomalous_metrics": anomalous_metrics,
        "total_score": round(total_score, 4),
        "max_score": round(max_score, 4),
        "final_score": round(final_score, 4),
    }
    return final_score, stats


def detect_fault_node(state: RCAState) -> dict:
    """
    自动检测故障类型。
    - 若用户已显式指定故障类型，则直接透传
    - 若为 unknown，则扫描全部数据集并选取得分最高者
    """
    ts = datetime.now().strftime("%H:%M:%S")
    specified_fault_type = state.get("fault_type", "unknown")

    if specified_fault_type != "unknown":
        return {
            "detected_fault_type": specified_fault_type,
            "thinking_log": [f"[{ts}] 自动检测跳过: 用户已显式指定故障类型 {specified_fault_type}"],
        }

    candidates = []
    failures = []
    for fault_type in FAULT_TYPES:
        try:
            raw = query_all_services_overview.invoke({"fault_type": fault_type})
            overview = json.loads(raw)
            score, stats = _score_overview(overview)
            candidates.append({
                "fault_type": fault_type,
                "score": score,
                **stats,
            })
        except Exception as e:
            failures.append(f"{fault_type}: {str(e)}")

    if not candidates:
        log_entry = f"[{ts}] 自动检测失败: 所有数据集扫描均失败。{'; '.join(failures) if failures else ''}"
        return {
            "detected_fault_type": "unknown",
            "thinking_log": [log_entry],
        }

    candidates.sort(key=lambda x: x["score"], reverse=True)
    best = candidates[0]

    ranking_text = "\n".join(
        [
            f"- {item['fault_type']}: score={item['score']:.4f}, 异常服务={item['anomalous_services']}, 异常指标={item['anomalous_metrics']}, max_score={item['max_score']:.4f}"
            for item in candidates
        ]
    )
    log_entry = (
        f"[{ts}] 自动检测完成: 识别故障类型为 {best['fault_type']}\n"
        f"候选排序:\n{ranking_text}"
    )

    return {
        "detected_fault_type": best["fault_type"],
        "thinking_log": [log_entry],
    }
