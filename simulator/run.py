"""
AIOps 实时模拟器 - 主程序入口

用法:
    python simulator/run.py                      # 默认 CPU 故障，15秒后注入
    python simulator/run.py --fault mem          # 内存故障
    python simulator/run.py --fault delay --delay 20  # 延迟故障，20秒后注入
    python simulator/run.py --fault loss --no-rca     # 丢包故障，仅展示监控不触发RCA
    python simulator/run.py --list               # 列出所有故障类型
"""
import sys
import os
import time
import argparse
import signal

# 将项目根目录加入 Python 路径
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)


def check_dependencies() -> bool:
    """检查必要依赖是否已安装"""
    missing = []
    try:
        import rich
    except ImportError:
        missing.append("rich")
    try:
        import numpy
    except ImportError:
        missing.append("numpy")
    try:
        import pandas
    except ImportError:
        missing.append("pandas")
    try:
        import scipy
    except ImportError:
        missing.append("scipy")

    if missing:
        print(f"[错误] 缺少依赖包: {', '.join(missing)}")
        print(f"请运行: pip install {' '.join(missing)}")
        return False
    return True


def check_llm_config() -> tuple[bool, str]:
    """检查 LLM 配置是否有效"""
    try:
        from config import LLM_CONFIG
        key = LLM_CONFIG.get("api_key", "")
        if not key or key.startswith("your-") or key == "":
            return False, "未配置 API Key"
        return True, LLM_CONFIG.get("model", "unknown")
    except Exception as e:
        return False, str(e)


def print_banner(fault_type: str, fault_delay: float, enable_rca: bool, llm_ok: bool, llm_model: str):
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text
    from simulator.stream_generator import FAULT_PROFILES

    console = Console()
    profile = FAULT_PROFILES[fault_type]

    lines = [
        "[bold cyan]AIOps 实时故障模拟 + 根因分析系统[/bold cyan]",
        "",
        f"  故障类型  : [bold yellow]{fault_type.upper()}[/bold yellow]  —  {profile['description']}",
        f"  根因服务  : [bold red]{profile['root_cause_service']}[/bold red]",
        f"  受影响服务: [yellow]{', '.join(profile['affected_services'])}[/yellow]",
        f"  故障延迟  : [cyan]{fault_delay:.0f} 秒后注入[/cyan]",
        "",
        f"  RCA 分析  : {'[bold green]已启用[/bold green]' if enable_rca else '[dim]已禁用（--no-rca）[/dim]'}",
        f"  LLM 模型  : {'[green]' + llm_model + '[/green]' if llm_ok else '[red]未配置（仅展示监控面板）[/red]'}",
        "",
        "  [dim]Ctrl+C 可随时退出[/dim]",
    ]

    console.print(Panel(
        Text.from_markup("\n".join(lines)),
        title="[bold white] 系统启动 [/bold white]",
        border_style="cyan",
        padding=(1, 3),
    ))
    time.sleep(2)


