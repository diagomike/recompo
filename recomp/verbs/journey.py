"""Journeys: authored sequences of cuts (the recipe), with sections and transitions."""

from __future__ import annotations

import json

from pydantic import BaseModel, Field

from ..compose import recipe as R
from ..core import refs
from ..core.timecode import clock, parse
from ..envelope import RecompError, Result
from ..registry import Ctx, verb


def mirror(ctx: Ctx, journey_id: str) -> None:
    j = ctx.db.get("journey", journey_id)
    if j:
        R.write_mirror(ctx.project, ctx.db, j)


def journey_of(db, ref: str) -> dict:
    return refs.resolve(db, ref.split("#")[0], "journey")[1]


def renumber(tx, journey_id: str) -> None:
    for k, s in enumerate(tx.all("SELECT id, pos FROM slot WHERE journey_id=? ORDER BY pos", (journey_id,)), start=1):
        if s["pos"] != float(k):
            tx.update("slot", s["id"], {"pos": float(k)})


def show(db, j: dict) -> dict:
    tl = R.timeline(db, j)
    slots = [{"slot": it["ref"], "cut": it["cut"]["ref"], "source": it["source"]["ref"],
              "source_title": it["source"]["title"], "span": f"{clock(it['in'])}–{clock(it['out'])}",
              "dur": round(it["dur"], 2), "at": clock(it["at"]), "section": it["section"],
              "title": it["cut"]["title"], "why": it["cut"]["why"], "quote": (it["cut"]["quote"] or "")[:160],
              "transition": it["transition"] or None,
              "trimmed": it["in"] != it["cut"]["start"] or it["out"] != it["cut"]["end"]} for it in tl]
    overlays = [{"ref": o["ref"], "kind": o["kind"], "text": o["text"],
                 "slot": next((it["ref"] for it in tl if it["id"] == o["slot_id"]), None), "at": o["at"], "dur": o["dur"]}
                for o in db.rows("overlay", "WHERE journey_id=? ORDER BY at", (j["id"],))]
    beds = []
    for b in db.rows("music_bed", "WHERE journey_id=?", (j["id"],)):
        t = db.get("music_track", b["track_id"])
        beds.append({"ref": b["ref"], "track": t["ref"], "title": t["title"], "artist": t["artist"], "licence": t["licence"],
                     "gain_db": b["gain_db"], "duck_db": b["duck_db"], "file": t["file"]})
    total = tl[-1]["end"] if tl else 0.0
    sources = sorted({it["source"]["ref"] for it in tl})
    formats = (j.get("settings") or {}).get("formats") or []
    return {"ref": j["ref"], "title": j["title"], "intent": j["intent"], "description": j["description"],
            "language": j["language"], "status": j["status"], "duration": clock(total), "duration_s": round(total, 2),
            "slots": slots, "overlays": overlays, "music": beds, "sources": sources, "by": j["created_by"],
            "links": j.get("links") or {}, "formats": formats, "target": target_length(formats)}


# Where a journey is going decides how long it should be and how it is exported. Profiles are formats;
# "hub" shares the recipe (sources and timecodes, no media) with the community hub.
DESTINATIONS = {
    "shorts": {"label": "Shorts, Reels, TikTok", "profile": "shorts", "ideal": (30, 90), "max": 180,
               "note": "Vertical 9:16. One idea, a hook in the first seconds, under 90 s."},
    "landscape": {"label": "YouTube (landscape)", "profile": "landscape", "ideal": (120, 900), "max": None,
                  "note": "16:9 with sections and lower thirds: room for an argument."},
    "square": {"label": "Feeds (square)", "profile": "square", "ideal": (30, 120), "max": 600,
               "note": "1:1 for Instagram, X, LinkedIn feeds."},
    "hub": {"label": "Community hub", "profile": None, "ideal": None, "max": None,
            "note": "Share the recipe: others play it from the original sources, no media copied."},
}


def mmss(s: float) -> str:
    s = int(round(s))
    return f"{s // 60}:{s % 60:02d}"


def target_length(formats: list[str]) -> dict | None:
    """The length that suits every destination chosen (the tightest one wins)."""
    ideals = [DESTINATIONS[f]["ideal"] for f in formats if f in DESTINATIONS and DESTINATIONS[f]["ideal"]]
    maxes = [DESTINATIONS[f]["max"] for f in formats if f in DESTINATIONS and DESTINATIONS[f]["max"]]
    if not ideals:
        return None
    lo, hi = min(i[0] for i in ideals), min(i[1] for i in ideals)
    return {"min_s": lo, "max_s": max(lo, hi), "hard_max_s": min(maxes) if maxes else None}


