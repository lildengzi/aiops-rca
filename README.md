# AIOps RCA

基于多智能体工作流的微服务故障检测与根因分析原型系统。

## 项目简介
该项目面向微服务场景，围绕故障检测、证据汇聚、根因分析和报告输出，构建了一条可运行的 AIOps RCA 主链路。系统以 CSV 遥测数据为输入，通过多 Agent 协同完成故障类型识别、指标/日志/调用链分析、知识检索辅助推理，并生成结构化结果与中文分析报告。

## 当前能力
- 支持自然语言故障描述输入
- 支持基于 LangGraph 的多 Agent RCA 工作流
- 支持 metric / log / trace 并行分析与多维证据汇聚
- 支持知识库检索辅助分析
- 支持拓扑上下文参与推理
- 支持规则回退与 LLM 推理混合模式
- 支持生成 Markdown RCA 报告与 think log
- 支持 Streamlit 页面查看分析结果、历史报告和趋势统计

## 核心流程
主执行链路如下：

```text
detect_fault -> retrieve_knowledge -> master -> (metric || log || trace) -> aggregate -> analyst -> reporter
```

各节点职责：
- `detect_fault`：从用户输入中识别故障类型
- `retrieve_knowledge`：检索历史案例与知识库内容
- `master`：生成本轮排查计划
- `metric/log/trace`：并行执行多维证据分析
- `aggregate`：汇总并规范化三路证据
- `analyst`：融合证据并给出根因判断
- `reporter`：生成最终 RCA 报告

## 目录结构
```text
aiops_rca/
├── agents/            # 多智能体定义与提示词
├── workflow/          # LangGraph 工作流与状态管理
├── tools/             # 指标、日志、调用链、拓扑工具
├── knowledge_base/    # 知识库与检索逻辑
├── ui/                # Streamlit 页面
├── benchmark/         # 示例数据集
├── reports/           # RCA 报告输出
├── think_log/         # 过程日志输出
├── docs/              # 开发与接口说明文档
├── main.py            # CLI 入口
└── app.py             # 前端入口
```

## 安装依赖
建议使用 Python 3.10 及以上版本。

```bash
pip install -r requirements.txt
```

## CLI 运行方式
使用示例数据运行一次根因分析：

```bash
python main.py
```

等价显式参数：

```bash
python main.py --csv benchmark/real_data.csv --input "frontend 延迟升高，请分析根因"
```

可选时间窗口：

```bash
python main.py --csv benchmark/real_data.csv --input "checkoutservice 错误升高" --start 1710000000 --end 1710003600
```

CLI 会输出：
- 统一根因摘要 JSON
- 报告文件路径
- think log 路径
- 报告预览片段

## Demo / Benchmark
一键演示标准样例：

```bash
python defense_demo.py
```

仅输出统一摘要 JSON：

```bash
python defense_demo.py --json
```

运行离线 benchmark：

```bash
python benchmark.py
```

可选小样本快速验证：

```bash
python benchmark.py --sample-count 3 --window-size 20
```

## 前端运行方式
启动 Streamlit 页面：

```bash
streamlit run app.py
```

当前页面包括：
- 故障分析
- 故障趋势
- 历史报告
- 知识库查看
- 反馈页

## 报告输出
分析完成后会生成：
- `reports/*.md`：中文 RCA 报告
- `think_log/*.md`：节点执行过程记录

当前报告采用双层结构：
1. 顶部稳定头字段，便于页面或后续接口解析
2. 中文正文，包含问题简述、影响概述、问题原因、详细分析、传播路径、证据缺口与优化建议

## 相关文档
- `docs/langchain_langgraph_workflow_development_and_interface_spec.md`
- `docs/knowledge_base_development_and_interface_spec.md`
- `docs/frontend_interface_spec.md`
- `docs/prompt_reporting_alignment_development_and_interface_spec.md`

## 说明
该项目当前定位为实验/课程原型系统，重点在于：
- 多智能体协同诊断流程
- 多源证据融合
- 根因分析可解释性
- 报告输出与展示闭环

部分能力仍可继续增强，例如更强的 structured output 校验、持久化与更丰富的知识推理。
