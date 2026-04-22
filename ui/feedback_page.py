import streamlit as st
import os
import json
import glob
from datetime import datetime


FEEDBACK_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "feedback")


def _ensure_feedback_dir():
    if not os.path.exists(FEEDBACK_DIR):
        os.makedirs(FEEDBACK_DIR)


def _get_feedback_file(fault_id):
    _ensure_feedback_dir()
    return os.path.join(FEEDBACK_DIR, f"{fault_id}.json")


def save_feedback(fault_id, original_diagnosis, user_correction, feedback_type, comment):
    """保存用户反馈"""
    _ensure_feedback_dir()
    
    feedback_file = _get_feedback_file(fault_id)
    
    feedback_data = {
        "fault_id": fault_id,
        "original_diagnosis": original_diagnosis,
        "user_correction": user_correction,
        "feedback_type": feedback_type,
        "comment": comment,
        "timestamp": datetime.now().isoformat(),
        "status": "pending"
    }
    
    with open(feedback_file, "w", encoding="utf-8") as f:
        json.dump(feedback_data, f, ensure_ascii=False, indent=2)
    
    return True


def load_feedback(fault_id):
    """加载反馈"""
    feedback_file = _get_feedback_file(fault_id)
    if os.path.exists(feedback_file):
        with open(feedback_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def load_all_feedback():
    """加载所有反馈"""
    _ensure_feedback_dir()
    feedbacks = []
    
    for f in glob.glob(os.path.join(FEEDBACK_DIR, "*.json")):
        with open(f, "r", encoding="utf-8") as fp:
            feedbacks.append(json.load(fp))
    
    feedbacks.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return feedbacks


def render_feedback_widget(fault_id, original_diagnosis):
    """渲染反馈组件（用于分析页面）"""
    if not fault_id or not original_diagnosis:
        return None
    
    st.markdown("---")
    st.subheader("💬 诊断反馈")
    
    existing = load_feedback(fault_id)
    if existing:
        st.success(f"您已提交过反馈: [{existing['feedback_type']}] {existing.get('comment', '')}")
        return None
    
    st.info("请对本次诊断结果进行评价和反馈")
    
    safe_id = str(fault_id)[:50].replace("/", "_").replace("-", "_")
    
    feedback_type = st.selectbox(
        "反馈类型",
        ["correct", "incorrect", "partial", "missing"],
        format_func=lambda x: {"correct": "✓ 诊断正确", "incorrect": "✗ 诊断错误", "partial": "△ 部分准确", "missing": "○ 缺少信息"}.get(x, x),
        key=f"fb_type_{safe_id}"
    )
    
    correction = st.text_area(
        "纠正/补充诊断内容",
        placeholder="如果诊断不正确，请给出正确的诊断...",
        key=f"fb_corr_{safe_id}"
    )
    
    comment = st.text_area(
        "备注（可选）",
        placeholder="其他建议...",
        key=f"fb_note_{safe_id}"
    )
    
    if st.button("💾 提交反馈", key=f"fb_submit_{safe_id}"):
        save_feedback(fault_id, original_diagnosis, correction, feedback_type, comment)
        st.success("✅ 反馈已提交！感谢您的帮助改进模型。")
        st.rerun()
    
    return None


def render_feedback_page():
    """渲染反馈管理页面"""
    st.header("💬 用户反馈管理")
    
    feedbacks = load_all_feedback()
    
    if not feedbacks:
        st.info("暂无反馈记录")
        return
    
    st.info(f"共 {len(feedbacks)} 条反馈")
    
    for fb in feedbacks:
        with st.expander(f"📝 {fb.get('fault_id', 'Unknown')} - {fb.get('feedback_type', 'N/A')} ({fb.get('timestamp', '')[:19]})"):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**原始诊断**")
                st.text(fb.get("original_diagnosis", "")[:200] + "...")
            with col2:
                st.markdown("**用户纠正**")
                st.text(fb.get("user_correction", "")[:200] + "...")
            
            st.markdown(f"**备注**: {fb.get('comment', '无')}")
            st.markdown(f"**状态**: {fb.get('status', 'pending')}")