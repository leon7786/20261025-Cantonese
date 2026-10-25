"""Small async HTTP helpers shared by the remote-model adapters."""

from __future__ import annotations

import httpx


def norm_base(url: str) -> str:
    return url.rstrip("/")


async def reachable(base: str, timeout: float = 3.0) -> tuple[bool, str]:
    """Best-effort reachability probe; any HTTP answer (even 404) counts."""
    if not base:
        return False, "未配置"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(norm_base(base) + "/")
        return True, f"HTTP {resp.status_code}"
    except Exception as exc:
        return False, f"無法連接：{type(exc).__name__}"


async def post_json(url: str, payload: dict, timeout: float = 120.0) -> httpx.Response:
    async with httpx.AsyncClient(timeout=timeout) as client:
        return await client.post(url, json=payload)


async def post_form(url: str, data: dict, timeout: float = 120.0) -> httpx.Response:
    async with httpx.AsyncClient(timeout=timeout) as client:
        return await client.post(url, data=data)


async def get_json(url: str, params: dict | None = None, timeout: float = 5.0):
    async with httpx.AsyncClient(timeout=timeout) as client:
        return await client.get(url, params=params)
