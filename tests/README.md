# AIOps RCA 测试模块

本目录包含 AIOps 根因分析系统的分模块测试。

## 测试结构

```
tests/
├── __init__.py                    # 模块初始化
├── conftest.py                    # pytest配置和公共fixtures
├── run_tests.py                   # 测试运行脚本
├── test_data_loader.py            # 数据加载模块测试
├── test_anomaly_detection.py      # 异常检测模块测试
├── test_knowledge_base.py         # 知识库模块测试（重点）
├── test_workflow.py               # 工作流测试（重点）
└── test_tools.py                  # 工具模块测试
```

## 运行测试

### 运行所有测试
```bash
cd E:\Repo\aiops-rca\aiops-rca
python tests/run_tests.py
```

### 运行指定模块测试
```bash
python tests/run_tests.py --module knowledge_base
python tests/run_tests.py --module workflow
python tests/run_tests.py --module data_loader
```

### 只运行知识库或工作流测试
```bash
python tests/run_tests.py --knowledge
python tests/run_tests.py --workflow
```

### 详细输出
```bash
python tests/run_tests.py --verbose
```

### 使用pytest直接运行
```bash
pytest tests/ -v
pytest tests/test_knowledge_base.py -v
```

## 测试重点

1. **知识库模块** (`test_knowledge_base.py`) - 重点测试
   - 知识库管理器初始化
   - 故障模式获取
   - 根因推荐
   - 缓解建议
   - RAG语义检索
   - 从数据分析故障
   - 知识库构建

2. **工作流模块** (`test_workflow.py`) - 重点测试
   - 工作流状态定义
   - 工作流构建
   - 知识库在工作流中的使用
   - 工作流配置

3. **数据加载模块** (`test_data_loader.py`)
   - 故障数据加载
   - 服务列表获取

4. **异常检测模块** (`test_anomaly_detection.py`)
   - Z-Score异常检测
   - 变化点检测
   - 相关性分析
   - 根因排序

5. **工具模块** (`test_tools.py`)
   - 拓扑工具
   - 指标工具
   - 链路追踪工具
   - 日志工具

## 注意事项

- 工作流测试中可能跳过需要LLM的测试（如果API不可用）
- 知识库测试不依赖LLM，应该使用FakeEmbeddings
- 所有测试都是为了验证功能是否跑通，不包含性能测试
- 不包含Web端(Streamlit)测试