def _check_formats(formats: list[str]) -> list[str]:
    bad = [f for f in formats if f not in DESTINATIONS]
    if bad:
        raise RecompError("E_INVALID", f"unknown destination(s): {', '.join(bad)}",
                          hint=f"choose from {', '.join(DESTINATIONS)}")
    return formats


class NewIn(BaseModel):
    title: str = Field(..., json_schema_extra={"pos": 0})
    intent: str = Field("", description="What the journey is for, in a sentence")
    description: str = ""
    language: str = "en"
    cuts: list[str] = Field(default_factory=list, description="Cuts to start with, in order")
    formats: list[str] = Field(default_factory=list,
                               description="Where it will go: shorts, landscape, square, hub (sets length goals and export profiles)")


@verb("journey.new", NewIn, effect="write",
      examples=['recomp journey new "Live long enough" --intent "What heroism costs" --cuts C4,C9,C2',
                'recomp journey new "On free will" --intent "Three answers in a minute" --formats shorts,hub'])
def journey_new(ctx: Ctx, inp: NewIn):
    """Start a journey (optionally with its first cuts and where it will go)."""
    db = ctx.db
    cut_rows = [refs.resolve(db, c, "cut")[1] for c in inp.cuts]
    _check_formats(inp.formats)
    with ctx.op(f"new journey {inp.title!r}") as tx:
        j = tx.insert("journey", {"title": inp.title, "intent": inp.intent, "description": inp.description,
                                  "language": inp.language, "settings": {"formats": inp.formats} if inp.formats else {}})
        for k, c in enumerate(cut_rows, start=1):
            tx.insert("slot", {"journey_id": j["id"], "pos": float(k), "cut_id": c["id"]})
    mirror(ctx, j["id"])
    return Result(data=show(db, db.get("journey", j["id"])), refs=[j["ref"]],
                  next=[f"recomp journey add {j['ref']} <cuts>", f"recomp ui show {j['ref']}"])


class AddIn(BaseModel):
    journey: str = Field(..., json_schema_extra={"pos": 0})
    cuts: list[str] = Field(..., description="Cut refs in order", json_schema_extra={"pos": 1})
    at: int | None = Field(None, description="Insert before this slot number (default: append)")
    section: str | None = Field(None, description="Section heading for the first added slot")


@verb("journey.add", AddIn, effect="write", examples=["recomp journey add J1 C3 C9 C4", "recomp journey add J1 C7 --at 2"])
def journey_add(ctx: Ctx, inp: AddIn):
    """Add cuts to a journey (append, or insert before slot --at)."""
    db = ctx.db
    j = journey_of(db, inp.journey)
    cut_rows = [refs.resolve(db, c, "cut")[1] for c in inp.cuts]
    existing = db.rows("slot", "WHERE journey_id=? ORDER BY pos", (j["id"],))
    n = len(existing)
    at = inp.at if inp.at is not None else n + 1
    if not 1 <= at <= n + 1:
        raise RecompError("E_INVALID", f"--at must be between 1 and {n + 1}")
    with ctx.op(f"add {len(cut_rows)} to {j['ref']}") as tx:
        base = existing[at - 2]["pos"] if at > 1 else 0.0
        nxt = existing[at - 1]["pos"] if at <= n else base + len(cut_rows) + 1
        step = (nxt - base) / (len(cut_rows) + 1)
        for k, c in enumerate(cut_rows, start=1):
            fields = {"journey_id": j["id"], "pos": base + step * k, "cut_id": c["id"]}
            if k == 1 and inp.section:
                fields["section"] = inp.section
            tx.insert("slot", fields)
        renumber(tx, j["id"])
    mirror(ctx, j["id"])
    return Result(data=show(db, j), refs=[j["ref"]])


class MoveIn(BaseModel):
    slot: str = Field(..., description="Slot ref, e.g. J1#4", json_schema_extra={"pos": 0})
    to: int = Field(..., description="New position (1-based)")


