"""
离线演示脚本（测试无知识库下整个工作流能否跑通）
"""
import sys
import os
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import numpy as np
from tabulate import tabulate

from config import FAULT_DATA_MAP, SERVICE_TOPOLOGY
from utils.data_loader import load_fault_data, get_all_services
from utils.anomaly_detection import (
    detect_anomalies_zscore,
    detect_anomalies_sliding_window,
    detect_change_point,
    find_correlated_metrics,
    rank_root_causes,
)


def analyze_fault_scenario(fault_type: str):
    """对指定故障场景进行完整的离线分析"""
    print(f"\n{'='*70}")
    print(f"   故障场景分析: {fault_type.upper()} 类故障")
    print(f"{'='*70}")

    # 1. 加载数据
    df = load_fault_data(fault_type)
    services = get_all_services(df)
    print(f"\n 数据概览:")
    print(f"   - 数据行数: {len(df)}")
    print(f"   - 时间范围: {df['time'].iloc[0]} ~ {df['time'].iloc[-1]}")
    print(f"   - 服务数量: {len(services)}")
    print(f"   - 指标列数: {len(df.columns) - 1}")
    print(f"   - 服务列表: {', '.join(services)}")

    # 2. 全局异常扫描
    print(f"\n{'─'*70}")
    print(f"   第一步: 全局异常扫描 ")
    print(f"{'─'*70}")

    all_anomalies = {}
    service_anomaly_summary = []

    for svc in services:
        svc_cols = [c for c in df.columns if c.startswith(f"{svc}_")]
        svc_anomalies = []
        for col in svc_cols:
            result = detect_anomalies_zscore(df[col])
            if result["is_anomalous"]:
                all_anomalies[col] = result
                svc_anomalies.append({
                    "指标": col,
                    "异常分数": f"{result['anomaly_score']:.4f}",
                    "最大Z值": f"{result['stats'].get('max_z_score', 0):.2f}",
                    "异常比例": f"{result.get('anomaly_ratio', 0):.2%}",
                })

        if svc_anomalies:
            service_anomaly_summary.append({
                "服务": svc,
                "异常指标数": len(svc_anomalies),
                "最高异常分数": max(float(a["异常分数"]) for a in svc_anomalies),
            })

    # 按异常程度排序
    service_anomaly_summary.sort(key=lambda x: x["最高异常分数"], reverse=True)

    print("\n 服务异常概览:")
    if service_anomaly_summary:
        print(tabulate(service_anomaly_summary, headers="keys", tablefmt="grid"))
    else:
        print("   未发现明显异常")

    # 详细异常指标
    if all_anomalies:
        ranked = rank_root_causes(all_anomalies)
        print("\n Top 10 异常指标排名 (可能的根因):")
        top_table = []
        for i, r in enumerate(ranked[:10], 1):
            top_table.append({
                "排名": i,
                "指标": r["metric"],
                "异常分数": f"{r['anomaly_score']:.4f}",
                "均值": f"{r['stats'].get('mean', 0):.2f}",
                "最大值": f"{r['stats'].get('max', 0):.2f}",
            })
        print(tabulate(top_table, headers="keys", tablefmt="grid"))

    # 3. 变化点检测
    print(f"\n{'─'*70}")
    print(f"   第二步: 变化点检测")
    print(f"{'─'*70}")

    change_points = []
    for col, anomaly in all_anomalies.items():
        cp = detect_change_point(df[col])
        if cp["has_change_point"]:
            change_points.append({
                "指标": col,
                "变化点位置": cp["change_point_index"],
                "变化点时间": int(df["time"].iloc[cp["change_point_index"]]) if cp["change_point_index"] < len(df) else "N/A",
            })

    if change_points:
        print(tabulate(change_points[:10], headers="keys", tablefmt="grid"))
    else:
        print("   未检测到明显变化点")

    # 4. 相关性分析
    print(f"\n{'─'*70}")
    print(f" 第三步: 指标相关性分析 (模拟 Trace Agent)")
    print(f"{'─'*70}")

    if ranked:
        top_metric = ranked[0]["metric"]
        print(f"\n   分析与 {top_metric} 高度相关的指标:")
        correlated = find_correlated_metrics(df, top_metric, threshold=0.6)
        if correlated:
            corr_table = [{"相关指标": c["metric"],
                          "相关系数": f"{c['correlation']:.4f}",
                          "方向": c["direction"]}
                         for c in correlated[:10]]
            print(tabulate(corr_table, headers="keys", tablefmt="grid"))
        else:
            print("   未发现高相关性指标")

    # 5. 拓扑分析
    print(f"\n{'─'*70}")
    print(f" 第四步: 拓扑传播分析")
    print(f"{'─'*70}")

    anomalous_services = set()
    for col in all_anomalies:
        for svc in services:
            if col.startswith(f"{svc}_"):
                anomalous_services.add(svc)

    propagation_paths = []
    for svc in anomalous_services:
        if svc in SERVICE_TOPOLOGY:
            upstream = [s for s, d in SERVICE_TOPOLOGY.items()
                       if svc in d.get("dependencies", [])]
            deps = SERVICE_TOPOLOGY[svc].get("dependencies", [])
            affected_deps = [d for d in deps if d in anomalous_services]
            propagation_paths.append({
                "异常服务": svc,
                "上游(被影响)": ", ".join(upstream) if upstream else "无",
                "下游(依赖)": ", ".join(deps) if deps else "无",
                "异常下游": ", ".join(affected_deps) if affected_deps else "无",
            })

    if propagation_paths:
        print(tabulate(propagation_paths, headers="keys", tablefmt="grid"))

    # 6. 根因推断（模拟值班长）
    print(f"\n{'─'*70}")
    print(f" 第五步: 根因推断 (模拟值班长 Agent)")
    print(f"{'─'*70}")

    if ranked:
        top_cause = ranked[0]
        metric_name = top_cause["metric"]
        svc_name = metric_name.rsplit("_", 1)[0] if "_" in metric_name else metric_name

        # 判断故障类型特征
        fault_desc = {
            "cpu": "CPU资源瓶颈",
            "mem": "内存泄漏或OOM",
            "delay": "服务响应延迟升高",
            "disk": "磁盘I/O异常",
            "loss": "网络丢包或连接异常",
        }

        print(f"""
    ┌─────────────────────────────────────────────────────┐
    │   根因分析结论                                        │
    ├─────────────────────────────────────────────────────┤
    │  根因服务:  {svc_name:<40s}                          │
    │  根因指标:  {metric_name:<40s}                       │
    │  异常分数:  {top_cause['anomaly_score']:<40.4f}      │
    │  故障类型:  {fault_desc.get(fault_type, '未知'):<38s}  │
    │  置信度:    {'HIGH' if top_cause['anomaly_score'] > 0.8 else 'MEDIUM':<40s} │
    └─────────────────────────────────────────────────────┘
        """)

        # 推理链
        print("     推理链:")
        print(f"    1. 全局扫描发现 {len(all_anomalies)} 个异常指标")
        print(f"    2. 异常分数最高的指标为 {metric_name} (score={top_cause['anomaly_score']:.4f})")
        print(f"    3. 该指标属于服务 {svc_name}")
        if svc_name in SERVICE_TOPOLOGY:
            deps = SERVICE_TOPOLOGY[svc_name].get("dependencies", [])
            if deps:
                print(f"    4. 该服务依赖: {', '.join(deps)}")
        upstream_svcs = [s for s, d in SERVICE_TOPOLOGY.items()
                        if svc_name in d.get("dependencies", [])]
        if upstream_svcs:
            print(f"    5. 受影响的上游服务: {', '.join(upstream_svcs)}")
        print(f"    6. 故障类型特征与 {fault_type} 场景一致")

    # 7. 生成报告摘要
    print(f"\n{'─'*70}")
    print(f"   第六步: 报告生成 (模拟运营专家 Agent)")
    print(f"{'─'*70}")

    print(f"""
### 事件分析报告

#### 一、问题简述
系统监控数据分析显示存在 {fault_desc.get(fault_type, '未知')} 类故障。
通过多维度数据关联分析，共发现 {len(all_anomalies)} 个异常指标，
涉及 {len(anomalous_services)} 个服务，根因定位于 {svc_name if ranked else '未确定'} 服务。

#### 二、影响概述
- 异常服务: {', '.join(anomalous_services)}
- 异常指标: {len(all_anomalies)} 个
- 最严重指标: {ranked[0]['metric'] if ranked else 'N/A'} (异常分数: {ranked[0]['anomaly_score']:.4f})

#### 三、根因分析
- 根因服务: {svc_name if ranked else '未确定'}
- 根因类型: {fault_desc.get(fault_type, '未知')}
- 置信度: {'HIGH' if ranked and ranked[0]['anomaly_score'] > 0.8 else 'MEDIUM'}

#### 四、优化建议
1. 对 {svc_name if ranked else '异常'} 服务进行资源扩容或配置优化
2. 检查近期是否有代码变更或配置修改
3. 增加相关服务的监控告警阈值覆盖
4. 建立故障自愈机制，实现自动化止损
    """)


def main():
    print("""
╔══════════════════════════════════════════════════════════════╗
║    AIOps 多智能体根因分析系统 - 离线演示                          ║
║    (无需 LLM API Key，直接运行异常检测算法)                       ║
╚══════════════════════════════════════════════════════════════╝
""")

    supported_fault_types = list(FAULT_DATA_MAP.keys())
    target_fault_type = (sys.argv[1].strip().lower() if len(sys.argv) > 1 else "cpu")

    if target_fault_type not in supported_fault_types:
        print(f"[警告] 不支持的故障类型: {target_fault_type}")
        print(f"[提示] 可选值: {', '.join(supported_fault_types)}")
        print("[提示] 将回退为 cpu 场景继续演示")
        target_fault_type = "cpu"

    try:
        analyze_fault_scenario(target_fault_type)
    except Exception as e:
        print(f"\n {target_fault_type} 场景分析失败: {e}")
        import traceback
        traceback.print_exc()

    print(f"\n{'='*70}")
    print(" 所有故障场景分析完成！")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()

