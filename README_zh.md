# 基于多智能体的微服务系统故障检测系统

> AIOps 根因分析系统 —— 基于 LangChain + LangGraph 实现 ReAct 模式多智能体协作的微服务故障智能诊断

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=fff)
![LangChain](https://img.shields.io/badge/LangChain-0.3+-1C3C3C?logo=langchain&logoColor=fff)
![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-3178C6)
![Streamlit](https://img.shields.io/badge/Streamlit-1.30+-FF4B4B?logo=streamlit&logoColor=fff)
![License](https://img.shields.io/badge/License-MIT-blue)

[English](README.md) | 中文

## 一、项目概述

本系统构建了一个基于多智能体协作的 AI 系统，模拟人类专家团队的协作模式，对微服务系统中发生的故障进行自动化、智能化的根因分析（RCA）。系统采用 **LangChain + LangGraph** 框架，通�� **ReAct（Reasoning + Acting）** 模式，将大模型的推理能力与外部工具调用能力深度融合，实现对故障问题的动态拆解、迭代验证与逐步收敛。

### 核心特性

- **智能故障类型自动检测**：用户输入任意告警信息，系统自动扫描5种数据集（CPU/延迟/磁盘/丢包/内存），分析异常指标特征后自动识别故障类型，无需手动指定
- **多智能体协作**：6 个专业智能体各司其职，协同完成复杂故障诊断
- **ReAct 模式**：交替执行"推理"与"行动"，迭代收敛至高置信度根因
- **工具化数据接入**：将指标、日志、链路追踪、CMDB 封装为可调用工具（模拟 MCP 服务）
- **透明化工作流**：每个智能体的输入、输出及决策依据均被显式记录
- **结构化输出**：生成标准化的事件分析报告

## 二、系统架构

```
┌──────────────────────────────────────────────────────────────────┐
│                        用户输入 / 告警触发                         │
└──────────────────┬───────────────────────────────────────────────┘
                    ▼
┌──────────────────────────────────────────────────────────────────┐
│                     运维专家 Agent (Master)                     │
│              任务规划 · 调度 · 反思 · 调整计划                      │
└──────┬──────────────┬────────────────┬───────────────────────────┘
        ▼              ▼                ▼
┌──────────┐  ┌──────────────┐  ┌───────────────┐
│  指标    │  │  日志        │  │  链路/拓扑     │
│  Agent   │  │  Agent       │  │  Agent        │
└──────┬───┘  └──────┬───────┘  └───────┬───────┘
       └──────────────┼─────────────────┘
                      ▼
┌──────────────────────────────────────────────────────────────────┐
│                        聚合节点 (Aggregate)                      │
│               并行结果汇总 · 状态同步 · 容错处理                     │
└──────────────────────────┬───────────────────────────────────────┘
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│                     值班长 Agent (Analyst)                      │
│            证据整合 · 逻辑校验 · 决策仲裁 · 停止判断                 │
└──────────────────┬───────────────────────────────────────────────┘
                    │
           ┌────────┴────────┐
           ▼                 ▼
    [证据不足:继续]     [证据充分:停止]
    回到运维专家              │
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│                     运营专家 Agent (Reporter)                    │
│                    生成结构化事件分析报告                            │
└──────────────────────────────────────────────────────────────────┘
```

## 三、项目结构

```
aiops-rca/
├── main.py                    # CLI入口（需要LLM API Key）
├── demo_offline.py            # 离线演示（无需API Key）
├── app.py                     # Streamlit Web界面入口
├── config.py                  # 系统配置
├── build_knowledge_base.py    # 知识库构建工具
├── requirements.txt           # Python依赖
├── .env.example               # 环境变量模板
├── agents/                    # 智能体定义
│   ├── __init__.py
│   ├── master_agent.py        # 运维专家 - 任务规划
│   ├── metric_agent.py        # 指标分析智能体
│   ├── log_agent.py           # 日志分析智能体
│   ├── trace_agent.py         # 链路/拓扑分析智能体
│   ├── analyst_agent.py       # 值班长 - 决策仲裁
│   └── reporter_agent.py      # 运营专家 - 报告生成
├── tools/                     # 工具层（模拟MCP服务）
│   ├── __init__.py
│   ├── metric_tools.py        # 指标查询工具
│   ├── log_tools.py           # 日志查询工具
│   ├── trace_tools.py         # 链路追踪工具
│   ├── topology_tools.py      # CMDB/拓扑工具
│   └── extract_reports_logs.py # 报告日志提取
├── workflow/                   # 工作流编排
│   ├── __init__.py
│   ├── orchestrator.py        # LangGraph工作流入口
│   ├── builder.py             # 工作流构建器
│   ├── state.py               # 工作流状态定义
│   ├── utils.py               # 工作流工具函数
│   └── nodes/                 # 工作流节点
│       ├── __init__.py
│       ├── master_node.py     # 运维专家节点
│       ├── metric_node.py    # 指标分析节点
│       ├── log_node.py       # 日志分析节点
│       ├── trace_node.py     # 链路分析节点
│       ├── analyst_node.py   # 值班长节点
│       ├── reporter_node.py  # 报告生成节点
│       └── aggregate_node.py # 证据聚合节点
├── ui/                        # Web界面组件
│   ├── __init__.py
│   ├── sidebar.py             # 侧边栏导航
│   ├── analysis_page.py       # 故障分析页面
│   ├── dashboard_page.py     # 监控仪表盘
│   ├── history_page.py        # 历史报告页面
│   ├── knowledge_page.py      # 知识库管理页面
│   ├── feedback_page.py       # 反馈管理页面
│   ├── voice_input.py        # 语音输入组件
│   └── image_input.py         # 图表上传组件
├── input_modules/              # 多模态输入后端
│   ├── __init__.py
│   ├── voice.py               # 语音识别后端
│   └── image.py               # 图像分析后端
├── utils/                     # 工具库
│   ├── __init__.py
│   ├── data_loader.py         # 数据加载
│   └── anomaly_detection.py   # 异常检测算法
├── data/                      # 测试数据
│   ├── data1.csv             # CPU故障数据
│   ├── data2.csv             # 延迟故障数据
│   ├── data3.csv             # 磁盘故障数据
│   ├── data4.csv             # 丢包故障数据
│   ├── data5.csv             # 内存故障数据
│   └── real_data/            # 真实场景数据
├── knowledge_base/            # 知识库
│   ├── __init__.py
│   ├── rca_knowledge.md       # RCA专家知识
│   ├── knowledge_manager.py  # 知识库管理器
│   ├── rag_index.py           # RAG索引构建
│   ├── data_analyzer.py       # 数据分析工具
│   ├── fault_patterns.py     # 故障模式库
│   └── storage.py            # 知识库存储
├── logs/                      # 系统运行日志
├── models/                    # 模型文件
├── bin/                       # 部署脚本
└── reports/                   # 生成的报告（自动创建）
```

## 四、快速开始

### 4.1 环境准备

```bash
pip install -r requirements.txt
```

### 4.2 Web界面启动（推荐）

```bash
streamlit run app.py
```

浏览器自动打开 http://localhost:8501

### 4.3 离线演示

```bash
python demo_offline.py
```

### 4.4 完整多智能体运行（需要LLM API Key）

```bash
# 自动检测故障类型（推荐）
python main.py --query "frontend服务延迟升高，请分析根因"

# 显式指定故障类型
python main.py --fault cpu --query "frontend服务CPU飙升，请分析根因"

# 交互模式
python main.py --interactive
```

### 4.5 多模态输入（Web界面）

系统支持三种输入方式：

| 输入方式 | 说明 |
|---------|------|
| 文本输入 | 直接输入告警描述或自然语言问题 |
| 语音输入 | 点击录制按钮，支持中文/英文语音识别 |
| 图表上传 | 上传监控图表，自动识别并生成告警描述 |

### 故障类型自动检测

系统支持两种模式：
1. **自动检测模式**（默认）：输入任意告警，系统自动扫描5种数据集判断故障类型
2. **手动指定模式**：通过 `--fault` 参数指定（cpu/delay/disk/loss/mem）

## 五、界面说明

系统包含5个主要页面，通过左侧sidebar切换：

| 页面 | 功能 |
|-----|------|
| Fault Trend | 系统故障趋势统计和高频故障排行 |
| Fault Analysis | 多模态输入、执行分析、查看报告 |
| History | 历史分析报告列表 |
| Knowledge Base | 故障知识库管理和RAG索引 |
| Feedback | 用户反馈管理 |

## 六、智能体设计

### 6.1 运维专家 Agent（Master）
- **角色**：SRE运维专家/总指挥
- **职责**：解析告警、制定排查计划、调度下游智能体
- **输出**：结构化排查计划（JSON格式）

### 6.2 指标分析 Agent（Metric）
- **工具**：`query_service_metrics`, `query_all_services_overview`, `query_metric_correlation`
- **能力**：Z-Score异常检测、变化点检测、指标相关性分析

### 6.3 日志分析 Agent（Log）
- **工具**：`query_service_logs`, `search_error_patterns`
- **能力**：错误模式提取、异常堆栈分析、日志聚类

### 6.4 链路分析 Agent（Trace）
- **工具**：`query_service_traces`, `analyze_call_chain`, `get_full_topology`
- **能力**：调用链分析、故障传播路径识别

### 6.5 值班长 Agent（Analyst）
- **职责**：证据整合、逻辑校验、置信度评估、停止判断
- **原则**：奥卡姆剃刀、依赖拓扑优先

### 6.6 运营专家 Agent（Reporter）
- **输出**：结构化事件分析报告

## 七、核心技术实现

### 7.1 ReAct 模式
交替执行"推理"与"行动"，迭代收敛至高置信度根因：
1. **Thought**：基于证据生成假设
2. **Action**：调用工具获取数据
3. **Observation**：分析工具结果
4. **Repeat**：更新假设，决定是否继续

### 7.2 LangGraph 状态图
- 动态并行执行
- 聚合节点汇总结果
- 值班长决策控制迭代
- 状态持久化
- 最大迭代限制

### 7.3 RAG 知识库
基于FAISS向量数据库的RAG知识系统：
- 专家知识存储
- 语义故障匹配
- 预定义5类故障模式
- 历史案例学习

构建索引：
```bash
python build_knowledge_base.py
```

## 八、数据集说明

RCAEval基准数据集（RE1子集），Online Boutique微服务系统：

| 数据文件 | 故障类型 | 描述 |
|---------|---------|------|
| data1.csv | CPU | CPU资源耗尽故障 |
| data2.csv | Delay | 服务延迟异常 |
| data3.csv | Disk | 磁盘I/O异常 |
| data4.csv | Loss | 网络丢包故障 |
| data5.csv | Memory | 内存泄漏/OOM |

每种数据包含12+微服务的CPU、内存、延迟、流量、错误率等指标。

### 自动检测流程

1. 扫描cpu, delay, disk, loss, mem五个数据集
2. 调用`query_all_services_overview`获取异常概览
3. 分析各数据集异常指标数量和严重程度
4. 根据异常特征判断最可能的故障类型
5. 后续迭代使用检测到的故障类型深入分析

## 九、配置说明

在`config.py`中调整：

- `z_score_threshold`：异常检测灵敏度（默认3.0）
- `max_iterations`：ReAct最大迭代次数（默认5）
- `convergence_threshold`：值班长停止判断阈值（默认0.8）

## 十、数据接入接口 (utils/)

`utils/data_loader.py` 模块提供接入真实运维数据的API接口。

### 核心接口

| 函数 | 描述 |
|------|------|
| `load_fault_data(fault_type)` | 加载故障数据（优先实时缓存>CSV）。`fault_type`: cpu/delay/disk/loss/mem |
| `set_realtime_data(fault_type, df)` | 从监控系统注入实时数据 |

**调用方式：**
```python
import pandas as pd
from utils.data_loader import set_realtime_data, load_fault_data

# 注入实时监控数据
df = pd.read_json("your_realtime_data.json")
set_realtime_data("cpu", df)

# 加载数据（自动优先使用实时缓存）
df = load_fault_data("cpu")
```

## 十一、环境变量

创建`.env`文件：
```
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=https://api.openai.com/v1
LLM_MODEL=your_model_name
```