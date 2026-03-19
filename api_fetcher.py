"""api_fetcher.py —— 统一 HTTP 请求 & 响应解析"""
from __future__ import annotations

import json
from typing import Any

import aiohttp

TIMEOUT = aiohttp.ClientTimeout(total=20)
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}


async def fetch(
    url: str,
    method: str = "GET",
    params: dict | None = None,
    data: dict | None = None,
    headers: dict | None = None,
) -> tuple[str, Any]:
    """
    发起请求，返回 (raw_type, content)
      raw_type: "image" | "json" | "text" | "video"
      content : bytes(image/video) | dict/list(json) | str(text)
    """
    merged = {**DEFAULT_HEADERS, **(headers or {})}
    async with aiohttp.ClientSession(headers=merged, timeout=TIMEOUT) as session:
        req_kwargs: dict = {"params": params}
        if method.upper() == "POST":
            req_kwargs["json"] = data
        async with session.request(method, url, **req_kwargs) as resp:
            resp.raise_for_status()
            ct = (resp.content_type or "").lower()

            if any(t in ct for t in ("image/", "jpeg", "png", "gif", "webp")):
                return "image", await resp.read()

            if any(t in ct for t in ("video/", "mp4", "webm")):
                return "video", await resp.read()

            text = await resp.text(errors="replace")

            # 尝试 JSON 解析（有些接口 content-type 是 text/html 但返回 JSON）
            try:
                return "json", json.loads(text)
            except Exception:
                return "text", text


def resolve_path(data: Any, path: str | None) -> Any:
    """按 'a.b.c' 路径从嵌套结构取值"""
    if path is None:
        return data
    for key in path.split("."):
        if isinstance(data, dict):
            data = data.get(key)
        elif isinstance(data, list):
            try:
                data = data[int(key)]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return data