def run_simulator(fault_type: str, fault_delay: float, enable_rca: bool, max_iter: int, tick: float):
    """
    主循环：
    1. 每 tick 秒生成一帧数据快照
    2. 刷新 TUI 面板
    3. 故障注入后若 enable_rca=True 则触发 RCA
    4. RCA 完成后展示报告
    """
    from simulator.stream_generator import RealtimeStreamGenerator, FAULT_PROFILES
    from simulator.dashboard import render_metrics_table, render_rca_report
    from simulator.rca_adapter import RCAAdapter, build_alert_query

    generator = RealtimeStreamGenerator(
        fault_type=fault_type,
        fault_delay=fault_delay,
        tick_interval=tick,
    )
    adapter = RCAAdapter(generator)

    history: list = []
    rca_triggered = False
    # 故障确认需要连续 N 帧异常才触发 RCA（避免噪声误触发）
    consecutive_alert_frames = 0
    RCA_TRIGGER_FRAMES = 3

    llm_ok, llm_model = check_llm_config()

    print(f"\n正在启动实时监控... (刷新间隔: {tick}s)\n")
    time.sleep(0.5)

    try:
        while True:
            snap = generator.next_snapshot()
            adapter.add_snapshot(snap)
            history.append(snap)

            # 每帧注入数据到工具缓存（供 RCA 工具层使用）
            if enable_rca and llm_ok:
                adapter.inject_into_tools()

            # 渲染面板
            rca_status = adapter.rca_status
            render_metrics_table(snap, history, rca_status)

            # 倒计时提示
            if not snap.fault_active:
                remaining = fault_delay - generator.elapsed
                from rich.console import Console
                Console().print(
                    f"[bold yellow]  {remaining:.1f}s 后注入故障: "
                    f"{fault_type.upper()} — {FAULT_PROFILES[fault_type]['description']}[/bold yellow]"
                )

            # 故障触发 RCA 判断
            if snap.fault_active and enable_rca and llm_ok and not rca_triggered:
                alerts = adapter.get_alert_services(snap) if hasattr(adapter, 'get_alert_services') else []
                # 直接用 generator 上的方法
                alerts = generator.get_alert_services(snap) if hasattr(generator, 'get_alert_services') else [
                    {"service": s} for s in FAULT_PROFILES[fault_type]["affected_services"]
                ]
                if alerts:
                    consecutive_alert_frames += 1
                else:
                    consecutive_alert_frames = 0

                if consecutive_alert_frames >= RCA_TRIGGER_FRAMES:
                    rca_triggered = True
                    query = build_alert_query(fault_type, alerts)
                    from rich.console import Console
                    Console().print(
                        f"\n[bold red]  告警确认！连续 {RCA_TRIGGER_FRAMES} 帧异常，触发 RCA 分析...[/bold red]\n"
                    )
                    time.sleep(1)
                    adapter.trigger_rca(query, max_iterations=max_iter)

            # RCA 完成后展示报告并等待退出
            if rca_triggered and not adapter.rca_running and adapter.rca_result:
                result = adapter.rca_result
                report = result.get("final_report", "报告生成失败")

                # 保存报告
                from datetime import datetime
                report_dir = os.path.join(_root, "reports")
                os.makedirs(report_dir, exist_ok=True)
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                report_path = os.path.join(report_dir, f"realtime_rca_{fault_type}_{ts}.md")
                with open(report_path, "w", encoding="utf-8") as f:
                    f.write(f"# AIOps 实时 RCA 报告\n\n")
                    f.write(f"- 故障类型: {fault_type}\n")
                    f.write(f"- 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n---\n\n")
                    f.write(report)

                render_rca_report(report, fault_type)
                from rich.console import Console
                Console().print(f"\n[green]报告已保存至: {report_path}[/green]")
                Console().print("[dim]按 Ctrl+C 退出[/dim]")

                # 继续刷新监控，等用户手动退出
                while True:
                    time.sleep(2)
                    snap = generator.next_snapshot()
                    adapter.add_snapshot(snap)
                    render_metrics_table(snap, history[-50:], {"phase": "done", "message": "RCA 已完成，报告已保存。", "iteration": max_iter, "max_iter": max_iter})
                    from rich.console import Console
                    Console().print(f"[green]报告已保存: {report_path}[/green]  [dim]Ctrl+C 退出[/dim]")

            elif enable_rca and not llm_ok and snap.fault_active and not rca_triggered:
                rca_triggered = True  # 防止重复打印
                from rich.console import Console
                Console().print(
                    "[bold yellow]  未配置 LLM API Key，跳过 RCA 分析（仅展示监控）[/bold yellow]\n"
                    "  请在 .env 或 config.py 中配置 OPENAI_API_KEY 后重新运行。"
                )

            time.sleep(tick)

    except KeyboardInterrupt:
        from rich.console import Console
        Console().print("\n[bold cyan]  已退出实时监控。再见！[/bold cyan]")
        sys.exit(0)


def main():
    parser = argparse.ArgumentParser(
        description="AIOps 实时故障模拟 + 根因分析系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python simulator/run.py                        # CPU故障，15秒后注入
  python simulator/run.py --fault mem            # 内存泄漏故障
  python simulator/run.py --fault delay --delay 10  # 延迟故障，10秒后注入
  python simulator/run.py --fault loss --no-rca  # 丢包故障，仅监控
  python simulator/run.py --list                 # 列出所有故障类型
        """,
    )
    parser.add_argument(
        "--fault", type=str, default="cpu",
        choices=["cpu", "delay", "disk", "loss", "mem"],
        help="故障类型 (默认: cpu)",
    )
    parser.add_argument(
        "--delay", type=float, default=15.0,
        help="正常运行多少秒后注入故障 (默认: 15)",
    )
    parser.add_argument(
        "--max-iter", type=int, default=2,
        help="RCA 最大迭代次数 (默认: 2)",
    )
    parser.add_argument(
        "--tick", type=float, default=1.5,
        help="监控刷新间隔秒数 (默认: 1.5)",
    )
    parser.add_argument(
        "--no-rca", action="store_true",
        help="禁用 RCA 分析，仅展示实时监控面板",
    )
    parser.add_argument(
        "--list", action="store_true",
        help="列出所有故障类型并退出",
    )

    args = parser.parse_args()

    if args.list:
        from simulator.stream_generator import FAULT_PROFILES
        print("\n可用故障类型:\n")
        for k, v in FAULT_PROFILES.items():
            print(f"  {k:8s}  {v['description']}")
            print(f"           根因服务: {v['root_cause_service']}")
            print(f"           影响范围: {', '.join(v['affected_services'])}\n")
        sys.exit(0)

    if not check_dependencies():
        sys.exit(1)

    llm_ok, llm_model = check_llm_config()
    enable_rca = not args.no_rca

    print_banner(args.fault, args.delay, enable_rca, llm_ok, llm_model)
    run_simulator(
        fault_type=args.fault,
        fault_delay=args.delay,
        enable_rca=enable_rca,
        max_iter=args.max_iter,
        tick=args.tick,
    )


if __name__ == "__main__":
    main()
