from __future__ import annotations

import streamlit as st

from input_modules.voice import transcribe_audio


def render_voice_input() -> None:
    st.subheader("语音输入")
    audio_file = st.file_uploader("上传语音文件", type=["wav", "mp3", "m4a"], key="voice_upload")
    if audio_file is None:
        return
    if st.button("解析语音", key="parse_voice"):
        st.session_state.voice_result = transcribe_audio(
            file_name=audio_file.name,
            mime_type=audio_file.type,
            file_bytes=audio_file.getvalue(),
        )

    result = st.session_state.get("voice_result")
    if result:
        st.info(result.get("message") or "")
        if result.get("text"):
            st.text_area("语音转写结果", value=result["text"], height=120, key="voice_text")
