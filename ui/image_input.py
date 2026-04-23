import streamlit as st
import os
import tempfile
from PIL import Image
import io


ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "bmp", "webp"}


def render_image_input():
    """Frontend - Image OCR input component"""
    st.subheader("图片文字识别")
    
    if "image_description" not in st.session_state:
        st.session_state.image_description = ""
    
    uploaded_file = st.file_uploader(
        "上传包含文字的图片 (告警截图/监控面板/日志截图等)",
        type=list(ALLOWED_EXTENSIONS),
        key="image_input_file"
    )
    
    if uploaded_file is not None and not st.session_state.image_description:
        with st.spinner("正在识别图片中的文字..."):
            from input_modules import ImageInputBackend
            backend = ImageInputBackend()
            
            img = Image.open(io.BytesIO(uploaded_file.read()))
            ext = uploaded_file.name.split('.')[-1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}") as tmp:
                img.save(tmp.name)
                path = tmp.name
            
            try:
                analysis = backend.analyze_chart(path, uploaded_file.name)
                st.session_state.image_description = analysis["description"]
                st.session_state.ocr_result = analysis
            finally:
                os.unlink(path)
        
        st.rerun()
    
    if st.session_state.get("ocr_result"):
        analysis = st.session_state.ocr_result
        
        col_a1, col_a2 = st.columns([1, 1])
        with col_a1:
            if uploaded_file:
                img = Image.open(io.BytesIO(uploaded_file.read()))
                st.image(img, caption=uploaded_file.name, width='stretch')
        
        with col_a2:
            st.markdown("**识别结果**")
            st.text_area(
                "识别出的文字:",
                value=st.session_state.image_description,
                height=300,
                key="ocr_text_edit"
            )
            st.caption("可直接编辑修改识别结果")
            
            # 实时更新session state
            if "ocr_text_edit" in st.session_state:
                st.session_state.image_description = st.session_state.ocr_text_edit
    
    col_b1, col_b2 = st.columns([3, 1])
    with col_b1:
        pass
    with col_b2:
        st.write("")
        if st.button("发送", key="image_submit") and st.session_state.get("ocr_result"):
            text = st.session_state.image_description
            st.session_state.image_description = ""
            if "ocr_result" in st.session_state:
                del st.session_state["ocr_result"]
            return text
        
        if st.button("清除", key="image_clear"):
            st.session_state.image_description = ""
            if "ocr_result" in st.session_state:
                del st.session_state["ocr_result"]
            st.rerun()
    
    return None