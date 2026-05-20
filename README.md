# 基于多智能体的微服务系统故障检测系统

> AIOps 根因分析系统 —— 基于 LangChain + LangGraph 实现 ReAct 模式多智能体协作的微服务故障智能诊断

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=fff)
![LangChain](https://img.shields.io/badge/LangChain-0.3+-1C3C3C?logo=langchain&logoColor=fff)
![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-3178C6)
![Streamlit](https://img.shields.io/badge/Streamlit-1.30+-FF4B4B?logo=streamlit&logoColor=fff)
![License](https://img.shields.io/badge/License-MIT-blue)

[English](README.md) | 中文

## 一、项目概述

本系统构建了一个基于多智能体协作的 AI 系统，模拟人类专家团队的协作模式，对微服务系统中发生的故障进行自动化、智能化的根因分析（RCA）。系统采用 **LangChain + LangGraph** 框架，通过 **ReAct（Reasoning + Acting）** 模式，将大模型的推理能力与外部工具调用能力深度融合，实现对故障问题的动态拆解、迭代验证与逐步收敛。

### 核心特性

- **异常检测与根因分析**：用户输入任意告警信息，系统自动扫描监控样本数据集，结合指标、日志、链路等证据识别异常模式并分析根因候选
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

> 根据当前仓库状态补充说明：除下面的核心模块外，项目目前还包含 `benchmark.py`、`benchmark_case_loader.py`、`defense_demo.py`、`开发文档.txt` 等文件，分别用于基准案例加载、对比实验、答辩演示与开发说明；运行过程中会自动创建 `reports/`、`think_log/` 等产物目录。

```
aiops-rca/
├── main.py                    # CLI 入口
├── app.py                     # Streamlit Web 界面入口（委托 ui.app）
├── config.py                  # 系统配置
├── build_knowledge_base.py    # 知识库构建工具
├── benchmark.py               # 基准实验脚本
├── benchmark_case_loader.py   # 基准案例加载
├── defense_demo.py            # 答辩演示脚本
├── requirements.txt           # Python 依赖
├── .env.example               # 环境变量模板
├── agents/                    # 智能体定义
│   ├── master_agent.py        # 运维专家 - 任务规划
│   ├── metric_agent.py        # 指标分析智能体
│   ├── log_agent.py           # 日志分析智能体
│   ├── trace_agent.py         # 链路/拓扑分析智能体
│   ├── analyst_agent.py       # 值班长 - 决策仲裁
│   └── reporter_agent.py      # 运营专家 - 报告生成
├── tools/                     # 工具层（指标 / 日志 / 链路 / 拓扑）
│   ├── metric_tools.py
│   ├── log_tools.py
│   ├── trace_tools.py
│   └── topology_tools.py
├── workflow/                  # LangGraph 工作流编排
│   ├── orchestrator.py        # 工作流入口
│   ├── builder.py             # 工作流构建器
│   ├── state.py               # 工作流状态定义
│   ├── graph_state.py         # 图状态定义
│   ├── query_builders.py      # 查询构造
│   ├── summary.py             # 分析结果摘要
│   └── nodes/                 # 工作流节点
│       ├── detect_fault_node.py
│       ├── retrieve_knowledge_node.py
│       ├── master_node.py
│       ├── metric_node.py
│       ├── log_node.py
│       ├── trace_node.py
│       ├── analyst_node.py
│       ├── reporter_node.py
│       └── aggregate_node.py
├── ui/                        # Web 界面组件
│   ├── app.py
│   ├── sidebar.py
│   ├── analysis_page.py
│   ├── dashboard_page.py
│   ├── history_page.py
│   ├── knowledge_page.py
│   ├── feedback_page.py
│   ├── voice_input.py
│   └── image_input.py
├── input_modules/             # 多模态输入后端
│   ├── voice.py
│   └── image.py
├── knowledge_base/            # 知识库与向量索引
│   ├── retriever.py
│   ├── schemas.py
│   ├── store.py
│   └── faiss_index/
├── llm/                       # 模型与结构化输出封装
├── utils/                     # 工具库
│   ├── data_loader.py
│   ├── anomaly_detection.py
│   ├── csv_processor.py
│   └── service_parser.py
├── benchmark/                 # 基准数据目录
├── docs/                      # 文档目录
├── reports/                   # 生成的报告（自动创建）
└── think_log/                 # 推理日志（自动创建）
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

### 4.3 CLI 运行

```bash
# 使用默认基准数据文件运行
python main.py

# 指定自然语言输入
python main.py --input "frontend 服务延迟升高，请分析根因"

# 指定 CSV 数据文件
python main.py --csv benchmark/real_data.csv

# 指定时间窗口
python main.py --input "检查 10:00 到 10:30 的异常" --start 1714557600 --end 1714559400
```

### 4.4 多模态输入（Web界面）

系统支持三种输入方式：

| 输入方式 | 说明                                 |
| -------- | ------------------------------------ |
| 文本输入 | 直接输入告警描述或自然语言问题       |
| 语音输入 | 点击录制按钮，支持中文/英文语音识别  |
| 图表上传 | 上传监控图表，自动识别并生成告警描述 |

### 故障分析模式

当前 CLI 入口以自然语言告警描述 + 指定遥测 CSV 的方式运行。默认数据文件为 `benchmark/real_data.csv`，也可以通过 `--csv` 参数切换到其他数据文件。

## 五、运行产物与辅助脚本

### 5.1 运行产物

执行 CLI 或 Web 分析后，系统会在需要时自动创建以下目录：

| 路径           | 说明                         |
| -------------- | ---------------------------- |
| `reports/`   | 最终根因分析报告（Markdown） |
| `think_log/` | 多智能体完整分析过程日志     |
| `docs/`      | 项目文档目录                 |

### 5.2 辅助脚本

| 脚本                        | 说明                            |
| --------------------------- | ------------------------------- |
| `benchmark.py`            | 与传统 SRE / 统计方法的对比实验 |
| `defense_demo.py`         | 面向答辩展示的演示脚本          |
| `build_knowledge_base.py` | 构建或刷新故障知识库            |

## 六、界面说明

系统包含5个主要页面，通过左侧sidebar切换：

| 页面           | 功能                           |
| -------------- | ------------------------------ |
| Fault Trend    | 系统故障趋势统计和高频故障排行 |
| Fault Analysis | 多模态输入、执行分析、查看报告 |
| History        | 历史分析报告列表               |
| Knowledge Base | 故障知识库管理和RAG索引        |
| Feedback       | 用户反馈管理                   |

## 七、智能体设计

### 7.1 运维专家 Agent（Master）

- **角色**：SRE运维专家/总指挥
- **职责**：解析告警、制定排查计划、调度下游智能体
- **输出**：结构化排查计划（JSON格式）

### 7.2 指标分析 Agent（Metric）

- **工具**：`query_service_metrics`, `query_all_services_overview`, `query_metric_correlation`
- **能力**：Z-Score异常检测、变化点检测、指标相关性分析

### 7.3 日志分析 Agent（Log）

- **工具**：`query_service_logs`, `search_error_patterns`
- **能力**：错误模式提取、异常堆栈分析、日志聚类

### 7.4 链路分析 Agent（Trace）

- **工具**：`query_service_traces`, `analyze_call_chain`, `get_full_topology`
- **能力**：调用链分析、故障传播路径识别

### 7.5 值班长 Agent（Analyst）

- **职责**：证据整合、逻辑校验、置信度评估、停止判断
- **原则**：奥卡姆剃刀、依赖拓扑优先

### 7.6 运营专家 Agent（Reporter）

- **输出**：结构化事件分析报告

## 八、核心技术实现

### 8.1 ReAct 模式

交替执行"推理"与"行动"，迭代收敛至高置信度根因：

1. **Thought**：基于证据生成假设
2. **Action**：调用工具获取数据
3. **Observation**：分析工具结果
4. **Repeat**：更新假设，决定是否继续

### 8.2 LangGraph 状态图

- 动态并行执行
- 聚合节点汇总结果
- 值班长决策控制迭代
- 状态持久化
- 最大迭代限制

### 8.3 RAG 知识库

基于FAISS向量数据库的RAG知识系统：

- 专家知识存储
- 语义异常模式匹配
- 预定义5类异常模式参考
- 历史案例学习

构建索引：

```bash
python build_knowledge_base.py
```

## 九、数据集说明

项目当前默认从 `benchmark/real_data.csv` 读取遥测数据，适用于基于时间序列指标的离线 RCA 分析。运行时也可以通过 `--csv` 参数切换到其他同结构 CSV 文件。

### 分析流程

1. 读取遥测 CSV 数据
2. 调用工具获取异常概览
3. 分析各服务异常指标数量和严重程度
4. 基于观测证据识别异常模式
5. 生成根因候选与分析报告

## 十、配置说明

在 `config.py` 中可调整部分关键配置，例如：

- `MAX_ITERATIONS`：最大迭代次数（默认 3）
- `DEFAULT_ZSCORE_THRESHOLD`：异常检测灵敏度（默认 2.5）
- `DEFAULT_TOP_K_SERVICES`：默认关注的异常服务数量（默认 3）
- `DEFAULT_WINDOW_SIZE`：默认分析窗口大小（默认 30）

## 十一、数据接入接口 (utils/)

`utils/data_loader.py` 模块提供接入真实运维数据的API接口。

### 核心接口

| 函数                                  | 描述                                                                      |
| ------------------------------------- | ------------------------------------------------------------------------- |
| `load_fault_data(fault_type)`       | 加载故障数据（优先实时缓存>CSV）。`fault_type`: cpu/delay/disk/loss/mem |
| `set_realtime_data(fault_type, df)` | 从监控系统注入实时数据                                                    |

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

## 十二、环境变量

创建 `.env`文件：

```
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=https://api.openai.com/v1
LLM_MODEL=your_model_name
```

## 十三、验收方法

本节用于软硬件验收时快速演示，建议按“基线对比 -> 知识库追加 -> CLI 单案例分析”的顺序执行。

### 13.1 30 个案例小量基线测试对比

该对比用于说明系统不是只做页面展示，而是可以在 RCAEval 案例集上批量验证根因召回效果。下面命令会把结果写入 `test_outputs/`，同时生成同名 Markdown 摘要。

1. 简单传统规则基线：

```powershell
python experiment_traditional_baseline.py --limit 30 --mode simple --top-k 5 --output test_outputs/traditional_simple_30.json
```

2. 增强传统规则基线：

```powershell
python experiment_traditional_baseline.py --limit 30 --mode enhanced --top-k 5 --output test_outputs/traditional_enhanced_30.json
```

3. 多智能体 RCA 系统：

```powershell
python experiment_rcaeval.py --limit 30 --top-k 5 --output test_outputs/rcaeval_agent_30.json
```

4. 查看输出文件：

```powershell
Get-ChildItem test_outputs\*30.md
```

数据口径解释：

- `traditional_simple_30.md`：只按指标、日志关键词、调用链出现情况排序。
- `traditional_enhanced_30.md`：在规则基线上增加服务名归一化和基础设施过滤。
- `rcaeval_agent_30.md`：使用多智能体任务拆解、多源证据融合、RAG 知识库和回退补证流程。
- 重点看 `Top-1`、`Top-K`、`MRR` 三个指标；Top-K 表示真实根因是否被纳入候选集合，适合说明系统能帮助人工快速缩小排查范围。

如需按数据集小量抽样，可以使用：

```powershell
python experiment_rcaeval.py --per-dataset 5 --top-k 5 --output test_outputs/rcaeval_agent_per_dataset_20.json
python experiment_traditional_baseline.py --limit 30 --dataset re3-tt --mode enhanced --top-k 5 --output test_outputs/traditional_enhanced_re3_tt_30.json
```

### 13.2 知识库内容追加方法

知识库支持两种演示方式：Web 页面手工追加，以及命令行从案例集重建索引。

#### 方式一：Web 页面追加单条知识

1. 启动 Web：

```powershell
streamlit run app.py
```

2. 打开左侧菜单 `知识库管理`。
3. 在 `新增知识条目` 中填写：
   - 标题：例如 `frontend latency caused by carts cpu`
   - 内容：描述故障现象、证据和处置经验。
   - 服务：例如 `carts`
   - 故障类型：例如 `cpu` 或 `latency`
   - 根因：例如 `carts`
   - 解决建议：例如 `检查 carts 服务 CPU 限额、近期发布和热点请求`
   - 标签：例如 `carts,cpu,latency,manual`
   - 元数据：保持 `{}` 或填写合法 JSON。
4. 点击 `新增条目`。
5. 点击页面右上侧 `重建索引`，让新增内容参与后续 RAG 检索。

验收讲解口径：这一步证明系统可以把人工复盘经验沉淀到知识库，后续遇到相似故障时作为辅助证据。

#### 方式二：从 RCAEval 案例重建知识库

该方式适合批量构建知识库。注意：下面命令会重建 `knowledge_base/documents.json` 和 `knowledge_base/faiss_index/`，不是增量追加。

```powershell
python build_knowledge_base.py --case-dir benchmark/rcaeval --limit 30
```

只构建某个数据集：

```powershell
python build_knowledge_base.py --case-dir benchmark/rcaeval --dataset re3-tt --limit 30
```

从普通 CSV 构建：

```powershell
python build_knowledge_base.py --csv benchmark/simple_metrics.csv
```

### 13.3 CLI 运行方法示例

CLI 适合演示“输入一句告警，输出结构化 RCA 摘要和报告预览”。

1. 使用默认数据运行：

```powershell
python main.py
```

2. 指定告警描述：

```powershell
python main.py --input "frontend 延迟升高，请分析根因"
```

3. 指定 RCAEval 某个案例目录作为数据源：

```powershell
python main.py --data-path benchmark/rcaeval/re2-ss/RE2-SS/carts_cpu/1 --input "frontend latency is increasing, please identify the root cause"
```

4. 指定时间窗口：

```powershell
python main.py --data-path benchmark/real_data.csv --input "frontend 延迟升高，请分析根因" --start 1714557600 --end 1714559400
```

运行完成后重点查看：

- 终端 JSON 摘要：包含根因候选、证据统计、置信度和产物路径。
- `reports/`：自动生成的 Markdown 根因分析报告。
- `think_log/`：多智能体分析过程日志，便于说明系统判断依据可追溯。
