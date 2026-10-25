"""edge-tts: free client for Microsoft Edge's online TTS (zh-HK Cantonese voices)."""

from __future__ import annotations

import asyncio

import edge_tts

from .base import Engine, Probe, TTSError, Voice

VOICES = [
    # 粵語（zh-HK）—— 同一批神經語音，edge 與 Azure 共用
    Voice("zh-HK-HiuMaanNeural", "曉曼 HiuMaan · 粵語女聲", note="新聞/旁白感，最常用"),
    Voice("zh-HK-HiuGaaiNeural", "曉佳 HiuGaai · 粵語女聲", note="偏活潑、口語"),
    Voice("zh-HK-WanLungNeural", "雲龍 WanLung · 粵語男聲", note="低沉、適合紀錄片"),
    # 台灣（zh-TW）—— 國語，非粵語，作對照
    Voice("zh-TW-HsiaoChenNeural", "曉臻 HsiaoChen · 台灣女聲", note="國語，非粵語"),
    Voice("zh-TW-HsiaoYuNeural", "曉雨 HsiaoYu · 台灣女聲", note="國語，非粵語"),
    Voice("zh-TW-YunJheNeural", "雲哲 YunJhe · 台灣男聲", note="國語，非粵語"),
    # 普通話（zh-CN）
    Voice("zh-CN-XiaoxiaoNeural", "曉曉 Xiaoxiao · 普通話女聲", note="最常用普通話音色"),
    Voice("zh-CN-XiaoyiNeural", "曉伊 Xiaoyi · 普通話女聲", note="年輕、活潑"),
    Voice("zh-CN-YunjianNeural", "雲健 Yunjian · 普通話男聲", note="紀錄片/解說"),
    Voice("zh-CN-YunxiNeural", "雲希 Yunxi · 普通話男聲", note="年輕、柔和"),
    Voice("zh-CN-YunxiaNeural", "雲夏 Yunxia · 普通話男聲", note="少年感"),
    Voice("zh-CN-YunyangNeural", "雲揚 Yunyang · 普通話男聲", note="新聞播報"),
    # 方言（zh-CN 變體）
    Voice("zh-CN-liaoning-XiaobeiNeural", "曉北 Xiaobei · 東北話女聲", note="方言對照"),
    Voice("zh-CN-shaanxi-XiaoniNeural", "曉妮 Xiaoni · 陝西話女聲", note="方言對照"),
]


class EdgeEngine(Engine):
    id = "edge-tts"
    name = "edge-tts"
    vendor = "Microsoft Edge（zh-HK）"
    kind = "online"
    category = "quality"
    description = "微軟 Edge 的粵語音色（另含台灣／普通話／方言音色作對照），免費、無需 GPU，依賴網絡。"
    homepage = "https://github.com/rany2/edge-tts"
    supports_rate = True
    supports_pitch = True

    async def probe(self) -> Probe:
        try:
            voices = await asyncio.wait_for(edge_tts.list_voices(), timeout=8)
        except Exception as exc:  # network / token issues
            return Probe(False, f"無法連接微軟服務：{type(exc).__name__}", VOICES)
        names = {v["ShortName"] for v in voices}
        missing = [v.id for v in VOICES if v.id.startswith("zh-HK") and v.id not in names]
        if missing:
            return Probe(False, "粵語音色不可用：" + ", ".join(missing), VOICES)
        return Probe(True, f"微軟在線音色 {len(VOICES)} 個（粵語 3）", VOICES)

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
