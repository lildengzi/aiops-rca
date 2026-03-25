"""
可视化脚本 - 生成毕设论文所需的图表
包含：系统架构图(Mermaid)、异常检测结果图、服务拓扑图
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import numpy as np
from utils.data_loader import load_fault_data, get_all_services
from utils.anomaly_detection import detect_anomalies_zscore, rank_root_causes
from config import FAULT_DATA_MAP, SERVICE_TOPOLOGY


def generate_mermaid_workflow():
    """生成 LangGraph 工作流的 Mermaid 流程图"""
    mermaid = """```mermaid
graph TD
    A[用户输入/告警触发] --> B[运维专家 Agent<br/>任务规划与调度]
    B --> C[指标分析 Agent<br/>时序异常检测]
    B --> D[日志分析 Agent<br/>错误模式提取]
    B --> E[链路分析 Agent<br/>故障传播追踪]
    C --> F[值班长 Agent<br/>证据整合与决策]
    D --> F
    E --> F
    F -->|证据不足| B
    F -->|证据充分| G[运营专家 Agent<br/>报告生成]
    G --> H[结构化分析报告]

    style A fill:#e1f5fe
    style B fill:#fff3e0
    style C fill:#e8f5e9
    style D fill:#e8f5e9
    style E fill:#e8f5e9
    style F fill:#fce4ec
    style G fill:#f3e5f5
    style H fill:#e0f2f1
```"""
    return mermaid


def generate_mermaid_topology():
    """生成 Online Boutique 服务拓扑的 Mermaid 图"""
    mermaid = """```mermaid
graph LR
    FE[Frontend] --> AD[AdService]
    FE --> CS[CartService]
    FE --> CO[CheckoutService]
    FE --> CU[CurrencyService]
    FE --> PC[ProductCatalogService]
    FE --> RC[RecommendationService]
    FE --> SH[ShippingService]
    CS --> RD[Redis]
    CO --> CS
    CO --> CU
    CO --> EM[EmailService]
    CO --> PS[PaymentService]
    CO --> PC
    CO --> SH
    RC --> PC

    style FE fill:#ff9800,color:white
    style RD fill:#f44336,color:white
    style CO fill:#2196f3,color:white
```"""
    return mermaid


def generate_anomaly_heatmap_data():
    """生成异常热力图数据（CSV格式，可用 Excel/Python 绘图）"""
    results = {}
    for fault_type in FAULT_DATA_MAP:
        df = load_fault_data(fault_type)
        services = get_all_services(df)
        for svc in services:
            cols = [c for c in df.columns if c.startswith(f"{svc}_")]
            max_score = 0
            for col in cols:
                res = detect_anomalies_zscore(df[col])
                if res["is_anomalous"]:
                    max_score = max(max_score, res["anomaly_score"])
            if fault_type not in results:
                results[fault_type] = {}
            results[fault_type][svc] = round(max_score, 4)

    # 转为 DataFrame
    heatmap_df = pd.DataFrame(results)
    heatmap_df.index.name = "service"
    return heatmap_df


def generate_react_sequence():
    """生成 ReAct 模式时序图的 Mermaid 代码"""
    mermaid = """```mermaid
sequenceDiagram
    participant U as 用户/告警
    participant M as 运维专家
    participant MT as 指标Agent
    participant LG as 日志Agent
    participant TR as 链路Agent
    participant A as 值班长
    participant R as 运营专家

    U->>M: 告警信息
    Note over M: Thought: 分析告警,<br/>制定排查计划

    rect rgb(230, 245, 255)
        Note over M,A: 第1轮 ReAct 迭代
        M->>MT: Action: 全局指标扫描
        MT-->>M: Observation: 异常指标列表
        M->>LG: Action: 查询错误日志
        LG-->>M: Observation: 错误模式
        M->>TR: Action: 分析调用链
        TR-->>M: Observation: 故障传播路径
        M->>A: 提交第1轮证据
        Note over A: 评估证据充分性
        A-->>M: 需要继续: 补充RDS指标
    end

    rect rgb(255, 245, 230)
        Note over M,A: 第2轮 ReAct 迭代
        M->>MT: Action: 查询RDS详细指标
        MT-->>M: Observation: 连接数异常
        M->>LG: Action: 查询DB超时日志
        LG-->>M: Observation: Connection timeout
        M->>A: 提交第2轮证据
        Note over A: 证据充分,置信度>0.8
        A-->>R: 触发报告生成
    end

    R-->>U: 结构化分析报告
```"""
    return mermaid


def main():
    output_dir = os.path.join(os.path.dirname(__file__), "reports")
    os.makedirs(output_dir, exist_ok=True)

    print("📊 生成毕设论文图表...\n")

    # 1. 工作流图
    workflow = generate_mermaid_workflow()
    with open(os.path.join(output_dir, "workflow_diagram.md"), "w") as f:
        f.write("# 多智能体工作流架构图\n\n" + workflow)
    print(" 工作流架构图 → reports/workflow_diagram.md")

    # 2. 服务拓扑图
    topology = generate_mermaid_topology()
    with open(os.path.join(output_dir, "topology_diagram.md"), "w") as f:
        f.write("# Online Boutique 服务拓扑图\n\n" + topology)
    print(" 服务拓扑图 → reports/topology_diagram.md")

    # 3. ReAct 时序图
    react = generate_react_sequence()
    with open(os.path.join(output_dir, "react_sequence.md"), "w") as f:
        f.write("# ReAct 模式时序图\n\n" + react)
    print(" ReAct 时序图 → reports/react_sequence.md")

    # 4. 异常热力图数据
    print("\n 生成异常热力图数据...")
    heatmap = generate_anomaly_heatmap_data()
    heatmap.to_csv(os.path.join(output_dir, "anomaly_heatmap.csv"))
    print(" 异常热力图 → reports/anomaly_heatmap.csv")
    print("\n热力图数据预览:")
    print(heatmap.to_string())

    # 5. 各故障场景 Top5 根因
    print("\n\n 各故障场景 Top5 根因:")
    for fault_type in FAULT_DATA_MAP:
        df = load_fault_data(fault_type)
        all_anomalies = {}
        for col in df.columns:
            if col == "time":
                continue
            res = detect_anomalies_zscore(df[col])
            if res["is_anomalous"]:
                all_anomalies[col] = res
        ranked = rank_root_causes(all_anomalies)
        print(f"\n  [{fault_type.upper()}] Top 5:")
        for i, r in enumerate(ranked[:5], 1):
            print(f"    {i}. {r['metric']} (score={r['anomaly_score']:.4f})")

    print(f"\n 所有图表数据已生成到 {output_dir}/")


if __name__ == "__main__":
    main()
