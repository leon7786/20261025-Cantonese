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

TONES = [
    {"n": 1, "char": "詩", "jy": "si1"},
    {"n": 2, "char": "史", "jy": "si2"},
    {"n": 3, "char": "試", "jy": "si3"},
    {"n": 4, "char": "時", "jy": "si4"},
    {"n": 5, "char": "市", "jy": "si5"},
    {"n": 6, "char": "事", "jy": "si6"},
    {"n": 7, "char": "色", "jy": "sik1"},
    {"n": 8, "char": "錫", "jy": "sik3"},
    {"n": 9, "char": "食", "jy": "sik6"},
]


TIP_AUDIO_IDS = {"digits", "chicken", "auntie", "beef", "crab", "rice",
                 "buy-sell", "patrol", "tea", "flowers",
                 "jan-set", "entering-boss"}  # 全部卡片的提示都做朗讀


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


def add_pause(audio: np.ndarray, pause_ms: int = 360) -> np.ndarray:
    """在「字」和後面的說明之間補一段靜音，避免連讀。"""
    frame = int(bl.SR * 0.01)
    n = len(audio) // frame
    rms = np.array([float(np.sqrt(np.mean(audio[i * frame:(i + 1) * frame] ** 2))) for i in range(n)])
    thresh = max(rms.max() * 0.05, 1e-4)
    start = None
    run = 0
    for i, v in enumerate(rms):
        if v < thresh and i * 10 > 200:
            if start is None:
                start = i
            run += 1
            if run >= 5:
                break
        else:
            start, run = None, 0
    if start is None:
        return audio
    cut = start * frame
    return np.concatenate([audio[:cut], np.zeros(int(bl.SR * pause_ms / 1000), dtype=np.float32), audio[cut:]])


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
                        tips_out.append({**tip, "audio": f"/tones/audio/{tname}", "dur": round(tip_ms / 1000, 2)})
                        continue

                    if tpath.exists():
                        # 舊檔 = 字音 + 320ms 靜音 + 說明，取出說明重用
                        old = read_wav(tpath)
                        zero = np.abs(old) < 1e-5
                        runs, st = [], None
                        for i, v in enumerate(zero):
                            if v and st is None:
                                st = i
                            elif not v and st is not None:
                                runs.append((st, i, i - st)); st = None
                        gap = next((r for r in runs if r[2] >= int(bl.SR * 0.25) and r[0] < bl.SR * 2.5), None)
                        note_a = old[gap[1]:].copy() if gap else None
                    else:
                        note_a = None

                    if note_a is None:
                        print(f"    tip note: {tip['note'][:16]}…", flush=True)
                        pcm, _ = await bl.synth(tip["note"], env)
                        note_a = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768

                    # 框框字單獨合成，避免切到隔籬字
                    word_text = tip.get("spoken", tip["word"])
                    print(f"    tip word: {word_text}", flush=True)
                    pcm_w, _ = await bl.synth(word_text, env)
                    word_a = np.frombuffer(pcm_w, dtype=np.int16).astype(np.float32) / 32768
                    nz = np.where(np.abs(word_a) > 0.004)[0]
                    if len(nz):
                        word_a = word_a[max(0, nz[0] - 240): min(len(word_a), nz[-1] + 480)]

                    gap_a = np.zeros(int(bl.SR * 0.32), dtype=np.float32)
                    tip_audio = np.concatenate([word_a, gap_a, note_a])
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

    tones = []
    for t in TONES:
        path = OUT_AUDIO / f"tone-{t['n']}.wav"
        if reuse and path.exists():
            ms = wav_ms(path)
        else:
            print(f"[tone] {t['char']} …", flush=True)
            pcm, _ = await bl.synth(t.get("spoken", t["char"]), env)
            a = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768
            bl.write_wav(path, a)
            ms = int(len(a) / bl.SR * 1000)
        tones.append({**t, "audio": f"/tones/audio/tone-{t['n']}.wav", "dur": round(ms / 1000, 2)})
    out["tones"] = tones

    mistakes = []
    for m in data.get("mistakes", []):
        path = OUT_AUDIO / f"mistake-{m['id']}.wav"
        if reuse and path.exists():
            ms = wav_ms(path)
        else:
            print(f"[mistake] {m['word']} …", flush=True)
            pcm, _ = await bl.synth(m.get("spoken", m["word"]), env)
            a = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768
            bl.write_wav(path, a)
            ms = int(len(a) / bl.SR * 1000)
        mistakes.append({**m, "audio": f"/tones/audio/mistake-{m['id']}.wav",
                         "dur": round(ms / 1000, 2)})
    out["mistakes"] = mistakes

    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("wrote", OUT_JSON)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--reuse", action="store_true", help="沿用已存在的整句 wav，不重新合成")
    args = ap.parse_args()
    asyncio.run(build(args.reuse))
