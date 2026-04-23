"""CLI 展示相关工具。"""
from datetime import datetime

from config import LLM_CONFIG


AGENT_NAMES = {
    "detect_fault": "故障类型检测",
    "master": "运维专家",
    "metric": "指标分析专家",
    "log": "日志分析专家",
    "trace": "链路分析专家",
    "aggregate": "数据汇总",
    "analyst": "值班长",
    "reporter": "运营专家",
}


BANNER = """
+--------------------------------------------------------------+
|      AIOps 多智能体根因分析系统 (Multi-Agent RCA)           |
|      基于 LangChain + LangGraph · ReAct 模式               |
+--------------------------------------------------------------+
|  智能体团队:                                                 |
|    [Master]   运维专家  - 任务规划与调度                     |
|    [Metric]   指标分析  - 时序指标异常检测                   |
|    [Log]      日志分析  - 错误模式提取                       |
|    [Trace]    链路分析  - 故障传播路径                       |
|    [Analyst]  值班长    - 证据整合与决策                     |
|    [Reporter] 运营专家  - 结构化报告生成                     |
+--------------------------------------------------------------+
"""


def print_banner() -> None:
    print(BANNER)


def print_analysis_header(fault_type: str, query: str, max_iter: int, full_analysis: bool) -> None:
    print(f"\n{'='*60}", flush=True)
    print(f" 故障类型: {fault_type if fault_type != 'unknown' else '自动检测中'}", flush=True)
    print(f" 分析问题: {query}", flush=True)
    print(f" 最大迭代: {max_iter} 轮", flush=True)
    print(f" 全指标分析: {'启用' if full_analysis else '禁用'}", flush=True)
    print(f" LLM模型:  {LLM_CONFIG['model']}", flush=True)
    print(f" 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
    print(f"{'='*60}\n", flush=True)
    print(" 正在启动多智能体工作流...\n", flush=True)


def create_progress_callback():
    def progress_callback(node_name, status):
        name = AGENT_NAMES.get(node_name, node_name)
        print(f"  [完成] {name} 任务完成", flush=True)

    return progress_callback


def print_result_summary(result: dict, final_fault_type: str) -> None:
    print(f"\n{'='*60}", flush=True)
    print(" 分析过程日志", flush=True)
    print(f"{'='*60}", flush=True)
    print(f"  分析轮次: {result.get('iteration', 0)}", flush=True)
    print(f"  初始故障类型: {result.get('fault_type')}", flush=True)
    print(f"  最终故障类型: {final_fault_type}", flush=True)
    print(f"  检测到的故障类型: {result.get('detected_fault_type', '未检测')}", flush=True)


def print_final_report(report: str) -> None:
    print(f"\n{'='*60}", flush=True)
    print(" 最终分析报告", flush=True)
    print(f"{'='*60}", flush=True)
    report_clean = report.encode('gbk', errors='replace').decode('gbk')
    print(report_clean, flush=True)
