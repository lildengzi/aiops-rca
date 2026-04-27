from __future__ import annotations

import streamlit as st

from input_modules.image import summarize_image


def render_image_input() -> None:
    st.subheader("图片输入")
    image_file = st.file_uploader("上传截图或图表", type=["png", "jpg", "jpeg"], key="image_upload")
    if image_file is None:
        return
    st.image(image_file, caption=image_file.name, use_container_width=True)
    if st.button("解析图片", key="parse_image"):
        st.session_state.image_result = summarize_image(
            file_name=image_file.name,
            mime_type=image_file.type,
            file_bytes=image_file.getvalue(),
        )

    result = st.session_state.get("image_result")
    if result:
        st.info(result.get("message") or "")
        if result.get("text"):
            st.text_area("图片解析结果", value=result["text"], height=120, key="image_text")
