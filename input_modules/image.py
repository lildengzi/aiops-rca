from __future__ import annotations

import base64
import json
import mimetypes
import os
import shutil
from io import BytesIO
from typing import Any
from urllib import error, request

from config import MODEL_NAME, OPENAI_API_KEY, OPENAI_BASE_URL

try:
    import cv2
except ModuleNotFoundError:
    cv2 = None

try:
    import numpy as np
except ModuleNotFoundError:
    np = None

try:
    import pytesseract
    from pytesseract import TesseractError, TesseractNotFoundError
except ModuleNotFoundError:
    pytesseract = None
    TesseractError = Exception
    TesseractNotFoundError = Exception

try:
    from PIL import Image
except ModuleNotFoundError:
    Image = None

try:
    from rapidocr_onnxruntime import RapidOCR
except ModuleNotFoundError:
    RapidOCR = None


OCR_PROMPT = (
    "请阅读这张监控截图、告警截图或异常图表，只基于图片可见内容输出简短中文摘要。"
    "优先提取服务名、异常指标、告警文字、时间范围和明显异常现象；"
    "如果无法确认，不要编造。"
)
_RAPID_OCR: Any = None


def summarize_image(file_name: str, mime_type: str | None, file_bytes: bytes) -> dict[str, Any]:
    if not file_bytes:
        return {"status": "empty", "text": "", "message": "未检测到图片内容。", "provider": "none"}

    diagnostics: list[str] = []

    rapid_text, rapid_reason = _extract_text_with_rapidocr(file_bytes)
    if rapid_text:
        return {
            "status": "success",
            "text": rapid_text,
            "message": "图片 OCR 完成。",
            "provider": "rapidocr/local",
        }
    if rapid_reason:
        diagnostics.append(rapid_reason)

    tesseract_text, tesseract_reason = _extract_text_with_tesseract(file_bytes)
    if tesseract_text:
        return {
            "status": "success",
            "text": tesseract_text,
            "message": "图片 OCR 完成。",
            "provider": "pytesseract/local",
            "diagnostics": diagnostics,
        }
    if tesseract_reason:
        diagnostics.append(tesseract_reason)

    remote_result, remote_reason = _summarize_with_openai_compatible(
        file_name,
        mime_type,
        file_bytes,
        rapid_text or tesseract_text,
    )
    if remote_result is not None:
        if diagnostics:
            remote_result["diagnostics"] = diagnostics
        return remote_result
    if remote_reason:
        diagnostics.append(remote_reason)

    size_kb = max(1, len(file_bytes) // 1024)
    reason = "；".join(diagnostics) if diagnostics else "没有可用的图片解析后端"
    message = (
        f"图片解析不可用：已上传图片 {file_name}（{mime_type or 'unknown'}, {size_kb} KB）。"
        f"失败原因：{reason}"
    )
    return {
        "status": "error",
        "text": "",
        "message": message,
        "provider": "none",
        "diagnostics": diagnostics,
    }


def _extract_text_with_rapidocr(file_bytes: bytes) -> tuple[str, str]:
    if RapidOCR is None:
        return "", "rapidocr-onnxruntime 未安装。"
    if Image is None:
        return "", "Pillow 未安装，无法读取图片。"
    if np is None:
        return "", "numpy 未安装，无法运行 RapidOCR。"

    try:
        image = Image.open(BytesIO(file_bytes)).convert("RGB")
    except (OSError, ValueError) as exc:
        return "", f"图片读取失败：{_safe_error(exc)}"

    try:
        ocr = _get_rapidocr()
        result, _ = ocr(np.array(image))
    except Exception as exc:
        return "", f"RapidOCR 识别失败：{_safe_error(exc)}"

    lines: list[str] = []
    for item in result or []:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue
        text = str(item[1]).strip()
        if text:
            lines.append(text)

    text = _clean_ocr_text("\n".join(lines))
    if not text:
        return "", "RapidOCR 没有识别到有效文字。"
    return text, ""


def _get_rapidocr() -> Any:
    global _RAPID_OCR
    if _RAPID_OCR is None:
        _RAPID_OCR = RapidOCR()
    return _RAPID_OCR


def _extract_text_with_tesseract(file_bytes: bytes) -> tuple[str, str]:
    available, reason = _check_tesseract_available()
    if not available:
        return "", reason
    if Image is None:
        return "", "Pillow 未安装，无法读取图片。"

    try:
        image = Image.open(BytesIO(file_bytes)).convert("RGB")
    except (OSError, ValueError) as exc:
        return "", f"图片读取失败：{_safe_error(exc)}"

    candidates = [image]
    preprocessed = _preprocess_for_ocr(image)
    if preprocessed is not None:
        candidates.insert(0, preprocessed)

    errors: list[str] = []
    for candidate in candidates:
        for lang in _tesseract_languages():
            try:
                text = pytesseract.image_to_string(candidate, lang=lang)
            except TesseractNotFoundError:
                return "", _tesseract_install_message()
            except TesseractError as exc:
                errors.append(f"{lang}: {_safe_error(exc)}")
                continue
            except Exception as exc:
                errors.append(f"{lang}: {_safe_error(exc)}")
                continue

            cleaned = _clean_ocr_text(text)
            if cleaned:
                return cleaned, ""

    if errors:
        return "", "Tesseract OCR 失败：" + "；".join(errors[:3])
    return "", "Tesseract 没有识别到有效文字。"


def _check_tesseract_available() -> tuple[bool, str]:
    if pytesseract is None:
        return False, "pytesseract Python 包未安装。"

    configured = os.getenv("TESSERACT_CMD", "").strip()
    if configured:
        pytesseract.pytesseract.tesseract_cmd = configured
        if not os.path.exists(configured):
            return False, f"TESSERACT_CMD 指向的文件不存在：{configured}"

    if not configured and shutil.which(str(pytesseract.pytesseract.tesseract_cmd)) is None:
        return False, _tesseract_install_message()

    try:
        pytesseract.get_tesseract_version()
    except TesseractNotFoundError:
        return False, _tesseract_install_message()
    except Exception as exc:
        return False, f"Tesseract 检测失败：{_safe_error(exc)}"

    return True, ""


def _tesseract_install_message() -> str:
    return (
        "未找到系统级 tesseract.exe。请安装 Tesseract OCR，并将安装目录加入 PATH，"
        "或在 .env 中设置 TESSERACT_CMD=C:\\Program Files\\Tesseract-OCR\\tesseract.exe。"
    )


def _tesseract_languages() -> list[str]:
    try:
        languages = set(pytesseract.get_languages(config=""))
    except Exception:
        return ["chi_sim+eng", "eng"]
    if "chi_sim" in languages and "eng" in languages:
        return ["chi_sim+eng", "eng"]
    if "eng" in languages:
        return ["eng"]
    return sorted(languages) or ["eng"]


def _preprocess_for_ocr(image: Any) -> Any:
    if cv2 is None or np is None or Image is None:
        return None

    try:
        array = np.array(image)
        gray = cv2.cvtColor(array, cv2.COLOR_RGB2GRAY)
        scale = 2 if min(gray.shape[:2]) < 1000 else 1
        if scale > 1:
            gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        denoised = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
        threshold = cv2.adaptiveThreshold(
            denoised,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31,
            9,
        )
        return Image.fromarray(threshold)
    except Exception:
        return None


def _clean_ocr_text(text: str) -> str:
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines)


