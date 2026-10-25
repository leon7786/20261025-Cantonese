"""Configuration loading for the Cantonese TTS playground."""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader so we do not depend on python-dotenv."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv(BASE_DIR / ".env")


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


CACHE_DIR = Path(env("CANTONESE_CACHE_DIR", str(BASE_DIR / ".cache")))
MAX_TEXT_LEN = int(env("CANTONESE_MAX_TEXT", "2000"))
SYNTH_TIMEOUT = float(env("CANTONESE_SYNTH_TIMEOUT", "120"))

# Remote engine endpoints (empty means "not configured").
GPT_SOVITS_URL = env("CANTONESE_GPT_SOVITS_URL")
GPT_SOVITS_REF = env("CANTONESE_GPT_SOVITS_REF")
GPT_SOVITS_PROMPT = env("CANTONESE_GPT_SOVITS_PROMPT")

COSYVOICE_URL = env("CANTONESE_COSYVOICE_URL")
COSYVOICE_SPK = env("CANTONESE_COSYVOICE_SPK", "中文女")

# Qwen3-TTS on Alibaba Cloud DashScope (Beijing region by default).
DASHSCOPE_KEY = env("CANTONESE_DASHSCOPE_KEY") or env("DASHSCOPE_API_KEY")
QWEN_URL = env(
    "CANTONESE_QWEN_URL",
    "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation",
)
QWEN_MODEL = env("CANTONESE_QWEN_MODEL", "qwen3-tts-flash")
QWEN_LANG = env("CANTONESE_QWEN_LANG", "Chinese")

OPENAI_TTS_URL = env("CANTONESE_OPENAI_URL")
OPENAI_TTS_KEY = env("CANTONESE_OPENAI_KEY")
OPENAI_TTS_MODEL = env("CANTONESE_OPENAI_MODEL", "tts-1")
OPENAI_TTS_VOICE = env("CANTONESE_OPENAI_VOICE", "alloy")

CACHE_DIR.mkdir(parents=True, exist_ok=True)
