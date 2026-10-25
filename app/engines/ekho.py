"""Ekho (余音): classic offline Cantonese TTS engine driven by a Jyutping lexicon."""

from __future__ import annotations

import asyncio
import shutil
import subprocess
import tempfile
from pathlib import Path

from .base import Engine, Probe, TTSError, Voice
from .. import config

VOICES = [Voice("Cantonese", "粵語 · Cantonese", note="粵拼詞典驅動，音質較舊")]


def binary() -> str | None:
    return shutil.which(config.env("CANTONESE_EKHO_BIN", "ekho"))


class EkhoEngine(Engine):
    id = "ekho"
    name = "Ekho"
    vendor = "eGuideDog（余音）"
    kind = "local"
    category = "baseline"
    description = "老牌粵語引擎，粵拼詞典 + 共振峰合成，體積細、完全離線，音質偏舊、固定語速。"
    homepage = "https://github.com/hgneng/ekho"
    supports_rate = False
    supports_pitch = False

    async def probe(self) -> Probe:
        exe = binary()
        if not exe:
            return Probe(False, "未安裝 ekho（可執行 scripts/install-ekho.sh）", VOICES)

        def smoke() -> str | None:
            with tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp) / "probe.wav"
                proc = subprocess.run(
                    [exe, "-v", "Cantonese", "-o", str(out), "--", "你好"],
                    capture_output=True,
                    timeout=15,
                )
                if proc.returncode != 0 or not out.exists():
                    return (proc.stderr or b"").decode("utf-8", "ignore")[:120]
            return None

        try:
            err = await asyncio.to_thread(smoke)
        except Exception as exc:
            return Probe(False, f"調用失敗：{type(exc).__name__}", VOICES)
        if err is not None:
            return Probe(False, f"粵語語音不可用：{err}", VOICES)
        return Probe(True, f"本地合成，{exe}", VOICES)

    async def synth(
        self, text: str, voice: str, rate: int = 0, pitch: int = 0, api_key: str = ""
    ) -> tuple[bytes, str, str]:
        exe = binary()
        if not exe:
            raise TTSError("未安裝 ekho")
        def run() -> bytes:
            with tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp) / "out.wav"
                proc = subprocess.run(
                    [
                        exe, "-v", "Cantonese", "-o", str(out), "--", text,
                    ],
                    capture_output=True,
                    timeout=120,
                )
                if proc.returncode != 0 or not out.exists():
                    err = (proc.stderr or b"").decode("utf-8", "ignore")[:200]
                    raise TTSError(f"ekho 合成失敗：{err}")
                return out.read_bytes()

        data = await asyncio.to_thread(run)
        if len(data) < 1000:
            raise TTSError("ekho 產生的音頻為空")
        return data, "audio/wav", "wav"
