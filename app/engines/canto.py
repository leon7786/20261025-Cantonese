"""canto-tts: CPU-first ONNX Cantonese TTS (Hong Kong), MOSS-TTS-Nano fine-tune."""

from __future__ import annotations

import asyncio
import tempfile
import threading
from pathlib import Path

from .base import Engine, Probe, TTSError, Voice
from .. import config

VOICES = [Voice("default", "canto-tts-nano · 單一音色", note="無條件生成，暫不支援克隆")]

_MODEL = None
_LOCK = threading.Lock()


def model_dir() -> Path:
    raw = config.env("CANTONESE_CANTO_MODEL", str(config.CACHE_DIR / "canto-model"))
    return Path(raw)


def _ready(path: Path) -> bool:
    return (path / "MOSS-TTS-Nano-cantophon-ONNX").is_dir()


def _load_model():
    global _MODEL
    if _MODEL is not None:
        return _MODEL
    with _LOCK:
        if _MODEL is not None:
            return _MODEL
        try:
            from canto_tts import CantoTTS
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise TTSError("未安裝 canto-tts（pip install canto-tts）") from exc

        path = model_dir()
        if not _ready(path):
            from huggingface_hub import snapshot_download

            path.mkdir(parents=True, exist_ok=True)
            snapshot_download("typangaa/canto-tts-nano", local_dir=str(path))
        _MODEL = CantoTTS(checkpoint=str(path))
        return _MODEL


class CantoEngine(Engine):
    id = "canto-tts"
    name = "canto-tts"
    vendor = "typangaa（香港粵語）"
    kind = "local"
    category = "quality"
    description = "專為港式粵語訓練的 0.1B ONNX 模型，純 CPU 可跑，粵拼前端、支援中英夾雜。"
    homepage = "https://github.com/typangaa/canto-tts"
    supports_rate = False
    supports_pitch = False

    async def probe(self) -> Probe:
        try:
            import canto_tts  # noqa: F401
        except ImportError:
            return Probe(False, "未安裝：pip install canto-tts", VOICES)

        path = model_dir()
        if _ready(path):
            return Probe(True, "本地 ONNX，模型已就緒（純 CPU）", VOICES)
        return Probe(True, "本地 ONNX，首次合成會下載約 730 MB 模型", VOICES)

    async def synth(
        self, text: str, voice: str, rate: int = 0, pitch: int = 0
    ) -> tuple[bytes, str, str]:
        def run() -> bytes:
            model = _load_model()
            with tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp) / "out.wav"
                model.synthesize(text, str(out))
                return out.read_bytes()

        try:
            audio = await asyncio.to_thread(run)
        except TTSError:
            raise
        except Exception as exc:
            raise TTSError(f"canto-tts 合成失敗：{exc}") from exc
        if len(audio) < 1000:
            raise TTSError("canto-tts 產生的音頻為空")
        return audio, "audio/wav", "wav"
