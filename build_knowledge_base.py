#!/usr/bin/env python3
"""
知识库构建脚本 - 从所有数据集自动生成故障模式知识库
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from knowledge_base.knowledge_manager import get_knowledge_manager

def main():
    print("="*60)
    print("  AIOps 知识库构建工具")
    print("="*60)
    
    km = get_knowledge_manager()
    
    print("\n📊 正在从所有数据集构建知识库...")
    results = km.build_knowledge_from_all_datasets()
    
    print("\n✅ 知识库构建完成！")
    print(f"\n📈 分析结果统计:")
    for fault_type, analysis in results.items():
        print(f"  - {fault_type}: {len(analysis.get('anomaly_distribution', {}))} 个异常服务")
        print(f"    典型服务: {', '.join(analysis.get('typical_services_observed', []))}")
    
    print(f"\n💾 知识库已保存至: knowledge_base/fault_patterns.json")
    
    # 显示知识库统计
    print(f"\n📚 当前知识库包含 {len(km.fault_patterns)} 种故障模式:")
    for ft, pattern in km.fault_patterns.items():
        print(f"  - {ft}: {pattern['name']}")

if __name__ == "__main__":
    main()
