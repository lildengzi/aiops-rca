from __future__ import annotations

import json
import mimetypes
import uuid
from pathlib import Path
from typing import Any
from urllib import error, request

from config import OPENAI_API_KEY, OPENAI_BASE_URL

try:
    import speech_recognition as sr
except ModuleNotFoundError:
    sr = None


TRANSCRIPTION_MODEL = "gpt-4o-mini-transcribe"


def transcribe_audio(file_name: str, mime_type: str | None, file_bytes: bytes) -> dict[str, Any]:
    if not file_bytes:
        return {"status": "empty", "text": "", "message": "未检测到音频内容。", "provider": "none"}

    remote_result = _transcribe_with_openai_compatible(file_name, mime_type, file_bytes)
    if remote_result is not None:
        return remote_result

    local_result = _transcribe_with_speech_recognition(file_name, file_bytes)
    if local_result is not None:
        return local_result

    size_kb = max(1, len(file_bytes) // 1024)
    placeholder = (
        f"语音解析暂不可用：已上传音频文件 {file_name}"
        f"（{mime_type or 'unknown'}, {size_kb} KB）。"
        "当前环境未启用远程转写，且本地识别依赖不可用，请手动补充语音内容。"
    )
    return {
        "status": "fallback",
        "text": placeholder,
        "message": placeholder,
        "provider": "fallback",
    }



def _transcribe_with_openai_compatible(
    file_name: str,
    mime_type: str | None,
    file_bytes: bytes,
) -> dict[str, Any] | None:
    if not OPENAI_API_KEY or not OPENAI_BASE_URL:
        return None

    endpoint = OPENAI_BASE_URL.rstrip("/") + "/audio/transcriptions"
    guessed_type = mime_type or mimetypes.guess_type(file_name)[0] or "application/octet-stream"
    fields = {"model": TRANSCRIPTION_MODEL}
    files = [("file", file_name or "audio.wav", guessed_type, file_bytes)]

    try:
        response = _post_multipart_json(endpoint, fields, files, OPENAI_API_KEY)
    except (OSError, error.URLError, error.HTTPError, TimeoutError):
        return None

    text = str(response.get("text") or response.get("transcript") or "").strip()
    if not text:
        return None

    return {
        "status": "success",
        "text": text,
        "message": "语音转写完成。",
        "provider": "openai-compatible audio transcription",
        "model": response.get("model") or TRANSCRIPTION_MODEL,
    }



def _transcribe_with_speech_recognition(file_name: str, file_bytes: bytes) -> dict[str, Any] | None:
    if sr is None:
        return None

    suffix = Path(file_name).suffix or ".wav"
    temp_path = Path(".streamlit_uploads") / f"voice_{uuid.uuid4().hex}{suffix}"
    temp_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path.write_bytes(file_bytes)

    recognizer = sr.Recognizer()
    try:
        with sr.AudioFile(str(temp_path)) as source:
            audio_data = recognizer.record(source)
        text = recognizer.recognize_google(audio_data, language="zh-CN").strip()
    except (sr.UnknownValueError, sr.RequestError, ValueError, OSError):
        return None
    finally:
        temp_path.unlink(missing_ok=True)

    if not text:
        return None

    return {
        "status": "success",
        "text": text,
        "message": "语音转写完成。",
        "provider": "speech_recognition/google",
    }



def _post_multipart_json(
    url: str,
    fields: dict[str, str],
    files: list[tuple[str, str, str, bytes]],
    api_key: str,
) -> dict[str, Any]:
    boundary = f"----ClaudeBoundary{uuid.uuid4().hex}"
    body = bytearray()

    for name, value in fields.items():
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
        body.extend(str(value).encode("utf-8"))
        body.extend(b"\r\n")

    for field_name, filename, content_type, content in files:
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(
            f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'.encode("utf-8")
        )
        body.extend(f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"))
        body.extend(content)
        body.extend(b"\r\n")

    body.extend(f"--{boundary}--\r\n".encode("utf-8"))

    req = request.Request(
        url,
        data=bytes(body),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    with request.urlopen(req, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))