def _summarize_with_openai_compatible(
    file_name: str,
    mime_type: str | None,
    file_bytes: bytes,
    ocr_text: str,
) -> tuple[dict[str, Any] | None, str]:
    if not OPENAI_API_KEY or not OPENAI_BASE_URL:
        return None, "远程视觉解析未配置 OPENAI_API_KEY 或 OPENAI_BASE_URL"

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

    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
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
    except Exception as exc:
        return None, f"远程视觉解析失败：{_safe_error(exc)}"

    text = _extract_message_text(raw).strip()
    if not text:
        return None, "远程视觉解析响应中没有文本内容"

    if ocr_text and ocr_text not in text:
        text = f"图片摘要：{text}\n\nOCR 原文：\n{ocr_text}"

    return (
        {
            "status": "success",
            "text": text,
            "message": "图片解析完成。",
            "provider": "openai-compatible vision",
            "ocr_text": ocr_text,
        },
        "",
    )


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


def _safe_error(exc: Exception) -> str:
    if isinstance(exc, error.HTTPError):
        try:
            body = exc.read().decode("utf-8", errors="replace").strip()
        except OSError:
            body = ""
        detail = f"HTTP {exc.code}"
        if body:
            detail += f", {body[:200]}"
        return detail
    text = str(exc).strip()
    return text[:200] if text else exc.__class__.__name__