@verb("journey.move", MoveIn, effect="write", examples=["recomp journey move J1#4 --to 1"])
def journey_move(ctx: Ctx, inp: MoveIn):
    """Move a slot to another position."""
    db = ctx.db
    _, s = refs.resolve(db, inp.slot, "slot")
    j = db.get("journey", s["journey_id"])
    ids = [r["id"] for r in db.all("SELECT id FROM slot WHERE journey_id=? ORDER BY pos", (j["id"],))]
    if not 1 <= inp.to <= len(ids):
        raise RecompError("E_INVALID", f"--to must be between 1 and {len(ids)}")
    ids.remove(s["id"])
    ids.insert(inp.to - 1, s["id"])
    with ctx.op(f"move {inp.slot} → {inp.to}") as tx:
        for k, sid in enumerate(ids, start=1):
            row = db.get("slot", sid)
            if row["pos"] != float(k):
                tx.update("slot", sid, {"pos": float(k)})
    mirror(ctx, j["id"])
    return show(db, j)


class OrderIn(BaseModel):
    journey: str = Field(..., json_schema_extra={"pos": 0})
    order: list[int] = Field(..., description="New order as current slot numbers, e.g. 3,1,2,4")


@verb("journey.reorder", OrderIn, effect="write", examples=["recomp journey reorder J1 --order 3,1,2,4"])
def journey_reorder(ctx: Ctx, inp: OrderIn):
    """Reorder all slots at once."""
    db = ctx.db
    j = journey_of(db, inp.journey)
    ids = [r["id"] for r in db.all("SELECT id FROM slot WHERE journey_id=? ORDER BY pos", (j["id"],))]
    if sorted(inp.order) != list(range(1, len(ids) + 1)):
        raise RecompError("E_INVALID", f"order must be a permutation of 1..{len(ids)}")
    with ctx.op(f"reorder {j['ref']}") as tx:
        for k, n in enumerate(inp.order, start=1):
            if db.get("slot", ids[n - 1])["pos"] != float(k):
                tx.update("slot", ids[n - 1], {"pos": float(k)})
    mirror(ctx, j["id"])
    return show(db, j)


class SlotIn(BaseModel):
    slot: str = Field(..., description="Slot ref, e.g. J1#3", json_schema_extra={"pos": 0})


@verb("journey.remove", SlotIn, effect="write")
def journey_remove(ctx: Ctx, inp: SlotIn):
    """Remove a slot from a journey (the cut itself stays)."""
    db = ctx.db
    _, s = refs.resolve(db, inp.slot, "slot")
    with ctx.op(f"remove {inp.slot}") as tx:
        tx.delete("slot", s["id"])
        renumber(tx, s["journey_id"])
    mirror(ctx, s["journey_id"])
    return show(db, db.get("journey", s["journey_id"]))


class SectionIn(BaseModel):
    journey: str = Field(..., json_schema_extra={"pos": 0})
    heading: str = Field(..., description="Section heading ('' clears it)", json_schema_extra={"pos": 1})
    at: int = Field(..., description="The slot the section starts at")


@verb("journey.section", SectionIn, effect="write", examples=['recomp journey section J1 "The bargain" --at 3'])
def journey_section(ctx: Ctx, inp: SectionIn):
    """Start a titled section at a slot (shown as a heading; long-form exports can show a card)."""
    db = ctx.db
    j = journey_of(db, inp.journey)
    _, s = refs.resolve(db, f"{j['ref']}#{inp.at}", "slot")
    with ctx.op(f"section {j['ref']}#{inp.at}") as tx:
        tx.update("slot", s["id"], {"section": inp.heading})
    mirror(ctx, j["id"])
    return show(db, j)


class TrimSlotIn(BaseModel):
    slot: str = Field(..., json_schema_extra={"pos": 0})
    start: str | None = Field(None, description="Source time, or +/− seconds relative to the cut's start ('reset' clears)")
    end: str | None = Field(None, description="Source time, or +/− relative to the cut's end ('reset' clears)")


