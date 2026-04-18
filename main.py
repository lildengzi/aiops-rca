"""
AIOps 多智能体根因分析系统 - 主入口
基于 LangChain + LangGraph 实现 ReAct 模式多智能体协作

使用方式:
    python main.py --fault cpu --query "frontend服务延迟升高，请分析根因"
    python main.py --fault mem --query "系统出现OOM告警"
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


def parse_fault_type_from_query(query: str) -> Optional[str]:
    """
    调用 LLM（analyst_agent）从用户自然语言中解析故障类型。
    返回 cpu/delay/disk/loss/mem 之一，无法识别时返回 None。
    """
    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import HumanMessage, SystemMessage
        from agents.analyst_agent import get_query_parse_prompt

        llm = ChatOpenAI(
            model=LLM_CONFIG["model"],
            api_key=LLM_CONFIG["api_key"],
            base_url=LLM_CONFIG["base_url"],
            temperature=0,
            max_tokens=64,
        )
        messages = [
            SystemMessage(content=get_query_parse_prompt()),
            HumanMessage(content=query),
        ]
        resp = llm.invoke(messages)
        fault_type = resp.content.strip().lower()
        if fault_type in FAULT_DATA_MAP:
            return fault_type
        return None
    except Exception:
        return None


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


def run_analysis(fault_type: str, query: str, max_iter: int = 3):
    """执行一次完整的根因分析"""
    print(f"\n{'='*60}")
    print(f" 故障类型: {fault_type}")
    print(f" 分析问题: {query}")
    print(f" 最大迭代: {max_iter} 轮")
    print(f" LLM模型:  {LLM_CONFIG['model']}")
    print(f" 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    print(" 正在启动多智能体工作流...\n")

    try:
        result = run_rca(
            user_query=query,
            fault_type=fault_type,
            max_iterations=max_iter,
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
    print("可用故障类型:", ", ".join(FAULT_DATA_MAP.keys()))
    print("输入 'quit' 退出\n")
    print("提示: 可直接输入自然语言，如 '过去1小时frontend服务CPU飙升'"
          "，系统将自动识别故障类型\n")

    while True:
        print("-" * 40)
        query = input("请输入告警描述或问题: ").strip()
        if query.lower() == "quit":
            print(" 再见！")
            break
        if not query:
            continue

        # 优先尝试用 LLM 解析故障类型
        print(" 正在识别故障类型...")
        fault_type = parse_fault_type_from_query(query)

        if not fault_type:
            # LLM 解析失败则手动选择
            fault_type = input(
                f" 未能自动识别，请手动输入故障类型 ({'/'.join(FAULT_DATA_MAP.keys())}): "
            ).strip().lower()
            if fault_type not in FAULT_DATA_MAP:
                print(f" 不支持的故障类型: {fault_type}")
                continue
        else:
            print(f" 识别到故障类型: {fault_type}")

        max_iter = input("最大迭代次数 (默认2): ").strip()
        max_iter = int(max_iter) if max_iter.isdigit() else 2

        run_analysis(fault_type, query, max_iter)
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
    parser.add_argument("--fault", type=str, choices=list(FAULT_DATA_MAP.keys()),
                        help="故障类型（可选，不填则由 LLM 从 query 自动识别）")
    parser.add_argument("--query", type=str, help="告警描述或问题（支持自然语言）")
    parser.add_argument("--max-iter", type=int, default=2, help="最大迭代次数（默认2）")
    parser.add_argument("--interactive", action="store_true", help="交互式模式")

    args = parser.parse_args()

    if args.interactive:
        interactive_mode()
    elif args.query:
        print_banner()
        fault_type = args.fault
        if not fault_type:
            print(" 正在识别故障类型...")
            fault_type = parse_fault_type_from_query(args.query)
            if fault_type:
                print(f" 识别到故障类型: {fault_type}")
            else:
                print(" 未能自动识别故障类型，请用 --fault 显式指定")
                sys.exit(1)
        run_analysis(fault_type, args.query, args.max_iter)
    else:
        parser.print_help()
        print("\n提示: 使用 --interactive 进入交互模式，或用 --query 传入告警描述")


if __name__ == "__main__":
    main()

