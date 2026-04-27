from __future__ import annotations

import base64
import json
import mimetypes
from io import BytesIO
from typing import Any
from urllib import error, request

from config import MODEL_NAME, OPENAI_API_KEY, OPENAI_BASE_URL

try:
    import pytesseract
except ModuleNotFoundError:
    pytesseract = None

try:
    from PIL import Image
except ModuleNotFoundError:
    Image = None


OCR_PROMPT = (
    "请阅读这张监控截图或异常图表，只基于图片可见内容输出简短中文摘要。"
    "优先提取服务名、异常指标、告警文字、时间范围和明显异常现象；"
    "如果无法确认，不要编造。"
)


def summarize_image(file_name: str, mime_type: str | None, file_bytes: bytes) -> dict[str, Any]:
    if not file_bytes:
        return {"status": "empty", "text": "", "message": "未检测到图片内容。", "provider": "none"}

    ocr_text = _extract_text_with_tesseract(file_bytes)
    remote_result = _summarize_with_openai_compatible(file_name, mime_type, file_bytes, ocr_text)
    if remote_result is not None:
        return remote_result

    if ocr_text:
        return {
            "status": "success",
            "text": ocr_text,
            "message": "图片 OCR 完成。",
            "provider": "pytesseract",
        }

    size_kb = max(1, len(file_bytes) // 1024)
    placeholder = (
        f"图像解析暂不可用：已上传图片文件 {file_name}"
        f"（{mime_type or 'unknown'}, {size_kb} KB）。"
        "当前环境未启用 OCR 或远程多模态解析，请将图片中的关键现象手动补充到问题描述中。"
    )
    return {
        "status": "fallback",
        "text": placeholder,
        "message": placeholder,
        "provider": "fallback",
    }



def _extract_text_with_tesseract(file_bytes: bytes) -> str:
    if Image is None or pytesseract is None:
        return ""
    try:
        image = Image.open(BytesIO(file_bytes))
        text = pytesseract.image_to_string(image, lang="chi_sim+eng")
    except (OSError, ValueError):
        return ""
    return text.strip()



def _summarize_with_openai_compatible(
    file_name: str,
    mime_type: str | None,
    file_bytes: bytes,
    ocr_text: str,
) -> dict[str, Any] | None:
    if not OPENAI_API_KEY or not OPENAI_BASE_URL:
        return None

    endpoint = OPENAI_BASE_URL.rstrip("/") + "/chat/completions"
    detected_type = mime_type or mimetypes.guess_type(file_name)[0] or "image/png"
    image_b64 = base64.b64encode(file_bytes).decode("utf-8")
    prompt = OCR_PROMPT
    if ocr_text:
        prompt += f"\n\n已提取到的 OCR 原文如下，可作为辅助参考：\n{ocr_text}"

    payload = {
        "model": MODEL_NAME or "gpt-4.1-mini",
        "temperature": 0,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{detected_type};base64,{image_b64}"},
                    },
                ],
            }
        ],
    }

    data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        endpoint,
        data=data,
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=60) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except (OSError, error.URLError, error.HTTPError, TimeoutError, json.JSONDecodeError):
        return None

    text = _extract_message_text(raw).strip()
    if not text:
        return None

    if ocr_text and ocr_text not in text:
        text = f"图片摘要：{text}\n\nOCR 原文：\n{ocr_text}"

    return {
        "status": "success",
        "text": text,
        "message": "图片解析完成。",
        "provider": "openai-compatible vision",
        "ocr_text": ocr_text,
    }



def _extract_message_text(payload: dict[str, Any]) -> str:
    choices = payload.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("text"):
                parts.append(str(item["text"]))
        return "\n".join(parts)
    return ""
