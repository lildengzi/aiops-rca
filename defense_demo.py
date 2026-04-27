from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from config import BENCHMARK_DIR
from workflow.orchestrator import RCAOrchestrator
from workflow.summary import DEFAULT_ANALYSIS_QUESTION, build_investigation_summary

DEFAULT_CSV_PATH = str(BENCHMARK_DIR / "real_data.csv")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a standard RCA defense demo")
    parser.add_argument("--csv", default=DEFAULT_CSV_PATH, help="Path to the telemetry CSV file")
    parser.add_argument(
        "--input",
        default=DEFAULT_ANALYSIS_QUESTION,
        help="Natural language alert or symptom description",
    )
    parser.add_argument("--start", type=int, default=None, help="Inclusive start timestamp")
    parser.add_argument("--end", type=int, default=None, help="Inclusive end timestamp")
    parser.add_argument("--json", action="store_true", help="Print the unified summary JSON only")
    parser.add_argument("--verbose", action="store_true", help="Print full node payloads")
    parser.add_argument(
        "--report-preview-chars",
        type=int,
        default=1200,
        help="Number of report characters to preview in text mode",
    )
    return parser


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "\n..."


def _format_node_summary(entry: dict[str, Any], verbose: bool) -> str:
    payload = entry.get("payload") if isinstance(entry, dict) else {}
    if not isinstance(payload, dict):
        payload = {}
    lines = [
        f"- node: {entry.get('node')}",
        f"  iteration: {entry.get('iteration')}",
        f"  timestamp: {entry.get('timestamp')}",
        f"  payload_keys: {', '.join(sorted(payload.keys())) if payload else '(none)'}",
    ]
    if verbose:
        lines.append("  payload:")
        for line in _json_dumps(payload).splitlines():
            lines.append(f"    {line}")
    else:
        highlight = {
            key: payload.get(key)
            for key in (
                "fault_type",
                "selected_services",
                "root_cause",
                "decision",
                "confidence",
                "report_path",
            )
            if key in payload
        }
        if highlight:
            lines.append(f"  highlights: {_json_dumps(highlight)}")
    return "\n".join(lines)


def _dedupe_node_history(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for entry in entries:
        signature = _json_dumps(entry)
        if signature in seen:
            continue
        seen.add(signature)
        deduped.append(entry)
    return deduped


def _print_text_demo(
    summary: dict[str, Any],
    report_preview_chars: int,
    verbose: bool,
) -> None:
    investigation_input = summary.get("investigation_input", {})
    decision_summary = summary.get("decision_summary", {})
    evidence_summary = summary.get("evidence_summary", {})
    artifacts = summary.get("artifacts", {})
    report_header = summary.get("report_header", {})
    node_history = _dedupe_node_history(summary.get("node_history", []))

    print("=== AIOps RCA Defense Demo ===")
    print()
    print("[1] 场景信息")
    print(f"- csv_path: {investigation_input.get('csv_path')}")
    print(f"- user_input: {investigation_input.get('user_input')}")
    print(f"- start: {investigation_input.get('start')}")
    print(f"- end: {investigation_input.get('end')}")
    print(f"- iteration: {investigation_input.get('iteration')} / {investigation_input.get('max_iter')}")
    print()

    print("[2] 节点执行摘要")
    if not node_history:
        print("- no node history recorded")
    else:
        for entry in node_history:
            print(_format_node_summary(entry, verbose=verbose))
    print()

    print("[3] 最终结论")
    print(f"- root_cause: {decision_summary.get('root_cause')}")
    print(f"- secondary_causes: {decision_summary.get('secondary_causes')}")
    print(f"- decision: {decision_summary.get('decision')}")
    print(f"- confidence: {decision_summary.get('confidence')}")
    print(f"- affected_services: {report_header.get('affected_services')}")
    print(f"- fault_type: {report_header.get('fault_type')}")
    print(f"- analysis_mode: {decision_summary.get('analysis_mode')}")
    print()

    print("[4] 证据摘要")
    print(f"- metric_count: {evidence_summary.get('metric_count')}")
    print(f"- log_count: {evidence_summary.get('log_count')}")
    print(f"- trace_count: {evidence_summary.get('trace_count')}")
    print(f"- knowledge_hit_count: {evidence_summary.get('knowledge_hit_count')}")
    print(f"- services: {evidence_summary.get('services')}")
    print()

    print("[5] 产物路径")
    print(f"- report_path: {artifacts.get('report_path')}")
    print(f"- think_log_path: {artifacts.get('think_log_path')}")
    print()

    report_path = artifacts.get("report_path")
    if report_path:
        try:
            report_content = Path(report_path).read_text(encoding="utf-8")
        except OSError as exc:
            print("[6] 报告预览")
            print(f"- failed_to_read_report: {exc}")
        else:
            print("[6] 报告预览")
            print(_truncate(report_content, report_preview_chars))


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    orchestrator = RCAOrchestrator(csv_path=args.csv)
    state = orchestrator.run_investigation(
        user_input=args.input,
        start=args.start,
        end=args.end,
    )
    summary = build_investigation_summary(state)

    if args.json:
        print(_json_dumps(summary))
        return

    _print_text_demo(
        summary=summary,
        report_preview_chars=max(200, args.report_preview_chars),
        verbose=args.verbose,
    )


if __name__ == "__main__":
    main()
