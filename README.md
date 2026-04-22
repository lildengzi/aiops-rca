# 基于多智能体的微服务系统故障检测系统

> AIOps 根因分析系统 —— 基于 LangChain + LangGraph 实现 ReAct 模式多智能体协作的微服务故障智能诊断

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=fff)
![LangChain](https://img.shields.io/badge/LangChain-0.3+-1C3C3C?logo=langchain&logoColor=fff)
![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-3178C6)
![Streamlit](https://img.shields.io/badge/Streamlit-1.30+-FF4B4B?logo=streamlit&logoColor=fff)
![License](https://img.shields.io/badge/License-MIT-blue)

## 一、项目概述

本系统构建了一个基于多智能体协作的 AI 系统，模拟人类专家团队的协作模式，对微服务系统中发生的故障进行自动化、智能化的根因分析（RCA）。系统采用 **LangChain + LangGraph** 框架，通过 **ReAct（Reasoning + Acting）** 模式，将大模型的推理能力与外部工具调用能力深度融合，实现对故障问题的动态拆解、迭代验证与逐步收敛。

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
│  指标   │    │  日志       │      │  链路/拓扑   │
│ Agent    │  │ Agent        │  │ Agent         │
│ (Metric) │  │ (Log)        │  │ (Trace)       │
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
├── main.py                    # 主入口（需要 LLM API Key）
├── demo_offline.py            # 离线演示（无需 API Key）
├── app.py                     # Streamlit Web 界面入口
├── config.py                  # 系统配置
├── build_knowledge_base.py      # 知识库构建工具
├── .env.example               # 环境变量模板
├── agents/                    # 智能体定义
│   ├── __init__.py
│   ├── master_agent.py        # 运维专家 - 任务规划
│   ├── metric_agent.py        # 指标分析智能体
│   ├── log_agent.py           # 日志分析智能体
│   ├── trace_agent.py         # 链路/拓扑分析智能体
│   ├── analyst_agent.py       # 值班长 - 决策仲裁
│   └── reporter_agent.py      # 运营专家 - 报告生成
├── tools/                     # 工具层（模拟 MCP 服务）
│   ├── __init__.py
│   ├── metric_tools.py        # 指标查询工具
│   ├── log_tools.py           # 日志查询工具
│   ├── trace_tools.py         # 链路追踪工具
│   ├── topology_tools.py      # CMDB/拓扑工具
│   └── extract_reports_logs.py # 报告日志提取工具
├── workflow/                   # 工作流编排
│   ├── __init__.py
│   ├── orchestrator.py        # LangGraph 工作流入口
│   ├── builder.py             # 工作流构建器
│   ├── state.py               # 工作流状态定义
│   ├── utils.py               # 工作流工具函数
│   └── nodes/                 # 工作流节点实现
│       ├── __init__.py
│       ├── master_node.py       # 运维专家节点
│       ├── metric_node.py     # 指标分析节点
│       ├── log_node.py        # 日志分析节点
│       ├── trace_node.py     # 链路分析节点
│       ├── analyst_node.py     # 值班长节点
│       ├── reporter_node.py  # 报告生成节点
│       └── aggregate_node.py  # 证据聚合节点
├── ui/                         # Web界面组件
│   ├── __init__.py
│   ├── sidebar.py            # 侧边栏导航
│   ├── analysis_page.py     # 故障分析页面
│   ├── dashboard_page.py    # 监控仪表盘
│   ├── history_page.py     # 历史报告页面
│   ├── knowledge_page.py   # 知识库管理页面
│   ├── voice_input.py    # 语音输入组件
│   └── image_input.py     # 图表上传组件
├── input_modules/              # 多模态输入后端
│   ├── __init__.py
│   ├── voice.py            # 语音识别后端
│   └── image.py            # 图像分析后端
├── utils/                     # 工具库
│   ├── __init__.py
│   ├── data_loader.py         # 数据加载
│   └── anomaly_detection.py   # 异常检测算法
├── data/                      # 测试数据（最小演示数据集）
│   └── real_data/            # 真实场景故障数据
├── knowledge_base/            # 知识库
│   ├── __init__.py
│   ├── rca_knowledge.md       # RCA 专家知识
│   ├── knowledge_manager.py   # 知识库管理器
│   ├── rag_index.py           # RAG 索引构建
│   ├── data_analyzer.py       # 数据分析工具
│   ├── fault_patterns.py      # 故障模式库
│   └── storage.py             # 知识库存储
├── logs/                       # 系统运行日志
├── models/                     # 模型文件
├── bin/                       # 一键部署\运行脚本
└── reports/                   # 生成的报告（自动创建）

```

## 四、快速开始

### 1. 环境准备

安装依赖：

```bash
pip install -r requirements.txt
```

### 2. Web 界面启动（推荐）

双击运行 `run.bat` 或执行：

```bash
streamlit run app.py
```

浏览器自动打开 http://localhost:8501

### 3. 离线演示（无需 API Key）

```bash
python demo_offline.py
```

### 4. 完整多智能体运行（需要 LLM API Key）

```bash
# 自动检测故障类型（推荐）
python main.py --query "frontend服务延迟升高，请分析根因"

# 也可显式指定故障类型
python main.py --fault cpu --query "frontend服务CPU飙升，请分析根因"

# 交互模式
python main.py --interactive
```

### 5. 多模态输入（Web界面）

系统支持三种输入方式：

#### 5.1 文本输入（默认）
直接输入告警描述或自然语言问题。

#### 5.2 语音输入
点击"🎤 语音输入"标签页：
- 点击录制按钮，支持中文/英文语音
- 系统自动识别语音为文本
- 确认后发送进行分析

#### 5.3 图表上传
点击"🖼️ 图表上传"标签页：
- 上传监控图表（柱状图/折线图/时序图等）
- 系统自动识别图表内容，提取关键数据点
- 生成告警描述发送分析

### 故障类型自动检测说明

系统支持两种模式：
1. **自动检测模式**（默认）：用户输入任意告警描述（如"frontend服务报错了"），系统自动扫描5种数据集，依据异常指标数量和严重程度自动判断故障类型
2. **手动指定模式**：通过 `--fault` 参数显式指定故障类型（cpu/delay/disk/loss/mem）

## 五、界面说明

### 5.1 页面导航

系统包含4个主要页面，通过左侧 sidebar 切换：

- **📊 故障趋势监控 (Dashboard)**
  - 查看系统故障趋势统计
  - 高频故障服务排行
  - 近期告警列表

- **🔍 故障分析 (Analysis)**
  - 多模态输入：文本/语音/图表
  - 执行根因分析
  - 查看分析报告

- **📜 历史报告 (History)**
  - 查看历史分析报告
  - 下载报告文件

- **📚 知识库管理 (Knowledge)**
  - 编辑故障知识库
  - 管理 RAG 索引

### 5.2 多模态输入组件

#### 文本输入
- 支持自然语言告警描述
- 自动故障类型识别

#### 语音输入
- Streamlit audio_input 组件
- 调用语音识别后端（VoiceInputBackend）
- 支持中文/英文识别

#### 图表上传
- 支持PNG/JPG/GIF/BMP/WebP格式
- 自动识别图表类型（柱状图/折线图等）
- 提取数据点、趋势、极值等信息
- 生成告警描述

## 六、智能体设计

### 6.1 运维专家 Agent（Master）

- **角色**：SRE 运维专家 / 总指挥
- **职责**：解析告警、制定排查计划、调度下游智能体、根据反馈调整策略
- **知识库**：访问 RAG 知识库获取历史故障排查经验
- **输出**：结构化的排查步骤计划（JSON 格式）

### 6.2 指标分析 Agent（Metric）

- **角色**：时序数据分析专家
- **工具**：`query_service_metrics`, `query_all_services_overview`, `query_metric_correlation`
- **知识库**：检索指标异常模式匹配历史案例
- **能力**：Z-Score 异常检测、变化点检测、指标相关性分析

### 6.3 日志分析 Agent（Log）

- **角色**：SLS 日志分析专家
- **工具**：`query_service_logs`, `search_error_patterns`
- **知识库**：匹配日志错误模式与已知故障
- **能力**：错误模式提取、异常堆栈分析、日志聚类

### 6.4 链路分析 Agent（Trace）

- **角色**：分布式追踪诊断专家
- **工具**：`query_service_traces`, `analyze_call_chain`, `lookup_service_topology`, `get_full_topology`
- **知识库**：检索故障传播路径历史案例
- **能力**：调用链分析、故障传播路径识别、拓扑感知

### 6.5 值班长 Agent（Analyst）

- **角色**：决策仲裁者
- **职责**：证据整合、逻辑校验、置信度评估、停止判断
- **知识库**：基于历史案例评估根因置信度
- **原则**：奥卡姆剃刀、依赖拓扑优先、显性化推理

### 6.6 运营专家 Agent（Reporter）

- **角色**：报告生成专家
- **输出**：结构化事件分析报告（问题简述、影响概述、根因分析、优化建议）

## 七、核心技术实现

### 7.1 ReAct 模式

系统采用 ReAct（Reasoning + Acting）模式，交替执行推理与工具调用：

1. **Thought**：基于当前证据生成的假设
2. **Action**：调用对应工具获取新数据
3. **Observation**：分析工具
4. **Repeat**：更新假设，决定是否继续

### 7.2 LangGraph 状态图

使用 LangGraph 构建有状态的工作流图，支持：

- 动态并行执行：指标/日志/链路分析智能体并行执行
- 聚合节点：等待所有并行任务完成后统一汇总结果
- 值班长决策：基于整合证据判断是否继续迭代
- 状态持久化：各轮分析结果累积存储
- 最大迭代控制：避免无限循环

### 7.3 RAG 知识库系统

系统内置基于 FAISS 向量数据库的 RAG（检索增强生成）知识库：

- **专家知识存储**：基于 `rca_knowledge.md` 构建结构化专家知识库
- **语义检索**：支持故障场景语义化匹配，自动检索相关根因模式
- **故障模式库**：预定义5类典型故障模式（CPU/延迟/磁盘/丢包/内存）
- **知识自学习**：支持从历史分析案例中自动学习并更新故障模式
- **无依赖降级**：LangChain 依赖缺失时自动降级为关键词匹配模式

使用 `build_knowledge_base.py` 脚本可重新构建向量索引：
```bash
python build_knowledge_base.py
```

## 八、数据集说明

使用 RCAEval 基准数据集（RE1 子集），包含 Online Boutique 微服务系统的5种故障场景：

| 数据文件  | 故障类型 | 描述             |
| --------- | -------- | ---------------- |
| data1.csv | CPU      | CPU 资源耗尽故障 |
| data2.csv | Delay    | 服务延迟异常     |
| data3.csv | Disk     | 磁盘 I/O 异常    |
| data4.csv | Loss     | 网络丢包故障     |
| data5.csv | Memory   | 内存泄漏/OOM     |

每种数据包含 12+ 微服务的 CPU、内存、延迟、流量、错误率等多维指标。

### 自动检测流程

当用户输入告警且未指定故障类型时，系统自动执行以下流程：

1. 依次扫描 cpu, delay, disk, loss, mem 五个数据集
2. 对每个数据集调用 `query_all_services_overview` 获取异常概览
3. 分析各数据集的异常指标数量和严重程度
4. 根据异常特征判断最可能的故障类型
5. 后续迭代使用检测到的故障类型进行专项深入分析

## 九、配置说明

### 关键参数

在 `config.py` 中可调整：

- `z_score_threshold`: 异常检测灵敏度（默认 3.0）
- `max_iterations`: ReAct 最大迭代次数（默认 5）
- `convergence_threshold`: 值班长停止判断阈值（默认 0.8）
