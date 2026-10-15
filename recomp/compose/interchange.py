"""Edit-decision interchange: CMX3600 EDL and OpenTimelineIO JSON (hand-written, no dependency)."""

from __future__ import annotations

import json
import re

from . import recipe as R

FPS = 30


def _tc(seconds: float, fps: int = FPS) -> str:
    frames = int(round(seconds * fps))
    h, rem = divmod(frames, 3600 * fps)
    m, rem = divmod(rem, 60 * fps)
    s, f = divmod(rem, fps)
    return f"{h:02d}:{m:02d}:{s:02d}:{f:02d}"


def _reel(ref: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", ref.upper())[:8] or "AX"


def edl(db, journey: dict) -> str:
    lines = [f"TITLE: {journey['title'][:60]}", "FCM: NON-DROP FRAME", ""]
    rec = 3600.0  # record timeline starts at 01:00:00:00, as editors expect
    for n, it in enumerate(R.timeline(db, journey), start=1):
        src = it["source"]
        lines.append(f"{n:03d}  {_reel(src['ref']):<8} AA/V  C        {_tc(it['in'])} {_tc(it['out'])} "
                     f"{_tc(rec + it['at'])} {_tc(rec + it['at'] + it['dur'])}")
        lines.append(f"* FROM CLIP NAME: {src['title']}")
        if src.get("path"):
            lines.append(f"* SOURCE FILE: {src['path']}")
        if it["cut"]["title"]:
            lines.append(f"* COMMENT: {it['cut']['ref']} {it['cut']['title']}")
        lines.append("")
    return "\n".join(lines)


def _rt(seconds: float, rate: int = FPS) -> dict:
    return {"OTIO_SCHEMA": "RationalTime.1", "rate": float(rate), "value": round(seconds * rate, 3)}


def _range(start: float, dur: float) -> dict:
    return {"OTIO_SCHEMA": "TimeRange.1", "start_time": _rt(start), "duration": _rt(dur)}


def otio(db, journey: dict) -> str:
    tl = R.timeline(db, journey)
    clips = []
    for it in tl:
        src = it["source"]
        if src.get("path"):
            ref = {"OTIO_SCHEMA": "ExternalReference.1", "target_url": "file:///" + src["path"].replace("\\", "/"),
                   "available_range": _range(0, src.get("duration") or it["out"]), "metadata": {}, "name": src["title"]}
        else:
            ref = {"OTIO_SCHEMA": "ExternalReference.1", "target_url": src.get("uri") or "", "metadata": {},
                   "name": src["title"], "available_range": None}
        clips.append({"OTIO_SCHEMA": "Clip.2", "name": f"{it['ref']} {it['cut']['title']}"[:80],
                      "source_range": _range(it["in"], it["dur"]),
                      "media_references": {"DEFAULT_MEDIA": ref}, "active_media_reference_key": "DEFAULT_MEDIA",
                      "metadata": {"recomposer": {"cut": it["cut"]["ref"], "source": src["ref"], "why": it["cut"]["why"],
                                                  "section": it["section"]}},
                      "effects": [], "markers": [], "enabled": True})
    track = lambda kind: {"OTIO_SCHEMA": "Track.1", "name": kind, "kind": kind, "children": clips,
                          "source_range": None, "effects": [], "markers": [], "enabled": True, "metadata": {}}
    doc = {"OTIO_SCHEMA": "Timeline.1", "name": journey["title"], "global_start_time": _rt(0),
           "metadata": {"recomposer": {"journey": journey["ref"], "intent": journey["intent"]}},
           "tracks": {"OTIO_SCHEMA": "Stack.1", "name": "tracks", "children": [track("Video"), track("Audio")],
                      "source_range": None, "effects": [], "markers": [], "enabled": True, "metadata": {}}}
    return json.dumps(doc, indent=2, ensure_ascii=False)
