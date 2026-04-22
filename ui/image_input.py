import streamlit as st
import os
import tempfile
from PIL import Image
import io


ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "bmp", "webp"}


def render_image_input():
    """Frontend - Image/Chart input component"""
    st.subheader("Image Upload")
    
    if "image_description" not in st.session_state:
        st.session_state.image_description = ""
    
    uploaded_file = st.file_uploader(
        "Upload monitoring chart (bar/line)",
        type=list(ALLOWED_EXTENSIONS),
        key="image_input_file"
    )
    
    if uploaded_file is not None and not st.session_state.image_description:
        with st.spinner("Analyzing chart..."):
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
                st.session_state.chart_analysis = analysis
            finally:
                os.unlink(path)
        
        st.rerun()
    
    if st.session_state.get("chart_analysis"):
        analysis = st.session_state.chart_analysis
        
        col_a1, col_a2 = st.columns([2, 1])
        with col_a1:
            if uploaded_file:
                img = Image.open(io.BytesIO(uploaded_file.read()))
                st.image(img, caption=uploaded_file.name, width='stretch')
        
        with col_a2:
            st.markdown("**Chart Analysis**")
            st.write(f"Type: {analysis.get('chart_type', 'unknown')}")
            st.write(f"Max: {analysis.get('max_value', 0)}")
            st.write(f"Min: {analysis.get('min_value', 0)}")
            st.write(f"Avg: {analysis.get('avg_value', 0)}")
            st.write(f"Trend: {analysis.get('trend', 'unknown')}")
            
            if analysis.get("data_points"):
                st.markdown("**Data Points:**")
                for pt in analysis["data_points"][:5]:
                    st.caption(f"{pt['time']}: {pt['value']}")
    
    col_b1, col_b2 = st.columns([3, 1])
    with col_b1:
        pass
    with col_b2:
        st.write("")
        if st.button("Send", key="image_submit") and st.session_state.get("chart_analysis"):
            text = st.session_state.image_description
            st.session_state.image_description = ""
            if "chart_analysis" in st.session_state:
                del st.session_state["chart_analysis"]
            return text
        
        if st.button("Clear", key="image_clear"):
            st.session_state.image_description = ""
            if "chart_analysis" in st.session_state:
                del st.session_state["chart_analysis"]
            st.rerun()
    
    return None