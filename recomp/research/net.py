"""Plain HTTP for feeds, search APIs and transcript pages: a browser user agent, timeouts, clear errors."""

from __future__ import annotations

import json
from typing import Any

import httpx

from ..envelope import RecompError

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"


def get_text(url: str, timeout: float = 30, max_bytes: int | None = None) -> str:
    """The body of ``url`` as text. ``max_bytes`` stops early (enough of a large feed to see what it offers)."""
    try:
        with httpx.Client(follow_redirects=True, timeout=timeout, headers={"User-Agent": UA}) as client:
            with client.stream("GET", url) as r:
                if r.status_code == 429:
                    raise RecompError("E_EXTERNAL", f"{_host(url)} is rate-limiting this machine (HTTP 429)",
                                      hint="Wait a few minutes and try again.")
                if r.status_code >= 400:
                    raise RecompError("E_EXTERNAL" if r.status_code >= 500 else "E_NOT_FOUND",
                                      f"{_host(url)} answered HTTP {r.status_code} for {url[:160]}")
                chunks, size = [], 0
                for chunk in r.iter_bytes():
                    chunks.append(chunk)
                    size += len(chunk)
                    if max_bytes and size >= max_bytes:
                        break
                raw = b"".join(chunks)
                return raw.decode(r.encoding or "utf-8", errors="replace")
    except httpx.HTTPError as exc:
        raise RecompError("E_NETWORK", f"{_host(url)} unreachable: {exc}",
                          hint="Check the connection; feeds and search work without any key.") from exc


def get_json(url: str, timeout: float = 30) -> Any:
    text = get_text(url, timeout=timeout)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise RecompError("E_EXTERNAL", f"{_host(url)} did not answer with JSON") from exc


def _host(url: str) -> str:
    return url.split("://", 1)[-1].split("/", 1)[0]
