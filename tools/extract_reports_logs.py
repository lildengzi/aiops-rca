"""
从 `reports/` 目录扫描可能包含的日志 JSON 或代码块，并将其提取保存到 `logs/` 目录。
用于把智能体生成但未保存的日志提取并归档。

用法:
python tools/extract_reports_logs.py

"""
import os
import re
import json
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(__file__))
REPORTS_DIR = os.path.join(ROOT, "reports")
LOGS_DIR = os.path.join(ROOT, "logs")
os.makedirs(LOGS_DIR, exist_ok=True)

BLOCK_RE = re.compile(r"```(?:json)?\n(.*?)```", re.S)
JSON_LIKE_RE = re.compile(r"\{\s*\"agent_type\"|\[\s*\{\s*\"timestamp\"", re.S)
SECTION_HEADER_RE = re.compile(r"^##+\s*分析过程日志\s*$", re.M)


def _try_parse_json(text: str):
    try:
        return json.loads(text)
    except Exception:
        # 尝试行级拼接
        try:
            return json.loads(text.strip())
        except Exception:
            return None


def extract_and_save():
    saved = []
    for fname in os.listdir(REPORTS_DIR):
        path = os.path.join(REPORTS_DIR, fname)
        if not os.path.isfile(path):
            continue
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            txt = f.read()
        # 先查找 ```json ``` 或 ``` ``` 块
        for m in BLOCK_RE.finditer(txt):
            block = m.group(1).strip()
            if JSON_LIKE_RE.search(block):
                parsed = _try_parse_json(block)
                if parsed and (isinstance(parsed, dict) or isinstance(parsed, list)):
                    # 如果是包含 logs 的 payload
                    if isinstance(parsed, dict) and parsed.get("data") and parsed["data"].get("logs"):
                        payload = parsed
                        service = payload.get("service") or "unknown"
                        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
                        out = os.path.join(LOGS_DIR, f"extracted_{os.path.splitext(fname)[0]}_{ts}.json")
                        with open(out, "w", encoding="utf-8") as o:
                            json.dump(payload, o, ensure_ascii=False, indent=2)
                        saved.append(out)
                    else:
                        # 如果是直接 logs 列表或包含 logs 字段的对象
                        if isinstance(parsed, dict) and parsed.get("logs"):
                            service = parsed.get("service") or "unknown"
                            ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
                            out = os.path.join(LOGS_DIR, f"extracted_{os.path.splitext(fname)[0]}_{ts}.json")
                            with open(out, "w", encoding="utf-8") as o:
                                json.dump(parsed, o, ensure_ascii=False, indent=2)
                            saved.append(out)
                        elif isinstance(parsed, list):
                            ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
                            out = os.path.join(LOGS_DIR, f"extracted_{os.path.splitext(fname)[0]}_{ts}.json")
                            with open(out, "w", encoding="utf-8") as o:
                                json.dump({"logs": parsed}, o, ensure_ascii=False, indent=2)
                            saved.append(out)
        # 其次，尝试在全文中寻找 JSON 对象的可能片段（简单启发式）
        for m in JSON_LIKE_RE.finditer(txt):
            start = m.start()
            # 尝试取后续最多 2000 字符作为候选
            candidate = txt[start:start+2000]
            # 尝试从最小起点向后找到闭合 '}' 或 ']'
            braces = [candidate.find('}'), candidate.find(']')]
            cut = None
            for b in braces:
                if b != -1:
                    cut = b
            if cut:
                candidate = candidate[:cut+1]
            parsed = _try_parse_json(candidate)
            if parsed:
                ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
                out = os.path.join(LOGS_DIR, f"extracted_{os.path.splitext(fname)[0]}_{ts}.json")
                with open(out, "w", encoding="utf-8") as o:
                    if isinstance(parsed, (dict, list)):
                        json.dump(parsed, o, ensure_ascii=False, indent=2)
                    else:
                        o.write(str(parsed))
                saved.append(out)
    return saved


if __name__ == "__main__":
    outs = extract_and_save()
    # 另外尝试按“分析过程日志”节提取为纯文本并保存
    # 适配 rca_report_*.md 文件中的分析过程日志段落
    for fname in os.listdir(REPORTS_DIR):
        if not fname.startswith("rca_report_"):
            continue
        path = os.path.join(REPORTS_DIR, fname)
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            txt = f.read()
        m = SECTION_HEADER_RE.search(txt)
        if m:
            start = m.end()
            # 截取到下一个二级标题或文件结尾
            next_header = re.search(r"^##+\s+", txt[start:], re.M)
            end = start + (next_header.start() if next_header else len(txt[start:]))
            section = txt[start:end].strip()
            if section:
                out = os.path.join(LOGS_DIR, f"extracted_section_{os.path.splitext(fname)[0]}.txt")
                with open(out, "w", encoding="utf-8") as o:
                    o.write(section)
                outs.append(out)
    if outs:
        print(f"Saved {len(outs)} extracted log file(s) to {LOGS_DIR}:")
        for p in outs:
            print(" - ", p)
    else:
        print("No logs extracted from reports.")
