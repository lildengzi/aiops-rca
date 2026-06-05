# 基于多智能体的微服务系统故障根因分析系统

> AIOps RCA 原型系统：面向微服务可观测数据的离线根因分析、证据聚合、知识检索和实验评估工具。

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=fff)
![LangChain](https://img.shields.io/badge/LangChain-0.3+-1C3C3C?logo=langchain&logoColor=fff)
![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-3178C6)
![Streamlit](https://img.shields.io/badge/Streamlit-1.44+-FF4B4B?logo=streamlit&logoColor=fff)

## 一、项目概述

本项目实现了一个面向微服务故障诊断的 AIOps RCA 系统。系统以 RCAEval 风格 case 目录或普通 CSV 遥测文件为输入，围绕一次告警描述组织多智能体协作，自动读取指标、日志、调用链和拓扑证据，输出根因候选、证据矩阵、处置建议、Markdown 报告和推理日志。

当前实现重点是离线可复现实验与演示，而不是直接接入线上监控系统。默认配置使用离线规则引擎完成分析；如配置 OpenAI 兼容接口，可启用 LLM 推理；知识库检索默认开启，向量后端默认使用 TF-IDF，也可按配置切换。

### 核心能力

- **多源证据分析**：支持指标、日志、调用链、日志模板和拓扑关系等证据。
- **多智能体协作**：按知识检索、任务规划、指标分析、日志分析、调用链分析、证据汇总、根因研判和报告生成拆分流程。
- **RCAEval case 支持**：可从 `benchmark/` 自动发现包含 `metrics.json`、`metrics.csv` 或 `simple_metrics.csv` 的 case 目录。
- **匿名演示界面**：Web 侧隐藏标注答案和真实 case 标签，只展示用于分析的输入、证据覆盖和结论。
- **RAG 知识库**：支持从 RCAEval case 或 CSV 构建 `knowledge_base/documents.json` 与索引。
- **实验评估**：提供多智能体 RCA 与传统规则基线的批量评估脚本，输出 Top-1、Top-K、MRR 等指标。
- **可追溯产物**：每次分析生成报告和 Think Log，便于复盘智能体执行过程。

## 二、系统流程

```text
用户告警 / RCAEval case / CSV 数据
        |
        v
数据加载与故障上下文识别
        |
        v
知识库检索 retrieve_knowledge
        |
        v
主控规划 master
        |
        +--> 指标分析 metric
        +--> 日志分析 log
        +--> 调用链与拓扑分析 trace
        |
        v
证据聚合 aggregate
        |
        v
根因研判 analyst
        |
        +--> 证据不足时回到 master 继续迭代
        |
        v
报告生成 reporter
```

## 三、项目结构

```text
aiops-rca/
├── app.py                         # Streamlit 入口，委托 ui.app
├── main.py                        # CLI 入口
├── config.py                      # 路径、模型、RAG、迭代次数等配置
├── build_knowledge_base.py        # 知识库文档与索引构建
├── benchmark_case_loader.py       # RCAEval case 发现与元数据加载
├── experiment_rcaeval.py          # 多智能体 RCA 批量评估
├── experiment_traditional_baseline.py # 传统规则基线评估
├── requirements.txt
├── agents/                        # 各智能体实现与提示词
├── workflow/                      # LangGraph 工作流、状态、节点与摘要
├── tools/                         # 指标、日志、调用链、拓扑工具
├── utils/                         # 数据加载、异常检测、服务解析等工具
├── knowledge_base/                # 知识库 schema、存储、检索与索引
├── llm/                           # LLM 与 embedding 适配层
├── ui/                            # Streamlit 页面
├── input_modules/                 # 语音输入和图片/OCR 输入
├── benchmark/                     # 本地 benchmark / RCAEval 数据目录
├── reports/                       # 自动生成的 Markdown 报告
├── think_log/                     # 自动生成的推理过程日志
└── test_outputs/                  # 实验脚本输出
```

## 四、快速开始

### 4.1 安装依赖

```powershell
pip install -r requirements.txt
```

语音和图片输入依赖 `faster-whisper`、`Pillow`、`pytesseract`、`opencv-python`、`rapidocr-onnxruntime` 等包。OCR 如使用本地 Tesseract，还需要系统中安装对应可执行程序。

### 4.2 配置环境变量

复制 `.env.example` 为 `.env`，按需要修改：

```env
LLM_PROVIDER=offline
MODEL_NAME=offline-rule-engine
ENABLE_LLM_REASONING=false
ENABLE_RAG_RETRIEVAL=true
EMBEDDING_PROVIDER=tfidf
MAX_ITERATIONS=3
KB_TOP_K=3
```

如需调用 OpenAI 兼容模型，可设置：

```env
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=https://api.openai.com/v1
LLM_PROVIDER=openai
MODEL_NAME=your_model_name
ENABLE_LLM_REASONING=true
```

### 4.3 启动 Web 界面

```powershell
streamlit run app.py
```

默认地址为 `http://localhost:8501`。Web 侧会从 `benchmark/` 自动加载可用 case，在侧边栏选择数据集、场景和 case 后运行分析。

### 4.4 CLI 单次分析

```powershell
# CLI 代码默认指向 benchmark/real_data.csv；如果本地没有该文件，请显式指定数据路径
python main.py --data-path benchmark/simple_metrics.csv --input "frontend 延迟升高，请分析根因"

# 指定 RCAEval case 目录
python main.py --data-path benchmark/rcaeval/re2-ss/RE2-SS/carts_cpu/1 --input "frontend latency is increasing, please identify the root cause"

# 指定普通 CSV 文件
python main.py --data-path benchmark/simple_metrics.csv --input "frontend 延迟升高，请分析根因"

# 指定时间窗口
python main.py --data-path benchmark/simple_metrics.csv --input "frontend 延迟升高，请分析根因" --start 1714557600 --end 1714559400
```

CLI 会在终端输出结构化 JSON 摘要，并预览生成的 Markdown 报告。

## 五、数据输入说明

### RCAEval case 目录

case 目录至少需要包含以下任一指标文件：

- `metrics.json`
- `metrics.csv`
- `simple_metrics.csv`

可选证据文件：

- `logs.csv`
- `logts.csv`
- `traces.csv`
- `inject_time.txt`
- `root_cause.txt`

系统会自动归一化时间列为 `time`，并从指标列名中解析服务与指标关系。

### 普通 CSV 文件

普通 CSV 需要包含时间列 `time` 或 `timestamp`。服务指标列建议采用能被解析出服务名和指标名的命名方式，例如：

```text
time,frontend_latency,carts_cpu,checkout_error_rate
```

## 六、Web 页面

当前 Web 应用包含 5 个页面：

| 页面 | 说明 |
| --- | --- |
| 故障分析 | 选择 case、输入告警、合并语音/OCR 补充信息、运行 RCA、查看结论和报告 |
| 故障趋势 | 展示历史报告与故障趋势统计 |
| 历史报告 | 浏览 `reports/` 下的历史分析结果 |
| 知识库 | 查看、追加知识条目并重建索引 |
| 反馈 | 记录用户反馈 |

Web 侧会隐藏 benchmark 标注答案，避免演示时直接暴露根因标签；评估脚本仍会使用标注答案计算指标。

## 七、智能体与节点职责

| 节点 / 智能体 | 职责 |
| --- | --- |
| `retrieve_knowledge` | 基于告警、候选服务和指标检索历史知识 |
| `master` | 解析问题、选择重点服务和指标、制定并迭代调查计划 |
| `metric` | 检测指标异常、服务异常强度和指标相关性 |
| `log` | 分析日志、错误模式和日志模板异常 |
| `trace` | 分析调用链证据，并结合静态拓扑判断传播路径 |
| `aggregate` | 合并指标、日志、调用链和知识库证据 |
| `analyst` | 对候选根因排序，给出置信度、证据缺口和是否继续迭代 |
| `reporter` | 生成 Markdown 根因分析报告 |

## 八、知识库构建

从 RCAEval case 批量构建知识库：

```powershell
python build_knowledge_base.py --case-dir benchmark/rcaeval --limit 30
```

按数据集过滤：

```powershell
python build_knowledge_base.py --case-dir benchmark/rcaeval --dataset re3-tt --limit 30
```

从普通 CSV 构建：

```powershell
python build_knowledge_base.py --csv benchmark/simple_metrics.csv
```

默认输出：

- `knowledge_base/documents.json`
- `knowledge_base/faiss_index/`

注意：当前构建命令会重写目标文档文件和索引目录，不是增量追加。Web 页面中的手动新增条目适合少量补充知识。

## 九、实验评估

### 9.1 多智能体 RCA 评估

```powershell
python experiment_rcaeval.py --limit 30 --top-k 5 --output test_outputs/rcaeval_agent_30.json
```

常用过滤参数：

```powershell
python experiment_rcaeval.py --dataset re3-tt --limit 30 --top-k 5 --output test_outputs/rcaeval_agent_re3_tt_30.json
python experiment_rcaeval.py --per-dataset 5 --top-k 5 --output test_outputs/rcaeval_agent_per_dataset.json
```

脚本会同时生成 JSON 和 Markdown 摘要，统计 Top-1、Top-K、MRR、RAG 命中、回退触发等信息。

### 9.2 传统规则基线

```powershell
python experiment_traditional_baseline.py --limit 30 --mode simple --top-k 5 --output test_outputs/traditional_simple_30.json
python experiment_traditional_baseline.py --limit 30 --mode enhanced --top-k 5 --output test_outputs/traditional_enhanced_30.json
```

`simple` 模式按指标、日志关键词和调用链出现情况排序；`enhanced` 模式会增加服务名归一化和基础设施噪声过滤。

## 十、运行产物

| 路径 | 说明 |
| --- | --- |
| `reports/` | 单次 RCA 分析生成的 Markdown 报告 |
| `think_log/` | 工作流节点执行过程与推理日志 |
| `test_outputs/` | 实验评估 JSON 与 Markdown 摘要 |
| `knowledge_base/documents.json` | 知识库文档 |
| `knowledge_base/faiss_index/` | 知识检索索引 |

## 十一、关键配置

配置来自 `config.py` 和 `.env`：

| 配置 | 默认值 | 说明 |
| --- | --- | --- |
| `MAX_ITERATIONS` | `3` | Analyst 判断证据不足时允许回到 Master 的最大迭代轮数 |
| `ENABLE_LLM_REASONING` | `false` | 是否启用 LLM 推理 |
| `ENABLE_RAG_RETRIEVAL` | `true` | 是否启用知识库检索 |
| `DEFAULT_ZSCORE_THRESHOLD` | `2.5` | 指标异常检测阈值 |
| `DEFAULT_TOP_K_SERVICES` | `3` | 默认关注的候选服务数量 |
| `DEFAULT_WINDOW_SIZE` | `30` | 默认分析窗口大小 |
| `KB_TOP_K` | `3` | 知识库检索返回条数 |
| `EMBEDDING_PROVIDER` | `tfidf` | embedding 后端 |
| `REPORTS_DIR` | `reports` | 报告输出目录 |
| `THINK_LOG_DIR` | `think_log` | 推理日志输出目录 |
| `TEST_OUTPUTS_DIR` | `test_outputs` | 实验输出目录 |

## 十二、适用范围与限制

- 当前系统主要用于离线 RCA 原型验证、论文/答辩演示、实验评估和知识库沉淀。
- 默认不会直接连接 Prometheus、Loki、Jaeger、CMDB 等线上系统；这些能力在当前代码中以本地文件和工具层封装形式模拟。
- 知识库命中只作为辅助证据，根因判断仍应以当前 case 的指标、日志、调用链和拓扑证据为主。
- Top-1 命中不应被过度包装；Top-K、证据覆盖、失败类型分析更适合说明系统作为排障辅助工具的价值。
