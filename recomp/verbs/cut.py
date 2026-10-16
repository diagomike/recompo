"""Cuts: meaningful moments, snapped to words and shots, labelled with why they matter."""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from ..core import refs
from ..core.timecode import clock, parse
from ..edit import snap
from ..envelope import RecompError, Result
from ..registry import Ctx, verb
from ..transcript.store import primary
from .search import SearchIn, run_search

SNAPS = ("words", "shots", "words+shots", "none")


def text_between(db, src: dict, a: float, b: float) -> str:
    tr = primary(db, src["id"])
    if not tr:
        return ""
    if tr["has_words"]:
        rows = db.all('SELECT w.text FROM word w JOIN segment s ON s.id=w.segment_id WHERE s.transcript_id=? '
                      'AND w.start >= ? AND w."end" <= ? ORDER BY w.start, w.idx', (tr["id"], a - 0.05, b + 0.05))
        if rows:
            return " ".join(r[0] for r in rows)
    rows = db.all('SELECT text FROM segment WHERE transcript_id=? AND "end" > ? AND start < ? ORDER BY idx',
                  (tr["id"], a + 0.1, b - 0.1))
    return " ".join(r[0] for r in rows)


def chapter_at(db, source_id: str, t: float) -> dict | None:
    r = db.one('SELECT id, ref, title FROM chapter WHERE source_id=? AND start<=? AND "end">? ORDER BY start DESC LIMIT 1',
               (source_id, t, t))
    return dict(r) if r else None


def brief(db, c: dict) -> dict:
    src = db.get("source", c["source_id"])
    ch = db.get("chapter", c["chapter_id"]) if c.get("chapter_id") else None
    return {"ref": c["ref"], "source": src["ref"] if src else None, "start": round(c["start"], 3),
            "end": round(c["end"], 3), "span": f"{clock(c['start'])}–{clock(c['end'])}",
            "dur": round(c["end"] - c["start"], 2), "title": c["title"], "why": c["why"], "tags": c["tags"],
            "emotions": c["emotions"], "people": c["people"], "rating": c["rating"],
            "chapter": ch["ref"] if ch else None, "quote": c["quote"], "by": c["created_by"]}


def _segment_span(db, tr: dict, spec: str) -> tuple[float, float]:
    m = re.match(r"^\s*(\d+)\s*(?:\.\.|-|:)\s*(\d+)\s*$", spec) or re.match(r"^\s*(\d+)\s*$", spec)
    if not m:
        raise RecompError("E_INVALID", "segments look like 412..430")
    a_idx = int(m.group(1))
    b_idx = int(m.group(2)) if m.lastindex and m.lastindex > 1 else a_idx
    a = db.one("SELECT start FROM segment WHERE transcript_id=? AND idx=?", (tr["id"], a_idx))
    b = db.one('SELECT "end" FROM segment WHERE transcript_id=? AND idx=?', (tr["id"], b_idx))
    if not a or not b:
        raise RecompError("E_NOT_FOUND", f"segments {spec} not in {tr['ref']}")
    return a[0], b[0]


class AddIn(BaseModel):
    ref: str = Field(..., description="Source ref", json_schema_extra={"pos": 0})
    from_: str | None = Field(None, alias="from", description="Start time")
    to: str | None = Field(None, description="End time")
    segments: str | None = Field(None, description="Segment range from `transcript read`, e.g. 412..430")
    quote_start: str | None = Field(None, description="Words the cut starts with (exact from the transcript)")
    quote_end: str | None = Field(None, description="Words the cut ends with")
    near: str | None = Field(None, description="Look for the quote near this time (± 10 min)")
    snap: str = Field("words", description="words | shots | words+shots | none")
    pad: str | None = Field(None, description="Lead-in,tail seconds (default 0.15,0.35)")
    title: str = ""
    why: str = Field("", description="Why this moment matters")
    tags: list[str] = Field(default_factory=list)
    emotions: list[str] = Field(default_factory=list)
    people: list[str] = Field(default_factory=list)
    rating: int | None = Field(None, description="1–5")
    note: str = ""
    journey: str | None = Field(None, description="Also append the new cut to this journey (e.g. J1)")
    model_config = {"populate_by_name": True}


