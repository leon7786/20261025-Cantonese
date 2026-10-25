#!/usr/bin/env python3
"""一次性生成「跟讀學粵語」的離線音頻。

流程：整篇文本 → Qwen-Audio-3.0-TTS-Plus（帶字級時間戳）→ 按「，」「！」切段 → 寫 wav + lessons.json
用法：python scripts/build_lessons.py
"""

from __future__ import annotations

import asyncio
import json
import re
import uuid
import wave
from pathlib import Path

import numpy as np
import websockets

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "articles.json"
OUT_AUDIO = ROOT / "web" / "lessons" / "audio"
OUT_JSON = ROOT / "web" / "lessons.json"
SR = 24000
MODEL = "qwen-audio-3.0-tts-plus"
VOICE = "longanlingxin"
INSTRUCTION = "请用广东话表达。"


def load_env() -> dict:
    env = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith("#"):
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip()
    return env


async def synth(text: str, env: dict) -> tuple[bytes, list[dict]]:
    url = env["CANTONESE_QWEN_WS_URL"]
    headers = {"Authorization": f"Bearer {env['CANTONESE_DASHSCOPE_KEY']}"}
    async with websockets.connect(url, additional_headers=headers, max_size=None) as ws:
        tid = str(uuid.uuid4())
        head = {"task_id": tid, "streaming": "duplex"}
        await ws.send(json.dumps({
            "header": {**head, "action": "run-task"},
            "payload": {
                "task_group": "audio", "task": "tts", "function": "SpeechSynthesizer",
                "model": MODEL,
                "parameters": {
                    "text_type": "PlainText", "voice": VOICE, "format": "pcm",
                    "sample_rate": SR, "word_timestamp_enabled": True,
                    "instruction": INSTRUCTION,
                },
                "input": {},
            },
        }))
        while True:
            msg = await ws.recv()
            if isinstance(msg, bytes):
                continue
            event = json.loads(msg)
            action = (event.get("header") or {}).get("event")
            if action == "task-started":
                break
            if action == "task-failed":
                raise RuntimeError(event)

        await ws.send(json.dumps({"header": {**head, "action": "continue-task"},
                                  "payload": {"input": {"text": text}}}))
        await ws.send(json.dumps({"header": {**head, "action": "finish-task"},
                                  "payload": {"input": {}}}))

        pcm = bytearray()
        words: list[dict] = []
        while True:
            msg = await ws.recv()
            if isinstance(msg, bytes):
                pcm += msg
                continue
            event = json.loads(msg)
            action = (event.get("header") or {}).get("event")
            if action == "result-generated":
                sentence = (((event.get("payload") or {}).get("output") or {}).get("sentence")) or {}
                if sentence.get("words"):
                    words = sentence["words"]  # 最後一份最完整
            elif action == "task-finished":
                break
            elif action == "task-failed":
                raise RuntimeError(event)
        return bytes(pcm), words


def cut_points(text: str, words: list[dict], total_ms: int) -> list[int]:
    """按「，」切點，用字級時間戳換算成毫秒。words 可能把多字合成一個 token，
    所以用累加字數建立 span，而不是依賴 begin_index。"""
    spans: list[tuple[int, int, dict]] = []
    pos = 0
    for word in words:
        length = len(word["text"])
        spans.append((pos, pos + length, word))
        pos += length
    if pos != len(text):
        raise RuntimeError(f"字數對不上：words={pos} text={len(text)}")

    def time_at(index: int) -> int:
        for start, end, word in spans:
            if start <= index < end:
                return int(word["begin_time"])
        return total_ms

    cuts = [0]
    offset = 0
    for seg in re.split(r"(?<=[，！])", text)[:-1]:
        offset += len(seg)
        cuts.append(time_at(offset))
    cuts.append(total_ms)

    # 保證單調遞增，避免 0 時長片段
    for i in range(1, len(cuts)):
        if cuts[i] <= cuts[i - 1] + 40:
            cuts[i] = cuts[i - 1] + 40
    return cuts


def write_wav(path: Path, samples: np.ndarray) -> None:
    fade = int(SR * 0.008)
    if len(samples) > fade * 2:
        samples[:fade] *= np.linspace(0, 1, fade)
        samples[-fade:] *= np.linspace(1, 0, fade)
    pcm = (np.clip(samples, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


async def build() -> None:
    env = load_env()
    articles = json.loads(DATA.read_text(encoding="utf-8"))
    OUT_AUDIO.mkdir(parents=True, exist_ok=True)

    lessons = {"model": MODEL, "voice": VOICE, "instruction": INSTRUCTION, "articles": []}
    for ai, art in enumerate(articles):
        text = art["text"]
        text_segments = [s for s in re.split(r"(?<=[，！])", text) if s]
        # 粵拼按「非標點字數」分配，避免頓號（、）在粵拼裡也是逗號而造成錯位
        jy_tokens = [t for t in art["jyutping"].split() if not re.fullmatch(r"[，。！？；：、,.!?;:]+", t)]
        jy_segments, cursor = [], 0
        for seg in text_segments:
            count = len([c for c in seg if not re.match(r"[，。！？；：、,.!?;:]", c)])
            jy_segments.append(" ".join(jy_tokens[cursor:cursor + count]))
            cursor += count
        assert cursor == len(jy_tokens), (art["title"], cursor, len(jy_tokens))

        print(f"[{ai+1}/{len(articles)}] {art['title']} …", flush=True)
        pcm, words = await synth(text, env)
        audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768
        total_ms = int(len(audio) / SR * 1000)
        cuts = cut_points(text, words, total_ms)

        segs = []
        for si, (zh, jy) in enumerate(zip(text_segments, jy_segments)):
            start, end = cuts[si], cuts[si + 1]
            start_i, end_i = int(start * SR / 1000), int(end * SR / 1000)
            chunk = audio[start_i:end_i].copy()
            name = f"a{ai}s{si}.wav"
            write_wav(OUT_AUDIO / name, chunk)
            segs.append({
                "zh": zh, "jy": jy.strip(),
                "audio": f"/lessons/audio/{name}",
                "dur": round(len(chunk) / SR, 2),
            })
        lessons["articles"].append({"title": art["title"], "tag": art["tag"], "segments": segs,
                                    "duration": round(total_ms / 1000, 2)})
        print(f"    {len(segs)} 段, {total_ms/1000:.1f}s", flush=True)

    OUT_JSON.write_text(json.dumps(lessons, ensure_ascii=False, indent=1), encoding="utf-8")
    print("wrote", OUT_JSON)


if __name__ == "__main__":
    asyncio.run(build())
