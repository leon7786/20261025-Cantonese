"""生成詩詞頁嘅粵語朗讀音頻。"""
from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("bl", ROOT / "scripts" / "build_lessons.py")
bl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bl)

DATA = ROOT / "data" / "poems.json"
OUT_JSON = ROOT / "web" / "poems.json"
OUT_AUDIO = ROOT / "web" / "poems" / "audio"
AUDIO_VER = "20261110d"


async def build(reuse: bool) -> None:
    env = bl.load_env()
    data = json.loads(DATA.read_text(encoding="utf-8"))
    OUT_AUDIO.mkdir(parents=True, exist_ok=True)
    out = {"sections": []}

    for sec in data["sections"]:
        poems = []
        for poem in sec["poems"]:
            title = re.sub(r"[（）()]", "，", poem["title"]).strip("，")
            text = f"{title}。{poem['author']}。{''.join(poem['lines'])}"
            path = OUT_AUDIO / f"{poem['id']}.wav"
            if reuse and path.exists():
                ms = int(__import__("wave").open(str(path), "rb").getnframes() / __import__("wave").open(str(path), "rb").getframerate() * 1000)
            else:
                print(f"[{poem['id']}] {poem['title']} …", flush=True)
                pcm, _ = await bl.synth(text, env)
                import numpy as np
                audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768
                bl.write_wav(path, audio)
                ms = int(len(audio) / bl.SR * 1000)
            poems.append({**poem, "audio": f"/poems/audio/{poem['id']}.wav?v={AUDIO_VER}",
                          "duration": round(ms / 1000, 2)})
        out["sections"].append({**{k: sec[k] for k in ("id", "title", "intro")}, "poems": poems})

    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("wrote", OUT_JSON)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--reuse", action="store_true")
    args = ap.parse_args()
    asyncio.run(build(args.reuse))
