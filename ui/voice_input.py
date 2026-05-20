from __future__ import annotations

import hashlib

import streamlit as st

from input_modules.voice import transcribe_audio


def render_voice_input() -> None:
    st.subheader("语音输入")
    st.caption("点击录音，停止后系统会使用本地 faster-whisper 自动转写。")

    audio_file = st.audio_input("录制语音", key="voice_audio_input")
    if audio_file is None:
        st.caption("等待录音。若浏览器提示麦克风权限，请允许访问麦克风。")
        return

    file_bytes = audio_file.getvalue()
    if not file_bytes:
        st.warning("录音已结束，但没有收到音频数据。请重新录音。")
        return

    file_name = getattr(audio_file, "name", "") or "recording.wav"
    mime_type = getattr(audio_file, "type", None) or "audio/wav"
    audio_hash = hashlib.sha256(file_bytes).hexdigest()

    st.audio(file_bytes, format=mime_type)
    st.caption(f"已收到录音：{max(1, len(file_bytes) // 1024)} KB")

    if st.session_state.get("voice_audio_hash") != audio_hash:
        st.session_state.voice_audio_hash = audio_hash
        st.session_state.voice_result = None
        with st.spinner("正在使用本地 faster-whisper 解析语音..."):
            st.session_state.voice_result = transcribe_audio(
                file_name=file_name,
                mime_type=mime_type,
                file_bytes=file_bytes,
            )

    if st.button("重新解析当前录音", key="parse_voice"):
        with st.spinner("正在使用本地 faster-whisper 解析语音..."):
            st.session_state.voice_result = transcribe_audio(
                file_name=file_name,
                mime_type=mime_type,
                file_bytes=file_bytes,
            )

    result = st.session_state.get("voice_result")
    if not result:
        return

    status = result.get("status")
    if status == "success":
        st.success(result.get("message") or "语音转写完成。")
    elif status in {"empty", "too_short"}:
        st.warning(result.get("message") or "录音不可用。")
    else:
        st.error(result.get("message") or "语音解析失败。")

    diagnostics = result.get("diagnostics") or []
    if diagnostics:
        with st.expander("语音解析诊断", expanded=False):
            for item in diagnostics:
                st.write(f"- {item}")

    if result.get("text"):
        st.text_area("语音转写结果", value=result["text"], height=120, key="voice_text")
