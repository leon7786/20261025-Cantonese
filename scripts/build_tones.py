"""生成「九聲六調」練習頁的資料與整句音頻。

每個練習項合成一句（去標點），存成一個 wav；頁面點一下整句播放。
易讀錯的字寫在 data/tones.json 的 tips，只作提示，不再逐字切音頻。
"""
from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import re
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("bl", ROOT / "scripts" / "build_lessons.py")
bl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bl)

DATA = ROOT / "data" / "tones.json"
OUT_JSON = ROOT / "web" / "tones.json"
OUT_AUDIO = ROOT / "web" / "tones" / "audio"
PUNCT = re.compile(r"[，。！？；：、,.!?;:]")


TIP_AUDIO_IDS = {"digits", "chicken", "auntie", "beef", "crab", "rice",
                 "buy-sell", "patrol", "tea", "flowers"}  # 全部卡片的提示都做朗讀


def read_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as w:
        frames = w.readframes(w.getnframes())
    return np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768


def speech_bounds(audio: np.ndarray) -> tuple[int, int]:
    frame = int(bl.SR * 0.01)
    n = len(audio) // frame
    rms = np.array([float(np.sqrt(np.mean(audio[i * frame:(i + 1) * frame] ** 2))) for i in range(n)])
    thresh = max(rms.max() * 0.06, 1e-4)
    idx = np.where(rms > thresh)[0]
    if not len(idx):
        return 0, int(len(audio) / bl.SR * 1000)
    start = max(0, int(idx[0] * frame / bl.SR * 1000) - 60)
    end = min(int(len(audio) / bl.SR * 1000), int((idx[-1] + 1) * frame / bl.SR * 1000) + 80)
    return start, end


def wav_ms(path: Path) -> int:
    with wave.open(str(path), "rb") as w:
        return int(w.getnframes() / w.getframerate() * 1000)


async def build(reuse: bool) -> None:
    env = bl.load_env()
    data = json.loads(DATA.read_text(encoding="utf-8"))
    OUT_AUDIO.mkdir(parents=True, exist_ok=True)
    out = {"sections": []}

    for sec in data["sections"]:
        items = []
        for item in sec["items"]:
            spoken = PUNCT.sub("", item["phrase"])
            assert len(spoken) == len(item["chars"]), (item["id"], len(spoken), len(item["chars"]))
            wav_path = OUT_AUDIO / f"{item['id']}.wav"

            if reuse and wav_path.exists():
                total_ms = wav_ms(wav_path)
                print(f"[{item['id']}] 沿用 {total_ms/1000:.1f}s", flush=True)
            else:
                print(f"[{item['id']}] {spoken} …", flush=True)
                pcm, _words = await bl.synth(spoken, env)
                audio = __import__("numpy").frombuffer(pcm, dtype=__import__("numpy").int16).astype(__import__("numpy").float32) / 32768
                total_ms = int(len(audio) / bl.SR * 1000)
                bl.write_wav(wav_path, audio)
                print(f"    {total_ms/1000:.1f}s", flush=True)

            tips_out = []
            for ti, tip in enumerate(item.get("tips", [])):
                tip = dict(tip)
                if item["id"] in TIP_AUDIO_IDS:
                    tname = f"{item['id']}-tip{ti}.wav"
                    tpath = OUT_AUDIO / tname
                    if reuse and tpath.exists():
                        tip_ms = wav_ms(tpath)
                    else:
                        spoken_tip = f"{tip['word']}，{tip['note']}".replace("—", "，").replace("「", "").replace("」", "")
                        print(f"    tip: {spoken_tip[:18]}…", flush=True)
                        pcm, _ = await bl.synth(spoken_tip, env)
                        tip_audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768
                        bl.write_wav(tpath, tip_audio)
                        tip_ms = int(len(tip_audio) / bl.SR * 1000)
                    tip.update({"audio": f"/tones/audio/{tname}", "dur": round(tip_ms / 1000, 2)})
                tips_out.append(tip)

            items.append({
                **{k: item[k] for k in ("id", "title", "tag", "note", "phrase")},
                "tips": tips_out,
                "audio": f"/tones/audio/{item['id']}.wav",
                "duration": round(total_ms / 1000, 2),
                "chars": [{"c": c, "jy": j} for (c, j) in item["chars"]],
            })
        out["sections"].append({**{k: sec[k] for k in ("id", "title", "subtitle")}, "items": items})

    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("wrote", OUT_JSON)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--reuse", action="store_true", help="沿用已存在的整句 wav，不重新合成")
    args = ap.parse_args()
    asyncio.run(build(args.reuse))
