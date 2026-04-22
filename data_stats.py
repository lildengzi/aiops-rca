import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import glob


DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
REPORTS_DIR = os.path.join(os.path.dirname(__file__), "reports")

SERVICE_NAMES = [
    "paymentservice", "cartservice", "checkoutservice", "currencyservice",
    "emailservice", "frontend", "main", "adservice", "productcatalogservice",
    "recommendationservice", "redis", "shippingservice"
]

FAULT_TYPES = ["cpu", "memory", "delay", "disk", "network"]


def load_csv_data(csv_path):
    """加载CSV数据"""
    if not os.path.exists(csv_path):
        return None
    try:
        df = pd.read_csv(csv_path)
        return df
    except Exception:
        return None


def generate_mock_realtime_data(hours=24, anomaly_probability=0.15):
    """生成模拟实时数据（按小时）"""
    now = datetime.now()
    data = []
    
    for i in range(hours * 6):
        timestamp = int((now - timedelta(minutes=i * 10)).timestamp())
        row = {"timestamp": timestamp, "time": timestamp}
        
        is_anomaly = np.random.random() < anomaly_probability
        
        for service in SERVICE_NAMES:
            if is_anomaly and np.random.random() < 0.3:
                base_cpu = np.random.uniform(60, 95)
            else:
                base_cpu = np.random.uniform(5, 40)
            row[f"{service}_cpu"] = round(base_cpu, 2)
            
            base_mem = np.random.uniform(10, 50) * 1e6
            row[f"{service}_mem"] = int(base_mem)
            
            base_workload = np.random.uniform(20, 200) if not (is_anomaly and np.random.random() < 0.2) else np.random.uniform(300, 800)
            row[f"{service}_workload"] = round(base_workload, 2)
        
        for service in ["frontend", "frontend-external"]:
            row[f"{service}_error"] = int(is_anomaly and np.random.random() < 0.4) * np.random.randint(0, 50)
        
        for service in SERVICE_NAMES:
            row[f"{service}_latency-50"] = round(np.random.uniform(0.001, 0.01), 6)
            row[f"{service}_latency-90"] = round(np.random.uniform(0.005, 0.05), 6)
        
        if is_anomaly and np.random.random() < 0.5:
            row["fault_type"] = np.random.choice(FAULT_TYPES)
            row["fault_service"] = np.random.choice(SERVICE_NAMES)
        else:
            row["fault_type"] = "normal"
            row["fault_service"] = "none"
        
        data.append(row)
    
    data.reverse()
    return pd.DataFrame(data)


def analyze_fault_trends(df):
    """分析故障趋势"""
    if df is None or df.empty:
        return {"labels": [], "values": [], "fault_count": 0}
    
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="s")
    df = df.sort_values("timestamp")
    
    fault_count = 0
    if "fault_type" in df.columns:
        fault_count = len(df[df["fault_type"] != "normal"])
    
    cpu_cols = [c for c in df.columns if c.endswith("_cpu")]
    if cpu_cols:
        df["avg_cpu"] = df[cpu_cols].mean(axis=1)
    else:
        df["avg_cpu"] = 0
    
    df["hour"] = df["datetime"].dt.floor("H")
    hourly = df.groupby("hour").agg({
        "avg_cpu": "mean",
        "timestamp": "count"
    }).reset_index()
    hourly["time_label"] = hourly["hour"].dt.strftime("%H:%M")
    
    return {
        "labels": hourly["time_label"].tolist(),
        "values": [round(v, 2) for v in hourly["avg_cpu"].tolist()],
        "fault_count": fault_count,
        "total_points": len(df)
    }


def analyze_fault_statistics(df):
    """分析高频故障统计"""
    if df is None or df.empty:
        return {"fault_types": [], "fault_services": []}
    
    result = {"fault_types": [], "fault_services": []}
    
    if "fault_type" in df.columns:
        fault_df = df[df["fault_type"] != "normal"]
        if not fault_df.empty:
            type_counts = fault_df["fault_type"].value_counts().to_dict()
            result["fault_types"] = [
                {"name": k, "count": int(v)} for k, v in type_counts.items()
            ]
            
            service_counts = fault_df["fault_service"].value_counts().to_dict()
            result["fault_services"] = [
                {"name": k, "count": int(v)} for k, v in service_counts.items()
            ]
    
    return result


def get_topology_fault_stats():
    """从报告目录分析历史故障统计"""
    stats = {
        "total_reports": 0,
        "fault_types": {},
        "services": {},
        "recent_faults": []
    }
    
    if not os.path.exists(REPORTS_DIR):
        return stats
    
    reports = glob.glob(os.path.join(REPORTS_DIR, "*.md"))
    stats["total_reports"] = len(reports)
    
    for report in reports[:50]:
        try:
            filename = os.path.basename(report)
            parts = filename.replace("rca_report_", "").replace(".md", "").split("_")
            if len(parts) >= 1:
                fault_type = parts[0]
                if fault_type in FAULT_TYPES:
                    stats["fault_types"][fault_type] = stats["fault_types"].get(fault_type, 0) + 1
        except Exception:
            continue
    
    for ft, count in stats["fault_types"].items():
        stats["fault_types"][ft] = count
    
    return stats


def get_dashboard_data():
    """获取仪表板所有数据"""
    trend_data = generate_mock_realtime_data(hours=24)
    trends = analyze_fault_trends(trend_data)
    fault_stats = analyze_fault_statistics(trend_data)
    history_stats = get_topology_fault_stats()
    
    combined = {
        "trend": trends,
        "fault_statistics": fault_stats,
        "history": history_stats,
        "generated_at": datetime.now().isoformat()
    }
    
    return combined


if __name__ == "__main__":
    data = get_dashboard_data()
    print(json.dumps(data, ensure_ascii=False, indent=2))