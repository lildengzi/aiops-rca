from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st

from config import BENCHMARK_DIR
from benchmark_case_loader import iter_benchmark_cases, list_benchmark_scenarios

PAGES = [
    ("analysis", "故障分析"),
    ("dashboard", "故障趋势"),
    ("history", "历史报告"),
    ("knowledge", "知识库管理"),
    ("feedback", "用户反馈"),
]


@st.cache_data(show_spinner=False)
def _get_benchmark_cases() -> list[dict[str, Any]]:
    return iter_benchmark_cases()


@st.cache_data(show_spinner=False)
def _get_benchmark_scenarios() -> list[str]:
    return list_benchmark_scenarios()


def render_sidebar() -> str:
    st.sidebar.title("AIOps RCA")
    default_csv = str(BENCHMARK_DIR / "real_data.csv")
    benchmark_cases = _get_benchmark_cases()
    benchmark_scenarios = _get_benchmark_scenarios()
    has_case_layout = bool(benchmark_cases)
    if "selected_page" not in st.session_state:
        st.session_state.selected_page = "analysis"
    if "csv_path" not in st.session_state:
        st.session_state.csv_path = default_csv
    st.session_state.setdefault("selected_benchmark_scenario", "")
    st.session_state.setdefault("selected_benchmark_case", "")
    st.session_state.setdefault("selected_benchmark_case_dir", "")
    st.session_state.setdefault("analysis_input", "")
    st.session_state.setdefault("analysis_start_raw", "")
    st.session_state.setdefault("analysis_end_raw", "")

    label_by_key = {key: label for key, label in PAGES}
    key_by_label = {label: key for key, label in PAGES}
    selected_label = st.sidebar.radio(
        "页面导航",
        options=[label for _, label in PAGES],
        index=[key for key, _ in PAGES].index(st.session_state.selected_page),
    )
    st.session_state.selected_page = key_by_label[selected_label]

    st.sidebar.caption("数据源")
    if has_case_layout and st.sidebar.button("刷新 benchmark 列表", use_container_width=True):
        _get_benchmark_cases.clear()
        _get_benchmark_scenarios.clear()
        benchmark_cases = _get_benchmark_cases()
        benchmark_scenarios = _get_benchmark_scenarios()
        has_case_layout = bool(benchmark_cases)

    source_options = ["直接输入 CSV"] + (["选择 benchmark case"] if has_case_layout else [])
    source_mode = st.sidebar.radio(
        "数据选择方式",
        options=source_options,
        index=1 if has_case_layout and st.session_state.get("selected_benchmark_case_dir") else 0,
    )

    if source_mode == "选择 benchmark case" and benchmark_cases:
        scenario_options = benchmark_scenarios
        current_scenario = st.session_state.get("selected_benchmark_scenario")
        if current_scenario not in scenario_options:
            current_scenario = scenario_options[0]
        selected_scenario = st.sidebar.selectbox(
            "Scenario",
            options=scenario_options,
            index=scenario_options.index(current_scenario),
        )
        st.session_state.selected_benchmark_scenario = selected_scenario

        cases_for_scenario = [case for case in benchmark_cases if case["scenario"] == selected_scenario]
        case_labels = [f"{case['case_id']}" for case in cases_for_scenario]
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
        st.session_state.selected_benchmark_case_dir = selected_case["case_dir"]
        st.session_state.csv_path = selected_case["csv_path"]
        st.session_state.analysis_input = selected_case.get("default_user_input") or st.session_state.get("analysis_input", "")
        inject_time = selected_case.get("inject_time")
        st.session_state.analysis_start_raw = "" if inject_time is None else str(inject_time)
        st.sidebar.caption(f"case_dir：{selected_case['case_dir']}")
        st.sidebar.caption(f"inject_time：{inject_time if inject_time is not None else '-'}")
    else:
        csv_path = st.sidebar.text_input("CSV 路径", value=st.session_state.csv_path)
        st.session_state.csv_path = csv_path.strip() or default_csv

        uploaded_csv = st.sidebar.file_uploader("或上传 CSV", type=["csv"])
        if uploaded_csv is not None:
            uploads_dir = Path(".streamlit_uploads")
            uploads_dir.mkdir(parents=True, exist_ok=True)
            target_path = uploads_dir / uploaded_csv.name
            target_path.write_bytes(uploaded_csv.getvalue())
            st.session_state.csv_path = str(target_path.resolve())
            st.session_state.selected_benchmark_case_dir = ""
            st.sidebar.success(f"已使用上传文件：{uploaded_csv.name}")

    st.sidebar.caption(f"当前路径：{st.session_state.csv_path}")
    return st.session_state.selected_page


def ensure_app_state() -> None:
    defaults: dict[str, Any] = {
        "analysis_result": None,
        "voice_result": None,
        "image_result": None,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)
