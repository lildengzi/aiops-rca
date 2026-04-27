from __future__ import annotations

import argparse
import json
from pathlib import Path

from config import BENCHMARK_DIR
from workflow.orchestrator import RCAOrchestrator
from workflow.summary import DEFAULT_ANALYSIS_QUESTION, build_investigation_summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Offline AIOps RCA MVP")
    parser.add_argument(
        "--csv",
        default=str(BENCHMARK_DIR / "real_data.csv"),
        help="Path to the telemetry CSV file",
    )
    parser.add_argument(
        "--input",
        default=DEFAULT_ANALYSIS_QUESTION,
        help="Natural language alert or symptom description",
    )
    parser.add_argument("--start", type=int, default=None, help="Inclusive start timestamp")
    parser.add_argument("--end", type=int, default=None, help="Inclusive end timestamp")
    return parser


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
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    report_path = summary["artifacts"].get("report_path")
    if report_path:
        print("\n--- REPORT PREVIEW ---\n")
        try:
            report_content = Path(report_path).read_text(encoding="utf-8")
            print(report_content[:2000])
        except OSError:
            pass


if __name__ == "__main__":
    main()
