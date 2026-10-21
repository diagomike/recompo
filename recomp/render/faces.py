"""Face-centred vertical crops (the `crop-face` reframe): find the main person in each shot and crop around them.

Detection runs YuNet (a 230 KB ONNX face detector, MIT, from the OpenCV model zoo) under the worker python over a
slot's range, a few frames a second (workers/scripts/faces.py); results are cached per file and range. Then, per
shot, the main face (big, confident, near the middle and near where it was a moment ago, so a two-shot does not
flip between people) gives one steady crop; a person who moves a lot within a long shot is followed with slow
pans. A slot with no face falls back to the blurred fill.
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from pathlib import Path

from ..core import config
from ..envelope import RecompError

MODEL_NAME = "face_detection_yunet_2023mar.onnx"
MODEL_URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/" + MODEL_NAME
MODEL_SHA256 = "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"
FPS = 4.0
STEADY = 0.2      # a shot whose face moves less than this share of the crop width keeps one crop
WINDOW_S = 2.0    # otherwise the crop follows the face in windows this long, panning between them


def model_path() -> Path:
    p = config.home() / "models" / "yunet" / MODEL_NAME
    if not p.exists():
        raise RecompError("E_NOT_FOUND", "the face detector model is not installed",
                          hint=f"Download {MODEL_URL} to {p} (230 KB, MIT; sha256 {MODEL_SHA256[:12]}…).")
    return p


def detect(project, path: str, start: float, dur: float, width: int, height: int, log=None) -> list[dict]:
    """[{t, faces: [[x, y, w, h, score], …]}] for start…start+dur of this file (t from start), cached."""
    key = hashlib.sha256(json.dumps([str(path), Path(path).stat().st_size, round(start, 3), round(dur, 3), FPS]).encode()).hexdigest()[:20]
    out = project.dir("cache", "faces") / f"{key}.json"
    if not out.exists():
        from ..media import ff
        from ..workers.worker_env import run_script
        if log:
            log(f"faces: {Path(path).name} {start:.1f}+{dur:.1f}s")
        run_script("faces", ["--model", str(model_path()), "--input", str(path), "--start", f"{start:.3f}",
                             "--dur", f"{dur:.3f}", "--fps", str(FPS), "--ffmpeg", ff.ffmpeg_bin(),
                             "--width", str(width), "--height", str(height), "--out", str(out)])
    return json.loads(out.read_text(encoding="utf-8"))["samples"]


def main_faces(samples: list[dict], width: int) -> list[tuple[float, float | None]]:
    """(t, centre x of the main face or None) per sample."""
    out, prev = [], None
    for s in samples:
        best, best_v = None, 0.0
        for x, y, w, h, score in s["faces"]:
            cx = x + w / 2
            v = w * h * score * (1.0 - 0.4 * abs(cx - width / 2) / (width / 2))      # big, sure, central
            if prev is not None:
                v *= math.exp(-abs(cx - prev) / (0.25 * width))                       # and where it just was
            if v > best_v:
                best, best_v = cx, v
        out.append((s["t"], best))
        if best is not None:
            prev = best
    return out


def keyframes(samples: list[dict], cuts: list[float], dur: float, src_w: int, src_h: int, out_w: int, out_h: int
              ) -> list[tuple[float, float]] | None:
    """Crop x (in the scaled picture's pixels) at times in the slot: [(t, x), …], steady per shot and jumping at
    shot cuts; None when no face was found anywhere (or the picture is no wider than the frame)."""
    scale = out_h / src_h
    sw = src_w * scale
    if sw <= out_w + 2:
        return None
    crop_src = out_w / scale                                    # crop width in source pixels
    to_x = lambda cx: round(min(max(cx * scale - out_w / 2, 0.0), sw - out_w), 1)  # noqa: E731
    faces = main_faces(samples, src_w)
    bounds = [0.0] + sorted(c for c in cuts if 0.0 < c < dur) + [dur]
    shots: list[list[tuple[float, float]] | None] = []
    for a, b in zip(bounds, bounds[1:]):
        pts = [(t, cx) for t, cx in faces if a <= t < b and cx is not None]
        if not pts:
            shots.append(None)
            continue
        xs = [cx for _, cx in pts]
        if max(xs) - min(xs) <= STEADY * crop_src:
            shots.append([(a, to_x(statistics.median(xs)))])
            continue
        keys, w0 = [], a
        while w0 < b:
            win = [cx for t, cx in pts if w0 <= t < min(b, w0 + WINDOW_S)]
            if win:
                keys.append((round(min(b, w0 + WINDOW_S / 2), 3), to_x(statistics.median(win))))
            w0 += WINDOW_S
        keys[0] = (a, keys[0][1])
        shots.append(keys)
    if not any(shots):
        return None
    # a shot without a face keeps the crop of the nearest shot that has one
    for k, s in enumerate(shots):
        if s is None:
            near = min((j for j in range(len(shots)) if shots[j]), key=lambda j: abs(j - k))
            shots[k] = [(bounds[k], shots[near][-1][1] if near < k else shots[near][0][1])]
    out: list[tuple[float, float]] = []
    for k, keys in enumerate(shots):
        for t, x in keys:
            if out and k and t == bounds[k]:
                out.append((round(t - 0.001, 3), out[-1][1]))      # hold until the cut, then jump
            out.append((round(t, 3), x))
    return out


def crop_expr(keys: list[tuple[float, float]]) -> str:
    """An ffmpeg expression of t: linear between keyframes, held after the last."""
    expr = f"{keys[-1][1]}"
    for (t0, x0), (t1, x1) in reversed(list(zip(keys, keys[1:]))):
        expr = f"if(lt(t,{t1}),{x0}+({x1 - x0:.1f})*(t-{t0})/{max(t1 - t0, 0.001):.3f},{expr})"
    return f"if(lt(t,{keys[0][0]}),{keys[0][1]},{expr})" if keys[0][0] > 0 else expr


def crop_for(project, item: dict, prof: dict, log=None) -> list[tuple[float, float]] | None:
    """The crop keyframes for one plan item, or None (no face, no file, no wider picture): it then uses fit-blur."""
    path = item.get("path")
    if not path or not Path(path).exists():
        return None
    v = item.get("video") or {}
    w, h = v.get("width"), v.get("height")
    if not (w and h):
        from ..media import ff
        info = (ff.probe(Path(path)).to_dict().get("video") or {})
        w, h = info.get("width"), info.get("height")
    if not (w and h):
        return None
    samples = detect(project, path, item["in"], item["dur"], int(w), int(h), log)
    db = project.db
    cuts = [r[0] - item["in"] for r in db.all("SELECT t FROM shot WHERE source_id=(SELECT id FROM source WHERE ref=?) "
                                              "AND t>? AND t<? ORDER BY t", (item["source"], item["in"], item["out"]))]
    return keyframes(samples, cuts, item["dur"], int(w), int(h), prof["width"], prof["height"])
