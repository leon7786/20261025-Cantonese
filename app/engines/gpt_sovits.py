"""GPT-SoVITS adapter (api_v2.py, GET /tts)."""

from __future__ import annotations

from . import _http
from .. import config
from .base import Engine, Probe, TTSError, Voice


class GptSovitsEngine(Engine):
    id = "gpt-sovits"
    name = "GPT-SoVITS"
    vendor = "RVC-Boss / 本機服務"
    kind = "remote"
    description = "59k★ 少樣本克隆框架，原生支援 yue 粵語；需自行啟動 api_v2 服務。"
    homepage = "https://github.com/RVC-Boss/GPT-SoVITS"
    supports_rate = False
    supports_pitch = False

    async def probe(self) -> Probe:
        voices = [Voice("default", "參考音色（由 REF 指定）")]
        if not config.GPT_SOVITS_URL:
            return Probe(False, "未配置 CANTONESE_GPT_SOVITS_URL", voices)
        if not config.GPT_SOVITS_REF:
            return Probe(False, "缺少 CANTONESE_GPT_SOVITS_REF（參考音頻路徑）", voices)
        ok, detail = await _http.reachable(config.GPT_SOVITS_URL)
        if not ok:
            return Probe(False, detail, voices)
        return Probe(True, f"api_v2 已連接（{detail}）", voices)

    async def synth(
        self, text: str, voice: str, rate: int = 0, pitch: int = 0
    ) -> tuple[bytes, str, str]:
        if not config.GPT_SOVITS_URL or not config.GPT_SOVITS_REF:
            raise TTSError("GPT-SoVITS 未配置")
        params = {
            "text": text,
            "text_lang": "yue",
            "ref_audio_path": config.GPT_SOVITS_REF,
            "prompt_lang": "yue",
            "prompt_text": config.GPT_SOVITS_PROMPT,
            "text_split_method": "cut5",
            "media_type": "wav",
            "streaming_mode": "false",
        }
        try:
            resp = await _http.get_json(_http.norm_base(config.GPT_SOVITS_URL) + "/tts", params=params)
        except Exception as exc:
            raise TTSError(f"GPT-SoVITS 請求失敗：{exc}") from exc
        if resp.status_code != 200:
            raise TTSError(f"GPT-SoVITS 返回 {resp.status_code}：{resp.text[:200]}")
        if not resp.content:
            raise TTSError("GPT-SoVITS 未返回音頻")
        return resp.content, "audio/wav", "wav"
