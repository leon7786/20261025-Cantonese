"""gTTS: Google Translate's Cantonese (yue) voice via the public TTS endpoint."""

from __future__ import annotations

import httpx

from .base import Engine, Probe, TTSError, Voice

VOICES = [Voice("yue", "Google 粵語", note="單一音色，較自然")]
ENDPOINT = "https://translate.google.com/translate_tts"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}
PUNCT = "。！？；：、，,.!?;\n"


def _chunks(text: str, limit: int = 160) -> list[str]:
    """Split long text so the query string stays small."""
    parts: list[str] = []
    buf = ""
    for ch in text:
        buf += ch
        if len(buf) >= limit and ch in PUNCT:
            parts.append(buf.strip())
            buf = ""
    if buf.strip():
        parts.append(buf.strip())
    return [p for p in parts if p]


async def _fetch(client: httpx.AsyncClient, text: str) -> bytes:
    params = {"ie": "UTF-8", "q": text, "tl": "yue", "client": "tw-ob", "ttsspeed": "1"}
    resp = await client.get(ENDPOINT, params=params, headers=HEADERS, timeout=25)
    if resp.status_code == 429:
        raise TTSError("Google 返回 429：請求過於頻繁，請稍後再試")
    if resp.status_code != 200:
        raise TTSError(f"Google TTS 返回 {resp.status_code}")
    return resp.content


class GTtsEngine(Engine):
    id = "gtts"
    name = "gTTS"
    vendor = "Google 翻譯（粵語）"
    kind = "online"
    category = "quality"
    description = "Google 翻譯的粵語音色，免費、自然度不錯；非官方接口，有頻率限制。"
    homepage = "https://github.com/pndurette/gTTS"
    supports_rate = False
    supports_pitch = False

    async def probe(self) -> Probe:
        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                data = await _fetch(client, "你好")
        except Exception as exc:
            return Probe(False, f"無法連接 Google：{type(exc).__name__}", VOICES)
        if len(data) < 500:
            return Probe(False, "Google 返回空音頻", VOICES)
        return Probe(True, "Google 在線粵語音色", VOICES)

    async def synth(
        self, text: str, voice: str, rate: int = 0, pitch: int = 0, api_key: str = ""
    ) -> tuple[bytes, str, str]:
        chunks = _chunks(text)
        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                audio = b"".join([await _fetch(client, c) for c in chunks])
        except TTSError:
            raise
        except Exception as exc:
            raise TTSError(f"gTTS 合成失敗：{exc}") from exc
        if len(audio) < 500:
            raise TTSError("gTTS 未返回音頻")
        return audio, "audio/mpeg", "mp3"
