"""Automatic checks on every export: length, format, audio, loudness, captions, endcard, credits."""

from __future__ import annotations

import re
from pathlib import Path

from ..media import ff


def loudness(path: Path) -> dict:
    text = ff.run_simple(["-i", str(path), "-map", "0:a:0", "-af", "ebur128=peak=true", "-f", "null", "-"], timeout=900)
    summary = text[text.rfind("Summary:"):]
    i = re.search(r"I:\s+(-?[\d.]+) LUFS", summary)
    tp = re.search(r"Peak:\s+(-?[\d.]+) dBFS", summary)
    return {"integrated": float(i.group(1)) if i else None, "true_peak": float(tp.group(1)) if tp else None}


def run(folder: Path, plan: dict) -> dict:
    video = folder / "video.mp4"
    prof = plan["profile"]
    out: dict = {"checks": [], "ok": True}

    def add(name, ok, detail):
        out["checks"].append({"check": name, "ok": bool(ok), "detail": detail})
        if not ok:
            out["ok"] = False

    if not video.exists():
        add("video exists", False, str(video))
        return out
    info = ff.probe(video)
    add("duration", info.duration is not None and abs(info.duration - plan["total"]) <= 0.12,
        f"{info.duration}s vs planned {plan['total']}s")
    v = info.video[0] if info.video else None
    add("frame size", v is not None and (v.width, v.height) == (prof["width"], prof["height"]),
        f"{v.width}x{v.height}" if v else "no video")
    add("audio stream", bool(info.audio), f"{len(info.audio)} audio stream(s)")
    lang = info.audio[0].language if info.audio else ""
    add("audio language tag", bool(lang) and lang != "und", lang or "none")
    try:
        ld = loudness(video)
        ok = ld["integrated"] is not None and abs(ld["integrated"] - prof["loudness"]) <= 1.0
        add("loudness", ok, f"{ld['integrated']} LUFS (target {prof['loudness']})")
        add("true peak", ld["true_peak"] is not None and ld["true_peak"] <= prof["true_peak"] + 0.5,
            f"{ld['true_peak']} dBFS (ceiling {prof['true_peak']})")
        out["loudness"] = ld
    except Exception as exc:  # noqa: BLE001
        add("loudness", False, str(exc)[:200])
    srt = folder / "captions.srt"
    n_caps = len(plan["captions"])
    add("captions file", srt.exists() and (n_caps == 0 or srt.stat().st_size > 10), f"{n_caps} captions")
    if prof["captions"] != "off" and not n_caps:
        add("captions present", False, "no captions for this language: translate the lines first")
    if plan.get("endcard"):
        add("endcard", True, f"{plan['endcard']['seconds']}s with {len(plan['credits'])} credit line(s)")
    add("credits", all(c.get("text") for c in plan["credits"]) and bool(plan["credits"]), f"{len(plan['credits'])} credits")
    music_ok = all(m.get("licence") for m in plan["music"])
    add("music licences", music_ok, ", ".join(f"{m['title']}: {m.get('licence') or 'MISSING'}" for m in plan["music"]) or "no music")
    desc = folder / "description.txt"
    add("description", desc.exists(), str(desc.name))
    return out
