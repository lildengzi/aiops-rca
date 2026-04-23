"""CLI 报告写入相关工具。"""
import os
from datetime import datetime


REPORT_LOG_KEYWORDS = (
    "运维专家",
    "指标分析完成",
    "日志分析完成",
    "链路分析完成",
    "值班长决策",
    "运营专家",
)


def filter_report_logs(thinking_logs: list[str]) -> list[str]:
    return [
        log for log in thinking_logs
        if any(keyword in log for keyword in REPORT_LOG_KEYWORDS)
    ]


def format_report_logs(thinking_logs: list[str]) -> str:
    if not thinking_logs:
        return "- 无可展示的分析过程日志\n"

    formatted_blocks = []
    for log in thinking_logs:
        lines = log.splitlines()
        if not lines:
            continue

        first_line = f"- {lines[0]}"
        if len(lines) == 1:
            formatted_blocks.append(first_line)
            continue

        remaining_lines = "\n".join(
            f"  {line}" if line else ""
            for line in lines[1:]
        )
        formatted_blocks.append(f"{first_line}\n{remaining_lines}")

    return "\n\n".join(formatted_blocks) + "\n"


def save_analysis_outputs(
    base_dir: str,
    fault_type: str,
    query: str,
    result: dict,
    final_fault_type: str,
) -> tuple[str, str]:
    report = result.get("final_report", "报告生成失败")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    report_dir = os.path.join(base_dir, "reports")
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, f"rca_report_{final_fault_type}_{timestamp}.md")

    think_log_dir = os.path.join(base_dir, "think_log")
    os.makedirs(think_log_dir, exist_ok=True)
    think_log_path = os.path.join(think_log_dir, f"think_log_{final_fault_type}_{timestamp}.md")

    with open(think_log_path, "w", encoding="utf-8") as f:
        f.write("# 分析过程完整日志\n\n")
        f.write(f"- 初始故障类型: {fault_type}\n")
        f.write(f"- 最终故障类型: {final_fault_type}\n")
        f.write(f"- 分析问题: {query}\n")
        f.write(f"- 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"- 分析轮次: {result.get('iteration', 0)}\n\n")
        f.write("---\n\n")
        for i, log in enumerate(result.get("thinking_log", []), 1):
            f.write(f"## 步骤 {i}\n")
            f.write(f"{log}\n\n")
            f.write("---\n\n")

    report_logs = filter_report_logs(result.get("thinking_log", []))
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# AIOps 根因分析报告\n\n")
        f.write(f"- 初始故障类型: {fault_type}\n")
        f.write(f"- 最终故障类型: {final_fault_type}\n")
        f.write(f"- 检测到的故障类型: {result.get('detected_fault_type', '未检测')}\n")
        f.write(f"- 分析问题: {query}\n")
        f.write(f"- 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"- 分析轮次: {result.get('iteration', 0)}\n")
        f.write(f"- 详细过程日志: {os.path.basename(think_log_path)}\n\n")
        f.write("---\n\n")
        f.write(report)
        f.write("\n\n---\n\n## 分析过程日志\n\n")
        f.write(format_report_logs(report_logs))
        f.write("\n---\n\n## 分析过程日志摘要\n\n")
        f.write(f"- 分析轮次: {result.get('iteration', 0)}\n")
        f.write(f"- 初始故障类型: {result.get('fault_type')}\n")
        f.write(f"- 最终故障类型: {final_fault_type}\n")
        f.write(f"- 检测到的故障类型: {result.get('detected_fault_type', '未检测')}\n")
        f.write(f"\n详细过程日志请查看: {os.path.basename(think_log_path)}\n")

    return report_path, think_log_path
