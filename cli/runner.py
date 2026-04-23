"""CLI 分析执行器。"""
import os

from workflow.orchestrator import run_rca
from cli.display import (
    create_progress_callback,
    print_analysis_header,
    print_final_report,
    print_result_summary,
)
from cli.reporting import save_analysis_outputs


def get_final_fault_type(result: dict, fallback_fault_type: str) -> str:
    return result.get("detected_fault_type") or result.get("fault_type") or fallback_fault_type


def run_analysis(fault_type: str, query: str, max_iter: int = 3, full_analysis: bool = True):
    """执行一次完整的根因分析。"""
    print_analysis_header(fault_type, query, max_iter, full_analysis)

    try:
        result = run_rca(
            user_query=query,
            fault_type=fault_type,
            max_iterations=max_iter,
            full_analysis=full_analysis,
            progress_callback=create_progress_callback(),
        )

        final_fault_type = get_final_fault_type(result, fault_type)
        print_result_summary(result, final_fault_type)

        report = result.get("final_report", "报告生成失败")
        print_final_report(report)

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        report_path, _ = save_analysis_outputs(
            base_dir=base_dir,
            fault_type=fault_type,
            query=query,
            result=result,
            final_fault_type=final_fault_type,
        )

        print(f"\n 报告已保存至: {report_path}", flush=True)
        return result

    except Exception as e:
        print(f"\n 分析执行失败: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return None
