"""
终端实时监控面板
使用 rich 库渲染美观的 TUI 界面，实时展示微服务指标
"""
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text
from rich.progress import BarColumn, Progress, TextColumn
from rich import box

from simulator.stream_generator import SERVICES, BASELINE, FAULT_PROFILES, MetricSnapshot

console = Console()

# 指标颜色阈值
def _cpu_color(v: float) -> str:
    if v >= 85: return "bold red"
    if v >= 60: return "yellow"
    return "green"

def _mem_color(v: float) -> str:
    if v >= 85: return "bold red"
    if v >= 70: return "yellow"
    return "cyan"

def _latency_color(v: float) -> str:
    if v >= 1000: return "bold red"
    if v >= 300:  return "yellow"
    return "green"

def _error_color(v: float) -> str:
    if v >= 0.1:  return "bold red"
    if v >= 0.02: return "yellow"
    return "dim green"

def _bar(value: float, max_val: float, width: int = 10) -> str:
    """生成简易 ASCII 进度条"""
    filled = int(min(value / max_val, 1.0) * width)
    return "█" * filled + "░" * (width - filled)


def render_metrics_table(snapshot: MetricSnapshot, history: list, rca_status: dict) -> None:
    """
    渲染完整的监控面板到终端
    """
    console.clear()

    ts = datetime.fromtimestamp(snapshot.timestamp).strftime("%Y-%m-%d %H:%M:%S")

    # ── 顶部标题栏 ──────────────────────────────────────────────────────────
    if snapshot.fault_active:
        profile = FAULT_PROFILES[snapshot.fault_type]
        fault_label = f"[bold red]  FAULT INJECTED: {snapshot.fault_type.upper()}  [/bold red]  "
        fault_label += f"[red]{profile['description']}[/red]  "
        fault_label += f"[yellow]进度: {snapshot.fault_progress*100:.0f}%[/yellow]  "
        fault_label += f"[red]根因服务: {profile['root_cause_service']}[/red]"
        title_text = Text.from_markup(fault_label)
        title_panel = Panel(title_text, style="bold red", padding=(0, 2))
    else:
        elapsed = snapshot.timestamp - (snapshot.timestamp % 1)  # rough
        title_panel = Panel(
            Text.from_markup(f"[bold green]  SYSTEM NORMAL  [/bold green]  [dim]{ts}[/dim]  "
                             f"[cyan]采样帧: {len(history)}[/cyan]"),
            style="green",
            padding=(0, 2),
        )
    console.print(title_panel)

    # ── 主指标表格 ────────────────────────────────────────────────────────────
    table = Table(
        box=box.SIMPLE_HEAVY,
        show_header=True,
        header_style="bold white on dark_blue",
        border_style="bright_black",
        expand=True,
        title=f"[bold]微服务实时指标监控[/bold]  [dim]{ts}[/dim]",
        title_style="bold cyan",
    )

    table.add_column("服务",      style="bold white",  min_width=22)
    table.add_column("CPU %",     justify="right",      min_width=12)
    table.add_column("内存 %",    justify="right",      min_width=12)
    table.add_column("延迟 ms",   justify="right",      min_width=12)
    table.add_column("负载",      justify="right",      min_width=8)
    table.add_column("错误率",    justify="right",      min_width=10)
    table.add_column("状态",      justify="center",     min_width=8)

    fault_services = set()
    if snapshot.fault_active:
        fault_services = set(FAULT_PROFILES[snapshot.fault_type]["affected_services"])

    for svc in SERVICES:
        m = snapshot.metrics[svc]
        cpu     = m["cpu"]
        mem     = m["mem"]
        latency = m["latency"]
        load    = m["load"]
        error   = m["error"]

        # 状态标签
        if svc in fault_services and snapshot.fault_active:
            if svc == FAULT_PROFILES[snapshot.fault_type]["root_cause_service"]:
                status = Text(" ROOT ", style="bold white on red")
                row_style = "on grey11"
            else:
                status = Text(" WARN ", style="bold black on yellow")
                row_style = "on grey11"
        else:
            status = Text("  OK  ", style="bold black on green")
            row_style = ""

        cpu_bar = f"[{_cpu_color(cpu)}]{_bar(cpu, 100)}  {cpu:5.1f}[/]"
        mem_bar = f"[{_mem_color(mem)}]{_bar(mem, 100)}  {mem:5.1f}[/]"
        lat_txt = f"[{_latency_color(latency)}]{latency:8.0f}[/]"
        load_txt = f"[bright_white]{load:6.0f}[/]"
        err_txt = f"[{_error_color(error)}]{error*100:6.2f}%[/]"

        table.add_row(svc, cpu_bar, mem_bar, lat_txt, load_txt, err_txt, status, style=row_style)

    console.print(table)

    # ── 告警栏 ────────────────────────────────────────────────────────────────
    alerts = []
    for svc in SERVICES:
        m = snapshot.metrics[svc]
        reasons = []
        if m["cpu"] > 80:    reasons.append(f"CPU={m['cpu']:.1f}%")
        if m["mem"] > 85:    reasons.append(f"MEM={m['mem']:.1f}%")
        if m["latency"] > 1000: reasons.append(f"LAT={m['latency']:.0f}ms")
        if m["error"] > 0.1: reasons.append(f"ERR={m['error']*100:.1f}%")
        if reasons:
            alerts.append(f"[bold red]{svc}[/bold red]: {', '.join(reasons)}")

    if alerts:
        alert_text = "  |  ".join(alerts)
        console.print(Panel(
            Text.from_markup(f" ALERTS  {alert_text}"),
            style="red",
            padding=(0, 1),
        ))
    else:
        console.print(Panel(
            Text.from_markup(" [green]无活跃告警[/green]"),
            style="bright_black",
            padding=(0, 1),
        ))

    # ── RCA 状态栏 ────────────────────────────────────────────────────────────
    rca_phase  = rca_status.get("phase", "idle")
    rca_msg    = rca_status.get("message", "等待故障触发...")
    rca_iter   = rca_status.get("iteration", 0)
    rca_max    = rca_status.get("max_iter", 3)

    phase_colors = {
        "idle":      "dim",
        "triggered": "bold yellow",
        "master":    "bold cyan",
        "metric":    "cyan",
        "log":       "blue",
        "trace":     "magenta",
        "analyst":   "bold yellow",
        "reporter":  "bold green",
        "done":      "bold green",
        "error":     "bold red",
    }
    color = phase_colors.get(rca_phase, "white")

    iter_bar = ""
    if rca_iter > 0:
        iter_bar = f"  迭代: [{'/'.join(['●']*rca_iter + ['○']*(rca_max-rca_iter))}] {rca_iter}/{rca_max}"

    console.print(Panel(
        Text.from_markup(
            f"[bold]RCA 引擎[/bold]  [{color}]{rca_phase.upper():12s}[/]  "
            f"[white]{rca_msg}[/white]{iter_bar}"
        ),
        style="bright_black",
        padding=(0, 1),
    ))

    # ── 操作提示 ──────────────────────────────────────────────────────────────
    console.print(
        "[dim]  Ctrl+C 停止  |  "
        "故障将在倒计时结束后自动注入  |  "
        "RCA 分析将在故障确认后自动触发[/dim]"
    )


def render_countdown(seconds_left: float, fault_type: str) -> None:
    """渲染倒计时提示（嵌入主面板中，直接打印一行）"""
    profile = FAULT_PROFILES[fault_type]
    console.print(
        f"[bold yellow]  {seconds_left:.0f}s 后注入故障: "
        f"{fault_type.upper()} ({profile['description']})[/bold yellow]"
    )


def render_rca_report(report: str, fault_type: str) -> None:
    """渲染最终 RCA 报告"""
    console.clear()
    console.print(Panel(
        Text.from_markup(f"[bold green]RCA 分析完成  |  故障类型: {fault_type.upper()}[/bold green]"),
        style="green",
    ))
    console.print(Panel(
        report,
        title="[bold cyan]事件分析报告[/bold cyan]",
        border_style="cyan",
        padding=(1, 2),
    ))
    console.print("[dim]按 Ctrl+C 退出[/dim]")