def resolve_range(ctx: Ctx, src: dict, inp) -> tuple[float, float, dict]:
    db = ctx.db
    tr = primary(db, src["id"])
    words = snap.load_words(db, tr) if tr else []
    info: dict = {}
    if inp.quote_start:
        near = parse(inp.near) if inp.near else None
        lo = near - 600 if near is not None else -1.0
        hi = near + 600 if near is not None else None
        i0, i1, sc = snap.find_quote(words, inp.quote_start, after=lo, before=hi)
        a = words[i0]["start"]
        if inp.quote_end:
            j0, j1, sc2 = snap.find_quote(words, inp.quote_end, after=a - 0.01, before=a + 600)
            b = words[j1]["end"]
            info["quote_match"] = [sc, sc2]
        else:
            b = parse(inp.to) if inp.to else words[i1]["end"]
            info["quote_match"] = [sc]
    elif inp.segments:
        if not tr:
            raise RecompError("E_NOT_FOUND", "no transcript")
        a, b = _segment_span(db, tr, inp.segments)
    else:
        a, b = parse(inp.from_), parse(inp.to)
        if a is None or b is None:
            raise RecompError("E_INVALID", "give --from and --to, --segments, or --quote-start",
                              hint="`recomp help cut.add`")
    if b <= a:
        raise RecompError("E_INVALID", f"end {clock(b)} is not after start {clock(a)}")
    pad = (snap.PAD_IN, snap.PAD_OUT)
    if inp.pad:
        p = [float(x) for x in inp.pad.split(",")]
        pad = (p[0], p[1] if len(p) > 1 else p[0])
    if inp.snap not in SNAPS:
        raise RecompError("E_INVALID", f"snap must be one of {SNAPS}")
    mode = inp.snap
    shots = snap.load_shots(db, src["id"]) if "shots" in mode else []
    na, nb, sinfo = snap.snap_range(a, b, words, shots, "words" if mode == "words" else mode, pad, src["duration"])
    info.update(sinfo)
    return na, nb, info


@verb("cut.add", AddIn, effect="write",
      examples=['recomp cut add S1 --quote-start "You either die a hero" --quote-end "become the villain" --title "Live long enough" --why "Harvey\'s thesis" --tags fate,heroism',
                "recomp cut add S1 --from 01:02:10.5 --to 01:02:55 --snap words+shots",
                "recomp cut add S1 --segments 412..430",
                'recomp cut add S2 --from 3:10 --to 3:42 --why "the turn" --journey J1   # cut straight into a journey'])
def cut_add(ctx: Ctx, inp: AddIn):
    """Make a cut by quote, segment range or times. Edges snap to words (and shots); the spoken text is stored with it."""
    db = ctx.db
    src = refs.source(db, inp.ref)
    a, b, info = resolve_range(ctx, src, inp)
    quote = text_between(db, src, a, b)
    ch = chapter_at(db, src["id"], (a + b) / 2)
    j = None
    if inp.journey:
        from .journey import journey_of
        j = journey_of(db, inp.journey)
    with ctx.op(f"cut {src['ref']} {clock(a)}" + (f" into {j['ref']}" if j else "")) as tx:
        c = tx.insert("cut", {"source_id": src["id"], "start": a, "end": b, "title": inp.title or quote[:60],
                              "quote": quote, "why": inp.why, "note": inp.note, "tags": inp.tags,
                              "emotions": inp.emotions, "people": inp.people, "rating": inp.rating,
                              "chapter_id": ch["id"] if ch else None, "snap": info})
        if j:
            last = db.scalar("SELECT MAX(pos) FROM slot WHERE journey_id=?", (j["id"],)) or 0.0
            tx.insert("slot", {"journey_id": j["id"], "pos": float(last) + 1.0, "cut_id": c["id"]})
            from .journey import renumber
            renumber(tx, j["id"])
    if j:
        from .journey import mirror
        mirror(ctx, j["id"])
    warnings = []
    dur = b - a
    if dur > 240:
        warnings.append(f"long cut ({dur:.0f}s): fine for long-form, too long for shorts")
    if dur < 3:
        warnings.append(f"very short cut ({dur:.1f}s)")
    if not inp.why:
        warnings.append("no --why given: say why this moment matters (it is what you and the user search later)")
    data = brief(db, c)
    if j:
        data["journey"] = j["ref"]
    return Result(data=data, refs=[c["ref"]] + ([j["ref"]] if j else []), warnings=warnings,
                  next=[f"recomp ui show {c['ref']} --play",
                        f"recomp journey guide {j['ref']}" if j else f"recomp journey add <J> {c['ref']}"])


