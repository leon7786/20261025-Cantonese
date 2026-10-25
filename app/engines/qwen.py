"""Qwen3-TTS via Alibaba Cloud DashScope (Model Studio).

Uses the non-realtime HTTP API; the API key can be supplied per request from the
web UI (stored only in the browser) or via CANTONESE_DASHSCOPE_KEY.
"""

from __future__ import annotations

import base64

import httpx

from .base import Engine, Probe, TTSError, Voice
from .. import config

VOICES = [
    Voice("Cherry", "Cherry · 女聲"),
    Voice("Serena", "Serena · 女聲"),
    Voice("Ethan", "Ethan · 男聲"),
    Voice("Chelsie", "Chelsie · 女聲"),
    Voice("Dylan", "Dylan · 北京男聲"),
    Voice("Eric", "Eric · 四川男聲"),
    Voice("Ryan", "Ryan · 男聲"),
    Voice("Aiden", "Aiden · 男聲"),
    Voice("Ono_Anna", "Ono Anna · 日語女聲"),
    Voice("Sohee", "Sohee · 韓語女聲"),
]


class QwenEngine(Engine):
    id = "qwen-tts"
    name = "Qwen3-TTS"
    vendor = "阿里雲百煉（DashScope）"
    kind = "api"
    category = "paid"
    free = False
    requires_key = True
    accepts_key = True
    description = "千問語音合成，需 DashScope API Key。官方語言清單未含粵語，粵字會以普通話音色讀出。"
    homepage = "https://github.com/QwenLM/Qwen3-TTS"

    async def probe(self) -> Probe:
        if config.DASHSCOPE_KEY:
            return Probe(True, "已由伺服器環境變數提供 Key", VOICES)
        return Probe(True, "填入 DashScope API Key 後可用", VOICES)

    async def synth(
        self, text: str, voice: str, rate: int = 0, pitch: int = 0, api_key: str = ""
    ) -> tuple[bytes, str, str]:
        key = (api_key or config.DASHSCOPE_KEY).strip()
        if not key:
            raise TTSError("請先在卡片填入 DashScope API Key")

        payload = {
            "model": config.QWEN_MODEL,
            "input": {
                "text": text,
                "voice": voice or "Cherry",
                "language_type": config.QWEN_LANG,
            },
        }
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=90) as client:
                resp = await client.post(config.QWEN_URL, json=payload, headers=headers)
        except Exception as exc:
            raise TTSError(f"千問 API 連接失敗：{exc}") from exc

        if resp.status_code != 200:
            detail = ""
            try:
                detail = resp.json().get("message") or resp.json().get("code") or ""
            except Exception:
                detail = resp.text[:160]
            if resp.status_code in (401, 403):
                raise TTSError(f"API Key 無效（{resp.status_code}）：{detail}")
            raise TTSError(f"千問 API {resp.status_code}：{detail}")

        audio = ((resp.json().get("output") or {}).get("audio")) or {}
        if audio.get("data"):
            raw = base64.b64decode(audio["data"])
        elif audio.get("url"):
            try:
                async with httpx.AsyncClient(timeout=90, follow_redirects=True) as client:
                    dl = await client.get(audio["url"])
                dl.raise_for_status()
                raw = dl.content
            except Exception as exc:
                raise TTSError(f"下載千問音頻失敗：{exc}") from exc
        else:
            raise TTSError("千問 API 未返回音頻")

        if len(raw) < 1000:
            raise TTSError("千問 API 返回的音頻為空")
        return raw, "audio/wav", "wav"
