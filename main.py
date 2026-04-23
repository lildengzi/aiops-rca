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
import os
import sys

# 确保项目根目录在路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cli.display import print_banner
from cli.runner import run_analysis


def detect_fault_type_from_data(query: str) -> str:
    """兼容保留：实际自动检测由工作流中的 detect_fault_node 完成。"""
    return "unknown"


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


def build_parser() -> argparse.ArgumentParser:
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
    return parser


def main():
    parser = build_parser()
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


