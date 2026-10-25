"""canto-tts: CPU-first ONNX Cantonese TTS (Hong Kong), MOSS-TTS-Nano fine-tune.

The published ONNX bundle ships a single baked voice, but the runtime still
conditions generation on audio codes. We encode short reference clips with the
bundled audio tokenizer and swap the prompt codes per request, which turns the
single-voice model into a small multi-voice picker.
"""

from __future__ import annotations

import asyncio
import tempfile
import threading
import wave
from pathlib import Path

import numpy as np

from .base import Engine, Probe, TTSError, Voice
from .. import config

DEFAULT_VOICE = Voice("default", "預設音色", note="模型自帶")
# 參考音頻放進 assets/voices/*.wav（48 kHz 立體聲）即自動成為可選音色
PRESET_LABELS = {"female": "女聲", "male": "男聲"}

_MODEL = None
_ENC = None
_CODES: dict[str, list[list[int]]] = {}
_DEFAULT_CODES: list[list[int]] | None = None
_LOAD_LOCK = threading.Lock()
_GEN_LOCK = threading.Lock()


def model_dir() -> Path:
    raw = config.env("CANTONESE_CANTO_MODEL", str(config.CACHE_DIR / "canto-model"))
    return Path(raw)


def voice_dir() -> Path:
    return Path(config.env("CANTONESE_CANTO_VOICES", str(config.BASE_DIR / "assets" / "voices")))


def _ready(path: Path) -> bool:
    return (path / "MOSS-TTS-Nano-cantophon-ONNX").is_dir()


def _presets() -> list[Voice]:
    out = [DEFAULT_VOICE]
    folder = voice_dir()
    if folder.is_dir():
        for path in sorted(folder.glob("*.wav")):
            vid = path.stem
            out.append(
                Voice(vid, PRESET_LABELS.get(vid, vid), note=f"參考音頻：{path.name}")
            )
    return out


def _encoder():
    global _ENC
    if _ENC is None:
        import onnxruntime as ort

        path = model_dir() / "MOSS-Audio-Tokenizer-Nano-ONNX" / "moss_audio_tokenizer_encode.onnx"
        _ENC = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
    return _ENC


def _wav_to_waveform(path: Path) -> np.ndarray:
    with wave.open(str(path)) as w:
        if w.getnchannels() != 2 or w.getframerate() != 48000:
            raise TTSError("參考音頻需為 48 kHz 立體聲 WAV")
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    return (data.astype(np.float32) / 32768.0).reshape(-1, 2).T[None, ...]


def _encode(path: Path) -> list[list[int]]:
    waveform = _wav_to_waveform(path)
    codes, _ = _encoder().run(
        None,
        {
            "waveform": waveform,
            "input_lengths": np.array([waveform.shape[-1]], dtype=np.int32),
        },
    )
    return codes[0].tolist()


def _load_model():
    global _MODEL, _DEFAULT_CODES
    if _MODEL is not None:
        return _MODEL
    with _LOAD_LOCK:
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
        model = CantoTTS(checkpoint=str(path))
        _DEFAULT_CODES = model._backend._default_voice_codes
        _MODEL = model
        return _MODEL


def _codes_for(voice: str) -> list[list[int]]:
    path = voice_dir() / f"{voice}.wav"
    if voice == "default" or not path.exists():
        return _DEFAULT_CODES or []
    if voice not in _CODES:
        _CODES[voice] = _encode(path)
    return _CODES[voice]


class CantoEngine(Engine):
    id = "canto-tts"
    name = "canto-tts"
    vendor = "typangaa（香港粵語）"
    kind = "local"
    category = "quality"
    description = "專為港式粵語訓練的 0.1B ONNX 模型，純 CPU 可跑；另以參考音頻擴充女聲／男聲。"
    homepage = "https://github.com/typangaa/canto-tts"
    supports_rate = False
    supports_pitch = False

    async def probe(self) -> Probe:
        try:
            import canto_tts  # noqa: F401
        except ImportError:
            return Probe(False, "未安裝：pip install canto-tts", _presets())

        voices = _presets()
        path = model_dir()
        if _ready(path):
            return Probe(True, f"本地 ONNX，{len(voices)} 個音色（純 CPU）", voices)
        return Probe(True, "本地 ONNX，首次合成會下載約 730 MB 模型", voices)

    async def synth(
        self, text: str, voice: str, rate: int = 0, pitch: int = 0
    ) -> tuple[bytes, str, str]:
        def run() -> bytes:
            model = _load_model()
            codes = _codes_for(voice)
            with _GEN_LOCK:
                model._backend._default_voice_codes = codes
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
