#!/usr/bin/env python3
"""Mock Qwen3-TTS-Realtime WebSocket server for local testing without an API key.

Usage:
    python scripts/mock_qwen_ws.py            # listens on 127.0.0.1:8765
    CANTONESE_QWEN_WS_URL=ws://127.0.0.1:8765/api-ws/v1/realtime python -m app

Sends a 1 kHz tone as PCM; text containing "ERROR" triggers an error event.
"""

from __future__ import annotations

import asyncio
import base64
import json
import math
import struct

import websockets

SR = 24000


def tone(seconds: float = 1.0, freq: int = 440) -> bytes:
    n = int(SR * seconds)
    return b"".join(
        struct.pack("<h", int(12000 * math.sin(2 * math.pi * freq * i / SR))) for i in range(n)
    )


async def handler(ws) -> None:
    configured = False
    text = ""
    await ws.send(json.dumps({
        "type": "session.created",
        "session": {"id": "sess_mock", "sample_rate": SR, "voice": "Cherry"},
    }))

    async for raw in ws:
        event = json.loads(raw)
        kind = event.get("type")

        if kind == "session.update":
            configured = True
            print("session.update:", event.get("session"), flush=True)
            await ws.send(json.dumps({"type": "session.updated", "session": {"id": "sess_mock"}}))

        elif kind == "input_text_buffer.append":
            assert configured, "append received before session.update"
            text += event.get("text", "")

        elif kind == "input_text_buffer.commit":
            print("commit:", text, flush=True)
            if "ERROR" in text:
                await ws.send(json.dumps({
                    "type": "error",
                    "error": {"code": "InvalidParameter", "message": "mock failure"},
                }))
                continue
            await ws.send(json.dumps({"type": "response.created", "response": {"id": "resp_1"}}))
            pcm = tone(1.0)
            step = len(pcm) // 4
            for i in range(0, len(pcm), step):
                await ws.send(json.dumps({
                    "type": "response.audio.delta",
                    "delta": base64.b64encode(pcm[i:i + step]).decode(),
                }))
            await ws.send(json.dumps({"type": "response.audio.done"}))
            await ws.send(json.dumps({"type": "response.done", "response": {"id": "resp_1"}}))

        elif kind == "session.finish":
            await ws.send(json.dumps({"type": "session.finished"}))
            break


async def main() -> None:
    async with websockets.serve(handler, "127.0.0.1", 8765):
        print("mock Qwen realtime listening on ws://127.0.0.1:8765", flush=True)
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
