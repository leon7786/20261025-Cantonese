"""cantonese.ai text-to-speech API (dedicated Cantonese service)."""

from __future__ import annotations

import base64

import httpx

from .base import Engine, Probe, TTSError, Voice

VOICES = [Voice("default", "系統預設音色")]
URL = "https://cantonese.ai/api/tts"


class CantoneseAIEngine(Engine):
    id = "cantonese-ai"
    name = "cantonese.ai"
    vendor = "cantonese.ai"
    kind = "api"
    category = "paid"
    free = False
    requires_key = True
    accepts_key = True
    voice_free_text = True
    description = "粵語專用雲端 API（V8.3），支援粵拼提示；需 API Key，voice_id 可自訂。"
    homepage = "https://docs.cantonese.ai/text-to-speech"

    async def probe(self) -> Probe:
        return Probe(True, "填入 cantonese.ai API Key 後可用", VOICES)

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
            raise TTSError("請先在卡片填入 cantonese.ai API Key")
        if len(text) > 5000:
            raise TTSError("cantonese.ai 單次上限 5000 字")

        payload = {
            "api_key": key,
            "text": text,
            "language": "cantonese",
            "output_extension": "wav",
            "frame_rate": "24000",
            "model_id": "8-3",
            "speed": max(0.5, min(2.0, 1 + rate / 100)),
            "pitch": pitch,
        }
        if voice and voice != "default":
            payload["voice_id"] = voice

        try:
            async with httpx.AsyncClient(timeout=90) as client:
                resp = await client.post(URL, json=payload)
        except Exception as exc:
            raise TTSError(f"cantonese.ai 連接失敗：{exc}") from exc

        if resp.status_code != 200:
            detail = ""
            try:
                detail = resp.json().get("message") or resp.json().get("error") or ""
            except Exception:
                detail = resp.text[:160]
            if resp.status_code in (401, 403):
                raise TTSError(f"API Key 無效或無權限（HTTP {resp.status_code}）：{detail}")
            raise TTSError(f"cantonese.ai {resp.status_code}：{detail}")

        ctype = resp.headers.get("content-type", "")
        if ctype.startswith("audio"):
            audio = resp.content
        else:
            body = resp.json() if resp.content else {}
            if body.get("audio_base64"):
                audio = base64.b64decode(body["audio_base64"])
            elif body.get("audio_url"):
                async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
                    dl = await client.get(body["audio_url"])
                dl.raise_for_status()
                audio = dl.content
            else:
                raise TTSError("cantonese.ai 未返回音頻")

        if len(audio) < 500:
            raise TTSError("cantonese.ai 返回的音頻為空")
        return audio, "audio/wav", "wav"