class EditIn(BaseModel):
    ref: str = Field(..., description="Cut ref", json_schema_extra={"pos": 0})
    title: str | None = None
    why: str | None = None
    note: str | None = None
    tags: list[str] | None = None
    emotions: list[str] | None = None
    people: list[str] | None = None
    rating: int | None = None


@verb("cut.edit", EditIn, effect="write")
def cut_edit(ctx: Ctx, inp: EditIn):
    """Change a cut's labels (title, why, note, tags, emotions, people, rating)."""
    c = refs.resolve(ctx.db, inp.ref, "cut")[1]
    fields = {k: v for k, v in inp.model_dump(exclude={"ref"}).items() if v is not None}
    with ctx.op(f"edit {c['ref']}") as tx:
        c = tx.update("cut", c["id"], fields)
    return brief(ctx.db, c)


class TrimIn(BaseModel):
    ref: str = Field(..., json_schema_extra={"pos": 0})
    start: str | None = Field(None, description="New start: absolute time, or +0.3 / -1.2 relative")
    end: str | None = Field(None, description="New end: absolute time, or relative")
    snap: str = Field("none", description="Snap the new edges: words | shots | words+shots | none")


def _rel(value: str | None, base: float) -> float | None:
    if value is None:
        return None
    v = value.strip()
    if v[:1] in "+-" and ":" not in v:
        return base + float(v)
    return parse(v)


@verb("cut.trim", TrimIn, effect="write", examples=["recomp cut trim C17 --start +0.3 --end -1.2"])
def cut_trim(ctx: Ctx, inp: TrimIn):
    """Move a cut's edges (absolute or relative); optionally re-snap."""
    db = ctx.db
    c = refs.resolve(db, inp.ref, "cut")[1]
    src = db.get("source", c["source_id"])
    a = _rel(inp.start, c["start"])
    b = _rel(inp.end, c["end"])
    a = c["start"] if a is None else a
    b = c["end"] if b is None else b
    if b <= a:
        raise RecompError("E_INVALID", "end would be before start")
    if inp.snap != "none":
        tr = primary(db, src["id"])
        words = snap.load_words(db, tr) if tr else []
        shots = snap.load_shots(db, src["id"])
        a, b, _ = snap.snap_range(a, b, words, shots, inp.snap, duration=src["duration"])
    with ctx.op(f"trim {c['ref']}") as tx:
        c = tx.update("cut", c["id"], {"start": round(a, 3), "end": round(b, 3), "quote": text_between(db, src, a, b)})
    return brief(db, c)


class SplitIn(BaseModel):
    ref: str = Field(..., json_schema_extra={"pos": 0})
    at: str = Field(..., description="Source time to split at")


@verb("cut.split", SplitIn, effect="write")
def cut_split(ctx: Ctx, inp: SplitIn):
    """Split a cut into two at a source time."""
    db = ctx.db
    c = refs.resolve(db, inp.ref, "cut")[1]
    t = parse(inp.at)
    if not c["start"] < t < c["end"]:
        raise RecompError("E_INVALID", "split time is outside the cut")
    src = db.get("source", c["source_id"])
    with ctx.op(f"split {c['ref']}") as tx:
        tx.update("cut", c["id"], {"end": t, "quote": text_between(db, src, c["start"], t)})
        new = tx.insert("cut", {k: c[k] for k in ("source_id", "title", "why", "tags", "emotions", "people", "chapter_id")}
                        | {"start": t, "end": c["end"], "quote": text_between(db, src, t, c["end"]),
                           "title": (c["title"] + " (2)")[:80]})
    return [brief(db, db.get("cut", c["id"])), brief(db, new)]


class MergeIn(BaseModel):
    ref: str = Field(..., json_schema_extra={"pos": 0})
    other: str = Field(..., json_schema_extra={"pos": 1})


@verb("cut.merge", MergeIn, effect="write")
def cut_merge(ctx: Ctx, inp: MergeIn):
    """Merge two cuts from the same source into one spanning both."""
    db = ctx.db
    a = refs.resolve(db, inp.ref, "cut")[1]
    b = refs.resolve(db, inp.other, "cut")[1]
    if a["source_id"] != b["source_id"]:
        raise RecompError("E_INVALID", "cuts come from different sources")
    if db.scalar("SELECT COUNT(*) FROM slot WHERE cut_id=?", (b["id"],)):
        raise RecompError("E_CONFLICT", f"{b['ref']} is used in a journey; remove it there first")
    src = db.get("source", a["source_id"])
    s, e = min(a["start"], b["start"]), max(a["end"], b["end"])
    with ctx.op(f"merge {a['ref']}+{b['ref']}") as tx:
        tx.update("cut", a["id"], {"start": s, "end": e, "quote": text_between(db, src, s, e),
                                   "tags": sorted(set(a["tags"]) | set(b["tags"]))})
        tx.delete("cut", b["id"])
    return brief(db, db.get("cut", a["id"]))


