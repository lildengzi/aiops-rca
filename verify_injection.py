"""简单的数据注入验证"""
import sys
import os

_root = os.path.dirname(os.path.abspath(__file__))
if _root not in sys.path:
    sys.path.insert(0, _root)

from simulator.stream_generator import RealtimeStreamGenerator
from simulator.rca_adapter import RCAAdapter
from tools.metric_tools import get_data_cache

# 创建生成器和适配器
generator = RealtimeStreamGenerator(fault_type="cpu", fault_delay=2.0, tick_interval=0.1)
adapter = RCAAdapter(generator)

# 生成 5 个快照
print("生成快照...")
for i in range(5):
    snap = generator.next_snapshot()
    adapter.add_snapshot(snap)

# 注入到工具层
print("注入数据到工具层...")
adapter.inject_into_tools()

# 验证数据是否成功注入
df = get_data_cache("cpu")
if df is not None and not df.empty:
    print(f"✓ 数据成功注入！")
    print(f"  - 数据形状: {df.shape}")
    print(f"  - 列数: {len(df.columns)}")
    print(f"  - 前几列: {list(df.columns[:5])}")
    print(f"  - 数据样本:\n{df.head(2)}")
else:
    print("✗ 数据注入失败")
