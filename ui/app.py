from __future__ import annotations

from importlib import import_module
from typing import Callable

import streamlit as st

from ui.sidebar import ensure_app_state, render_sidebar

PAGES: dict[str, tuple[str, str]] = {
    "analysis": ("ui.analysis_page", "render_analysis_page"),
    "dashboard": ("ui.dashboard_page", "render_dashboard_page"),
    "history": ("ui.history_page", "render_history_page"),
    "knowledge": ("ui.knowledge_page", "render_knowledge_page"),
    "feedback": ("ui.feedback_page", "render_feedback_page"),
}


def _resolve_renderer(page_key: str) -> Callable[[], None]:
    module_name, function_name = PAGES.get(page_key, PAGES["analysis"])
    module = import_module(module_name)
    return getattr(module, function_name)


def main() -> None:
    st.set_page_config(page_title="AIOps RCA", layout="wide")
    ensure_app_state()
    selected_page = render_sidebar()
    renderer = _resolve_renderer(selected_page)
    renderer()


if __name__ == "__main__":
    main()
