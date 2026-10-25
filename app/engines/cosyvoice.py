"""CosyVoice adapter (runtime/python/fastapi/server.py)."""

from __future__ import annotations

from . import _http
from .. import config
from .base import Engine, Probe, TTSError, Voice


class CosyVoiceEngine(Engine):
    id = "cosyvoice"
    name = "CosyVoice 3"
    vendor = "FunAudioLLM / 本機服務"
    kind = "remote"
    category = "selfhost"
    description = "阿里 24k★ 語音大模型，CosyVoice 3 覆蓋 18+ 中文方言（含粵語）；需自建 FastAPI 服務。"
    homepage = "https://github.com/FunAudioLLM/CosyVoice"
    supports_rate = False
    supports_pitch = False

    async def probe(self) -> Probe:
        fallback = [Voice(config.COSYVOICE_SPK or "中文女", "預設音色")]
        if not config.COSYVOICE_URL:
            return Probe(False, "未配置 CANTONESE_COSYVOICE_URL", fallback)
        ok, detail = await _http.reachable(config.COSYVOICE_URL)
        if not ok:
            return Probe(False, detail, fallback)
        voices = fallback
        try:
            resp = await _http.get_json(_http.norm_base(config.COSYVOICE_URL) + "/list_available_spks")
            spks = (resp.json() or {}).get("spks") or []
            if spks:
                voices = [Voice(str(s), str(s)) for s in spks]
        except Exception:
            pass
        return Probe(True, f"FastAPI 服務已連接（{detail}）", voices)

    async def synth(
        self, text: str, voice: str, rate: int = 0, pitch: int = 0, api_key: str = "", instruction: str = ""
    ) -> tuple[bytes, str, str]:
        if not config.COSYVOICE_URL:
            raise TTSError("CosyVoice 未配置")
        data = {"tts_text": text, "spk_id": voice or config.COSYVOICE_SPK}
        try:
            resp = await _http.post_form(
                _http.norm_base(config.COSYVOICE_URL) + "/inference_sft", data
            )
        except Exception as exc:
            raise TTSError(f"CosyVoice 請求失敗：{exc}") from exc
        if resp.status_code != 200:
            raise TTSError(f"CosyVoice 返回 {resp.status_code}：{resp.text[:200]}")
        if not resp.content:
            raise TTSError("CosyVoice 未返回音頻")
        return resp.content, "audio/wav", "wav"
