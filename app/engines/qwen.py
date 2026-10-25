"""Qwen-Audio-3.0-TTS-Plus on Alibaba Cloud Model Studio (DashScope).

The model family exposes two transports; we support both and pick at runtime:

* HTTP  — POST /api/v1/services/aigc/multimodal-generation/generation
          {"model": ..., "input": {"text", "voice", "language_type"}}
          returns {"output": {"audio": {"url" | "data"}}}
* WS    — wss://.../api-ws/v1/realtime?model=...
          session.update -> append -> commit -> response.audio.delta (PCM)

Set CANTONESE_QWEN_PROTOCOL=http|realtime|auto (default auto: try HTTP first,
fall back to WS when the endpoint rejects the model/voice).
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import wave

import httpx
import websockets
from websockets.exceptions import InvalidStatus

from .base import Engine, Probe, TTSError, Voice
from .. import config

VOICES = [
    Voice("longanlingxin", "longanlingxin · 龍安靈心"),
    Voice("Cherry", "Cherry · 女聲"),
    Voice("Serena", "Serena · 女聲"),
    Voice("Ethan", "Ethan · 男聲"),
    Voice("Chelsie", "Chelsie · 女聲"),
]


def _pcm_to_wav(pcm: bytes, sample_rate: int = 24000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm)
    return buf.getvalue()


def _looks_like_model_error(exc: TTSError) -> bool:
    text = str(exc).lower()
    return any(k in text for k in ("model", "voice", "unsupported", "invalidparameter", "404"))


async def _http_synth(text: str, voice: str, key: str) -> bytes:
    payload = {
        "model": config.QWEN_MODEL,
        "input": {
            "text": text,
            "voice": voice,
            "language_type": config.QWEN_LANG,
        },
    }
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=90) as client:
            resp = await client.post(config.QWEN_HTTP_URL, json=payload, headers=headers)
    except Exception as exc:
        raise TTSError(f"千問 HTTP 連接失敗：{exc}") from exc

    if resp.status_code != 200:
        detail = ""
        try:
            body = resp.json()
            detail = body.get("message") or body.get("code") or ""
        except Exception:
            detail = resp.text[:160]
        if resp.status_code in (401, 403):
            raise TTSError(f"API Key 無效或無權限（HTTP {resp.status_code}）：{detail}")
        raise TTSError(f"千問 HTTP {resp.status_code}：{detail}")

    audio = ((resp.json().get("output") or {}).get("audio")) or {}
    if audio.get("data"):
        return base64.b64decode(audio["data"])
    if audio.get("url"):
        try:
            async with httpx.AsyncClient(timeout=90, follow_redirects=True) as client:
                dl = await client.get(audio["url"])
            dl.raise_for_status()
            return dl.content
        except Exception as exc:
            raise TTSError(f"下載千問音頻失敗：{exc}") from exc
    raise TTSError("千問 HTTP 未返回音頻")


async def _wait_event(ws, wanted: str, timeout: float = 20.0) -> dict:
    while True:
        raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
        if isinstance(raw, bytes):
            continue
        event = json.loads(raw)
        if event.get("type") == wanted:
            return event
        if event.get("type") == "error":
            err = event.get("error") or {}
            raise TTSError(f"千問 API 錯誤：{err.get('message') or err.get('code') or err}")


async def _connect(url: str, headers: dict):
    try:
        return await websockets.connect(
            url, additional_headers=headers, max_size=None, open_timeout=20
        )
    except TypeError:  # websockets < 13
        return await websockets.connect(
            url, extra_headers=headers, max_size=None, open_timeout=20
        )


async def _ws_synth(text: str, voice: str, key: str) -> bytes:
    url = f"{config.QWEN_WS_URL}?model={config.QWEN_MODEL}"
    try:
        ws = await _connect(url, {"Authorization": f"Bearer {key}"})
    except InvalidStatus as exc:
        code = getattr(exc.response, "status_code", "?")
        raise TTSError(f"API Key 無效或無權限（HTTP {code}）") from exc
    except Exception as exc:
        raise TTSError(f"千問 WebSocket 連接失敗：{exc}") from exc

    chunks: list[bytes] = []
    sample_rate = 24000
    try:
        async with ws:
            await _wait_event(ws, "session.created")
            await ws.send(json.dumps({
                "type": "session.update",
                "session": {
                    "mode": "server_commit",
                    "voice": voice or "Cherry",
                    "language_type": config.QWEN_LANG,
                    "response_format": "pcm",
                    "sample_rate": 24000,
                },
            }))
            try:
                await _wait_event(ws, "session.updated", timeout=5.0)
            except asyncio.TimeoutError:
                pass

            await ws.send(json.dumps({"type": "input_text_buffer.append", "text": text}))
            await ws.send(json.dumps({"type": "input_text_buffer.commit"}))

            while True:
                raw = await asyncio.wait_for(ws.recv(), timeout=60)
                if isinstance(raw, bytes):
                    continue
                event = json.loads(raw)
                kind = event.get("type", "")
                if kind == "session.created":
                    sample_rate = (event.get("session") or {}).get("sample_rate", sample_rate)
                elif kind == "response.audio.delta":
                    payload = event.get("delta") or event.get("audio") or event.get("data") or ""
                    if payload:
                        chunks.append(base64.b64decode(payload))
                elif kind == "error":
                    err = event.get("error") or {}
                    raise TTSError(
                        f"千問 API 錯誤：{err.get('message') or err.get('code') or err}"
                    )
                elif kind == "response.done":
                    break

            try:
                await ws.send(json.dumps({"type": "session.finish"}))
            except Exception:
                pass
    except TTSError:
        raise
    except asyncio.TimeoutError as exc:
        raise TTSError("千問 API 超時（60s 未返回完整音頻）") from exc
    except Exception as exc:
        raise TTSError(f"千問 realtime 失敗：{exc}") from exc

    if not chunks:
        raise TTSError("千問 API 未返回音頻")
    return _pcm_to_wav(b"".join(chunks), sample_rate)


class QwenEngine(Engine):
    id = "qwen-tts"
    name = "Qwen-Audio-3.0-TTS-Plus"
    vendor = "阿里雲百煉（DashScope）"
    kind = "api"
    category = "paid"
    free = False
    requires_key = True
    accepts_key = True
    voice_free_text = True
    description = "千問語音合成，官方稱加強中文方言（含粵語）真實度。需 DashScope API Key，音色可手填。"
    homepage = "https://www.alibabacloud.com/help/en/model-studio/qwen-audio-3-0-tts-plus"

    async def probe(self) -> Probe:
        if config.DASHSCOPE_KEY:
            return Probe(True, "已由伺服器環境變數提供 Key", VOICES)
        return Probe(True, "填入 DashScope API Key 後可用", VOICES)

    async def synth(
        self, text: str, voice: str, rate: int = 0, pitch: int = 0, api_key: str = ""
    ) -> tuple[bytes, str, str]:
        if len(text) > 600:
            raise TTSError("千問單次上限 600 字，請縮短文本")

        key = (api_key or config.DASHSCOPE_KEY).strip()
        if not key:
            raise TTSError("請先在卡片填入 DashScope API Key")

        voice = voice or config.QWEN_VOICE
        protocol = config.QWEN_PROTOCOL

        if protocol == "http":
            audio = await _http_synth(text, voice, key)
        elif protocol == "realtime":
            audio = await _ws_synth(text, voice, key)
        else:
            try:
                audio = await _http_synth(text, voice, key)
            except TTSError as exc:
                if not _looks_like_model_error(exc):
                    raise
                audio = await _ws_synth(text, voice, key)

        if len(audio) < 1000:
            raise TTSError("千問 API 返回的音頻為空")
        return audio, "audio/wav", "wav"