@verb("journey.trim-slot", TrimSlotIn, effect="write", examples=["recomp journey trim-slot J1#2 --start +1.5 --end -2"])
def journey_trim_slot(ctx: Ctx, inp: TrimSlotIn):
    """Trim one slot inside its cut (the cut itself is unchanged; other journeys are unaffected)."""
    db = ctx.db
    _, s = refs.resolve(db, inp.slot, "slot")
    cut = db.get("cut", s["cut_id"])

    def val(v, base):
        if v is None:
            return "keep"
        if v == "reset":
            return None
        if v[:1] in "+-" and ":" not in v:
            return base + float(v)
        return parse(v)

    fields = {}
    a = val(inp.start, cut["start"])
    b = val(inp.end, cut["end"])
    if a != "keep":
        fields["trim_in"] = a
    if b != "keep":
        fields["trim_out"] = b
    na = fields.get("trim_in", s["trim_in"]) if "trim_in" in fields else s["trim_in"]
    nb = fields.get("trim_out", s["trim_out"]) if "trim_out" in fields else s["trim_out"]
    na = cut["start"] if na is None else na
    nb = cut["end"] if nb is None else nb
    if nb <= na:
        raise RecompError("E_INVALID", "the slot would be empty")
    with ctx.op(f"trim {inp.slot}") as tx:
        tx.update("slot", s["id"], fields)
    mirror(ctx, s["journey_id"])
    return show(db, db.get("journey", s["journey_id"]))


class TransIn(BaseModel):
    slot: str = Field(..., json_schema_extra={"pos": 0})
    type: str = Field("fade", description="cut | fade | dip (to black)")
    dur: float = Field(0.5, description="Seconds")


@verb("journey.transition", TransIn, effect="write", examples=["recomp journey transition J1#3 --type fade --dur 0.6"])
def journey_transition(ctx: Ctx, inp: TransIn):
    """Set the transition *into* a slot."""
    if inp.type not in ("cut", "fade", "dip"):
        raise RecompError("E_INVALID", "type must be cut, fade or dip")
    db = ctx.db
    _, s = refs.resolve(db, inp.slot, "slot")
    with ctx.op(f"transition {inp.slot}") as tx:
        tx.update("slot", s["id"], {"transition": {} if inp.type == "cut" else {"type": inp.type, "dur": inp.dur}})
    mirror(ctx, s["journey_id"])
    return show(db, db.get("journey", s["journey_id"]))


class RefIn(BaseModel):
    journey: str = Field(..., json_schema_extra={"pos": 0})


@verb("journey.show", RefIn, examples=["recomp journey show J1"])
def journey_show(ctx: Ctx, inp: RefIn):
    """A journey's timeline: slots (source span, output position, section), overlays, music, total length."""
    return show(ctx.db, journey_of(ctx.db, inp.journey))


class ListIn(BaseModel):
    status: str | None = None


@verb("journey.list", ListIn)
def journey_list(ctx: Ctx, inp: ListIn):
    """All journeys with slot counts and lengths."""
    db = ctx.db
    rows = db.rows("journey", ("WHERE status=?" if inp.status else "") + " ORDER BY created_at",
                   (inp.status,) if inp.status else ())
    out = []
    for j in rows:
        tl = R.timeline(db, j)
        out.append({"ref": j["ref"], "title": j["title"], "intent": j["intent"], "slots": len(tl),
                    "duration": clock(tl[-1]["end"] if tl else 0), "sources": sorted({t["source"]["ref"] for t in tl}),
                    "status": j["status"], "by": j["created_by"]})
    return out


class EditIn(BaseModel):
    journey: str = Field(..., json_schema_extra={"pos": 0})
    title: str | None = None
    intent: str | None = None
    description: str | None = None
    language: str | None = None
    status: str | None = Field(None, description="draft | ready | published")
    formats: list[str] | None = Field(None, description="Where it will go: shorts, landscape, square, hub")


@verb("journey.edit", EditIn, effect="write", examples=["recomp journey edit J1 --formats shorts,landscape"])
def journey_edit(ctx: Ctx, inp: EditIn):
    """Change a journey's title, intent, description, language, status or destinations."""
    db = ctx.db
    j = journey_of(db, inp.journey)
    fields = {k: v for k, v in inp.model_dump(exclude={"journey", "formats"}).items() if v is not None}
    if inp.formats is not None:
        fields["settings"] = {**(j.get("settings") or {}), "formats": _check_formats(inp.formats)}
    with ctx.op(f"edit {j['ref']}") as tx:
        tx.update("journey", j["id"], fields)
    mirror(ctx, j["id"])
    return show(db, db.get("journey", j["id"]))


