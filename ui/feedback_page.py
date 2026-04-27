from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import streamlit as st

from config import BASE_DIR, REPORTS_DIR

FEEDBACK_DIR = BASE_DIR / "feedback"
FEEDBACK_FILE = FEEDBACK_DIR / "feedback.json"


@st.cache_data(show_spinner=False)
def _list_report_names() -> list[str]:
    return [path.name for path in sorted(REPORTS_DIR.glob("*.md"), reverse=True)]


@st.cache_data(show_spinner=False)
def _read_feedback_items() -> list[dict]:
    if not FEEDBACK_FILE.exists():
        return []
    return json.loads(FEEDBACK_FILE.read_text(encoding="utf-8"))


def render_feedback_page() -> None:
    st.title("用户反馈")
    FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)

    report_names = _list_report_names()
    with st.form("feedback_form"):
        rating = st.slider("评分", min_value=1, max_value=5, value=4)
        report_name = st.selectbox("关联报告（可选）", options=[""] + report_names)
        comment = st.text_area("反馈内容", height=140, placeholder="例如：结论准确，但希望补充更多日志依据")
        submitted = st.form_submit_button("提交反馈")
        if submitted:
            if not comment.strip():
                st.error("请填写反馈内容。")
            else:
                entry = {
                    "feedback_id": f"feedback-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    "rating": rating,
                    "report_name": report_name or None,
                    "comment": comment.strip(),
                    "created_at": datetime.now().isoformat(timespec="seconds"),
                }
                feedback_items = _read_feedback_items()
                feedback_items.append(entry)
                FEEDBACK_FILE.write_text(json.dumps(feedback_items, ensure_ascii=False, indent=2), encoding="utf-8")
                _read_feedback_items.clear()
                st.success("反馈已保存。")

    feedback_items = list(reversed(_read_feedback_items()))
    if feedback_items:
        st.subheader("历史反馈")
        st.dataframe(feedback_items, use_container_width=True)
    else:
        st.info("当前还没有反馈记录。")
