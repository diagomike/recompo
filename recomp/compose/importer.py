"""Rebuild a journey from a recipe (a file, or a recipe pulled from the hub).

Link sources are matched by platform id (or added as link sources); file sources by fingerprint,
then by title + year + length. A file source with no match becomes a *missing* source the user
can relink; its cuts and slots are still created, so the journey is complete once it is.
"""

from __future__ import annotations

from ..envelope import Result
from . import recipe as R


def _match_source(db, entry: dict) -> tuple[dict | None, str]:
    """The local source for a recipe entry and how it was found: id, url, fingerprint, title (another copy of
    the work: release matching shifts its cuts) or none."""
    if entry.get("kind") == "link":
        if entry.get("id"):
            row = db.rows("source", "WHERE platform=? AND platform_id=?", (entry.get("platform"), entry["id"]))
            if row:
                return row[0], "id"
        if entry.get("url"):
            row = db.rows("source", "WHERE uri=?", (entry["url"],))
            return (row[0], "url") if row else (None, "none")
        return None, "none"
    if entry.get("fingerprint"):
        row = db.rows("source", "WHERE fingerprint=?", (entry["fingerprint"],))
        if row:
            return row[0], "fingerprint"
    for s in db.rows("source", "WHERE kind='file' AND lower(title)=lower(?)", (entry.get("title", ""),)):
        if entry.get("year") and s.get("year") and int(entry["year"]) != int(s["year"]):
            continue
        # another release may run minutes longer (PAL speed-up, extra scenes): length only rules out other works
        if entry.get("duration") and s.get("duration") and abs(entry["duration"] - s["duration"]) > max(3.0, 0.06 * entry["duration"]):
            continue
        return s, "fingerprint" if s.get("fingerprint") and s["fingerprint"] == entry.get("fingerprint") else "title"
    return None, "none"


def _match_releases(tx, db, rec: dict, src_ids: dict, how: dict, cuts_of: dict) -> list[str]:
    """File sources found by title (or missing) may be another copy of the film: keep the recipe's anchors on the
    source and, when this copy has a transcript, shift the imported cuts by the offset measured near each."""
    from ..envelope import RecompError
    from . import release
    out = []
    for ref, e in rec["sources"].items():
        if e.get("kind") != "file" or how.get(ref) in ("fingerprint", "id", "url") or not e.get("anchors"):
            continue
        src = db.get("source", src_ids[ref])
        meta = dict(src.get("meta") or {})
        meta.update({"release_anchors": e["anchors"], "release_fingerprint": e.get("fingerprint"),
                     "release_cuts": [db.get("cut", c)["ref"] for c in cuts_of.get(ref, [])]})
        try:
            tx.update("source", src["id"], {"meta": meta})
            segs = release.segments(db, src["id"])
            if not segs:
                out.append(f"{ref} → {src['ref']}: another copy of the film; once it has a transcript, "
                           f"`recomp source match-release {src['ref']}` lines the cuts up with it")
                continue
            m = release.match(e["anchors"], segs)
            if m["offset_s"] is None:
                out.append(f"{ref} → {src['ref']}: another copy, and none of the recipe's {len(e['anchors'])} anchor lines "
                           f"were found in its transcript: check the cuts by eye")
                continue
            release.apply(tx, db, db.get("source", src["id"]), m, cuts_of.get(ref, []))
            out.append(f"{ref} → {src['ref']}: another copy of the film, {m['offset_s']:+.2f} s from the recipe's "
                       f"({m['matched']}/{m['anchors']} anchor lines found); cuts shifted"
                       + ("; the offset changes along the film (a scene cut or added, or another speed), so each cut "
                          "took the offset measured near it" if m["edit"] else ""))
        except RecompError as exc:
            out.append(f"{src['ref']}: release matching skipped ({exc.message})")
    return out


