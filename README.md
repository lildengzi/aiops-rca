# Multi-Agent Microservice Fault Detection System

> AIOps Root Cause Analysis System - Multi-Agent Fault Detection Based on LangChain + LangGraph

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=fff)
![LangChain](https://img.shields.io/badge/LangChain-0.3+-1C3C3C?logo=langchain&logoColor=fff)
![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-3178C6)
![Streamlit](https://img.shields.io/badge/Streamlit-1.30+-FF4B4B?logo=streamlit&logoColor=fff)
![License](https://img.shields.io/badge/License-MIT-blue)

[English] | [中文](README_zh.md)

## 1. Project Overview

This system implements a multi-agent collaborative AI system that simulates expert team collaboration patterns for automated and intelligent root cause analysis (RCA) of faults in microservice systems. Built on **LangChain + LangGraph** framework with **ReAct (Reasoning + Acting)** pattern, it leverages LLM reasoning capabilities and external tool invocation for dynamic fault analysis, iterative validation, and progressive convergence.

### Core Features

- **Anomaly Detection**: Input any alert description, system scans monitoring sample datasets and identifies anomaly patterns based on evidence from metrics, logs, and traces
- **Multi-Agent Collaboration**: 6 specialized agents working together for complex fault diagnosis
- **ReAct Pattern**: Alternating reasoning and action for iterative convergence to high-confidence root causes
- **Tool-Based Data Access**: Metrics, logs, traces, and topology encapsulated as callable tools (MCP simulation)
- **Transparent Workflow**: All agent inputs, outputs, and decision rationale explicitly recorded
- **Structured Output**: Standardized event analysis reports

## 2. System Architecture

```
+------------------------------------------------------------------+
|                        User Input / Alert                        |
+-----------------------------+------------------------------------+
                              v
+------------------------------------------------------------------+
|                    Master Agent (Orchestrator)                  |
|              Task Planning - Scheduling - Reflection              |
+-------+-----------------+----------------+-----------------------+
        v                 v                v
+----------+     +---------------+    +---------------+
|  Metric  |     |      Log      |    |     Trace     |
|  Agent   |     |    Agent      |    |    Agent      |
+------+---+     +------+-------+    +------+--------+
       +---------------+----------------+
                      v
+------------------------------------------------------------------+
|                      Aggregate Node                             |
|              Parallel Aggregation - Sync - Fault Tolerance       |
+----------------------------+-------------------------------------+
                              v
+------------------------------------------------------------------+
|                    Analyst Agent                                 |
|          Evidence Integration - Logic Validation - Decision      |
+-------------------+----------------------------------------------------+
                    |
           +--------+--------+
           v                 v
    [Continue]          [Stop]
    Return to Master         |
                              v
+------------------------------------------------------------------+
|                    Reporter Agent                                |
|                   Generate Analysis Report                      |
+------------------------------------------------------------------+
```

## 3. Project Structure

> Supplement for the current repository state: besides the core modules below, the project now also includes `benchmark.py`, `defense_demo.py`, `benchmark_results/`, `feedback/`, and `think_log/` for experiments, demos, user feedback, and full reasoning logs.

```
aiops-rca/
├── main.py                    # CLI entry point (requires LLM API Key)
├── app.py                     # Streamlit Web UI entry
├── config.py                  # System configuration
├── build_knowledge_base.py    # Knowledge base builder
├── requirements.txt           # Python dependencies
├── .env.example               # Environment template
├── agents/                    # Agent definitions
│   ├── __init__.py
│   ├── master_agent.py        # Master - Task planning
│   ├── metric_agent.py        # Metric analysis agent
│   ├── log_agent.py           # Log analysis agent
│   ├── trace_agent.py         # Trace/topology analysis agent
│   ├── analyst_agent.py       # Analyst - Decision arbitration
│   └── reporter_agent.py      # Reporter - Report generation
├── tools/                     # Tool layer (MCP simulation)
│   ├── __init__.py
│   ├── metric_tools.py        # Metric query tools
│   ├── log_tools.py           # Log query tools
│   ├── trace_tools.py         # Trace query tools
│   └── topology_tools.py      # Topology/CMDB tools
├── workflow/                  # Workflow orchestration
│   ├── __init__.py
│   ├── orchestrator.py        # LangGraph workflow entry
│   ├── builder.py             # Workflow builder
│   ├── state.py              # Workflow state definition
│   ├── utils.py              # Workflow utilities
│   └── nodes/                # Workflow nodes
│       ├── __init__.py
│       ├── detect_fault_node.py  # Fault type detection node
│       ├── master_node.py     # Master node
│       ├── metric_node.py     # Metric node
│       ├── log_node.py        # Log node
│       ├── trace_node.py      # Trace node
│       ├── analyst_node.py    # Analyst node
│       ├── reporter_node.py   # Reporter node
│       └── aggregate_node.py  # Aggregate node
├── ui/                        # Web UI components
│   ├── __init__.py
│   ├── sidebar.py            # Sidebar navigation
│   ├── analysis_page.py      # Fault analysis page
│   ├── dashboard_page.py     # Dashboard page
│   ├── history_page.py       # History page
│   ├── knowledge_page.py     # Knowledge base page
│   ├── feedback_page.py     # Feedback page
│   ├── voice_input.py        # Voice input component
│   └── image_input.py        # Image upload component
├── input_modules/             # Multimodal input backend
│   ├── __init__.py
│   ├── voice.py              # Voice recognition backend
│   └── image.py             # Image analysis backend
├── cli/                       # CLI components
│   ├── __init__.py
│   ├── runner.py              # CLI runner
│   ├── display.py             # Display utilities
│   └── reporting.py           # Report generation
├── utils/                     # Utilities
│   ├── __init__.py
│   ├── data_loader.py         # Data loading
│   ├── anomaly_detection.py   # Anomaly detection algorithms
│   ├── csv_processor.py        # CSV validation and processing
│   └── service_parser.py       # Service name/metric extraction
├── data/                      # Test datasets
│   ├── data1.csv             # Monitoring sample data
│   ├── data2.csv             # Monitoring sample data
│   ├── data3.csv             # Monitoring sample data
│   ├── data4.csv             # Monitoring sample data
│   └── data5.csv             # Monitoring sample data
├── knowledge_base/            # Knowledge base
│   ├── __init__.py
│   ├── rca_knowledge.md      # RCA expert knowledge
│   ├── knowledge_manager.py  # Knowledge manager
│   ├── rag_index.py          # RAG index builder
│   ├── data_analyzer.py       # Data analyzer
│   ├── fault_patterns.py     # Fault pattern library
│   ├── fault_patterns.json   # Predefined anomaly patterns
│   └── storage.py            # Knowledge storage
├── logs/                      # System logs
├── models/                    # Model files
├── bin/                       # Deployment scripts
└── reports/                   # Generated reports (auto-created)
```

## 4. Quick Start

### 4.1 Environment Setup

```bash
pip install -r requirements.txt
```

### 4.2 Web UI (Recommended)

```bash
streamlit run app.py
```

Browser opens http://localhost:8501

### 4.3 Full Multi-Agent Analysis (Requires LLM API Key)

```bash
# Auto-detect fault type (recommended)
python main.py --query "frontend service delay increase, analyze root cause"

# Explicitly specify fault type
python main.py --fault cpu --query "frontend service CPU spike"

# Limit the number of reasoning iterations
python main.py --query "system reports OOM alert" --max-iter 3

# Disable full-analysis mode and focus on the target service only
python main.py --query "frontend latency spike" --disable-full-analysis

# Interactive mode
python main.py --interactive
```

### 4.4 Multimodal Input (Web UI)

System supports three input methods:

| Input Method | Description |
|-------------|-------------|
| Text Input | Direct alert description or natural language |
| Voice Input | Click record button, supports Chinese/English |
| Image Upload | Upload monitoring charts, auto-generate alert |

### Fault Analysis Mode

System supports two modes:
1. **Auto Detection (Default)**: Input any alert, system automatically scans monitoring sample datasets to identify anomaly patterns
2. **Manual Mode**: Use `--fault` parameter to specify which sample dataset to load (cpu/delay/disk/loss/mem)

## 5. Runtime Outputs and Auxiliary Scripts

### 5.1 Generated Outputs

After CLI or Web analysis runs, the system will create the following directories automatically when needed:

| Path | Description |
|------|-------------|
| `reports/` | Final RCA reports in Markdown format |
| `think_log/` | Full agent reasoning / workflow logs |
| `feedback/` | User feedback records from the Streamlit page |
| `benchmark_results/` | Saved benchmark comparison results |

### 5.2 Auxiliary Scripts

| Script | Description |
|--------|-------------|
| `benchmark.py` | Comparison with traditional SRE/statistical methods |
| `defense_demo.py` | Defense / presentation-oriented demo output |
| `build_knowledge_base.py` | Build or refresh the fault knowledge base |

### 5.3 Current Web UI Pages

The Streamlit app currently exposes these pages through the sidebar:

- **Fault Trend**: trend monitoring and high-frequency fault statistics
- **Fault Analysis**: text / voice / image input for RCA
- **History**: browse and download generated reports
- **Knowledge Base**: inspect knowledge-base related content
- **Feedback**: collect diagnosis feedback for later improvement

> Note: in the current implementation, fault auto-detection is handled inside the workflow node `detect_fault_node`, while `main.py` keeps a compatibility placeholder function.

## 6. UI Pages

System contains 5 main pages via sidebar:

| Page | Function |
|-----|---------|
| Fault Trend | System fault trends and statistics |
| Fault Analysis | Multimodal input, run analysis, view reports |
| History | Historical analysis reports |
| Knowledge Base | Fault knowledge and RAG management |
| Feedback | User feedback management |

## 7. Agent Design

### 7.1 Master Agent
- **Role**: SRE Expert / Commander
- **Responsibilities**: Parse alerts, create plans, dispatch agents, adjust strategy
- **Output**: Structured action plan (JSON format)

### 7.2 Metric Agent
- **Tools**: `query_service_metrics`, `query_all_services_overview`, `query_metric_correlation`
- **Capabilities**: Z-Score anomaly detection, change point detection, correlation analysis

### 7.3 Log Agent
- **Tools**: `query_service_logs`, `search_error_patterns`
- **Capabilities**: Error pattern extraction, stack trace analysis, log clustering

### 7.4 Trace Agent
- **Tools**: `query_service_traces`, `analyze_call_chain`, `get_full_topology`
- **Capabilities**: Call chain analysis, propagation path identification

### 7.5 Analyst Agent
- **Responsibilities**: Evidence integration, logic validation, confidence assessment, stop decision
- **Principles**: Occam's razor, topology priority, explicit reasoning

### 7.6 Reporter Agent
- **Output**: Structured event analysis report

## 8. Core Technologies

### 8.1 ReAct Pattern
Alternating reasoning and action for iterative convergence:
1. **Thought**: Generate hypothesis based on evidence
2. **Action**: Call tools to get new data
3. **Observation**: Analyze tool results
4. **Repeat**: Update hypothesis, decide continue/stop

### 8.2 LangGraph State Graph
- Dynamic parallel execution
- Aggregate node for result consolidation
- Analyst decision for iteration control
- State persistence across iterations
- Maximum iteration limits

### 8.3 RAG Knowledge Base
FAISS-based RAG knowledge system:
- Expert knowledge storage
- Semantic anomaly pattern matching
- 5 predefined anomaly pattern templates
- Historical case learning

Rebuild index:
```bash
python build_knowledge_base.py
```

## 9. Dataset Description

RCAEval benchmark dataset (RE1 subset), Online Boutique microservice system:

| File     | Description          |
|----------|----------------------|
| data1.csv | Monitoring sample with anomaly patterns |
| data2.csv | Monitoring sample with anomaly patterns |
| data3.csv | Monitoring sample with anomaly patterns |
| data4.csv | Monitoring sample with anomaly patterns |
| data5.csv | Monitoring sample with anomaly patterns |

Each dataset contains 12+ microservices with CPU, memory, latency, load, error rate metrics. The system analyzes evidence from metrics, logs, and traces to identify anomaly patterns and root cause candidates, rather than relying on dataset file names.

### Analysis Flow

1. Scan monitoring sample datasets
2. Call `query_all_services_overview` for anomaly overview
3. Analyze anomaly count and severity across services
4. Identify anomaly patterns based on evidence
5. Use detected patterns for subsequent deep analysis

## 10. Configuration

Adjust in `config.py`:

| Parameter | Description | Default |
|-----------|-------------|---------|
| z_score_threshold | Anomaly detection sensitivity | 3.0 |
| max_iterations | ReAct max iterations | 5 |
| convergence_threshold | Analyst stop decision threshold | 0.8 |

## 11. Data Integration API (utils/)

The `utils/data_loader.py` module provides the API for accessing real operational data.

### Primary API

| Function | Description |
|----------|-------------|
| `load_fault_data(fault_type)` | Load fault data (priority: real-time cache > CSV). `fault_type`: cpu/delay/disk/loss/mem |
| `set_realtime_data(fault_type, df)` | Inject real-time data from monitoring systems |

**Usage:**
```python
import pandas as pd
from utils.data_loader import set_realtime_data, load_fault_data

# Inject real-time monitoring data
df = pd.read_json("your_realtime_data.json")
set_realtime_data("cpu", df)

# Load data (auto-uses real-time cache if available)
df = load_fault_data("cpu")
```

## 12. Environment Variables

Create `.env` file:
```
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=https://api.openai.com/v1
LLM_MODEL=your_model_name
```