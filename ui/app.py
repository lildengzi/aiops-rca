from __future__ import annotations

import streamlit as st

from ui.analysis_page import render_analysis_page
from ui.dashboard_page import render_dashboard_page
from ui.feedback_page import render_feedback_page
from ui.history_page import render_history_page
from ui.knowledge_page import render_knowledge_page
from ui.sidebar import ensure_app_state, render_sidebar

PAGES = {
    "analysis": render_analysis_page,
    "dashboard": render_dashboard_page,
    "history": render_history_page,
    "knowledge": render_knowledge_page,
    "feedback": render_feedback_page,
}


def main() -> None:
    st.set_page_config(page_title="AIOps RCA", layout="wide")
    ensure_app_state()
    selected_page = render_sidebar()
    renderer = PAGES.get(selected_page, render_analysis_page)
    renderer()


if __name__ == "__main__":
    main()