def import_recipe(ctx, rec: dict, forked_from: str | None = None) -> Result:
    errs = R.validate(rec)
    if errs:
        from ..envelope import RecompError
        raise RecompError("E_INVALID", "not a valid recipe", data=errs)
    db = ctx.db
    warnings = []
    src_ids: dict[str, str] = {}
    how: dict[str, str] = {}
    cuts_of: dict[str, list[str]] = {}
    with ctx.op(f"import recipe {rec['title']!r}") as tx:
        for ref, e in rec["sources"].items():
            s, how[ref] = _match_source(db, e)
            if s is None:
                if e["kind"] == "link":
                    s = tx.insert("source", {"kind": "link", "uri": e.get("url") or f"https://youtu.be/{e.get('id')}",
                                             "platform": e.get("platform"), "platform_id": e.get("id"),
                                             "title": e.get("title", ""), "creator": e.get("creator", ""),
                                             "duration": e.get("duration"), "language": e.get("language"),
                                             "rights": e.get("rights") or {}, "status": {"probe": "pending"},
                                             "meta": {"from_recipe": rec.get("id")}})
                    warnings.append(f"{ref} → {s['ref']}: link added (metadata only); `recomp transcript fetch-captions {s['ref']}`")
                else:
                    s = tx.insert("source", {"kind": "file", "uri": "", "path": None, "title": e.get("title", ""),
                                             "year": e.get("year"), "creator": e.get("creator", ""),
                                             "duration": e.get("duration"), "fingerprint": e.get("fingerprint"),
                                             "rights": e.get("rights") or {}, "status": {"probe": "missing"},
                                             "meta": {"from_recipe": rec.get("id")}})
                    warnings.append(f"{ref} → {s['ref']}: you don't have this file yet; `recomp source relink {s['ref']} <your copy>`")
            src_ids[ref] = s["id"]
        j = tx.insert("journey", {"title": rec["title"], "intent": rec.get("intent", ""),
                                  "description": rec.get("description", ""), "language": rec.get("language", "en"),
                                  "settings": rec.get("settings") or {},
                                  "links": {"forked_from": forked_from or rec.get("links", {}).get("hub"),
                                            "recipe_hash": rec.get("hash")}})
        slot_ids = {}
        for n, sl in enumerate(rec["slots"], start=1):
            cut = tx.insert("cut", {"source_id": src_ids[sl["source"]], "start": sl["in"], "end": sl["out"],
                                    "title": sl.get("title", ""), "quote": sl.get("quote", ""), "why": sl.get("why", ""),
                                    "people": sl.get("people", []), "tags": list(sl.get("tags", [])) + ["imported"]})
            cuts_of.setdefault(sl["source"], []).append(cut["id"])
            slot = tx.insert("slot", {"journey_id": j["id"], "pos": float(n), "cut_id": cut["id"],
                                      "section": sl.get("section", ""),
                                      "transition": {} if (sl.get("transition") or {}).get("type", "cut") == "cut" else sl["transition"]})
            slot_ids[n] = slot["id"]
        for o in (rec.get("overlays") or {}).values():
            tx.insert("overlay", {"journey_id": j["id"], "slot_id": slot_ids.get(o.get("slot")), "kind": o["kind"],
                                  "text": o.get("text", ""), "style": o.get("style") or {}, "at": o.get("at", 0),
                                  "dur": o.get("dur")})
        for m in rec.get("music") or []:
            tr = tx.insert("music_track", {"provider": m.get("provider") or "recipe", "url": m.get("url"),
                                           "page_url": m.get("url"), "title": m.get("title", ""), "artist": m.get("artist", ""),
                                           "licence": m.get("licence", ""), "licence_url": m.get("licence_url", "")})
            tx.insert("music_bed", {"journey_id": j["id"], "track_id": tr["id"], "at": m.get("at", 0),
                                    "track_in": m.get("track_in", 0), "dur": m.get("dur"), "gain_db": m.get("gain_db", -16),
                                    "duck_db": m.get("duck_db", -10), "fade_in": m.get("fade_in", 1.5),
                                    "fade_out": m.get("fade_out", 2.5)})
            warnings.append(f"music {tr['ref']} needs its file: `recomp music get {tr['ref']}`")
        warnings += _match_releases(tx, db, rec, src_ids, how, cuts_of)
    R.write_mirror(ctx.project, db, db.get("journey", j["id"]))
    return Result(data={"journey": j["ref"], "slots": len(rec["slots"]), "sources": {k: db.get("source", v)["ref"] for k, v in src_ids.items()}},
                  refs=[j["ref"]], warnings=warnings)
