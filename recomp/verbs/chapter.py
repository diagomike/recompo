"""Chapters: the map of each source (scenes for films, topics for conversations)."""

from __future__ import annotations

import bisect

from pydantic import BaseModel, Field

from ..core import refs
from ..core.store import RANK, top_rank
from ..core.timecode import clock, parse
from ..envelope import RecompError, Result
from ..registry import Ctx, verb
from ..transcript.store import primary


def _seg_starts(db, src: dict) -> list[float]:
    tr = primary(db, src["id"])
    if not tr:
        return []
    return [r[0] for r in db.all("SELECT start FROM segment WHERE transcript_id=? ORDER BY idx", (tr["id"],))]


def snap_boundary(t: float, starts: list[float], reach: float = 6.0) -> float:
    """Move a chapter boundary to the nearest segment start, but never across speech."""
    if not starts:
        return t
    k = bisect.bisect_left(starts, t)
    cands = [s for s in starts[max(0, k - 1):k + 1] if abs(s - t) <= reach]
    return min(cands, key=lambda s: abs(s - t)) if cands else t


def brief(c: dict) -> dict:
    return {"ref": c["ref"], "start": round(c["start"], 2), "end": round(c["end"], 2),
            "span": f"{clock(c['start'])}–{clock(c['end'])}", "title": c["title"], "summary": c["summary"],
            "tags": c["tags"], "by": c["created_by"], "method": c["method"]}


class ChapterItem(BaseModel):
    start: str | float
    end: str | float | None = None
    title: str = ""
    summary: str = ""
    tags: list[str] = Field(default_factory=list)


class SetIn(BaseModel):
    ref: str = Field(..., description="Source ref", json_schema_extra={"pos": 0})
    items: list[ChapterItem] = Field(..., description="Chapters (use --input chapters.json: a list or {items: [...]})")
    snap: bool = Field(True, description="Snap boundaries to transcript segment starts")
    method: str = Field("written", description="written | seed | auto")


@verb("chapter.set", SetIn, effect="write",
      examples=["recomp chapter set S1 --input chapters.json"])
def chapter_set(ctx: Ctx, inp: SetIn):
    """Replace a source's chapters in bulk (chapters the user wrote are kept and reported). Ends default to the next chapter's start."""
    db = ctx.db
    src = refs.source(db, inp.ref)
    starts = _seg_starts(db, src) if inp.snap else []
    dur = src["duration"] or 0
    items = sorted(inp.items, key=lambda x: parse(x.start) or 0)
    rows = []
    for k, it in enumerate(items):
        a = parse(it.start) or 0.0
        b = parse(it.end) if it.end is not None else (parse(items[k + 1].start) if k + 1 < len(items) else dur)
        if starts:
            a = snap_boundary(a, starts)
            if it.end is None and k + 1 < len(items):
                b = snap_boundary(b, starts)
        if b is None or b <= a:
            raise RecompError("E_INVALID", f"chapter {k + 1} ({it.title!r}) ends before it starts")
        rows.append({"start": round(a, 3), "end": round(min(b, dur) if dur else b, 3), "title": it.title.strip(),
                     "summary": it.summary.strip(), "tags": it.tags})
    kept = []
    with ctx.op(f"chapters {src['ref']} ({len(rows)})") as tx:
        for old in db.rows("chapter", "WHERE source_id=?", (src["id"],)):
            if top_rank(old) > RANK.get(ctx.actor, 0):
                kept.append(old["ref"])
                continue
            tx.delete("chapter", old["id"])
        made = [tx.insert("chapter", dict(r, source_id=src["id"], method=inp.method), ref_kind=f"{src['ref']}.c")
                for r in rows]
        status = dict(src["status"] or {})
        status["chapters"] = "done"
        tx.update("source", src["id"], {"status": status}, log=False)
    warnings = [f"kept chapters written by a higher-precedence actor: {', '.join(kept)}"] if kept else []
    return Result(data=[brief(c) for c in made], refs=[c["ref"] for c in made], warnings=warnings,
                  next=[f"recomp ui show {made[0]['ref']}" if made else "", f"recomp cut suggest \"<theme>\" --sources {src['ref']}"])


