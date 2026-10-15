"""Recipes: a journey as portable JSON (sources + timecodes + overlays + music + credits).

The recipe is the product; renders are disposable. ``hash`` covers the content (not links), so two
renders of the same hash are interchangeable. See docs/RECIPE_SPEC.md.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from ..core.timecode import clock

SPEC = "recomposer/1"


def slots_of(db, journey_id: str) -> list[dict]:
    return db.rows("slot", "WHERE journey_id=? ORDER BY pos", (journey_id,))


def slot_span(slot: dict, cut: dict) -> tuple[float, float]:
    a = slot["trim_in"] if slot.get("trim_in") is not None else cut["start"]
    b = slot["trim_out"] if slot.get("trim_out") is not None else cut["end"]
    return a, b


def timeline(db, journey: dict) -> list[dict]:
    """Slots with their source span and their place on the output timeline (transitions overlap)."""
    out, t = [], 0.0
    for n, s in enumerate(slots_of(db, journey["id"]), start=1):
        cut = db.get("cut", s["cut_id"])
        src = db.get("source", cut["source_id"])
        a, b = slot_span(s, cut)
        tr = s.get("transition") or {}
        overlap = float(tr.get("dur", 0)) if tr.get("type") in ("fade", "dissolve") and n > 1 else 0.0
        start = max(0.0, t - overlap)
        out.append({"n": n, "ref": f"{journey['ref']}#{n}", "id": s["id"], "cut": cut, "source": src,
                    "in": a, "out": b, "dur": b - a, "at": start, "end": start + (b - a),
                    "section": s.get("section") or "", "transition": tr, "settings": s.get("settings") or {}})
        t = start + (b - a)
    return out


def source_entry(src: dict) -> dict:
    rights = src.get("rights") or {}
    e = {"kind": src["kind"], "title": src["title"], "year": src.get("year"), "creator": src.get("creator") or "",
         "duration": src.get("duration"), "language": src.get("language"),
         "rights": {k: v for k, v in rights.items() if k in ("owner", "notice", "licence", "url")}}
    if src["kind"] == "link":
        e.update({"platform": src.get("platform"), "id": src.get("platform_id"), "url": src.get("uri")})
    else:
        e["fingerprint"] = src.get("fingerprint")
        e["subtitle_fingerprint"] = (src.get("meta") or {}).get("subtitle_fingerprint")
    return e


def build(db, journey: dict, project_meta: dict | None = None, author: str = "local") -> dict:
    tl = timeline(db, journey)
    sources: dict[str, dict] = {}
    for item in tl:
        sources.setdefault(item["source"]["ref"], source_entry(item["source"]))
    overlays = {}
    for o in db.rows("overlay", "WHERE journey_id=? ORDER BY at", (journey["id"],)):
        slot_n = next((it["n"] for it in tl if it["id"] == o["slot_id"]), None)
        overlays[o["ref"]] = {"kind": o["kind"], "text": o["text"], "slot": slot_n, "at": o["at"], "dur": o["dur"],
                              "style": o["style"] or {}}
    music = []
    for bed in db.rows("music_bed", "WHERE journey_id=? ORDER BY at", (journey["id"],)):
        tr = db.get("music_track", bed["track_id"])
        music.append({"track": tr["ref"], "title": tr["title"], "artist": tr["artist"], "licence": tr["licence"],
                      "licence_url": tr["licence_url"], "url": tr["page_url"] or tr["url"], "provider": tr["provider"],
                      "at": bed["at"], "track_in": bed["track_in"], "dur": bed["dur"], "gain_db": bed["gain_db"],
                      "duck_db": bed["duck_db"], "fade_in": bed["fade_in"], "fade_out": bed["fade_out"]})
    translations: dict[str, dict] = {}
    for tr in db.rows("translation", "WHERE kind IN ('overlay','title','slot_caption') ORDER BY lang"):
        translations.setdefault(tr["lang"], {}).setdefault(tr["kind"], {})[tr["target_id"]] = tr["text"]
    slots = []
    for it in tl:
        c = it["cut"]
        slots.append({"source": it["source"]["ref"], "in": round(it["in"], 3), "out": round(it["out"], 3),
                      "title": c["title"], "quote": c["quote"], "why": c["why"], "people": c["people"],
                      "tags": c["tags"], "section": it["section"], "transition": it["transition"] or {"type": "cut"},
                      "cut": c["ref"]})
    content = {"recipe": SPEC, "id": journey["id"], "ref": journey["ref"], "title": journey["title"],
               "intent": journey["intent"], "description": journey["description"], "language": journey["language"],
               "sources": sources, "slots": slots, "overlays": overlays, "music": music,
               "settings": journey.get("settings") or {}}
    content["hash"] = content_hash(content)
    content["credits"] = credits(content)
    content["author"] = {"handle": author}
    content["links"] = journey.get("links") or {}
    content["duration"] = round(tl[-1]["end"], 3) if tl else 0.0
    return content


def content_hash(content: dict) -> str:
    body = {k: v for k, v in content.items() if k not in ("hash", "links", "author", "credits", "duration", "id", "ref")}
    return "sha256:" + hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:32]


def credits(recipe: dict) -> list[dict]:
    """Attribution, derived from source and music metadata (never typed by hand)."""
    out = []
    for ref, s in recipe["sources"].items():
        used = [x for x in recipe["slots"] if x["source"] == ref]
        rights = s.get("rights") or {}
        line = rights.get("notice") or f"{s['title']}" + (f" ({s['year']})" if s.get("year") else "")
        if s.get("creator") and s["creator"] not in line:
            line += f", {s['creator']}"
        if rights.get("owner") and rights["owner"] not in line:
            line += f", © {rights['owner']}"
        out.append({"type": "source", "ref": ref, "text": line, "url": s.get("url") or rights.get("url"),
                    "moments": [f"{clock(x['in'], 0)}–{clock(x['out'], 0)}" for x in used]})
    for m in recipe["music"]:
        lic = m.get("licence") or "licence unknown"
        out.append({"type": "music", "ref": m["track"], "text": f"Music: \"{m['title']}\" by {m['artist'] or 'unknown'} ({lic})",
                    "url": m.get("url"), "licence_url": m.get("licence_url")})
    return out


def slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()[:60] or "journey"


def write_mirror(project, db, journey: dict) -> Path:
    rec = build(db, journey, project.meta)
    path = project.dir("recipes") / f"{journey['ref']}-{slug(journey['title'])}.recipe.json"
    for old in project.dir("recipes").glob(f"{journey['ref']}-*.recipe.json"):
        if old != path:
            old.unlink()
    path.write_text(json.dumps(rec, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Recomposer recipe",
    "type": "object",
    "required": ["recipe", "title", "sources", "slots"],
    "properties": {
        "recipe": {"const": SPEC},
        "title": {"type": "string", "minLength": 1},
        "intent": {"type": "string"}, "description": {"type": "string"}, "language": {"type": "string"},
        "sources": {"type": "object", "additionalProperties": {
            "type": "object", "required": ["kind", "title"],
            "properties": {"kind": {"enum": ["file", "link"]}, "title": {"type": "string"},
                           "platform": {"type": ["string", "null"]}, "id": {"type": ["string", "null"]},
                           "url": {"type": ["string", "null"]}, "fingerprint": {"type": ["string", "null"]}}}},
        "slots": {"type": "array", "items": {
            "type": "object", "required": ["source", "in", "out"],
            "properties": {"source": {"type": "string"}, "in": {"type": "number", "minimum": 0},
                           "out": {"type": "number"}, "title": {"type": "string"}, "quote": {"type": "string"},
                           "section": {"type": "string"}, "transition": {"type": "object"}}}},
        "overlays": {"type": "object"}, "music": {"type": "array"}, "credits": {"type": "array"},
        "hash": {"type": "string"}, "links": {"type": "object"},
    },
}


def validate(recipe: dict) -> list[str]:
    """Structural validation without a jsonschema dependency (mirrors SCHEMA)."""
    errs = []
    if recipe.get("recipe") != SPEC:
        errs.append(f"recipe must be {SPEC!r}")
    if not recipe.get("title"):
        errs.append("title is required")
    srcs = recipe.get("sources") or {}
    for ref, s in srcs.items():
        if s.get("kind") not in ("file", "link"):
            errs.append(f"source {ref}: kind must be file or link")
        if s.get("kind") == "link" and not (s.get("url") or s.get("id")):
            errs.append(f"source {ref}: a link needs url or id")
    for i, sl in enumerate(recipe.get("slots") or [], start=1):
        if sl.get("source") not in srcs:
            errs.append(f"slot {i}: unknown source {sl.get('source')!r}")
        if not isinstance(sl.get("in"), (int, float)) or not isinstance(sl.get("out"), (int, float)):
            errs.append(f"slot {i}: in/out must be numbers")
        elif sl["out"] <= sl["in"]:
            errs.append(f"slot {i}: out must be after in")
    return errs
