"""Engine registry with a short-lived probe cache."""

from __future__ import annotations

import asyncio
import time

from .base import Engine, Probe, TTSError
from .canto import CantoEngine
from .cosyvoice import CosyVoiceEngine
from .edge import EdgeEngine
from .ekho import EkhoEngine
from .espeak import EspeakEngine
from .gpt_sovits import GptSovitsEngine
from .openai_compat import OpenAICompatEngine
from .sherpa import SherpaEngine

ENGINES: dict[str, Engine] = {
    e.id: e
    for e in (
        EdgeEngine(),
        CantoEngine(),
        SherpaEngine(),
        EspeakEngine(),
        EkhoEngine(),
        GptSovitsEngine(),
        CosyVoiceEngine(),
        OpenAICompatEngine(),
    )
}

_CACHE: dict[str, tuple[float, Probe]] = {}
_TTL = 60.0
_LOCK = asyncio.Lock()


async def probe_all(force: bool = False) -> dict[str, Probe]:
    now = time.monotonic()
    async with _LOCK:
        pending = [
            eid for eid, e in ENGINES.items()
            if force or eid not in _CACHE or now - _CACHE[eid][0] > _TTL
        ]
        if pending:
            results = await asyncio.gather(
                *(asyncio.wait_for(ENGINES[eid].probe(), timeout=15) for eid in pending),
                return_exceptions=True,
            )
            for eid, result in zip(pending, results):
                if isinstance(result, BaseException):
                    _CACHE[eid] = (now, Probe(False, f"探測失敗：{type(result).__name__}"))
                else:
                    _CACHE[eid] = (now, result)
        return {eid: _CACHE[eid][1] for eid in ENGINES}


async def get_engine(engine_id: str) -> tuple[Engine, Probe]:
    await probe_all()
    engine = ENGINES.get(engine_id)
    if engine is None:
        raise TTSError(f"未知引擎：{engine_id}")
    return engine, _CACHE[engine_id][1]