class AddIn(BaseModel):
    ref: str = Field(..., description="Source ref", json_schema_extra={"pos": 0})
    start: str = Field(..., description="Start time")
    end: str = Field(..., description="End time")
    title: str = ""
    summary: str = ""
    tags: list[str] = Field(default_factory=list)


@verb("chapter.add", AddIn, effect="write")
def chapter_add(ctx: Ctx, inp: AddIn):
    """Add one chapter."""
    src = refs.source(ctx.db, inp.ref)
    a, b = parse(inp.start), parse(inp.end)
    if b <= a:
        raise RecompError("E_INVALID", "end must be after start")
    with ctx.op(f"chapter {src['ref']}") as tx:
        c = tx.insert("chapter", {"source_id": src["id"], "start": a, "end": b, "title": inp.title,
                                  "summary": inp.summary, "tags": inp.tags}, ref_kind=f"{src['ref']}.c")
    return Result(data=brief(c), refs=[c["ref"]])


class EditIn(BaseModel):
    ref: str = Field(..., description="Chapter ref, e.g. S1.c4", json_schema_extra={"pos": 0})
    start: str | None = None
    end: str | None = None
    title: str | None = None
    summary: str | None = None
    tags: list[str] | None = None


@verb("chapter.edit", EditIn, effect="write")
def chapter_edit(ctx: Ctx, inp: EditIn):
    """Change a chapter's span, title, summary or tags."""
    c = refs.resolve(ctx.db, inp.ref, "chapter")[1]
    fields = {k: v for k, v in {"title": inp.title, "summary": inp.summary, "tags": inp.tags}.items() if v is not None}
    if inp.start is not None:
        fields["start"] = parse(inp.start)
    if inp.end is not None:
        fields["end"] = parse(inp.end)
    with ctx.op(f"edit {c['ref']}") as tx:
        c = tx.update("chapter", c["id"], fields)
    return brief(c)


class RefIn(BaseModel):
    ref: str = Field(..., json_schema_extra={"pos": 0})


@verb("chapter.remove", RefIn, effect="write")
def chapter_remove(ctx: Ctx, inp: RefIn):
    """Delete a chapter."""
    c = refs.resolve(ctx.db, inp.ref, "chapter")[1]
    with ctx.op(f"remove {c['ref']}") as tx:
        tx.delete("chapter", c["id"])
    return {"removed": c["ref"]}


class SplitIn(BaseModel):
    ref: str = Field(..., json_schema_extra={"pos": 0})
    at: str = Field(..., description="Time to split at")
    title: str = Field("", description="Title for the second half")


@verb("chapter.split", SplitIn, effect="write")
def chapter_split(ctx: Ctx, inp: SplitIn):
    """Split a chapter in two at a time."""
    db = ctx.db
    c = refs.resolve(db, inp.ref, "chapter")[1]
    t = parse(inp.at)
    if not c["start"] < t < c["end"]:
        raise RecompError("E_INVALID", f"{inp.at} is outside {c['ref']}")
    src = db.get("source", c["source_id"])
    with ctx.op(f"split {c['ref']}") as tx:
        tx.update("chapter", c["id"], {"end": t})
        new = tx.insert("chapter", {"source_id": c["source_id"], "start": t, "end": c["end"], "title": inp.title,
                                    "summary": "", "tags": c["tags"]}, ref_kind=f"{src['ref']}.c")
    return [brief(db.get("chapter", c["id"])), brief(new)]


class MergeIn(BaseModel):
    ref: str = Field(..., description="First chapter", json_schema_extra={"pos": 0})
    other: str = Field(..., description="The chapter to absorb", json_schema_extra={"pos": 1})


@verb("chapter.merge", MergeIn, effect="write")
def chapter_merge(ctx: Ctx, inp: MergeIn):
    """Merge two chapters of the same source (the first keeps its title)."""
    db = ctx.db
    a = refs.resolve(db, inp.ref, "chapter")[1]
    b = refs.resolve(db, inp.other, "chapter")[1]
    if a["source_id"] != b["source_id"]:
        raise RecompError("E_INVALID", "chapters belong to different sources")
    with ctx.op(f"merge {a['ref']}+{b['ref']}") as tx:
        tx.update("chapter", a["id"], {"start": min(a["start"], b["start"]), "end": max(a["end"], b["end"]),
                                       "summary": (a["summary"] + " " + b["summary"]).strip()})
        tx.delete("chapter", b["id"])
    return brief(db.get("chapter", a["id"]))


