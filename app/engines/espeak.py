"""eSpeak NG: offline formant synthesiser with a built-in Cantonese (yue) voice."""

from __future__ import annotations

import asyncio
import shutil
import tempfile
from pathlib import Path

from .base import Engine, Probe, TTSError, Voice

VOICES = [
    Voice("yue", "粵語（漢字）", note="直接讀中文，音質機械但可離線"),
    Voice("yue-Latn-jyutping", "粵語（粵拼輸入）", note="用 jyutping 拼寫控制發音"),
]


class EspeakEngine(Engine):
    id = "espeak-ng"
    name = "eSpeak NG"
    vendor = "eSpeak NG"
    kind = "local"
    category = "baseline"
    description = "純離線共振峰合成，體積僅幾 MB，音質明顯機械，適合做對照基線。"
    homepage = "https://github.com/espeak-ng/espeak-ng"
    supports_rate = True
    supports_pitch = True

    async def probe(self) -> Probe:
        binary = shutil.which("espeak-ng")
        if not binary:
            return Probe(False, "未安裝 espeak-ng（apt install espeak-ng）", VOICES)
        try:
            proc = await asyncio.create_subprocess_exec(
                binary, "--voices=yue",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            out, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
        except Exception as exc:
            return Probe(False, f"調用失敗：{exc}", VOICES)
        if b"yue" not in out:
            return Probe(False, "當前 eSpeak NG 不包含粵語語音", VOICES)
        return Probe(True, f"本地合成，{binary}", VOICES)

    async def synth(
        self, text: str, voice: str, rate: int = 0, pitch: int = 0, api_key: str = ""
    ) -> tuple[bytes, str, str]:
        binary = shutil.which("espeak-ng")
        if not binary:
            raise TTSError("未安裝 espeak-ng")
        voice = voice if voice in {v.id for v in VOICES} else "yue"
        wpm = max(80, min(320, round(170 * (1 + rate / 100))))
        pitch_val = max(0, min(99, 50 + pitch))
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.wav"
            proc = await asyncio.create_subprocess_exec(
                binary, "-v", voice, "-s", str(wpm), "-p", str(pitch_val),
                "-w", str(out), "--stdin",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            _, err = await asyncio.wait_for(proc.communicate(text.encode("utf-8")), timeout=60)
            if proc.returncode != 0 or not out.exists():
                raise TTSError(f"espeak-ng 失敗：{err.decode('utf-8', 'ignore')[:200]}")
            audio = out.read_bytes()
        if len(audio) < 1000:
            raise TTSError("espeak-ng 產生的音頻為空")
        return audio, "audio/wav", "wav"
