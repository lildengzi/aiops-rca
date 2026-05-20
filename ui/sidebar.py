from __future__ import annotations

from typing import Any

import streamlit as st

from benchmark_case_loader import build_case_context, iter_benchmark_cases, list_benchmark_datasets

PAGES = [
    ("analysis", "故障分析"),
    ("dashboard", "故障趋势"),
    ("history", "历史报告"),
    ("knowledge", "知识库"),
    ("feedback", "反馈"),
]


@st.cache_data(show_spinner=False)
def _get_benchmark_cases() -> list[dict[str, Any]]:
    return iter_benchmark_cases()


@st.cache_data(show_spinner=False)
def _get_benchmark_datasets() -> list[str]:
    return list_benchmark_datasets()


def render_sidebar() -> str:
    st.sidebar.title("AIOps RCA")
    benchmark_cases = _get_benchmark_cases()
    benchmark_datasets = _get_benchmark_datasets()

    if "selected_page" not in st.session_state:
        st.session_state.selected_page = "analysis"
    st.session_state.setdefault("selected_benchmark_dataset", "")
    st.session_state.setdefault("selected_benchmark_scenario", "")
    st.session_state.setdefault("selected_benchmark_case", "")
    st.session_state.setdefault("selected_benchmark_case_dir", "")
    st.session_state.setdefault("selected_benchmark_case_metadata", {})
    st.session_state.setdefault("data_path", "")
    st.session_state.setdefault("csv_path", "")
    st.session_state.setdefault("analysis_input", "")
    st.session_state.setdefault("analysis_start_raw", "")
    st.session_state.setdefault("analysis_end_raw", "")

    key_by_label = {label: key for key, label in PAGES}
    selected_label = st.sidebar.radio(
        "页面",
        options=[label for _, label in PAGES],
        index=[key for key, _ in PAGES].index(st.session_state.selected_page),
    )
    st.session_state.selected_page = key_by_label[selected_label]

    st.sidebar.caption("数据源：RCAEval case 目录")
    if st.sidebar.button("刷新 benchmark cases", width="stretch"):
        _get_benchmark_cases.clear()
        _get_benchmark_datasets.clear()
        benchmark_cases = _get_benchmark_cases()
        benchmark_datasets = _get_benchmark_datasets()

    if not benchmark_cases:
        st.sidebar.error("benchmark/ 下没有找到 RCAEval case。")
        st.sidebar.caption("期望文件：metrics.json、logs.csv、traces.csv、inject_time.txt。")
        return st.session_state.selected_page

    if not benchmark_datasets:
        benchmark_datasets = sorted({str(case.get("dataset") or "local") for case in benchmark_cases})

    current_dataset = st.session_state.get("selected_benchmark_dataset")
    if current_dataset not in benchmark_datasets:
        current_dataset = benchmark_datasets[0]
    selected_dataset = st.sidebar.selectbox(
        "数据集",
        options=benchmark_datasets,
        index=benchmark_datasets.index(current_dataset),
        help="不同数据集对应不同服务场景和知识库背景，先选数据集再选 case。",
    )
    st.session_state.selected_benchmark_dataset = selected_dataset

    cases_for_dataset = [case for case in benchmark_cases if case.get("dataset") == selected_dataset]
    benchmark_scenarios = sorted({str(case.get("scenario") or "unknown") for case in cases_for_dataset})
    if not cases_for_dataset or not benchmark_scenarios:
        st.sidebar.error(f"数据集 {selected_dataset} 下没有可用 case。")
        return st.session_state.selected_page

    current_scenario = st.session_state.get("selected_benchmark_scenario")
    if current_scenario not in benchmark_scenarios:
        current_scenario = benchmark_scenarios[0]
    selected_scenario = st.sidebar.selectbox(
        "场景",
        options=benchmark_scenarios,
        index=benchmark_scenarios.index(current_scenario),
    )
    st.session_state.selected_benchmark_scenario = selected_scenario

    cases_for_scenario = [case for case in cases_for_dataset if case["scenario"] == selected_scenario]
    case_labels = [case["case_id"] for case in cases_for_scenario]
    if not case_labels:
        st.sidebar.error(f"场景 {selected_scenario} 下没有可用 case。")
        return st.session_state.selected_page

    current_case = st.session_state.get("selected_benchmark_case")
    if current_case not in case_labels:
        current_case = case_labels[0]
    selected_case_label = st.sidebar.selectbox(
        "Case",
        options=case_labels,
        index=case_labels.index(current_case),
    )
    st.session_state.selected_benchmark_case = selected_case_label

    selected_case = next(case for case in cases_for_scenario if case["case_id"] == selected_case_label)
    selected_case_metadata = build_case_context(selected_case)
    data_path = selected_case["data_path"]
    st.session_state.selected_benchmark_case_dir = selected_case["case_dir"]
    st.session_state.selected_benchmark_case_metadata = selected_case_metadata
    st.session_state.data_path = data_path
    st.session_state.csv_path = data_path
    st.session_state.analysis_input = selected_case.get("default_user_input") or st.session_state.get("analysis_input", "")

    inject_time = selected_case.get("inject_time")
    st.session_state.analysis_start_raw = "" if inject_time is None else str(inject_time)

    st.sidebar.caption(f"case 目录：{selected_case['case_dir']}")
    st.sidebar.caption(f"注入时间：{inject_time if inject_time is not None else '-'}")
    st.sidebar.caption(f"标注根因：{selected_case.get('root_cause') or '-'}")
    evidence = selected_case_metadata.get("evidence_availability") or {}
    col1, col2, col3 = st.sidebar.columns(3)
    col1.metric("指标", "有" if evidence.get("metrics") else "无")
    col2.metric("日志", "有" if evidence.get("logs") else "无")
    col3.metric("调用链", "有" if evidence.get("traces") else "无")
    return st.session_state.selected_page


def ensure_app_state() -> None:
    defaults: dict[str, Any] = {
        "analysis_result": None,
        "voice_result": None,
        "image_result": None,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)
