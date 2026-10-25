#!/usr/bin/env python3
"""Mock 百煉 WebSocket inference server for local tests (no API key needed).

    python scripts/mock_qwen_ws.py
    CANTONESE_QWEN_WS_URL=ws://127.0.0.1:8765/api-ws/v1/inference python -m app

Speaks a 1 s tone as PCM; text containing "ERROR" triggers task-failed.
"""

from __future__ import annotations

import asyncio
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
    try:
        await _serve(ws)
    except websockets.ConnectionClosed:
        pass


async def _serve(ws) -> None:
    task_id = None
    text = ""
    async for raw in ws:
        if isinstance(raw, bytes):
            continue
        event = json.loads(raw)
        header = event.get("header") or {}
        action = header.get("action")

        if action == "run-task":
            task_id = header.get("task_id")
            payload = event.get("payload") or {}
            print("run-task:", payload.get("model"), payload.get("parameters"), flush=True)
            await ws.send(json.dumps({
                "header": {"event": "task-started", "task_id": task_id},
                "payload": {},
            }))

        elif action == "continue-task":
            text += ((event.get("payload") or {}).get("input") or {}).get("text", "")

        elif action == "finish-task":
            if "ERROR" in text:
                await ws.send(json.dumps({
                    "header": {
                        "event": "task-failed",
                        "task_id": task_id,
                        "error_code": "InvalidParameter",
                        "error_message": "mock failure",
                    },
                    "payload": {},
                }))
                continue
            pcm = tone(1.0)
            step = len(pcm) // 4
            for i in range(0, len(pcm), step):
                await ws.send(pcm[i:i + step])
            await ws.send(json.dumps({
                "header": {"event": "result-generated", "task_id": task_id},
                "payload": {"output": {"finish_reason": "stop"}},
            }))
            await ws.send(json.dumps({
                "header": {"event": "task-finished", "task_id": task_id},
                "payload": {"output": {}},
            }))
            print("finished:", text, flush=True)


async def main() -> None:
    async with websockets.serve(handler, "127.0.0.1", 8765):
        print("mock 百煉 inference listening on ws://127.0.0.1:8765", flush=True)
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
