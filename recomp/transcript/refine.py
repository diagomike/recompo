"""Snap ASR word starts to real speech onsets.

Whisper's word timestamps run early (measured on the fixture: turbo puts "Why" at 1.71 s, the
energy onset is at 2.12 s). Cuts and karaoke captions need better, so every word that follows
a pause is moved to the first sustained energy rise near it, when the rise is clear.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from ..media.audio import read_wav

FRAME = 0.01


def _onset(wav: Path, t: float, before: float = 0.25, after: float = 0.7) -> float | None:
    a = max(0.0, t - before)
    data, sr = read_wav(wav, a, t + after)
    hop = int(sr * FRAME)
    if data.size < hop * 10:
        return None
    frames = data[: data.size // hop * hop].reshape(-1, hop)
    db = 20 * np.log10(np.sqrt((frames ** 2).mean(axis=1)) + 1e-9)
    floor = np.percentile(db, 15)
    peak = db.max()
    if peak - floor < 15:  # no clear rise (music bed, crowd): leave it
        return None
    thr = floor + 0.45 * (peak - floor)
    above = db > thr
    for i in range(len(above) - 3):
        if above[i] and above[i + 1] and above[i + 2]:
            return round(a + i * FRAME, 3)
    return None


def refine_segments(segments: list[dict], wav: Path, gap: float = 0.25) -> dict:
    moved = 0
    total = 0
    shifts = []
    prev_end = -10.0
    for seg in segments:
        words = seg.get("words") or []
        for k, w in enumerate(words):
            if w["start"] - prev_end >= gap:
                total += 1
                on = _onset(wav, w["start"])
                if on is not None and -0.2 <= on - w["start"] <= 0.6 and on < w["end"] - 0.03:
                    shifts.append(on - w["start"])
                    w["start"] = on
                    moved += 1
            prev_end = w["end"]
        if words:
            seg["start"] = min(seg["start"], words[0]["start"]) if words[0]["start"] < seg["start"] else words[0]["start"]
            seg["end"] = max(words[-1]["end"], seg["start"] + 0.05)
    return {"checked": total, "moved": moved,
            "median_shift": round(float(np.median(shifts)), 3) if shifts else 0.0}