@verb("journey.duplicate", RefIn, effect="write")
def journey_duplicate(ctx: Ctx, inp: RefIn):
    """Copy a journey (slots, overlays and music) to try a variation."""
    db = ctx.db
    j = journey_of(db, inp.journey)
    with ctx.op(f"duplicate {j['ref']}") as tx:
        new = tx.insert("journey", {k: j[k] for k in ("intent", "description", "language", "settings")}
                        | {"title": j["title"] + " (copy)"})
        slot_map = {}
        for s in db.rows("slot", "WHERE journey_id=? ORDER BY pos", (j["id"],)):
            ns = tx.insert("slot", {k: s[k] for k in ("pos", "cut_id", "trim_in", "trim_out", "section", "transition", "settings")}
                           | {"journey_id": new["id"]})
            slot_map[s["id"]] = ns["id"]
        for o in db.rows("overlay", "WHERE journey_id=?", (j["id"],)):
            tx.insert("overlay", {k: o[k] for k in ("kind", "text", "style", "at", "dur")}
                      | {"journey_id": new["id"], "slot_id": slot_map.get(o["slot_id"])})
        for b in db.rows("music_bed", "WHERE journey_id=?", (j["id"],)):
            tx.insert("music_bed", {k: b[k] for k in ("track_id", "at", "track_in", "dur", "gain_db", "duck_db", "fade_in", "fade_out")}
                      | {"journey_id": new["id"]})
    mirror(ctx, new["id"])
    return Result(data=show(db, db.get("journey", new["id"])), refs=[new["ref"]])


@verb("journey.delete", RefIn, effect="write")
def journey_delete(ctx: Ctx, inp: RefIn):
    """Delete a journey (its cuts stay). Undo restores it."""
    db = ctx.db
    j = journey_of(db, inp.journey)
    with ctx.op(f"delete {j['ref']}") as tx:
        tx.delete("journey", j["id"])
    for old in ctx.project.dir("recipes").glob(f"{j['ref']}-*.recipe.json"):
        old.unlink()
    return {"deleted": j["ref"]}


class FromSearchIn(BaseModel):
    query: str = Field(..., json_schema_extra={"pos": 0})
    title: str | None = None
    limit: int = Field(8, description="How many cuts")
    sources: list[str] = Field(default_factory=list)
    min_s: float = 15
    max_s: float = 75


@verb("journey.from-search", FromSearchIn, effect="write",
      examples=['recomp journey from-search "forgiveness" --limit 8 --title "On forgiveness"'])
def journey_from_search(ctx: Ctx, inp: FromSearchIn):
    """Draft a journey from search: whole-thought cuts for the best hits, in search order. Edit it afterwards."""
    from .cut import SuggestIn, cut_suggest
    sug = cut_suggest(ctx, SuggestIn(query=inp.query, sources=inp.sources, limit=inp.limit, min_s=inp.min_s, max_s=inp.max_s))
    if not sug["candidates"]:
        raise RecompError("E_NOT_FOUND", f"nothing found for {inp.query!r}")
    db = ctx.db
    import re as _re
    with ctx.op(f"draft journey from {inp.query!r}") as tx:
        j = tx.insert("journey", {"title": inp.title or inp.query.title(), "intent": f"Drafted from search: {inp.query}"})
        for k, c in enumerate(sug["candidates"], start=1):
            m = _re.search(r"recomp cut add (\S+) --segments (\d+)\.\.(\d+)", c["cut"])
            src = refs.source(db, m.group(1))
            from ..transcript.store import primary
            tr = primary(db, src["id"])
            a = db.one("SELECT start FROM segment WHERE transcript_id=? AND idx=?", (tr["id"], int(m.group(2))))[0]
            b = db.one('SELECT "end" FROM segment WHERE transcript_id=? AND idx=?', (tr["id"], int(m.group(3))))[0]
            from ..edit import snap as S
            na, nb, info = S.snap_range(a, b, S.load_words(db, tr), [], "words", duration=src["duration"])
            from .cut import text_between
            q = text_between(db, src, na, nb)
            cut = tx.insert("cut", {"source_id": src["id"], "start": na, "end": nb, "title": q[:60], "quote": q,
                                    "why": f"search: {inp.query}", "tags": ["draft"], "snap": info})
            tx.insert("slot", {"journey_id": j["id"], "pos": float(k), "cut_id": cut["id"]})
    mirror(ctx, j["id"])
    return Result(data=show(db, db.get("journey", j["id"])), refs=[j["ref"]],
                  warnings=["Draft cuts are tagged 'draft' with placeholder titles: retitle them and say why each matters."])


