#!/usr/bin/env python3
"""Smoke test against a running server: python scripts/smoke_test.py [base_url]"""

from __future__ import annotations

import sys

import httpx

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")
TEXT = "你好，我係阿明，今日天氣好好，不如一齊去飲茶？"


def main() -> int:
    with httpx.Client(timeout=120) as client:
        health = client.get(f"{BASE}/api/health")
        health.raise_for_status()
        print("health:", health.json())

        engines = client.get(f"{BASE}/api/engines").json()
        for e in engines:
            print(f"  {e['id']:<14} available={e['available']!s:<5} {e['detail']}")

        usable = [e["id"] for e in engines if e["available"]]
        if not usable:
            print("FAIL: 沒有可用引擎")
            return 1

        failed = 0
        for engine_id in usable:
            resp = client.post(f"{BASE}/api/tts", json={"engine": engine_id, "text": TEXT})
            if resp.status_code != 200:
                print(f"FAIL {engine_id}: HTTP {resp.status_code} {resp.text[:160]}")
                failed += 1
                continue
            data = resp.json()
            audio = client.get(f"{BASE}{data['url']}")
            ok = audio.status_code == 200 and len(audio.content) > 1000
            print(f"  {engine_id:<14} {len(audio.content):>7} bytes  {data['ms']:>5} ms  {'OK' if ok else 'FAIL'}")
            failed += 0 if ok else 1

        print("PASS" if failed == 0 else f"FAIL ({failed})")
        return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
