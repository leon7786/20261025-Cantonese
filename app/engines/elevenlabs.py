"""ElevenLabs text-to-speech (supports Cantonese via multilingual models)."""

from __future__ import annotations

import httpx

from .base import Engine, Probe, TTSError, Voice

DEFAULT_VOICE = "21m00Tcm4TlvDq8ikWAM"  # Rachel
VOICES = [Voice(DEFAULT_VOICE, "Rachel · 預設音色")]


class ElevenLabsEngine(Engine):
    id = "elevenlabs"
    name = "ElevenLabs"
    vendor = "ElevenLabs"
    kind = "api"
    category = "paid"
    free = False
    requires_key = True
    accepts_key = True
    voice_free_text = True
    description = "多語音合成，官方語言表含粵語 `yue`；需 API Key，音色 ID 可自訂。"
    homepage = "https://elevenlabs.io/docs"

    async def probe(self) -> Probe:
        return Probe(True, "填入 ElevenLabs API Key 後可用", VOICES)

    async def synth(
        self,
        text: str,
        voice: str,
        rate: int = 0,
        pitch: int = 0,
        api_key: str = "",
        instruction: str = "",
    ) -> tuple[bytes, str, str]:
        key = api_key.strip()
        if not key:
            raise TTSError("請先在卡片填入 ElevenLabs API Key")

        voice_id = voice or DEFAULT_VOICE
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        try:
            async with httpx.AsyncClient(timeout=90) as client:
                resp = await client.post(
                    url,
                    params={"output_format": "mp3_44100_128"},
                    headers={"xi-api-key": key, "Accept": "audio/mpeg"},
                    json={"text": text, "model_id": "eleven_multilingual_v2"},
                )
        except Exception as exc:
            raise TTSError(f"ElevenLabs 連接失敗：{exc}") from exc

        if resp.status_code != 200:
            detail = ""
            try:
                detail = (resp.json().get("detail") or {}).get("message", "") or resp.text[:160]
            except Exception:
                detail = resp.text[:160]
            if resp.status_code in (401, 403):
                raise TTSError(f"API Key 無效或無權限（HTTP {resp.status_code}）：{detail}")
            raise TTSError(f"ElevenLabs {resp.status_code}：{detail}")

        if len(resp.content) < 500:
            raise TTSError("ElevenLabs 返回的音頻為空")
        return resp.content, "audio/mpeg", "mp3"
