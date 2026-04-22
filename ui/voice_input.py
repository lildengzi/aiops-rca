import streamlit as st
import os
import tempfile


def render_voice_input():
    """前端 - 语音输入组件"""
    st.subheader("Voice Input")
    
    if "voice_text" not in st.session_state:
        st.session_state.voice_text = ""
    if "voice_pending" not in st.session_state:
        st.session_state.voice_pending = False
    
    col_v1, col_v2 = st.columns([2, 1])
    with col_v1:
        audio_input = st.audio_input(
            "Click to record voice (Chinese/English)", 
            key="voice_input_audio"
        )
    with col_v2:
        st.write("")
        st.write("")
        if st.button("Reset", key="voice_clear"):
            st.session_state.voice_text = ""
            st.session_state.voice_pending = False
            st.rerun()
    
    if audio_input is not None and not st.session_state.voice_pending:
        with st.spinner("Recognizing..."):
            try:
                from input_modules import VoiceInputBackend
                backend = VoiceInputBackend()
                audio_bytes = audio_input.read()
                result = backend.process_audio(audio_bytes)
                
                if result["success"]:
                    st.session_state.voice_text = result["text"]
                    st.session_state.voice_pending = True
                else:
                    error_msg = result.get("error", "Unknown error")
                    st.session_state.voice_error = error_msg
                    st.session_state.voice_pending = True
            except Exception as e:
                st.session_state.voice_error = str(e)
                st.session_state.voice_pending = True
        
        st.rerun()
    
    if st.session_state.voice_text:
        st.success(f"Result: {st.session_state.voice_text}")
        if st.button("Send", key="voice_submit"):
            text = st.session_state.voice_text
            st.session_state.voice_text = ""
            st.session_state.voice_pending = False
            return text
    elif st.session_state.voice_pending:
        error = st.session_state.get("voice_error", "Recognition failed")
        st.warning(error + ", please use text input")
    
    return None
    
    if "voice_text" not in st.session_state:
        st.session_state.voice_text = ""
    if "voice_pending" not in st.session_state:
        st.session_state.voice_pending = False
    
    col_v1, col_v2 = st.columns([2, 1])
    with col_v1:
        audio_input = st.audio_input(
            "点击录制语音（支持中文/英文）", 
            key="voice_input_audio"
        )
    with col_v2:
        st.write("")
        st.write("")
        if st.button("🔄 重新录制", key="voice_clear"):
            st.session_state.voice_text = ""
            st.session_state.voice_pending = False
            st.rerun()
    
    if audio_input is not None and not st.session_state.voice_pending:
        with st.spinner("正在识别语音..."):
            try:
                audio_bytes = audio_input.read()
                result = backend.process_audio(audio_bytes)
                
                if result["success"]:
                    st.session_state.voice_text = result["text"]
                    st.session_state.voice_pending = True
                else:
                    error_msg = result.get("error", "未知错误")
                    st.session_state.voice_error = error_msg
                    st.session_state.voice_pending = True
            except Exception as e:
                st.session_state.voice_error = str(e)
                st.session_state.voice_pending = True
        
        st.rerun()
    
    if st.session_state.voice_text:
        st.success(f"识别结果: {st.session_state.voice_text}")
        if st.button("📤 发送", key="voice_submit"):
            text = st.session_state.voice_text
            st.session_state.voice_text = ""
            st.session_state.voice_pending = False
            return text
    elif st.session_state.voice_pending:
        error = st.session_state.get("voice_error", "语音识别失败")
        st.warning(error + "，请重试或使用文本输入")
    
    return None