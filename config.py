from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv() -> bool:
        return False

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
BENCHMARK_DIR = BASE_DIR / "benchmark"
REPORTS_DIR = BASE_DIR / os.getenv("REPORTS_DIR", "reports")
THINK_LOG_DIR = BASE_DIR / os.getenv("THINK_LOG_DIR", "think_log")
DOCS_DIR = BASE_DIR / "docs"
KNOWLEDGE_BASE_DIR = BASE_DIR / os.getenv("KNOWLEDGE_BASE_DIR", "knowledge_base")
KNOWLEDGE_DOCS_PATH = KNOWLEDGE_BASE_DIR / os.getenv("KNOWLEDGE_DOCS_FILE", "documents.json")
FAISS_INDEX_PATH = KNOWLEDGE_BASE_DIR / os.getenv("FAISS_INDEX_DIR", "faiss_index")

MAX_ITERATIONS = int(os.getenv("MAX_ITERATIONS", "3"))
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "offline")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "sk-Pz0ejAAF1TE8ef8TK601IFbURJDcAYDCD")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.")
OPENAI_TIMEOUT = float(os.getenv("OPENAI_TIMEOUT", "30"))
OPENAI_MAX_RETRIES = int(os.getenv("OPENAI_MAX_RETRIES", "2"))
ENABLE_LLM_REASONING = os.getenv("ENABLE_LLM_REASONING", "false").strip().lower() in {"1", "true", "yes", "on"}
ENABLE_RAG_RETRIEVAL = os.getenv("ENABLE_RAG_RETRIEVAL", "true").strip().lower() in {"1", "true", "yes", "on"}
DEFAULT_ZSCORE_THRESHOLD = float(os.getenv("DEFAULT_ZSCORE_THRESHOLD", "2.5"))
DEFAULT_TOP_K_SERVICES = int(os.getenv("DEFAULT_TOP_K_SERVICES", "3"))
DEFAULT_WINDOW_SIZE = int(os.getenv("DEFAULT_WINDOW_SIZE", "30"))
DEFAULT_REPORT_PREFIX = os.getenv("DEFAULT_REPORT_PREFIX", "rca_report")
KB_TOP_K = int(os.getenv("KB_TOP_K", "3"))
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "tfidf")
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "")
EMBEDDING_BASE_URL = os.getenv("EMBEDDING_BASE_URL", OPENAI_BASE_URL)

REPORTS_DIR.mkdir(parents=True, exist_ok=True)
THINK_LOG_DIR.mkdir(parents=True, exist_ok=True)
DOCS_DIR.mkdir(parents=True, exist_ok=True)
KNOWLEDGE_BASE_DIR.mkdir(parents=True, exist_ok=True)
