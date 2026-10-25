"""Cantonese TTS comparison playground — FastAPI backend."""

from __future__ import annotations

import asyncio
import time

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import cache, config
from .engines import ENGINES, get_engine, probe_all
from .engines.base import TTSError

app = FastAPI(title="Cantonese TTS Playground", version="0.1.0")
WEB_DIR = config.BASE_DIR / "web"


class TTSRequest(BaseModel):
    engine: str = Field(min_length=1, max_length=64)
    text: str = Field(min_length=1, max_length=config.MAX_TEXT_LEN)
    voice: str = Field(default="", max_length=128)
    rate: int = Field(default=0, ge=-50, le=50)
    pitch: int = Field(default=0, ge=-50, le=50)


@app.get("/api/health")
async def health() -> dict:
    return {"ok": True, "engines": len(ENGINES), "cache_dir": str(config.CACHE_DIR)}


@app.get("/api/engines")
async def engines(refresh: bool = Query(default=False)) -> list[dict]:
    probes = await probe_all(force=refresh)
    return [e.meta(probes[eid]) for eid, e in ENGINES.items()]


@app.post("/api/tts")
async def tts(req: TTSRequest) -> JSONResponse:
    text = req.text.strip()
    if not text:
        raise HTTPException(400, "文字為空")

    engine, probe = await get_engine(req.engine)
    if not probe.available:
        raise HTTPException(503, f"{engine.name} 不可用：{probe.detail}")

    voice = req.voice or (probe.voices[0].id if probe.voices else "")
    key = cache.key_for(engine.id, voice, req.rate, req.pitch, text)
    started = time.perf_counter()

    cached = cache.read(key, "mp3") or cache.read(key, "wav")
    if cached:
        ext = "mp3" if cache.path_for(key, "mp3").exists() else "wav"
        mime = "audio/mpeg" if ext == "mp3" else "audio/wav"
        return JSONResponse(_payload(engine.id, voice, key, ext, len(cached), started, mime, True))

    try:
        audio, mime, ext = await asyncio.wait_for(
            engine.synth(text, voice, req.rate, req.pitch), timeout=config.SYNTH_TIMEOUT
        )
    except asyncio.TimeoutError:
        raise HTTPException(504, f"{engine.name} 合成超時（>{config.SYNTH_TIMEOUT:.0f}s）")
    except TTSError as exc:
        raise HTTPException(502, str(exc))
    except Exception as exc:  # unexpected engine failure
        raise HTTPException(500, f"{engine.name} 內部錯誤：{type(exc).__name__}: {exc}")

    cache.write(key, ext, audio)
    return JSONResponse(_payload(engine.id, voice, key, ext, len(audio), started, mime, False))


def _payload(engine_id: str, voice: str, key: str, ext: str, size: int,
             started: float, mime: str, cached: bool) -> dict:
    return {
        "engine": engine_id,
        "voice": voice,
        "url": f"/audio/{key}.{ext}",
        "mime": mime,
        "bytes": size,
        "ms": round((time.perf_counter() - started) * 1000),
        "cached": cached,
    }


@app.get("/audio/{name}")
async def audio(name: str) -> FileResponse:
    if not cache.safe_name(name):
        raise HTTPException(404, "not found")
    path = config.CACHE_DIR / name
    if not path.exists():
        raise HTTPException(404, "not found")
    mime = "audio/mpeg" if name.endswith(".mp3") else "audio/wav"
    return FileResponse(path, media_type=mime, headers={"Cache-Control": "public, max-age=86400"})


app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
