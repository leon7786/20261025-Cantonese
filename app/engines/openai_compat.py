"""Generic OpenAI-compatible /v1/audio/speech adapter (VoxCPM, self-hosted, ...)."""

from __future__ import annotations

import httpx

from . import _http
from .. import config
from .base import Engine, Probe, TTSError, Voice


def _speech_url(base: str) -> str:
    base = _http.norm_base(base)
    return base + "/audio/speech" if base.endswith("/v1") else base + "/v1/audio/speech"


class OpenAICompatEngine(Engine):
    id = "openai-compat"
    name = "OpenAI 兼容接口"
    vendor = "自建 / 第三方"
    kind = "remote"
    description = "任何實現 /v1/audio/speech 的服務（自架 VoxCPM、聚合網關等）都可接入。"
    homepage = "https://platform.openai.com/docs/api-reference/audio"
    supports_rate = True
    supports_pitch = False

    async def probe(self) -> Probe:
        voices = [Voice(config.OPENAI_TTS_VOICE, config.OPENAI_TTS_VOICE)]
        if not config.OPENAI_TTS_URL:
            return Probe(False, "未配置 CANTONESE_OPENAI_URL", voices)
        ok, detail = await _http.reachable(config.OPENAI_TTS_URL)
        if not ok:
            return Probe(False, detail, voices)
        return Probe(True, f"接口已連接（{detail}）", voices)

    async def synth(
        self, text: str, voice: str, rate: int = 0, pitch: int = 0
    ) -> tuple[bytes, str, str]:
        if not config.OPENAI_TTS_URL:
            raise TTSError("OpenAI 兼容接口未配置")
        headers = {}
        if config.OPENAI_TTS_KEY:
            headers["Authorization"] = f"Bearer {config.OPENAI_TTS_KEY}"
        payload = {
            "model": config.OPENAI_TTS_MODEL,
            "input": text,
            "voice": voice or config.OPENAI_TTS_VOICE,
            "response_format": "wav",
            "speed": max(0.5, min(2.0, 1 + rate / 100)),
        }
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    _speech_url(config.OPENAI_TTS_URL), json=payload, headers=headers
                )
        except Exception as exc:
            raise TTSError(f"OpenAI 兼容接口失敗：{exc}") from exc
        if resp.status_code != 200:
            raise TTSError(f"接口返回 {resp.status_code}：{resp.text[:200]}")
        if not resp.content:
            raise TTSError("接口未返回音頻")
        mime = resp.headers.get("content-type", "audio/wav")
        return resp.content, mime, "wav"
