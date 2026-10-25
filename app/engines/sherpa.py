"""sherpa-onnx: offline Cantonese VITS model on CPU (official k2-fsa model zoo)."""

from __future__ import annotations

import asyncio
import io
import tarfile
import threading
import urllib.request
import wave
from pathlib import Path

import numpy as np

from .base import Engine, Probe, TTSError, Voice
from .. import config

MODEL_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/"
    "vits-cantonese-hf-xiaomaiiwn.tar.bz2"
)
SUBDIR = "vits-cantonese-hf-xiaomaiiwn"
VOICES = [Voice("xiaomaiiwn", "xiaomaiiwn · 女聲", note="單一 VITS 音色")]

_TTS = None
_LOCK = threading.Lock()


def root_dir() -> Path:
    return Path(config.env("CANTONESE_SHERPA_DIR", str(config.CACHE_DIR / "sherpa")))


def model_dir() -> Path:
    return root_dir() / SUBDIR


def _ready(path: Path) -> bool:
    return all(
        (path / name).exists()
        for name in ("vits-cantonese-hf-xiaomaiiwn.onnx", "lexicon.txt", "tokens.txt")
    )


def _download(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    archive = path.parent / "model.tar.bz2"
    urllib.request.urlretrieve(MODEL_URL, archive)
    with tarfile.open(archive, "r:bz2") as tar:
        tar.extractall(path.parent, filter="data")
    archive.unlink(missing_ok=True)


def _load():
    global _TTS
    if _TTS is not None:
        return _TTS
    with _LOCK:
        if _TTS is not None:
            return _TTS
        try:
            import sherpa_onnx
        except ImportError as exc:  # pragma: no cover
            raise TTSError("未安裝 sherpa-onnx（pip install sherpa-onnx）") from exc

        path = model_dir()
        if not _ready(path):
            _download(path)
        cfg = sherpa_onnx.OfflineTtsConfig(
            model=sherpa_onnx.OfflineTtsModelConfig(
                vits=sherpa_onnx.OfflineTtsVitsModelConfig(
                    model=str(path / "vits-cantonese-hf-xiaomaiiwn.onnx"),
                    lexicon=str(path / "lexicon.txt"),
                    tokens=str(path / "tokens.txt"),
                ),
                num_threads=2,
                provider="cpu",
            ),
            rule_fsts=str(path / "rule.fst"),
            max_num_sentences=2,
        )
        _TTS = sherpa_onnx.OfflineTts(cfg)
        return _TTS


def _to_wav(samples, sample_rate: int) -> bytes:
    pcm = (np.clip(np.asarray(samples, dtype=np.float32), -1, 1) * 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm.tobytes())
    return buf.getvalue()


class SherpaEngine(Engine):
    id = "sherpa-onnx"
    name = "sherpa-onnx"
    vendor = "k2-fsa · VITS"
    kind = "local"
    category = "baseline"
    description = "官方粵語 VITS 模型，ONNX Runtime 純 CPU，離線、體積細、速度最快。"
    homepage = "https://github.com/k2-fsa/sherpa-onnx"
    supports_rate = True
    supports_pitch = False

    async def probe(self) -> Probe:
        try:
            import sherpa_onnx  # noqa: F401
        except ImportError:
            return Probe(False, "未安裝：pip install sherpa-onnx", VOICES)

        if _ready(model_dir()):
            return Probe(True, "本地 VITS，模型已就緒（純 CPU）", VOICES)
        return Probe(True, "本地 VITS，首次合成會下載約 108 MB 模型", VOICES)

    async def synth(
        self, text: str, voice: str, rate: int = 0, pitch: int = 0, api_key: str = ""
    ) -> tuple[bytes, str, str]:
        speed = max(0.5, min(2.0, 1 + rate / 100))

        def run() -> bytes:
            tts = _load()
            audio = tts.generate(text, sid=0, speed=speed)
            return _to_wav(audio.samples, audio.sample_rate)

        try:
            data = await asyncio.to_thread(run)
        except TTSError:
            raise
        except Exception as exc:
            raise TTSError(f"sherpa-onnx 合成失敗：{exc}") from exc
        if len(data) < 1000:
            raise TTSError("sherpa-onnx 產生的音頻為空")
        return data, "audio/wav", "wav"
