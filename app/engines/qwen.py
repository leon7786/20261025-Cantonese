"""Qwen3-TTS Realtime via Alibaba Cloud DashScope WebSocket API.

Protocol (Model Studio "Qwen-TTS-Realtime WebSocket API"):
  wss://dashscope.aliyuncs.com/api-ws/v1/realtime?model=qwen3-tts-flash-realtime
  Authorization: Bearer <key>
  -> session.update {mode, voice, language_type, response_format:"pcm", sample_rate}
  -> input_text_buffer.append {text}
  -> input_text_buffer.commit
  <- response.audio.delta (base64 PCM) ... response.done

The API key can be supplied per request from the web UI (kept in the browser
only) or via CANTONESE_DASHSCOPE_KEY.
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import wave

import websockets
from websockets.exceptions import InvalidStatus

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


def _pcm_to_wav(pcm: bytes, sample_rate: int = 24000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm)
    return buf.getvalue()


async def _connect(url: str, headers: dict):
    try:
        return await websockets.connect(
            url, additional_headers=headers, max_size=None, open_timeout=20
        )
    except TypeError:  # websockets < 13
        return await websockets.connect(
            url, extra_headers=headers, max_size=None, open_timeout=20
        )


async def _synthesize(text: str, voice: str, key: str) -> bytes:
    url = f"{config.QWEN_WS_URL}?model={config.QWEN_MODEL}"
    headers = {"Authorization": f"Bearer {key}"}
    try:
        ws = await _connect(url, headers)
    except InvalidStatus as exc:
        code = getattr(exc.response, "status_code", "?")
        raise TTSError(f"API Key 無效或無權限（HTTP {code}）") from exc
    except Exception as exc:
        raise TTSError(f"千問 WebSocket 連接失敗：{exc}") from exc

    chunks: list[bytes] = []
    sample_rate = 24000
    try:
        async with ws:
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
    name = "Qwen3-TTS Realtime"
    vendor = "阿里雲百煉（DashScope）"
    kind = "api"
    category = "paid"
    free = False
    requires_key = True
    accepts_key = True
    description = "千問實時語音合成（qwen3-tts-flash-realtime，WebSocket）。官方語言清單未含粵語。"
    homepage = "https://github.com/QwenLM/Qwen3-TTS"

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

        audio = await _synthesize(text, voice, key)
        if len(audio) < 1000:
            raise TTSError("千問 API 返回的音頻為空")
        return audio, "audio/wav", "wav"
