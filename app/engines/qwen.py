"""Qwen-Audio-3.0-TTS-Plus on Alibaba Cloud Model Studio (百炼).

官方手册的接入方式是 WebSocket inference（SpeechSynthesizer）：

    wss://dashscope.aliyuncs.com/api-ws/v1/inference
    Authorization: Bearer <api key>
    -> run-task      {task_group: audio, task: tts, function: SpeechSynthesizer, model, parameters}
    <- task-started
    -> continue-task {input: {text}}
    -> finish-task   {input: {}}
    <- 二进制音频帧 / result-generated / task-finished

方言通过 `instruction` 控制（例如「用广东话朗读」），音色见
https://help.aliyun.com/zh/model-studio/qwen-audio-tts-voice-list
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import uuid
import wave

import httpx
import websockets
from websockets.exceptions import InvalidStatus

from .base import Engine, Probe, TTSError, Voice
from .. import config

VOICES = [
    Voice("longanlingxin", "龍安靈心 · 女聲（普通話/英文）"),
    Voice("longanlufeng", "龍安魯風 · 男聲（普通話/英文）"),
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


def _headers(key: str) -> dict:
    headers = {"Authorization": f"Bearer {key}"}
    if config.QWEN_WORKSPACE:
        headers["X-DashScope-WorkSpace"] = config.QWEN_WORKSPACE
    return headers


async def _ws_inference(text: str, voice: str, key: str, instruction: str) -> bytes:
    params = {
        "text_type": "PlainText",
        "voice": voice,
        "format": "pcm",
        "sample_rate": 24000,
        "volume": 50,
        "rate": 1,
        "pitch": 1,
        "enable_ssml": False,
    }
    if instruction:
        params["instruction"] = instruction
    if config.QWEN_LANG_HINTS:
        params["language_hints"] = [config.QWEN_LANG_HINTS]

    task_id = str(uuid.uuid4())
    header = {"task_id": task_id, "streaming": "duplex"}

    try:
        ws = await _connect(config.QWEN_WS_URL, _headers(key))
    except InvalidStatus as exc:
        code = getattr(exc.response, "status_code", "?")
        raise TTSError(f"API Key 無效或無權限（HTTP {code}）") from exc
    except Exception as exc:
        raise TTSError(f"百煉 WebSocket 連接失敗：{exc}") from exc

    chunks: list[bytes] = []
    try:
        async with ws:
            await ws.send(json.dumps({
                "header": {**header, "action": "run-task"},
                "payload": {
                    "task_group": "audio",
                    "task": "tts",
                    "function": "SpeechSynthesizer",
                    "model": config.QWEN_MODEL,
                    "parameters": params,
                    "input": {},
                },
            }))

            # 等待 task-started
            while True:
                raw = await asyncio.wait_for(ws.recv(), timeout=30)
                if isinstance(raw, bytes):
                    continue
                event = json.loads(raw)
                action = (event.get("header") or {}).get("event")
                if action == "task-started":
                    break
                if action == "task-failed":
                    raise TTSError(_event_error(event))

            await ws.send(json.dumps({
                "header": {**header, "action": "continue-task"},
                "payload": {"input": {"text": text}},
            }))
            await ws.send(json.dumps({
                "header": {**header, "action": "finish-task"},
                "payload": {"input": {}},
            }))

            while True:
                raw = await asyncio.wait_for(ws.recv(), timeout=90)
                if isinstance(raw, bytes):
                    chunks.append(raw)
                    continue
                event = json.loads(raw)
                action = (event.get("header") or {}).get("event")
                if action == "result-generated":
                    audio = (event.get("payload") or {}).get("output", {}).get("audio") or {}
                    if audio.get("data"):
                        chunks.append(base64.b64decode(audio["data"]))
                elif action == "task-finished":
                    break
                elif action == "task-failed":
                    raise TTSError(_event_error(event))
    except TTSError:
        raise
    except asyncio.TimeoutError as exc:
        raise TTSError("百煉 API 超時（90s 未返回完整音頻）") from exc
    except Exception as exc:
        raise TTSError(f"百煉 WebSocket 失敗：{exc}") from exc

    if not chunks:
        raise TTSError("百煉 API 未返回音頻")
    return _pcm_to_wav(b"".join(chunks), 24000)


def _event_error(event: dict) -> str:
    header = event.get("header") or {}
    return (
        header.get("error_message")
        or header.get("error_code")
        or json.dumps(event, ensure_ascii=False)[:200]
    )


async def _http_synth(text: str, voice: str, key: str, instruction: str) -> bytes:
    """Fallback: multimodal-generation HTTP endpoint (used by qwen3-tts family)."""
    payload = {
        "model": config.QWEN_MODEL,
        "input": {"text": text, "voice": voice, "language_type": config.QWEN_LANG},
    }
    if instruction:
        payload["input"]["instruction"] = instruction
    try:
        async with httpx.AsyncClient(timeout=90) as client:
            resp = await client.post(config.QWEN_HTTP_URL, json=payload, headers=_headers(key))
    except Exception as exc:
        raise TTSError(f"百煉 HTTP 連接失敗：{exc}") from exc

    if resp.status_code != 200:
        try:
            body = resp.json()
            detail = body.get("message") or body.get("code") or ""
        except Exception:
            detail = resp.text[:160]
        if resp.status_code in (401, 403):
            raise TTSError(f"API Key 無效或無權限（HTTP {resp.status_code}）：{detail}")
        raise TTSError(f"百煉 HTTP {resp.status_code}：{detail}")

    audio = ((resp.json().get("output") or {}).get("audio")) or {}
    if audio.get("data"):
        return base64.b64decode(audio["data"])
    if audio.get("url"):
        async with httpx.AsyncClient(timeout=90, follow_redirects=True) as client:
            dl = await client.get(audio["url"])
        dl.raise_for_status()
        return dl.content
    raise TTSError("百煉 HTTP 未返回音頻")


class QwenEngine(Engine):
    id = "qwen-tts"
    name = "Qwen-Audio-3.0-TTS-Plus"
    vendor = "阿里雲百煉（DashScope）"
    kind = "api"
    category = "paid"
    free = False
    requires_key = True
    accepts_key = True
    accepts_instruction = True
    voice_free_text = True
    collapsible_fields = True
    description = "百煉語音合成（WebSocket inference），方言靠 instruction 控制，例如「用廣東話朗讀」。"
    homepage = "https://help.aliyun.com/zh/model-studio/qwen-audio-3-0-tts-plus"

    async def probe(self) -> Probe:
        if config.DASHSCOPE_KEY:
            return Probe(True, "已由伺服器環境變數提供 Key", VOICES)
        return Probe(True, "填入百煉 API Key 後可用", VOICES)

    async def synth(
        self,
        text: str,
        voice: str,
        rate: int = 0,
        pitch: int = 0,
        api_key: str = "",
        instruction: str = "",
    ) -> tuple[bytes, str, str]:
        if len(text) > 2000:
            raise TTSError("百煉單次文本過長，請縮短")

        key = (api_key or config.DASHSCOPE_KEY).strip()
        if not key:
            raise TTSError("請先在卡片填入百煉 API Key")

        voice = voice or config.QWEN_VOICE
        instruction = (instruction or config.QWEN_INSTRUCTION).strip()
        protocol = config.QWEN_PROTOCOL

        if protocol == "http":
            audio = await _http_synth(text, voice, key, instruction)
        else:
            audio = await _ws_inference(text, voice, key, instruction)

        if len(audio) < 1000:
            raise TTSError("百煉返回的音頻為空")
        return audio, "audio/wav", "wav"
