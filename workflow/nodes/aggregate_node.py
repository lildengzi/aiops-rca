"""
并行结果汇总节点实现
"""
from datetime import datetime
from workflow.state import RCAState


def aggregate_node(state: RCAState) -> dict:
    """
    并行结果汇总节点：等待所有并行任务完成后汇总结果
    支持动态并行度和容错处理
    """
    ts = datetime.now().strftime("%H:%M:%S")
    
    # 检查各智能体执行状态
    status = []
    if state.get("metric_results"):
        status.append("指标分析: 完成")
    else:
        status.append("指标分析: 未执行/失败")
        
    if state.get("log_results"):
        status.append("日志分析: 完成")
    else:
        status.append("日志分析: 未执行/失败")
        
    if state.get("trace_results"):
        status.append("链路分析: 完成")
    else:
        status.append("链路分析: 未执行/失败")
    
    log_entry = f"[{ts}] 并行任务汇总完成 - {'; '.join(status)}"
    
    return {
        "thinking_log": [log_entry],
    }
