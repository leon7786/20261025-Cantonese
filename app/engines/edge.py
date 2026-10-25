"""edge-tts: free client for Microsoft Edge's online TTS (zh-HK Cantonese voices)."""

from __future__ import annotations

import asyncio

import edge_tts

from .base import Engine, Probe, TTSError, Voice

VOICES = [
    Voice("zh-HK-HiuMaanNeural", "曉曼 HiuMaan · 女聲", note="新聞/旁白感，最常用"),
    Voice("zh-HK-HiuGaaiNeural", "曉佳 HiuGaai · 女聲", note="偏活潑、口語"),
    Voice("zh-HK-WanLungNeural", "雲龍 WanLung · 男聲", note="低沉、適合紀錄片"),
]


class EdgeEngine(Engine):
    id = "edge-tts"
    name = "edge-tts"
    vendor = "Microsoft Edge（zh-HK）"
    kind = "online"
    category = "quality"
    description = "微軟 Edge 朗讀服務的粵語音色，免費、無需 GPU，但依賴網絡。"
    homepage = "https://github.com/rany2/edge-tts"
    supports_rate = True
    supports_pitch = True

    async def probe(self) -> Probe:
        try:
            voices = await asyncio.wait_for(edge_tts.list_voices(), timeout=8)
        except Exception as exc:  # network / token issues
            return Probe(False, f"無法連接微軟服務：{type(exc).__name__}", VOICES)
        names = {v["ShortName"] for v in voices}
        missing = [v.id for v in VOICES if v.id not in names]
        if missing:
            return Probe(False, "粵語音色不可用：" + ", ".join(missing), VOICES)
        return Probe(True, "微軟在線粵語音色，共 3 個", VOICES)

    async def synth(
        self, text: str, voice: str, rate: int = 0, pitch: int = 0, api_key: str = "", instruction: str = ""
    ) -> tuple[bytes, str, str]:
        voice = voice or VOICES[0].id
        rate_s = f"{rate:+d}%"
        pitch_s = f"{pitch:+d}Hz"
        chunks: list[bytes] = []
        try:
            comm = edge_tts.Communicate(text, voice, rate=rate_s, pitch=pitch_s)
            async for chunk in comm.stream():
                if chunk["type"] == "audio":
                    chunks.append(chunk["data"])
        except Exception as exc:
            raise TTSError(f"edge-tts 合成失敗：{exc}") from exc
        audio = b"".join(chunks)
        if not audio:
            raise TTSError("edge-tts 未返回音頻")
        return audio, "audio/mpeg", "mp3"
