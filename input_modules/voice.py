from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any

try:
    from faster_whisper import WhisperModel
except ModuleNotFoundError:
    WhisperModel = None


LOCAL_WHISPER_MODEL = os.getenv("LOCAL_WHISPER_MODEL", "base")
LOCAL_WHISPER_DEVICE = os.getenv("LOCAL_WHISPER_DEVICE", "cpu")
LOCAL_WHISPER_COMPUTE_TYPE = os.getenv("LOCAL_WHISPER_COMPUTE_TYPE", "int8")
LOCAL_WHISPER_LANGUAGE = os.getenv("LOCAL_WHISPER_LANGUAGE", "zh")
LOCAL_WHISPER_LOCAL_ONLY = os.getenv("LOCAL_WHISPER_LOCAL_ONLY", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
_WHISPER_MODEL: Any = None


def transcribe_audio(file_name: str, mime_type: str | None, file_bytes: bytes) -> dict[str, Any]:
    if not file_bytes:
        return {
            "status": "empty",
            "text": "",
            "message": "未检测到录音内容。",
            "provider": "none",
        }

    if len(file_bytes) < 8192:
        size_kb = max(1, len(file_bytes) // 1024)
        message = f"录音数据过少（{size_kb} KB），请录制至少 2 秒并靠近麦克风说话。"
        return {
            "status": "too_short",
            "text": "",
            "message": message,
            "provider": "faster-whisper/local",
            "diagnostics": [message],
        }

    result, reason = _transcribe_with_faster_whisper(file_name, file_bytes)
    if result is not None:
        return result

    size_kb = max(1, len(file_bytes) // 1024)
    message = (
        f"语音解析失败：已收到页面录音 {file_name}"
        f"（{mime_type or 'unknown'}, {size_kb} KB）。失败原因：{reason}"
    )
    return {
        "status": "error",
        "text": "",
        "message": message,
        "provider": "faster-whisper/local",
        "diagnostics": [reason] if reason else [],
    }


def _transcribe_with_faster_whisper(file_name: str, file_bytes: bytes) -> tuple[dict[str, Any] | None, str]:
    if WhisperModel is None:
        return None, "本地 faster-whisper 依赖未安装，请先安装 requirements.txt 中的 faster-whisper。"

    suffix = Path(file_name).suffix or ".webm"
    temp_path = Path(".streamlit_uploads") / f"voice_{uuid.uuid4().hex}{suffix}"
    temp_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path.write_bytes(file_bytes)

    try:
        model = _get_faster_whisper_model()
        segments, info = model.transcribe(
            str(temp_path),
            language=LOCAL_WHISPER_LANGUAGE or None,
            vad_filter=True,
            beam_size=1,
        )
        text = "".join(segment.text for segment in segments).strip()
    except Exception as exc:
        return None, f"本地 faster-whisper 转写失败：{_safe_error(exc)}"
    finally:
        temp_path.unlink(missing_ok=True)

    if not text:
        return None, "本地 faster-whisper 没有识别到文本，请确认录音中有清晰人声。"

    return (
        {
            "status": "success",
            "text": text,
            "message": "语音转写完成。",
            "provider": "faster-whisper/local",
            "model": LOCAL_WHISPER_MODEL,
            "language": getattr(info, "language", LOCAL_WHISPER_LANGUAGE),
            "language_probability": round(float(getattr(info, "language_probability", 0.0) or 0.0), 4),
        },
        "",
    )


def _get_faster_whisper_model() -> Any:
    global _WHISPER_MODEL
    if _WHISPER_MODEL is None:
        _WHISPER_MODEL = WhisperModel(
            LOCAL_WHISPER_MODEL,
            device=LOCAL_WHISPER_DEVICE,
            compute_type=LOCAL_WHISPER_COMPUTE_TYPE,
            local_files_only=LOCAL_WHISPER_LOCAL_ONLY,
        )
    return _WHISPER_MODEL


def _safe_error(exc: Exception) -> str:
    text = str(exc).strip()
    return text[:200] if text else exc.__class__.__name__
