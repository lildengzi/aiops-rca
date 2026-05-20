from __future__ import annotations

import hashlib

import streamlit as st

from input_modules.image import summarize_image


def render_image_input() -> None:
    st.subheader("图片输入")
    image_file = st.file_uploader(
        "上传截图或图表",
        type=["png", "jpg", "jpeg", "bmp", "webp"],
        key="image_upload",
    )
    if image_file is None:
        return

    file_bytes = image_file.getvalue()
    image_hash = hashlib.sha256(file_bytes).hexdigest()
    st.image(image_file, caption=image_file.name, width="stretch")

    if st.session_state.get("image_file_hash") != image_hash:
        st.session_state.image_file_hash = image_hash
        st.session_state.image_result = None

    if st.button("解析图片", key="parse_image"):
        with st.spinner("正在解析图片..."):
            st.session_state.image_result = summarize_image(
                file_name=image_file.name,
                mime_type=image_file.type,
                file_bytes=file_bytes,
            )

    result = st.session_state.get("image_result")
    if not result:
        return

    status = result.get("status")
    if status == "success":
        st.success(result.get("message") or "图片解析完成。")
    elif status == "empty":
        st.warning(result.get("message") or "未检测到图片内容。")
    else:
        st.error(result.get("message") or "图片解析失败。")

    diagnostics = result.get("diagnostics") or []
    if diagnostics:
        with st.expander("图片解析诊断", expanded=False):
            for item in diagnostics:
                st.write(f"- {item}")

    if result.get("provider"):
        st.caption(f"来源：{result['provider']}")
    if result.get("text"):
        st.text_area("图片解析结果", value=result["text"], height=160, key="image_text")
