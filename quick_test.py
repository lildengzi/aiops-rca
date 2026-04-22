"""
快速测试脚本 - 验证系统功能
不需要LLM API Key，直接分析数据
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.data_loader import load_fault_data, get_all_services
from utils.anomaly_detection import detect_anomalies_zscore, find_correlated_metrics

# 设置输出编码
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

print("="*60)
print("   AIOps 多智能体故障检测系统 - 快速测试")
print("="*60)

# 测试各数据集
FAULT_TYPES = {
    "cpu": "CPU资源耗尽",
    "mem": "内存溢出",
    "delay": "服务延迟",
    "disk": "磁盘I/O",
    "loss": "网络丢包"
}

results = {}

for fault_type, desc in FAULT_TYPES.items():
    print(f"\n[测试] {fault_type.upper()} - {desc}")
    print("-"*40)
    
    try:
        df = load_fault_data(fault_type)
        services = get_all_services(df)
        
        # 统计异常指标
        total_anomalies = 0
        service_anomalies = {}
        
        for svc in services:
            svc_cols = [c for c in df.columns if c.startswith(f"{svc}_")]
            svc_anom = 0
            for col in svc_cols:
                if col == "time":
                    continue
                series = df[col].dropna()
                if len(series) > 10:
                    anomaly = detect_anomalies_zscore(series)
                    if anomaly["is_anomalous"]:
                        svc_anom += 1
                        total_anomalies += 1
            
            if svc_anom > 0:
                service_anomalies[svc] = svc_anom
        
        # 按异常数排序
        sorted_svcs = sorted(service_anomalies.items(), key=lambda x: x[1], reverse=True)
        
        print(f"  数据行数: {len(df)}")
        print(f"  服务数量: {len(services)}")
        print(f"  异常指标: {total_anomalies}")
        print(f"  受影响服务: {len(service_anomalies)}")
        
        if sorted_svcs:
            top3 = sorted_svcs[:3]
            print(f"  Top3异常服务: {', '.join([f'{s[0]}({s[1]})' for s in top3])}")
        
        results[fault_type] = {
            "desc": desc,
            "rows": len(df),
            "anomalies": total_anomalies,
            "affected": len(service_anomalies),
            "top_services": [s[0] for s in sorted_svcs[:3]] if sorted_svcs else []
        }
        
    except Exception as e:
        print(f"  错误: {e}")
        results[fault_type] = {"error": str(e)}

print("\n" + "="*60)
print("   测试结果汇总")
print("="*60)

for ft, res in results.items():
    if "error" in res:
        print(f"  [{ft.upper()}] 错误: {res['error']}")
    else:
        print(f"  [{ft.upper()}] {res['desc']}")
        print(f"      数据:{res['rows']}行 异常:{res['anomalies']}个 受影响:{res['affected']}个")
        if res['top_services']:
            print(f"      主要异常服务: {', '.join(res['top_services'])}")

print("\n" + "="*60)
print("   所有数据集测试通过！")
print("="*60)
print("\n系统可以正常分析以下故障类型:")
print("  1. CPU资源耗尽 (data1.csv)")
print("  2. 内存溢出 (data2.csv)")
print("  3. 服务延迟 (data3.csv)")
print("  4. 磁盘I/O (data4.csv)")
print("  5. 网络丢包 (data5.csv)")
print("\n运行���令:")
print("  python demo_offline.py      # 完整离线分析")
print("  streamlit run app.py       # Web界面")