class RefIn(BaseModel):
    ref: str = Field(..., json_schema_extra={"pos": 0})


@verb("cut.remove", RefIn, effect="write")
def cut_remove(ctx: Ctx, inp: RefIn):
    """Delete a cut (refused while a journey uses it)."""
    db = ctx.db
    c = refs.resolve(db, inp.ref, "cut")[1]
    used = db.all("SELECT j.ref FROM slot s JOIN journey j ON j.id=s.journey_id WHERE s.cut_id=?", (c["id"],))
    if used:
        raise RecompError("E_CONFLICT", f"{c['ref']} is used in {', '.join(sorted({u[0] for u in used}))}",
                          hint="Remove it from those journeys first.")
    with ctx.op(f"remove {c['ref']}") as tx:
        tx.delete("cut", c["id"])
    return {"removed": c["ref"]}


@verb("cut.show", RefIn)
def cut_show(ctx: Ctx, inp: RefIn):
    """One cut in full, with the lines around it and the journeys that use it."""
    db = ctx.db
    c = refs.resolve(db, inp.ref, "cut")[1]
    out = brief(db, c)
    out["note"] = c["note"]
    out["snap"] = c["snap"]
    out["journeys"] = sorted({r[0] for r in db.all(
        "SELECT j.ref FROM slot s JOIN journey j ON j.id=s.journey_id WHERE s.cut_id=?", (c["id"],))})
    src = db.get("source", c["source_id"])
    out["before"] = text_between(db, src, max(0, c["start"] - 8), c["start"])[-200:]
    out["after"] = text_between(db, src, c["end"], c["end"] + 8)[:200]
    return out


class TagIn(BaseModel):
    refs_: list[str] = Field(..., alias="refs", description="Cut refs", json_schema_extra={"pos": 0})
    add: list[str] = Field(default_factory=list)
    remove: list[str] = Field(default_factory=list)
    model_config = {"populate_by_name": True}


@verb("cut.tag", TagIn, effect="write", examples=["recomp cut tag C3 C9 --add sacrifice --remove draft"])
def cut_tag(ctx: Ctx, inp: TagIn):
    """Add or remove tags on several cuts at once."""
    db = ctx.db
    out = []
    with ctx.op("tag cuts") as tx:
        for r in inp.refs_:
            c = refs.resolve(db, r, "cut")[1]
            tags = [t for t in c["tags"] if t not in inp.remove]
            tags += [t for t in inp.add if t not in tags]
            out.append(brief(db, tx.update("cut", c["id"], {"tags": tags})))
    return out


class ListIn(BaseModel):
    source: str | None = Field(None, description="Source ref")
    tag: str | None = None
    person: str | None = None
    emotion: str | None = None
    chapter: str | None = None
    match: str | None = Field(None, description="Text in title, why or quote")
    unused: bool = Field(False, description="Only cuts not in any journey")
    journey: str | None = Field(None, description="Only cuts in this journey")
    min: float | None = Field(None, description="Shortest, in seconds")
    max: float | None = Field(None, description="Longest, in seconds")
    by: str | None = Field(None, description="Made by: user, agent or machine")
    rating: int | None = Field(None, description="At least this rating")
    limit: int = 200