@verb("journey.validate", RefIn)
def journey_validate(ctx: Ctx, inp: RefIn):
    """Check a journey before export: media available, sane lengths, labels, music licences, recipe structure."""
    return validate(ctx.db, journey_of(ctx.db, inp.journey))


def validate(db, j: dict) -> dict:
    tl = R.timeline(db, j)
    problems, notes = [], []
    if not tl:
        problems.append("no slots")
    from pathlib import Path
    from ..core import config
    links_noted = set()
    for it in tl:
        src = it["source"]
        if src["kind"] == "file" and not (src["path"] and Path(src["path"]).exists()):
            problems.append(f"{it['ref']}: media for {src['ref']} is missing (relink it)")
        if src["kind"] == "link" and src["id"] not in links_noted and not (src["path"] and Path(src["path"]).exists()):
            links_noted.add(src["id"])
            got = db.one("SELECT path FROM asset WHERE source_id=? AND role='video'", (src["id"],))
            if (config.get("network.link_video") or "full") != "full":
                notes.append(f"{src['ref']} is a link; export downloads only each slot's range")
            elif not (got and Path(got["path"]).exists()):
                notes.append(f"{src['ref']} is a link; export downloads its whole video once "
                             f"(`recomp source fetch-video {src['ref']}` does it now)")
        if it["dur"] < 1.5:
            problems.append(f"{it['ref']}: only {it['dur']:.1f}s")
        if not it["cut"]["why"]:
            notes.append(f"{it['ref']}: cut {it['cut']['ref']} has no 'why'")
    total = tl[-1]["end"] if tl else 0
    formats = (j.get("settings") or {}).get("formats") or []
    for f in formats:
        d = DESTINATIONS.get(f) or {}
        if tl and d.get("max") and total > d["max"]:
            notes.append(f"{mmss(total)} is longer than {d['label']} allow ({mmss(d['max'])}): shorten it or drop {f}")
        elif tl and d.get("ideal") and not d["ideal"][0] <= total <= d["ideal"][1]:
            lo, hi = d["ideal"]
            notes.append(f"{d['label']} work best at {lo}–{hi} s; this is {round(total)} s")
    if not formats and total > 180:
        notes.append(f"{clock(total)} long: fine for landscape; shorts profiles cap at 3 min")
    for b in db.rows("music_bed", "WHERE journey_id=?", (j["id"],)):
        t = db.get("music_track", b["track_id"])
        if not t["licence"]:
            problems.append(f"music {t['ref']} has no licence recorded")
    rec = R.build(db, j)
    problems += R.validate(rec)
    return {"journey": j["ref"], "ok": not problems, "problems": problems, "notes": notes,
            "duration": clock(total), "hash": rec["hash"]}


STEPS = ("purpose", "gather", "order", "look", "check", "export")
REVIEWED = ("order", "look", "check")  # judgement calls: done when the person (or agent) says so


