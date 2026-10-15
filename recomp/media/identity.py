"""File fingerprints and what a filename says about a work (title, year, release noise)."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

CHUNK = 4 * 1024 * 1024

_NOISE = re.compile(
    r"^(\d{3,4}p|x26[45]|h\.?26[45]|hevc|av1|aac\d?(\.\d)?|ac3|dts|ddp?\d?(\.\d)?|atmos|web-?(rip|dl)|blu-?ray|"
    r"brrip|bdrip|hdrip|dvdrip|hdtv|remux|proper|repack|extended|unrated|imax|10bit|8bit|hdr\d*|sdr|"
    r"yify|yts|rarbg|\d+ch|5\.1|7\.1|multi|subs?|eng?)$", re.I)
_YEAR = re.compile(r"^(19|20)\d{2}$")


def fingerprint(path: str | Path) -> str:
    """``pf1:<size>:<sha256 of first and last 4 MB>``: fast on films, stable across moves."""
    path = Path(path)
    size = path.stat().st_size
    h = hashlib.sha256()
    with path.open("rb") as f:
        h.update(f.read(CHUNK))
        if size > CHUNK:
            f.seek(max(CHUNK, size - CHUNK))
            h.update(f.read(CHUNK))
    return f"pf1:{size}:{h.hexdigest()[:32]}"


def title_from_filename(name: str) -> tuple[str, int | None]:
    """``The.Dark.Knight.2026.1080p.WEBRip.x264`` → ("The Dark Knight", 2026)."""
    stem = Path(name).stem
    stem = re.sub(r"\[[^\]]*\]|\([^)]*(rip|1080|720|yts|web)[^)]*\)", " ", stem, flags=re.I)
    tokens = [t for t in re.split(r"[.\s_]+", stem) if t]
    words: list[str] = []
    year = None
    for i, tok in enumerate(tokens):
        bare = tok.strip("()[]-")
        if _YEAR.match(bare) and i > 0:
            year = int(bare)
            break
        if _NOISE.match(bare):
            break
        words.append(tok)
    title = " ".join(words).strip(" -") or stem
    title = re.sub(r"\s+-\s*$", "", title)
    return title, year
