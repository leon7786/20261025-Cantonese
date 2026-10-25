"""Google Cloud Text-to-Speech (yue-HK Cantonese voices)."""

from __future__ import annotations

import base64

import httpx

from .base import Engine, Probe, TTSError, Voice

VOICES = [
    Voice("yue-HK-Standard-A", "yue-HK Standard A · 女聲"),
    Voice("yue-HK-Standard-B", "yue-HK Standard B · 男聲"),
    Voice("yue-HK-Standard-C", "yue-HK Standard C · 男聲"),
    Voice("yue-HK-Standard-D", "yue-HK Standard D · 女聲"),
]
URL = "https://texttospeech.googleapis.com/v1/text:synthesize"


class GoogleTTSEngine(Engine):
    id = "google-tts"
    name = "Google Cloud TTS"
    vendor = "Google Cloud"
    kind = "api"
    category = "paid"
    free = False
    requires_key = True
    accepts_key = True
    description = "Google Cloud 的粵語音色（yue-HK），需 API Key。"
    homepage = "https://cloud.google.com/text-to-speech"

    async def probe(self) -> Probe:
        return Probe(True, "填入 Google Cloud API Key 後可用", VOICES)

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
            raise TTSError("請先在卡片填入 Google Cloud API Key")

        payload = {
            "input": {"text": text},
            "voice": {"languageCode": "yue-HK", "name": voice or VOICES[0].id},
            "audioConfig": {"audioEncoding": "MP3", "speakingRate": 1 + rate / 100},
        }
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(URL, params={"key": key}, json=payload)
        except Exception as exc:
            raise TTSError(f"Google TTS 連接失敗：{exc}") from exc

        if resp.status_code != 200:
            detail = ""
            try:
                detail = (resp.json().get("error") or {}).get("message", "")
            except Exception:
                detail = resp.text[:160]
            if resp.status_code in (401, 403):
                raise TTSError(f"API Key 無效或未授權（HTTP {resp.status_code}）：{detail}")
            raise TTSError(f"Google TTS {resp.status_code}：{detail}")

        content = (resp.json() or {}).get("audioContent")
        if not content:
            raise TTSError("Google TTS 未返回音頻")
        audio = base64.b64decode(content)
        if len(audio) < 500:
            raise TTSError("Google TTS 返回的音頻為空")
        return audio, "audio/mpeg", "mp3"