def guide(ctx: Ctx, j: dict) -> dict:
    """The guided flow for one journey: six steps, each with its state, what is done, and the next action."""
    db = ctx.db
    ref = j["ref"]
    tl = R.timeline(db, j)
    n = len(tl)
    srcs = sorted({it["source"]["ref"] for it in tl})
    total = tl[-1]["end"] if tl else 0.0
    settings = j.get("settings") or {}
    formats = settings.get("formats") or []
    reviewed = set(settings.get("reviewed") or [])
    target = target_length(formats)
    sections = sum(1 for it in tl if it["section"])
    kinds = [o["kind"] for o in db.rows("overlay", "WHERE journey_id=?", (j["id"],))]
    beds = db.rows("music_bed", "WHERE journey_id=?", (j["id"],))
    exps = db.rows("export", "WHERE journey_id=? ORDER BY created_at DESC", (j["id"],))
    previews = [e for e in exps if "preview-" in (e["folder"] or "")]
    finals = [e for e in exps if "preview-" not in (e["folder"] or "")]
    steps: list[dict] = []

    def step(key, title, state, detail, hint, actions=(), agent=""):
        steps.append({"key": key, "n": len(steps) + 1, "title": title, "state": state, "detail": detail, "hint": hint,
                      "actions": list(actions), "agent": agent, "reviewed": key in reviewed})

    def act(label, verb_, args):
        return {"label": label, "verb": verb_, "args": args}

    where = ", ".join(DESTINATIONS[f]["label"] for f in formats if f in DESTINATIONS)
    step("purpose", "Purpose", "done" if j["intent"] and formats else "partial" if j["intent"] or formats else "todo",
         (j["intent"] or "No intent yet") + (f" · for {where}" if where else ""),
         "Say in one sentence what it is for and where people will see it: that sets the length goal, the suggestions "
         "and the export formats.",
         [] if formats else [act("For Shorts and the hub", "journey.edit", {"journey": ref, "formats": ["shorts", "hub"]})],
         f"Help me phrase what {ref} is for")

    length = mmss(total) + (f" of {target['min_s']}–{target['max_s']} s" if target else "")
    step("gather", "Gather cuts", "done" if n >= 2 else "partial" if n else "todo",
         f"{n} cut(s) from {len(srcs)} source(s) · {length}" if n else "No cuts yet",
         "Pick moments from any of your sources: suggestions for the intent, the cut bin, or cut new ones in a source room.",
         [act("Suggest cuts for the intent", "cut.suggest", {"query": j["intent"] or j["title"], "limit": 8})],
         f"Find cuts for {ref} ({j['intent'] or j['title']}) across my sources and add the best ones")

    step("order", "Order", "done" if n >= 2 and ("order" in reviewed or sections) else "todo" if n < 2 else "partial",
         f"{n} slot(s)" + (f", {sections} section(s)" if sections else "") if n else "Nothing to order yet",
         "Drag the cuts into the order that tells it best. Sections help longer journeys.",
         [act("Order looks right", "journey.review", {"journey": ref, "step": "order"})] if n >= 2 else [],
         f"Put {ref}'s cuts in the strongest order")

    have = {"title card": "title" in kinds, "lower thirds": "lower_third" in kinds, "music": bool(beds)}
    got = [k for k, v in have.items() if v]
    step("look", "Look", "done" if "look" in reviewed or all(have.values()) else "partial" if got else "todo",
         ("Has " + ", ".join(got) if got else "Plain cuts") + (f"; no {', '.join(k for k, v in have.items() if not v)}"
                                                               if len(got) < 3 else ""),
         "A title card, who-is-speaking lower thirds and a quiet music bed. All optional.",
         [act("Lower thirds", "overlay.auto-lower-thirds", {"journey": ref})]
         + [act("Looks good", "journey.review", {"journey": ref, "step": "look"})],
         f"Give {ref} a title card, lower thirds and a fitting music bed")

    chk = validate(db, j) if tl else {"ok": False, "problems": ["no slots"], "notes": []}
    pdone = [e for e in previews if e["status"] == "done"]
    step("check", "Check", "todo" if not tl else "problem" if not chk["ok"] else "done" if pdone or "check" in reviewed
         else "partial",
         "Nothing to check yet" if not tl else ("; ".join(chk["problems"]) if not chk["ok"] else
          "Ready to export" + (" · preview watched" if pdone else " · no preview yet")),
         "Validate the journey and watch a quick low-resolution preview before the real render.",
         [act("Preview", "preview", {"target": ref, "profile": (formats[0] if formats and formats[0] != "hub" else "landscape")})],
         f"Check {ref} and tell me what to fix before export")

    profs = [DESTINATIONS[f]["profile"] for f in formats if DESTINATIONS.get(f, {}).get("profile")] or ["landscape"]
    fdone = [e for e in finals if e["status"] == "done"]
    frun = [e for e in finals if e["status"] in ("queued", "rendering")]
    shared = bool((j.get("links") or {}).get("hub"))
    step("export", "Export & share", "done" if fdone and ("hub" not in formats or shared) else "running" if frun
         else "partial" if fdone else "todo",
         (f"{len(fdone)} export(s) done" if fdone else "Not exported yet") + (f", {len(frun)} rendering" if frun else "")
         + (" · on the hub" if shared else ""),
         "Render for each destination (and language). Each export has captions and a ready-to-paste description with credits.",
         [act("Export " + ", ".join(profs), "export.run", {"journey": ref, "profiles": profs})]
         + ([act("Share on the hub", "hub.publish", {"journey": ref})] if "hub" in formats and not shared else []),
         f"Export {ref} as {', '.join(profs)}")

    nxt = next((s["key"] for s in steps if s["state"] != "done"), None)
    return {"journey": ref, "title": j["title"], "intent": j["intent"], "formats": formats, "target": target,
            "duration_s": round(total, 2), "slots": n, "sources": srcs, "steps": steps, "next": nxt,
            "done": sum(1 for s in steps if s["state"] == "done"), "notes": chk.get("notes", []),
            "destinations": {k: {x: v[x] for x in ("label", "profile", "note")} for k, v in DESTINATIONS.items()}}


