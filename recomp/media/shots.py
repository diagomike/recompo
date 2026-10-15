"""Shot boundaries with ffmpeg's scene score, ported from recomposer_v2 ``analysis/engines/shots.py``.

Full resolution, every frame: measured there as both the fastest and the most accurate option
(downscaling costs more than it saves; sub-sampling frames turns camera motion into false cuts).
"""

from __future__ import annotations

import re
from pathlib import Path

from . import ff

_FRAME = re.compile(r"pts_time:([0-9.]+)")
_SCORE = re.compile(r"lavfi\.scene_score=([0-9.]+)")
MIN_SHOT_S = 0.35


def detect(path: Path, duration: float | None, threshold: float = 0.3, progress=None, cancelled=None) -> list[dict]:
    res = ff.run(["-i", str(path), "-an", "-sn", "-map", "0:v:0",
                  "-vf", f"select='gt(scene,{threshold})',metadata=print:file=-", "-f", "null", "-"],
                 duration=duration, progress=progress, cancelled=cancelled, capture_stdout=True)
    return merge_close(parse(res.stdout.decode("utf-8", "replace")), MIN_SHOT_S)


def parse(stdout: str) -> list[dict]:
    out: list[dict] = []
    pending = None
    for line in stdout.splitlines():
        f = _FRAME.search(line)
        if f:
            pending = float(f.group(1))
            continue
        s = _SCORE.search(line)
        if s and pending is not None:
            out.append({"t": round(pending, 3), "score": round(float(s.group(1)), 4)})
            pending = None
    return sorted(out, key=lambda c: c["t"])


def merge_close(cuts: list[dict], min_shot: float) -> list[dict]:
    if min_shot <= 0 or not cuts:
        return cuts
    kept = [cuts[0]]
    for c in cuts[1:]:
        if c["t"] - kept[-1]["t"] < min_shot:
            if c["score"] > kept[-1]["score"]:
                kept[-1] = c
        else:
            kept.append(c)
    return kept
