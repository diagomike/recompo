"""Render plans: journey (or single cuts) + profile + language → what the engine draws, on the output timeline.

A pure function of the database state, so it is golden-testable and its hash keys the caches.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ..compose import recipe as R
from ..envelope import RecompError
from ..transcript.store import primary
from . import profiles

PLAN_VERSION = 5


def _words_in(db, tr: dict, a: float, b: float) -> list[tuple[float, float, str]]:
    if not tr or not tr["has_words"]:
        return []
    rows = db.all('SELECT w.start, w."end", w.text FROM word w JOIN segment s ON s.id=w.segment_id '
                  'WHERE s.transcript_id=? AND w."end" > ? AND w.start < ? ORDER BY w.start, w.idx', (tr["id"], a, b))
    return [(max(a, r[0]), min(b, r[1]), r[2]) for r in rows]


def _segments_in(db, tr: dict, a: float, b: float) -> list[dict]:
    if not tr:
        return []
    return [dict(r) for r in db.all('SELECT id, idx, start, "end", text FROM segment WHERE transcript_id=? '
                                    'AND "end" > ? AND start < ? ORDER BY idx', (tr["id"], a + 0.05, b - 0.05))]


def captions_for_slot(db, src: dict, a: float, b: float, at: float, lang: str | None) -> list[dict]:
    """Source captions for [a, b) mapped to output time ``at``; translations replace text when lang differs."""
    tr = primary(db, src["id"])
    if not tr:
        return []
    out = []
    translated = lang and tr.get("language") and lang != tr["language"]
    for seg in _segments_in(db, tr, a, b):
        s0, s1 = max(a, seg["start"]), min(b, seg["end"])
        if s1 - s0 < 0.2:
            continue
        text = seg["text"]
        raw = _words_in(db, tr, s0, s1)
        if not raw:  # no word timing: spread words over the line so long lines can be chunked in time
            from ..transcript.align import proportional_words
            raw = [(w["start"], w["end"], w["text"]) for w in proportional_words(seg) if s0 <= w["start"] < s1]
        words = [(w0 - a + at, w1 - a + at, t) for (w0, w1, t) in raw]
        if translated:
            row = db.one("SELECT text FROM translation WHERE lang=? AND kind='segment' AND target_id=?",
                         (lang, str(seg["id"])))
            if row is None:
                continue  # untranslated lines are left out (export checks report coverage)
            text, words = row[0], []
        out.append({"start": round(s0 - a + at, 3), "end": round(s1 - a + at, 3), "text": text, "words": words,
                    "seg": seg["id"]})
    return out


def _item(src: dict, a: float, b: float, at: float, slot_settings: dict, transition: dict, ref: str, cut_ref: str) -> dict:
    probe = (src.get("meta") or {}).get("probe") or {}
    return {"ref": ref, "cut": cut_ref, "source": src["ref"], "path": src.get("path"), "fingerprint": src.get("fingerprint"),
            "in": round(a, 3), "out": round(b, 3), "dur": round(b - a, 3), "at": round(at, 3),
            "transition": transition or {}, "reframe_x": slot_settings.get("crop_x"),
            "video": probe.get("video"), "audio": probe.get("audio"), "kind": src["kind"]}


def quantize(items: list[dict], fps: int) -> None:
    """Whole frames per slot, and output positions recomputed from them, so the rendered body's
    length equals the plan exactly and captions don't drift on long journeys."""
    t = 0.0
    for k, it in enumerate(items):
        frames = max(1, round(it["dur"] * fps))
        it["frames"] = frames
        it["dur"] = round(frames / fps, 4)
        it["out"] = round(it["in"] + it["dur"], 4)
        tr = it.get("transition") or {}
        overlap = 0.0
        if k and tr.get("type") in ("fade", "dip"):
            overlap = round(min(float(tr.get("dur", 0.5)), it["dur"] / 2, items[k - 1]["dur"] / 2) * fps) / fps
            tr["dur"] = overlap
        it["at"] = round(max(0.0, t - overlap), 4)
        t = it["at"] + it["dur"]


