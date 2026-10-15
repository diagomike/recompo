"""Google Translate's public web endpoints, batched with context and verified line by line.

Ported from lang_bridge ``app/translate/google_batch.py`` (same owner): every line is tagged ``[[id]]``,
tags are read back leniently, and a block counts only if every id returns exactly once; otherwise it
is halved and retried. No key is needed; it is a draft engine (the agent's own translation is preferred).
"""

from __future__ import annotations

import re
import time

import httpx

from ..envelope import RecompError

MAX_CHARS = 4500
_TAG = re.compile(r"^\s*\[+\s*(\d+)\s*\]+\s*")
ENDPOINTS = [
    ("https://clients5.google.com/translate_a/t", {"client": "dict-chrome-ex"}, "dict"),
    ("https://translate.googleapis.com/translate_a/single", {"client": "gtx", "dt": "t"}, "gtx"),
]
_INVISIBLE = dict.fromkeys(map(ord, "​‌‍⁠﻿"))


def _parse(data, kind: str) -> str:
    if kind == "dict":
        first = data[0]
        return first if isinstance(first, str) else first[0]
    return "".join(part[0] for part in data[0] if part and part[0])


def _strip(s: str) -> str:
    return " ".join(s.translate(_INVISIBLE).split())


def _clean(s: str) -> str:
    return " ".join(s.split())


def _read_tags(text: str) -> dict[int, str]:
    got: dict[int, str] = {}
    dup: set[int] = set()
    for line in text.splitlines():
        m = _TAG.match(line)
        if not m:
            continue
        k = int(m.group(1))
        if k in got or k in dup:
            dup.add(k)
            got.pop(k, None)
            continue
        got[k] = _strip(line[m.end():])
    return got


class Translator:
    def __init__(self, src: str, tgt: str, context: int = 2, pause_s: float = 0.8):
        self.src, self.tgt, self.context, self.pause_s = src, tgt, context, pause_s
        self.http = httpx.Client(headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        self.calls = 0

    def raw(self, text: str) -> str:
        last = None
        for attempt in range(4):
            for url, extra, kind in ENDPOINTS:
                try:
                    r = self.http.post(url, params={"sl": self.src, "tl": self.tgt, **extra}, data={"q": text})
                    self.calls += 1
                    if r.status_code == 200:
                        return _parse(r.json(), kind)
                    last = f"{kind} HTTP {r.status_code}"
                except (httpx.HTTPError, ValueError) as exc:
                    last = f"{kind} {type(exc).__name__}"
            time.sleep(self.pause_s * 2 ** (attempt + 1))
        raise RecompError("E_NETWORK", f"translation failed: {last}",
                          hint="Translate the lines yourself: `recomp lang translate <J> --to <lang> --template`.")

    def translate(self, units: list[dict]) -> dict[int, str]:
        out: dict[int, str] = {}
        i = 0
        while i < len(units):
            j, size = i, 0
            while j < len(units) and size + len(units[j]["text"]) + 10 < MAX_CHARS * 0.8:
                size += len(units[j]["text"]) + 10
                j += 1
            j = max(j, i + 1)
            self._block(units, i, j, out)
            i = j
        return out

    def _block(self, units, i, j, out) -> None:
        ctx = self.context
        while True:
            lo, hi = max(0, i - ctx), min(len(units), j + ctx)
            request = "\n".join(f"[[{u['id']}]] {_clean(u['text'])}" for u in units[lo:hi])
            if len(request) <= MAX_CHARS or (j - i == 1 and ctx == 0):
                break
            if j - i > 1:
                mid = (i + j) // 2
                self._block(units, i, mid, out)
                self._block(units, mid, j, out)
                return
            ctx -= 1
        want = {u["id"] for u in units[i:j]}
        got = _read_tags(self.raw(request))
        if self.pause_s:
            time.sleep(self.pause_s)
        if want <= got.keys():
            for k in want:
                out[k] = got[k]
            return
        if j - i > 1:
            mid = (i + j) // 2
            self._block(units, i, mid, out)
            self._block(units, mid, j, out)
            return
        out[units[i]["id"]] = _strip(self.raw(_clean(units[i]["text"])))
