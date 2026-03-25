"""
RCA 适配器
将实时数据流生成器产生的快照注入到现有 tools 层，
让原有的 orchestrator 工作流直接消费实时数据
"""
import sys
import os
import threading
from typing import Optional

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from simulator.stream_generator import RealtimeStreamGenerator, MetricSnapshot, FAULT_PROFILES


class RCAAdapter:
    def __init__(self, generator: RealtimeStreamGenerator):
        self.generator = generator
        self._lock = threading.Lock()
        self._snapshots: list = []
        self._rca_running = False
        self._rca_result: Optional[dict] = None
        self._rca_status: dict = {
            "phase": "idle",
            "message": "等待故障触发...",
            "iteration": 0,
            "max_iter": 3,
        }
        self._rca_thread: Optional[threading.Thread] = None

    def add_snapshot(self, snap: MetricSnapshot) -> None:
        with self._lock:
            self._snapshots.append(snap)
            if len(self._snapshots) > 300:
                self._snapshots = self._snapshots[-300:]

    def get_dataframe(self):
        with self._lock:
            snaps = list(self._snapshots)
        if not snaps:
            return None
        return self.generator.to_dataframe(snaps)

    def inject_into_tools(self) -> None:
        """将当前快照数据注入到统一数据缓存，供所有工具层使用"""
        df = self.get_dataframe()
        if df is None or df.empty:
            return
        try:
            from utils.data_loader import set_realtime_data
            set_realtime_data(self.generator.fault_type, df)
        except Exception:
            pass

    @property
    def rca_status(self) -> dict:
        return dict(self._rca_status)

    @property
    def rca_result(self) -> Optional[dict]:
        return self._rca_result

    @property
    def rca_running(self) -> bool:
        return self._rca_running

    def _update_status(self, phase: str, message: str, iteration: int = 0, max_iter: int = 3):
        self._rca_status = {
            "phase": phase,
            "message": message,
            "iteration": iteration,
            "max_iter": max_iter,
        }

    def trigger_rca(self, query: str, max_iterations: int = 3) -> None:
        """在后台线程中启动 RCA 分析（非阻塞）"""
        if self._rca_running:
            return

        def _run():
            self._rca_running = True
            fault_type = self.generator.fault_type
            try:
                self._update_status("triggered", f"检测到 {fault_type.upper()} 故障，正在启动分析...")
                self.inject_into_tools()

                from workflow.orchestrator import build_rca_workflow, RCAState
                app = build_rca_workflow()

                initial_state: RCAState = {
                    "user_query": query,
                    "fault_type": fault_type,
                    "iteration": 0,
                    "max_iterations": max_iterations,
                    "should_stop": False,
                    "master_plan": "",
                    "metric_results": [],
                    "log_results": [],
                    "trace_results": [],
                    "analyst_decision": "",
                    "final_report": "",
                    "thinking_log": [],
                }

                node_labels = {
                    "master":   ("master",   "运维专家正在制定排查计划..."),
                    "metric":   ("metric",   "指标分析 Agent 正在检测异常指标..."),
                    "log":      ("log",      "日志分析 Agent 正在提取错误模式..."),
                    "trace":    ("trace",    "链路分析 Agent 正在追踪故障传播路径..."),
                    "analyst":  ("analyst",  "值班长正在整合证据、评估置信度..."),
                    "reporter": ("reporter", "运营专家正在生成结构化分析报告..."),
                }

                current_iter = 0
                accumulated: dict = dict(initial_state)

                for event in app.stream(initial_state):
                    for node_name, node_output in event.items():
                        phase, msg = node_labels.get(
                            node_name, (node_name, f"{node_name} 执行中...")
                        )
                        if node_name == "master":
                            current_iter += 1
                        self._update_status(phase, msg, current_iter, max_iterations)
                        if isinstance(node_output, dict):
                            for k, v in node_output.items():
                                if isinstance(v, list) and isinstance(accumulated.get(k), list):
                                    accumulated[k] = accumulated[k] + v
                                else:
                                    accumulated[k] = v

                self._rca_result = accumulated
                self._update_status("done", "RCA 分析完成！报告已生成。", current_iter, max_iterations)

            except Exception as e:
                import traceback
                tb = traceback.format_exc()
                self._update_status("error", f"分析异常: {str(e)[:80]}")
                self._rca_result = {
                    "final_report": f"分析过程中发生错误：{e}\n\n{tb}",
                    "error": str(e),
                }
            finally:
                self._rca_running = False

        self._rca_thread = threading.Thread(target=_run, daemon=True)
        self._rca_thread.start()


def build_alert_query(fault_type: str, alerts: list) -> str:
    """根据告警信息构建 RCA 查询语句"""
    profile = FAULT_PROFILES.get(fault_type, {})
    desc = profile.get("description", fault_type)
    affected = [a["service"] for a in alerts[:3]]
    services_str = "、".join(affected) if affected else "未知服务"
    return (
        f"系统检测到 {desc}，受影响服务包括 {services_str}，"
        f"请进行根因分析并给出处置建议。"
    )