def build(db, project, journey: dict | None = None, cuts: list[dict] | None = None, profile: dict | None = None,
          lang: str | None = None, title: str | None = None) -> dict:
    prof = profiles.resolve(profile or {})
    items: list[dict] = []
    overlays: list[dict] = []
    captions: list[dict] = []
    beds: list[dict] = []
    if journey is not None:
        tl = R.timeline(db, journey)
        for it in tl:
            items.append(_item(it["source"], it["in"], it["out"], it["at"], it["settings"], it["transition"],
                               it["ref"], it["cut"]["ref"]))
        quantize(items, prof["fps"])
        rec = R.build(db, journey)
        lang = lang or journey["language"]
        title = title or journey["title"]
        slot_at = {it["id"]: {"at": items[k]["at"], "end": items[k]["at"] + items[k]["dur"]} for k, it in enumerate(tl)}
        for o in db.rows("overlay", "WHERE journey_id=? ORDER BY at", (journey["id"],)):
            if o["kind"] == "lower_third" and not prof["lower_thirds"]:
                continue
            if not prof["overlays"] and o["kind"] != "lower_third":
                continue
            base = slot_at[o["slot_id"]]["at"] if o["slot_id"] in slot_at else 0.0
            limit = slot_at[o["slot_id"]]["end"] if o["slot_id"] in slot_at else None
            text = o["text"]
            if lang and lang != journey["language"]:
                row = db.one("SELECT text FROM translation WHERE lang=? AND kind='overlay' AND target_id=?", (lang, o["id"]))
                text = row[0] if row else text
            start = base + (o["at"] or 0)
            end = start + (o["dur"] or 4)
            if limit is not None:
                end = min(end, limit)
            overlays.append({"ref": o["ref"], "kind": o["kind"], "text": text, "start": round(start, 3),
                             "end": round(end, 3), "style": o["style"] or {}})
        if prof["title_card"] and not any(o["kind"] == "title" for o in overlays) and items:
            t_text = title
            if lang and lang != journey["language"]:
                row = db.one("SELECT text FROM translation WHERE lang=? AND kind='title' AND target_id=?", (lang, journey["id"]))
                t_text = row[0] if row else title
            overlays.insert(0, {"ref": "title", "kind": "title", "text": t_text, "start": 0.0,
                                "end": min(2.8, items[0]["dur"]), "style": {}})
        if prof["music"]:
            for m in rec["music"]:
                tr = db.by_ref("music_track", m["track"])
                if not tr or not tr.get("file") or not Path(tr["file"]).exists():
                    raise RecompError("E_NOT_FOUND", f"music {m['track']} has no local file",
                                      hint=f"`recomp music get {m['track']}` or turn music off in the profile")
                beds.append({**m, "file": tr["file"]})
        credits = rec["credits"]
        links = journey.get("links") or {}
        recipe_hash = rec["hash"]
        description_src = rec
    else:
        at = 0.0
        for c in cuts or []:
            src = db.get("source", c["source_id"])
            items.append(_item(src, c["start"], c["end"], at, {}, {}, c["ref"], c["ref"]))
            at += c["end"] - c["start"]
        quantize(items, prof["fps"])
        title = title or (cuts[0]["title"] if cuts else "clip")
        srcs = {}
        for it in items:
            srcs.setdefault(it["source"], R.source_entry(db.by_ref("source", it["source"])))
        fake = {"sources": srcs, "slots": [{"source": it["source"], "in": it["in"], "out": it["out"]} for it in items], "music": []}
        credits = R.credits(fake)
        links = {}
        recipe_hash = "cut:" + ",".join(it["cut"] for it in items)
        description_src = None
        if prof["lower_thirds"] and items:
            s = db.by_ref("source", items[0]["source"])
            name = s["title"] + (f" ({s['year']})" if s.get("year") else "")
            overlays.append({"ref": "lt", "kind": "lower_third", "text": name, "start": 0.6,
                             "end": min(4.0, items[0]["dur"] - 0.5), "style": {}})
        if cuts and not lang:
            lang = db.get("source", cuts[0]["source_id"]).get("language") or "en"
    if not items:
        raise RecompError("E_INVALID", "nothing to render: the journey has no slots")
    for it in items:
        if it["kind"] == "link" and not (it["path"] and Path(it["path"]).exists()):
            it["needs_fetch"] = True
        elif not it["path"] or not Path(it["path"]).exists():
            raise RecompError("E_NOT_FOUND", f"{it['ref']}: media for {it['source']} is missing",
                              hint=f"`recomp source relink {it['source']} <path>`")
    # Captions on the output timeline.
    if prof["captions"] != "off":
        for it in items:
            src = db.by_ref("source", it["source"])
            caps = captions_for_slot(db, src, it["in"], it["out"], it["at"], lang)
            captions += caps
    body = items[-1]["at"] + items[-1]["dur"]
    end_s = prof["endcard_seconds"] if prof["endcard"] else 0.0
    plan = {"version": PLAN_VERSION, "profile": prof, "lang": lang, "title": title, "items": items,
            "overlays": overlays, "captions": captions, "music": beds, "credits": credits,
            "links": links, "recipe_hash": recipe_hash, "body_dur": round(body, 3),
            "endcard": {"seconds": end_s} if end_s else None, "total": round(body + end_s, 3)}
    plan["hash"] = plan_hash(plan)
    plan["_recipe"] = description_src
    return plan


def plan_hash(plan: dict) -> str:
    body = {k: v for k, v in plan.items() if not k.startswith("_") and k != "hash"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()[:16]


def slot_key(item: dict, prof: dict) -> str:
    """Cache key for one slot's intermediate render (independent of its position)."""
    body = {"fp": item.get("fingerprint") or item.get("path"), "in": item["in"], "out": item["out"],
            "w": prof["width"], "h": prof["height"], "fps": prof["fps"], "reframe": prof["reframe"],
            "x": item.get("reframe_x"), "crf": prof["crf"], "preset": prof["preset"], "v": PLAN_VERSION,
            "path": item.get("path")}
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()[:20]
