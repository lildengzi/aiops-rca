"""
AIOps 多智能体根因分析系统 - 主入口
基于 LangChain + LangGraph 实现 ReAct 模式多智能体协作
支持故障类型自动检测，用户可输入任意告警描述

使用方式:
    python main.py --query "frontend服务延迟升高，请分析根因"  # 自动检测
    python main.py --fault cpu --query "CPU异常"   # 也可显式指定
    python main.py --interactive
"""
import argparse
import sys
import os
import json
from datetime import datetime
from typing import Optional

# 确保项目根目录在路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import FAULT_DATA_MAP, LLM_CONFIG
from workflow.orchestrator import run_rca


def detect_fault_type_from_data(query: str) -> str:
    """
    用户输入任意告警信息，系统自动从数据中检测故障类型。
    首次迭代时由工作流自动分析数据特征得出结论。
    """
    return "unknown"


def print_banner():
    banner = """
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
    print(banner)


def run_analysis(fault_type: str, query: str, max_iter: int = 3, full_analysis: bool = True):
    """执行一次完整的根因分析"""
    print(f"\n{'='*60}")
    print(f" 故障类型: {fault_type if fault_type != 'unknown' else '自动检测中'}")
    print(f" 分析问题: {query}")
    print(f" 最大迭代: {max_iter} 轮")
    print(f" 全指标分析: {'启用' if full_analysis else '禁用'}")
    print(f" LLM模型:  {LLM_CONFIG['model']}")
    print(f" 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    print(" 正在启动多智能体工作流...\n")
    
    # 专家进度显示回调 - 兼容Windows GBK编码
    def progress_callback(node_name, status):
        agent_names = {
            "master": "运维专家",
            "metric": "指标分析专家", 
            "log": "日志分析专家",
            "trace": "链路分析专家",
            "aggregate": "数据汇总",
            "analyst": "值班长",
            "reporter": "运营专家"
        }
        name = agent_names.get(node_name, node_name)
        print(f"  [完成] {name} 任务完成")

    try:
        result = run_rca(
            user_query=query,
            fault_type=fault_type,
            max_iterations=max_iter,
            full_analysis=full_analysis,
            progress_callback=progress_callback,
        )

        # 输出过程日志
        print(f"\n{'='*60}")
        print(" 分析过程日志")
        print(f"{'='*60}")
        for log in result.get("thinking_log", []):
            print(f"  {log}")

        # 输出最终报告
        print(f"\n{'='*60}")
        print(" 最终分析报告")
        print(f"{'='*60}")
        report = result.get("final_report", "报告生成失败")
        print(report)

        # 保存报告
        report_dir = os.path.join(os.path.dirname(__file__), "reports")
        os.makedirs(report_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = os.path.join(report_dir, f"rca_report_{fault_type}_{timestamp}.md")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(f"# AIOps 根因分析报告\n\n")
            f.write(f"- 故障类型: {fault_type}\n")
            f.write(f"- 分析问题: {query}\n")
            f.write(f"- 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"- 分析轮次: {result.get('iteration', 0)}\n\n")
            f.write(f"---\n\n")
            f.write(report)
            f.write(f"\n\n---\n\n## 分析过程日志\n\n")
            for log in result.get("thinking_log", []):
                f.write(f"- {log}\n")

        print(f"\n 报告已保存至: {report_path}")
        return result

    except Exception as e:
        print(f"\n 分析执行失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def interactive_mode():
    """交互式模式 - 支持自然语言输入"""
    print_banner()
    print("输入 'quit' 退出\n")
    print("提示: 可直接输入任意告警描述，如 'frontend服务报错'"
          "，系统将自动分析数据并识别故障类型\n")

    while True:
        print("-" * 40)
        query = input("请输入告警描述或问题: ").strip()
        if query.lower() == "quit":
            print(" 再见！")
            break
        if not query:
            continue

        fault_type = "unknown"
        print(" 故障类型将根据数据分析自动识别")

        max_iter = input("最大迭代次数 (默认2): ").strip()
        max_iter = int(max_iter) if max_iter.isdigit() else 2

        full_analysis = input("启用全指标分析模式? (y/n, 默认y): ").strip().lower() != 'n'
        run_analysis(fault_type, query, max_iter, full_analysis)
        print()


def main():
    parser = argparse.ArgumentParser(
        description="AIOps 多智能体根因分析系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""示例:
  python main.py --query "过去1小时frontend服务CPU飙升，请分析根因"
  python main.py --query "系统出现OOM告警" --max-iter 3
  python main.py --fault cpu --query "CPU异常"   # 也可显式指定故障类型
  python main.py --interactive
        """,
    )
    parser.add_argument("--fault", type=str, default="unknown",
                        help="故障类型（可选，默认unknown由系统自动检测）")
    parser.add_argument("--query", type=str, help="告警描述或问题（支持自然语言）")
    parser.add_argument("--max-iter", type=int, default=2, help="最大迭代次数（默认2）")
    parser.add_argument("--interactive", action="store_true", help="交互式模式")
    parser.add_argument("--disable-full-analysis", action="store_true", 
                        help="禁用全指标分析模式（仅针对目标服务）")

    args = parser.parse_args()

    if args.interactive:
        interactive_mode()
    elif args.query:
        print_banner()
        fault_type = args.fault if args.fault != "unknown" else "unknown"
        run_analysis(fault_type, args.query, args.max_iter, not args.disable_full_analysis)
    else:
        parser.print_help()
        print("\n提示: 使用 --interactive 进入交互模式，或用 --query 传入告警描述")


if __name__ == "__main__":
    main()