@verb("cut.list", ListIn, examples=["recomp cut list --source S1", "recomp cut list --tag sacrifice --unused"])
def cut_list(ctx: Ctx, inp: ListIn):
    """Cuts with spans, titles, why, tags and chapter; filter by source, tag, person, emotion, text, or unused."""
    db = ctx.db
    where, params = [], []
    if inp.source:
        where.append("source_id=?")
        params.append(refs.source(db, inp.source)["id"])
    if inp.tag:
        where.append("tags LIKE ?")
        params.append(f'%"{inp.tag}"%')
    if inp.person:
        where.append("people LIKE ?")
        params.append(f"%{inp.person}%")
    if inp.emotion:
        where.append("emotions LIKE ?")
        params.append(f'%"{inp.emotion}"%')
    if inp.chapter:
        where.append("chapter_id=?")
        params.append(refs.resolve(db, inp.chapter, "chapter")[1]["id"])
    if inp.match:
        where.append("(title LIKE ? OR why LIKE ? OR quote LIKE ?)")
        params += [f"%{inp.match}%"] * 3
    if inp.unused:
        where.append("id NOT IN (SELECT cut_id FROM slot)")
    if inp.journey:
        where.append("id IN (SELECT cut_id FROM slot WHERE journey_id=?)")
        params.append(refs.resolve(db, inp.journey, "journey")[1]["id"])
    if inp.min is not None:
        where.append('("end" - start) >= ?')
        params.append(inp.min)
    if inp.max is not None:
        where.append('("end" - start) <= ?')
        params.append(inp.max)
    if inp.by:
        where.append("created_by=?")
        params.append(inp.by)
    if inp.rating is not None:
        where.append("COALESCE(rating, 0) >= ?")
        params.append(inp.rating)
    rows = db.rows("cut", ("WHERE " + " AND ".join(where) if where else "") + " ORDER BY source_id, start LIMIT ?",
                   (*params, inp.limit))
    out = []
    titles = {r[0]: r[1] for r in db.all("SELECT id, title FROM source")}
    for c in rows:
        b = brief(db, c)
        b["quote"] = (c["quote"] or "")[:140]
        b["source_title"] = titles.get(c["source_id"])
        b["journeys"] = [r[0] for r in db.all("SELECT DISTINCT j.ref FROM slot s JOIN journey j ON j.id=s.journey_id "
                                              "WHERE s.cut_id=? ORDER BY j.ref", (c["id"],))]
        out.append(b)
    return out


class SuggestIn(BaseModel):
    query: str = Field(..., json_schema_extra={"pos": 0})
    sources: list[str] = Field(default_factory=list)
    min_s: float = Field(15, description="Shortest suggestion")
    max_s: float = Field(90, description="Longest suggestion")
    limit: int = 10


@verb("cut.suggest", SuggestIn, examples=['recomp cut suggest "what it costs to be good" --limit 8'])
def cut_suggest(ctx: Ctx, inp: SuggestIn):
    """Turn search hits into whole-thought cut candidates (sentence and pause boundaries, min/max length). Nothing is created."""
    db = ctx.db
    hits, mode = run_search(db, SearchIn(query=inp.query, sources=inp.sources, limit=inp.limit * 3, context=0))
    out, taken = [], []
    for h in hits:
        segs = [dict(r) for r in db.all('SELECT idx, start, "end", text FROM segment WHERE transcript_id=? '
                                        "AND idx BETWEEN ? AND ? ORDER BY idx", (h["transcript_id"], h["idx"] - 12, h["idx"] + 12))]
        pos = next(k for k, s in enumerate(segs) if s["idx"] == h["idx"])
        lo = hi = pos
        while lo > 0 and not segs[lo - 1]["text"].rstrip().endswith((".", "?", "!", '"')) \
                and segs[lo]["start"] - segs[lo - 1]["end"] < 1.2 and segs[hi]["end"] - segs[lo - 1]["start"] < inp.max_s:
            lo -= 1
        while hi + 1 < len(segs) and (segs[hi]["end"] - segs[lo]["start"] < inp.min_s or
                                      not segs[hi]["text"].rstrip().endswith((".", "?", "!", '"'))) \
                and segs[hi + 1]["end"] - segs[lo]["start"] <= inp.max_s and segs[hi + 1]["start"] - segs[hi]["end"] < 2.5:
            hi += 1
        a, b = segs[lo]["start"], segs[hi]["end"]
        if any(x[0] == h["source_id"] and a < x[2] and b > x[1] for x in taken):
            continue
        taken.append((h["source_id"], a, b))
        out.append({"source": h["sref"], "span": f"{clock(a)}–{clock(b)}", "dur": round(b - a, 1), "start": round(a, 3), "end": round(b, 3),
                    "text": " ".join(s["text"] for s in segs[lo:hi + 1])[:600],
                    "cut": f"recomp cut add {h['sref']} --segments {segs[lo]['idx']}..{segs[hi]['idx']} --title \"…\" --why \"…\""})
        if len(out) >= inp.limit:
            break
    return {"query": inp.query, "mode": mode, "candidates": out}