class ListIn(BaseModel):
    ref: str | None = Field(None, description="Source ref (default: all sources)", json_schema_extra={"pos": 0})
    tag: str | None = None


@verb("chapter.list", ListIn)
def chapter_list(ctx: Ctx, inp: ListIn):
    """Chapters of one source (or all), with spans, titles, summaries and tags."""
    db = ctx.db
    where, params = [], []
    if inp.ref:
        where.append("source_id=?")
        params.append(refs.source(db, inp.ref)["id"])
    if inp.tag:
        where.append("tags LIKE ?")
        params.append(f'%"{inp.tag}"%')
    rows = db.rows("chapter", ("WHERE " + " AND ".join(where) if where else "") + " ORDER BY source_id, start", params)
    return [brief(c) for c in rows]


class SeedIn(BaseModel):
    ref: str = Field(..., json_schema_extra={"pos": 0})


@verb("chapter.seed", SeedIn, effect="write")
def chapter_seed(ctx: Ctx, inp: SeedIn):
    """Import the chapters the creator published (YouTube chapters, or chapters embedded in the file)."""
    db = ctx.db
    src = refs.source(db, inp.ref)
    meta = src["meta"] or {}
    raw = meta.get("chapters") or meta.get("embedded_chapters") or []
    if not raw:
        raise RecompError("E_NOT_FOUND", f"{src['ref']} has no creator or embedded chapters",
                          hint=f"Write them: `recomp transcript outline {src['ref']}`, then `recomp chapter set`.")
    items = [ChapterItem(start=c.get("start_time", c.get("start", 0)), end=c.get("end_time", c.get("end")),
                         title=c.get("title", "")) for c in raw]
    ctx.verb_name = "chapter.set"
    return chapter_set(ctx, SetIn(ref=inp.ref, items=items, snap=False, method="seed"))


class AutoIn(BaseModel):
    ref: str = Field(..., json_schema_extra={"pos": 0})
    target_min: float = Field(0, description="Target chapter length in minutes (default: 5 for films, 8 for talks)")


@verb("chapter.auto", AutoIn, effect="write")
def chapter_auto(ctx: Ctx, inp: AutoIn):
    """Machine draft chapters from pauses and shot rhythm (titles are placeholders: rewrite them)."""
    db = ctx.db
    src = refs.source(db, inp.ref)
    tr = primary(db, src["id"])
    if not tr:
        raise RecompError("E_NOT_FOUND", "no transcript")
    segs = [dict(r) for r in db.all('SELECT idx, start, "end", text FROM segment WHERE transcript_id=? ORDER BY idx', (tr["id"],))]
    dur = src["duration"] or (segs[-1]["end"] if segs else 0)
    kind = ctx.project.meta.get("kind")
    target = (inp.target_min or (5 if kind == "movies" else 8)) * 60
    gaps = [(y["start"] - x["end"], y["start"]) for x, y in zip(segs, segs[1:])]
    bounds = [0.0]
    while bounds[-1] + target * 1.5 < dur:
        lo, hi = bounds[-1] + target * 0.6, bounds[-1] + target * 1.4
        cands = [(g, t) for g, t in gaps if lo <= t <= hi]
        if not cands:
            bounds.append(bounds[-1] + target)
            continue
        bounds.append(max(cands)[1])
    items = []
    for k, a in enumerate(bounds):
        first = next((s["text"] for s in segs if s["start"] >= a), "")
        items.append(ChapterItem(start=a, title=f"Part {k + 1}: {first[:50]}", summary="(draft)"))
    actor = ctx.actor
    ctx.actor = "machine"
    try:
        return chapter_set(ctx, SetIn(ref=inp.ref, items=items, method="auto"))
    finally:
        ctx.actor = actor
