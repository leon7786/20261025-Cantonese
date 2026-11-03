"""生成「九聲六調」練習頁的音頻。

做法：整句（去標點）合成一次，做靜音裁剪後按字數平均切開，
每個字一段音頻；整句另存一份。Qwen 的 token 時間戳只覆蓋最後一句、
而且會把「狸」正規化成「黎」，所以唔用 token 對齊。
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import re
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


def speech_bounds(audio: np.ndarray) -> tuple[int, int]:
    """用 10ms RMS 找有聲區間（毫秒）。"""
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


async def build() -> None:
    env = bl.load_env()
    data = json.loads(DATA.read_text(encoding="utf-8"))
    OUT_AUDIO.mkdir(parents=True, exist_ok=True)
    out = {"sections": []}

    for sec in data["sections"]:
        items = []
        for item in sec["items"]:
            spoken = PUNCT.sub("", item["phrase"])
            chars = [c for c in spoken]
            assert len(chars) == len(item["chars"]), (item["id"], len(chars), len(item["chars"]))

            print(f"[{item['id']}] {spoken} …", flush=True)
            pcm, _words = await bl.synth(spoken, env)
            audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768
            total_ms = int(len(audio) / bl.SR * 1000)
            bl.write_wav(OUT_AUDIO / f"{item['id']}.wav", audio)

            start_ms, end_ms = speech_bounds(audio)
            step = (end_ms - start_ms) / len(chars)
            seg_chars = []
            for i, (ch, jy) in enumerate(item["chars"]):
                s = max(0, start_ms + i * step - 20)
                e = min(total_ms, start_ms + (i + 1) * step + 30)
                if e - s < 120:
                    e = min(total_ms, s + 120)
                chunk = audio[int(s * bl.SR / 1000):int(e * bl.SR / 1000)].copy()
                name = f"{item['id']}-{i}.wav"
                bl.write_wav(OUT_AUDIO / name, chunk)
                seg_chars.append({"c": ch, "jy": jy, "audio": f"/tones/audio/{name}",
                                  "dur": round(len(chunk) / bl.SR, 2)})
            items.append({**{k: item[k] for k in ("id", "title", "tag", "note", "phrase")},
                          "audio": f"/tones/audio/{item['id']}.wav",
                          "duration": round(total_ms / 1000, 2), "chars": seg_chars})
            print(f"    {len(seg_chars)} 字, {total_ms/1000:.1f}s", flush=True)
        out["sections"].append({**{k: sec[k] for k in ("id", "title", "subtitle")}, "items": items})

    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("wrote", OUT_JSON)


if __name__ == "__main__":
    asyncio.run(build())
