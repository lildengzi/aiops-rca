from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st

from config import BENCHMARK_DIR

PAGES = [
    ("analysis", "故障分析"),
    ("dashboard", "故障趋势"),
    ("history", "历史报告"),
    ("knowledge", "知识库管理"),
    ("feedback", "用户反馈"),
]


def render_sidebar() -> str:
    st.sidebar.title("AIOps RCA")
    default_csv = str(BENCHMARK_DIR / "real_data.csv")
    if "selected_page" not in st.session_state:
        st.session_state.selected_page = "analysis"
    if "csv_path" not in st.session_state:
        st.session_state.csv_path = default_csv

    label_by_key = {key: label for key, label in PAGES}
    key_by_label = {label: key for key, label in PAGES}
    selected_label = st.sidebar.radio(
        "页面导航",
        options=[label for _, label in PAGES],
        index=[key for key, _ in PAGES].index(st.session_state.selected_page),
    )
    st.session_state.selected_page = key_by_label[selected_label]

    st.sidebar.caption("数据源")
    csv_path = st.sidebar.text_input("CSV 路径", value=st.session_state.csv_path)
    st.session_state.csv_path = csv_path.strip() or default_csv

    uploaded_csv = st.sidebar.file_uploader("或上传 CSV", type=["csv"])
    if uploaded_csv is not None:
        uploads_dir = Path(".streamlit_uploads")
        uploads_dir.mkdir(parents=True, exist_ok=True)
        target_path = uploads_dir / uploaded_csv.name
        target_path.write_bytes(uploaded_csv.getvalue())
        st.session_state.csv_path = str(target_path.resolve())
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
