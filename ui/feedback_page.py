import streamlit as st
import os
import json
import glob
from datetime import datetime
from pathlib import Path


FEEDBACK_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "feedback")


def _ensure_feedback_dir():
    if not os.path.exists(FEEDBACK_DIR):
        os.makedirs(FEEDBACK_DIR)


def _sanitize_fault_id(fault_id):
    """Convert fault_id to a safe file name while keeping it readable."""
    return str(fault_id).replace("/", "_").replace("\\", "_").strip()


def _get_feedback_file(fault_id):
    _ensure_feedback_dir()
    safe_fault_id = _sanitize_fault_id(fault_id)
    return os.path.join(FEEDBACK_DIR, f"{safe_fault_id}.json")


def save_feedback(fault_id, original_diagnosis, user_correction, feedback_type, comment):
    """Save user feedback"""
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
    """Load feedback"""
    feedback_file = _get_feedback_file(fault_id)
    if os.path.exists(feedback_file):
        with open(feedback_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def load_all_feedback():
    """Load all feedback"""
    _ensure_feedback_dir()
    feedbacks = []
    
    for feedback_path in Path(FEEDBACK_DIR).glob("*.json"):
        try:
            with open(feedback_path, "r", encoding="utf-8") as fp:
                feedbacks.append(json.load(fp))
        except (json.JSONDecodeError, OSError):
            continue
    
    feedbacks.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return feedbacks


def render_feedback_widget(fault_id, original_diagnosis):
    """Render feedback widget (for analysis page)"""
    if not fault_id or not original_diagnosis:
        return None
    
    st.markdown("---")
    st.subheader("Diagnostic Feedback")
    
    existing = load_feedback(fault_id)
    if existing:
        submitted_comment = existing.get("comment", "").strip()
        success_message = f"You have submitted feedback: [{existing['feedback_type']}]"
        if submitted_comment:
            success_message += f" {submitted_comment}"
        st.success(success_message)
        return None
    
    st.info("Please evaluate and provide feedback on this diagnosis")
    
    safe_id = str(fault_id)[:50].replace("/", "_").replace("-", "_")
    label_map = {
        "correct": "Correct",
        "incorrect": "Incorrect",
        "partial": "Partial",
        "missing": "Missing Info",
    }

    with st.form(key=f"fb_form_{safe_id}", clear_on_submit=True):
        feedback_type = st.selectbox(
            "Feedback Type",
            ["correct", "incorrect", "partial", "missing"],
            format_func=lambda x: label_map.get(x, x),
            key=f"fb_type_{safe_id}"
        )
        
        correction = st.text_area(
            "Correct/Add diagnosis",
            placeholder="If diagnosis is incorrect, please provide the correct diagnosis...",
            key=f"fb_corr_{safe_id}"
        )
        
        comment = st.text_area(
            "Comment (optional)",
            placeholder="Other suggestions...",
            key=f"fb_note_{safe_id}"
        )

        submit_feedback = st.form_submit_button("Submit Feedback", use_container_width=True)
    
    if submit_feedback:
        correction = correction.strip()
        comment = comment.strip()

        if feedback_type in {"incorrect", "partial", "missing"} and not correction:
            st.warning("Please provide the corrected or additional diagnosis before submitting.")
            return None

        save_feedback(fault_id, original_diagnosis, correction, feedback_type, comment)
        st.success("Feedback submitted! Thank you for helping improve the model.")
        st.rerun()
    
    return None


def render_feedback_page():
    """Render feedback management page"""
    st.header("User Feedback Management")
    
    feedbacks = load_all_feedback()
    
    if not feedbacks:
        st.info("No feedback records")
        return
    
    st.info(f"Total {len(feedbacks)} feedback entries")
    
    for fb in feedbacks:
        with st.expander(f"{fb.get('fault_id', 'Unknown')} - {fb.get('feedback_type', 'N/A')} ({fb.get('timestamp', '')[:19]})"):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Original Diagnosis**")
                original_diagnosis = fb.get("original_diagnosis", "")
                st.text(original_diagnosis[:200] + ("..." if len(original_diagnosis) > 200 else ""))
            with col2:
                st.markdown("**User Correction**")
                user_correction = fb.get("user_correction", "")
                st.text(user_correction[:200] + ("..." if len(user_correction) > 200 else ""))
            
            st.markdown(f"**Comment**: {fb.get('comment', 'None')}")
            st.markdown(f"**Status**: {fb.get('status', 'pending')}")