@verb("journey.guide", RefIn, examples=["recomp journey guide J1"])
def journey_guide(ctx: Ctx, inp: RefIn):
    """The guided flow for a journey — purpose → gather → order → look → check → export — with each step's state and
    next action. The viewer's journey studio shows the same steps (`recomp ui show J1 --filter step=look`)."""
    return guide(ctx, journey_of(ctx.db, inp.journey))


class ReviewIn(BaseModel):
    journey: str = Field(..., json_schema_extra={"pos": 0})
    step: str = Field(..., description="order | look | check", json_schema_extra={"pos": 1})
    done: bool = Field(True, description="false reopens the step")


@verb("journey.review", ReviewIn, effect="write", examples=["recomp journey review J1 look"])
def journey_review(ctx: Ctx, inp: ReviewIn):
    """Mark a judgement step of the guided flow as reviewed (the order reads well, the look is right, the check is
    enough without a preview), so the guide moves on."""
    if inp.step not in REVIEWED:
        raise RecompError("E_INVALID", f"step must be one of {', '.join(REVIEWED)}",
                          hint="purpose, gather and export are done by doing them")
    db = ctx.db
    j = journey_of(db, inp.journey)
    settings = j.get("settings") or {}
    reviewed = [s for s in settings.get("reviewed") or [] if s != inp.step] + ([inp.step] if inp.done else [])
    with ctx.op(f"{'review' if inp.done else 'reopen'} {inp.step} of {j['ref']}") as tx:
        tx.update("journey", j["id"], {"settings": {**settings, "reviewed": reviewed}})
    return guide(ctx, db.get("journey", j["id"]))


@verb("recipe.show", RefIn, examples=["recomp recipe show J1"])
def recipe_show(ctx: Ctx, inp: RefIn):
    """The journey as a recipe (portable JSON: sources, timecodes, overlays, music, credits)."""
    db = ctx.db
    return R.build(db, journey_of(db, inp.journey), ctx.project.meta)


class RecipeOutIn(BaseModel):
    journey: str = Field(..., json_schema_extra={"pos": 0})
    format: str = Field("json", description="json | edl (CMX3600) | otio (OpenTimelineIO)")
    out: str | None = Field(None, description="Write to this file (default: recipes/ folder)")


@verb("recipe.export", RecipeOutIn, effect="write", examples=["recomp recipe export J1 --format otio"])
def recipe_export(ctx: Ctx, inp: RecipeOutIn):
    """Write the recipe as JSON, a CMX3600 EDL or an OpenTimelineIO file (to finish in Resolve/Premiere/Kdenlive)."""
    from ..compose import interchange
    db = ctx.db
    j = journey_of(db, inp.journey)
    rec = R.build(db, j, ctx.project.meta)
    if inp.format == "json":
        text, ext = json.dumps(rec, indent=2, ensure_ascii=False), "recipe.json"
    elif inp.format == "edl":
        text, ext = interchange.edl(db, j), "edl"
    elif inp.format == "otio":
        text, ext = interchange.otio(db, j), "otio"
    else:
        raise RecompError("E_INVALID", "format must be json, edl or otio")
    from pathlib import Path
    path = Path(inp.out) if inp.out else ctx.project.dir("recipes") / f"{j['ref']}-{R.slug(j['title'])}.{ext}"
    path.write_text(text, encoding="utf-8")
    return {"path": str(path), "format": inp.format, "bytes": len(text.encode("utf-8"))}


class ImportIn(BaseModel):
    file: str = Field(..., description="A recipe JSON file", json_schema_extra={"pos": 0})


@verb("recipe.import", ImportIn, effect="write")
def recipe_import(ctx: Ctx, inp: ImportIn):
    """Rebuild a journey from a recipe file: link sources are added; file sources are matched by fingerprint or title."""
    from ..compose.importer import import_recipe
    from pathlib import Path
    rec = json.loads(Path(inp.file).read_text(encoding="utf-8"))
    return import_recipe(ctx, rec)
