"""Speakers and people: diarise sources, name voices, recognise the same person across sources."""

from __future__ import annotations

import json
import re

from pydantic import BaseModel, Field

from ..core import refs
from ..core.timecode import clock
from ..envelope import RecompError, Result
from ..registry import Ctx, NoInput, verb
from ..speakers import people
from ..workers import jobs


class DiarizeIn(BaseModel):
    ref: str = Field(..., description="Source ref", json_schema_extra={"pos": 0})
    speakers: int | None = Field(None, description="Exact number of speakers, if known")
    min: int | None = None
    max: int | None = None
    on: str | None = Field(None, description="local or remote (default: config worker.default_backend)")


@verb("speaker.diarize", DiarizeIn, effect="heavy", examples=["recomp speaker diarize S2 --speakers 2"])
def speaker_diarize(ctx: Ctx, inp: DiarizeIn):
    """Find who speaks when (pyannote, local) and label transcript lines; known people are recognised automatically."""
    s = refs.source(ctx.db, inp.ref)
    params = {k: v for k, v in {"speakers": inp.speakers, "min": inp.min, "max": inp.max}.items() if v}
    j = jobs.enqueue(ctx.db, "diarize", target=s["ref"], source_id=s["id"], params=params, backend=jobs.backend(inp.on))
    mode = jobs.kick(ctx.project)
    return Result(data={"job": j["ref"], "runner": mode}, job=j["ref"], next=[f"recomp job wait {j['ref']} --timeout 120",
                                                                             f"recomp speaker list {s['ref']}"])


class ListIn(BaseModel):
    ref: str | None = Field(None, description="Source ref (default: all)", json_schema_extra={"pos": 0})


@verb("speaker.list", ListIn)
def speaker_list(ctx: Ctx, inp: ListIn):
    """Voices per source (label, seconds, linked person, match score, a sample line) and the people in the project."""
    db = ctx.db
    where, params = "", ()
    if inp.ref:
        where, params = "WHERE sl.source_id=?", (refs.source(db, inp.ref)["id"],)
    out = []
    for r in db.all(f"SELECT sl.*, s.ref AS sref FROM speaker_label sl JOIN source s ON s.id=sl.source_id {where} "
                    "ORDER BY s.ref, sl.seconds DESC", params):
        p = db.get("person", r["person_id"]) if r["person_id"] else None
        sample = db.one("SELECT seg.idx, seg.start, seg.text FROM segment seg JOIN transcript t ON t.id=seg.transcript_id "
                        "WHERE t.source_id=? AND t.is_primary=1 AND seg.speaker=? AND length(seg.text) > 30 "
                        "ORDER BY seg.idx LIMIT 1", (r["source_id"], r["label"]))
        out.append({"voice": f"{r['sref']}:{r['label']}", "seconds": r["seconds"], "minutes": round((r["seconds"] or 0) / 60, 1),
                    "person": {"ref": p["ref"], "name": p["name"]} if p else None, "score": r["score"],
                    "linked_by": json.loads(r["prov"] or "{}").get("person_id") or None,
                    "sample": {"at": clock(sample["start"]), "idx": sample["idx"], "text": sample["text"][:120]} if sample else None})
    persons = [{"ref": p["ref"], "name": p["name"], "aliases": p["aliases"],
                "voices": db.scalar("SELECT COUNT(*) FROM speaker_label WHERE person_id=?", (p["id"],))}
               for p in db.rows("person", "ORDER BY name")]
    return {"voices": out, "people": persons}


def _voice(db, voice: str) -> tuple[dict, dict]:
    if ":" not in voice:
        raise RecompError("E_INVALID", "a voice looks like S2:SPEAKER_00 (from `speaker list`)")
    sref, label = voice.split(":", 1)
    s = refs.source(db, sref)
    row = db.rows("speaker_label", "WHERE source_id=? AND label=?", (s["id"], label))
    if not row:
        raise RecompError("E_NOT_FOUND", f"{voice} not found", hint=f"`recomp speaker list {sref}`")
    return s, row[0]


class NameIn(BaseModel):
    voice: str = Field(..., description="Voice, e.g. S2:SPEAKER_00", json_schema_extra={"pos": 0})
    name: str = Field(..., description="The person's name", json_schema_extra={"pos": 1})
    propagate: bool = Field(True, description="Recognise this person in other sources' voices")


@verb("speaker.name", NameIn, effect="write", examples=['recomp speaker name S2:SPEAKER_01 "Alex O\'Connor"'])
def speaker_name(ctx: Ctx, inp: NameIn):
    """Say who a voice is. The person is created if new; their voice is then recognised in other sources."""
    db = ctx.db
    s, lab = _voice(db, inp.voice)
    with ctx.op(f"name {inp.voice} = {inp.name}") as tx:
        p = db.rows("person", "WHERE lower(name)=lower(?)", (inp.name,))
        person = p[0] if p else tx.insert("person", {"name": inp.name})
        tx.update("speaker_label", lab["id"], {"person_id": person["id"], "score": 1.0})
        n = people.apply_person(tx, db, s["id"], lab["label"], person["id"])
        matched = people.match_all(ctx.project, db, tx) if inp.propagate else []
    return Result(data={"person": {"ref": person["ref"], "name": person["name"]}, "segments": n, "recognised_elsewhere": matched},
                  refs=[person["ref"]])


@verb("speaker.match", NoInput, effect="write")
def speaker_match(ctx: Ctx, inp: NoInput):
    """Re-run recognition: link unnamed voices to known people when they sound alike enough."""
    with ctx.op("match speakers") as tx:
        return {"matched": people.match_all(ctx.project, ctx.db, tx)}


class UnlinkIn(BaseModel):
    voice: str = Field(..., json_schema_extra={"pos": 0})


@verb("speaker.unlink", UnlinkIn, effect="write")
def speaker_unlink(ctx: Ctx, inp: UnlinkIn):
    """Remove a wrong person link from a voice."""
    db = ctx.db
    s, lab = _voice(db, inp.voice)
    with ctx.op(f"unlink {inp.voice}") as tx:
        tx.update("speaker_label", lab["id"], {"person_id": None, "score": None})
        people.apply_person(tx, db, s["id"], lab["label"], None)
    return {"unlinked": inp.voice}


class MergeIn(BaseModel):
    person: str = Field(..., description="Person to keep (P1)", json_schema_extra={"pos": 0})
    other: str = Field(..., description="Person to merge into it", json_schema_extra={"pos": 1})


@verb("speaker.merge", MergeIn, effect="write")
def speaker_merge(ctx: Ctx, inp: MergeIn):
    """Merge two people who are the same person."""
    db = ctx.db
    a = refs.resolve(db, inp.person, "person")[1]
    b = refs.resolve(db, inp.other, "person")[1]
    with ctx.op(f"merge {b['ref']} into {a['ref']}") as tx:
        for lab in db.rows("speaker_label", "WHERE person_id=?", (b["id"],)):
            tx.update("speaker_label", lab["id"], {"person_id": a["id"]})
            people.apply_person(tx, db, lab["source_id"], lab["label"], a["id"])
        tx.update("person", a["id"], {"aliases": sorted(set(a["aliases"]) | {b["name"]} | set(b["aliases"]))})
        tx.delete("person", b["id"])
    return {"kept": a["ref"], "merged": b["ref"]}


# ---- naming lines directly (no models) ----

PREFIX = re.compile(r"^\s*-?\s*([A-Z][A-Z0-9 .'’\-]{1,30}?)\s*:\s+(?=\S)")


def _person(tx, db, name: str) -> dict:
    p = db.rows("person", "WHERE lower(name)=lower(?)", (name,))
    if p:
        return p[0]
    for row in db.rows("person"):  # an alias names the same person
        if name.lower() in [a.lower() for a in row["aliases"] or []]:
            return row
    return tx.insert("person", {"name": name})


def _label_for(tx, db, source_id: str, person: dict) -> str:
    """The voice label a person has in a source: their diarised voice if linked, else their name."""
    row = db.one("SELECT label FROM speaker_label WHERE source_id=? AND person_id=? ORDER BY seconds DESC", (source_id, person["id"]))
    if row:
        return row[0]
    label = person["name"]
    if not db.one("SELECT 1 FROM speaker_label WHERE source_id=? AND label=?", (source_id, label)):
        tx.insert("speaker_label", {"source_id": source_id, "label": label, "person_id": person["id"], "score": 1.0,
                                    "seconds": 0.0})
    return label


def _refresh_labels(tx, db, source_id: str, tr_id: str) -> None:
    """Seconds per label from the transcript lines (manual labels have no diarisation to measure them)."""
    for lab in db.rows("speaker_label", "WHERE source_id=?", (source_id,)):
        if db.one("SELECT 1 FROM speaker_turn WHERE source_id=? AND label=? AND conf IS NULL", (source_id, lab["label"])):
            continue  # diarised voices keep their measured time
        secs = db.scalar('SELECT COALESCE(SUM("end"-start), 0) FROM segment WHERE transcript_id=? AND speaker=?',
                         (tr_id, lab["label"]))
        tx.update("speaker_label", lab["id"], {"seconds": round(secs or 0.0, 1)}, log=False)


def _retune_turns(tx, source_id: str, spans: list[tuple[float, float, str, str | None]]) -> None:
    """Replace the speaker lane's turns under newly named lines with those lines (contiguous ones joined)."""
    merged: list[list] = []
    for a, b, label, pid in sorted(spans, key=lambda x: x[0]):
        if merged and merged[-1][2] == label and a - merged[-1][1] < 1.0:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b, label, pid])
    for a, b, label, pid in merged:
        tx.conn.execute('DELETE FROM speaker_turn WHERE source_id=? AND start >= ? AND "end" <= ?', (source_id, a - 0.05, b + 0.05))
        tx.conn.execute('INSERT INTO speaker_turn(source_id, start, "end", label, person_id, conf) VALUES(?,?,?,?,?,1.0)',
                        (source_id, a, b, label, pid))


class AssignIn(BaseModel):
    ref: str = Field(..., description="Source or transcript ref", json_schema_extra={"pos": 0})
    name: str | None = Field(None, description="Person or character to give the selected lines", json_schema_extra={"pos": 1})
    by: str | None = Field(None, description="marks: YouTube '>>' turns, cycling --names · prefix: 'NAME:' line prefixes "
                                             "in subtitles (film characters)")
    names: str | None = Field(None, description="With --by marks: comma list in speaking order, e.g. \"Alex O'Connor,Anil Seth\"")
    lines: str | None = Field(None, description="Line indices: 12, 12-40, 3,7,9-11")
    from_: str | None = Field(None, alias="from", description="Lines ending after this time")
    to: str | None = Field(None, description="Lines starting before this time")
    cut: str | None = Field(None, description="Lines inside this cut (C3)")
    match: str | None = Field(None, description="Lines containing this text")
    strip: bool = Field(True, description="With --by prefix: remove the 'NAME:' prefix from the text")
    clear: bool = Field(False, description="Remove the speaker from the selected lines instead")
    dry_run: bool = False
    model_config = {"populate_by_name": True}


@verb("speaker.assign", AssignIn, effect="write",
      examples=['recomp speaker assign S4 "Anil Seth" --from 12:30 --to 48:10',
                'recomp speaker assign S5 --by marks --names "Alex O\'Connor,Michael Pollan"',
                "recomp speaker assign S1 --by prefix --dry-run",
                'recomp speaker assign S1 "The Joker" --cut C4'])
def speaker_assign(ctx: Ctx, inp: AssignIn):
    """Say who speaks which lines, directly: by range, time, cut or text, from '>>' turns, or from 'NAME:' prefixes. No models needed."""
    from ..transcript import edit as E
    from .transcript import transcript_for
    db = ctx.db
    src, tr = transcript_for(db, inp.ref)
    frm, to = inp.from_, inp.to
    if inp.cut:
        c = refs.resolve(db, inp.cut, "cut")[1]
        if c["source_id"] != src["id"]:
            raise RecompError("E_INVALID", f"{inp.cut} is not a cut of {src['ref']}")
        frm, to = str(c["start"]), str(c["end"])
    pat = E.compile_pattern(inp.match) if inp.match else None
    segs = E.select(db, tr, inp.lines, frm, to, pat)
    plan: list[tuple[dict, str | None, str | None]] = []  # (line, person name or None to clear, new text)
    if inp.clear:
        plan = [(s, None, None) for s in segs if s["speaker"] or s["person_id"]]
    elif inp.by == "marks":
        names = [n.strip() for n in (inp.names or "").split(",") if n.strip()]
        if len(names) < 2:
            raise RecompError("E_INVALID", "--by marks needs --names with at least two people in speaking order",
                              hint="who speaks first, then who answers: --names \"Alex O'Connor,Anil Seth\"")
        k = 0
        for n_, s in enumerate(segs):
            pos = s["text"].find(">>")
            early = 0 <= pos < max(1, len(s["text"]) // 2)
            if early and n_ > 0:
                k += 1  # the turn starts with this line
            plan.append((s, names[k % len(names)], None))
            if pos >= 0 and not early:
                k += 1  # the next speaker starts at the end of this line
    elif inp.by == "prefix":
        for s in segs:
            m = PREFIX.match(s["text"])
            if not m or m.group(1).strip().upper() in ("NOTE", "PS", "AM", "PM"):
                continue
            name = " ".join(w.capitalize() for w in m.group(1).strip().split())
            plan.append((s, name, s["text"][m.end():].strip() if inp.strip else None))
    elif inp.by:
        raise RecompError("E_INVALID", "--by must be marks or prefix")
    else:
        if not inp.name:
            raise RecompError("E_INVALID", "give a name, or --by marks / --by prefix, or --clear")
        if not (inp.lines or frm or to or inp.match):
            raise RecompError("E_INVALID", "say which lines: --lines, --from/--to, --cut or --match",
                              hint="or --by marks / --by prefix to name every line")
        plan = [(s, inp.name, None) for s in segs]
    counts: dict[str, int] = {}
    for _, n, _t in plan:
        counts[n or "(cleared)"] = counts.get(n or "(cleared)", 0) + 1
    changes = [{"line": f"{tr['ref']}#{s['idx']}", "at": clock(s["start"]), "speaker": n, "text": (t or s["text"])[:90]}
               for s, n, t in plan[:40]]
    data = {"dry_run": inp.dry_run, "lines": len(plan), "by_person": counts, "changes": changes}
    if inp.dry_run or not plan:
        return Result(data=data, next=["run again without --dry-run to apply"] if plan else [])
    made = []
    with ctx.op(f"assign speakers in {tr['ref']} ({len(plan)} lines)") as tx:
        persons: dict[str, tuple[dict, str]] = {}
        spans = []
        for s, n, t in plan:
            if n is None:
                tx.update("segment", s["id"], {"speaker": None, "person_id": None})
                continue
            if n not in persons:
                p = _person(tx, db, n)
                persons[n] = (p, _label_for(tx, db, src["id"], p))
                made.append({"ref": p["ref"], "name": p["name"]})
            p, label = persons[n]
            tx.update("segment", s["id"], {"speaker": label, "person_id": p["id"]})
            if t:
                E.set_text(tx, s, t)
            spans.append((s["start"], s["end"], label, p["id"]))
        _retune_turns(tx, src["id"], spans)
        _refresh_labels(tx, db, src["id"], tr["id"])
    data["people"] = made
    return Result(data=data, refs=[m["ref"] for m in made],
                  next=[f"recomp speaker list {src['ref']}", "recomp op undo   # reverts the whole assignment"])


class PeopleIn(BaseModel):
    person: str | None = Field(None, description="Person to change (P1 or name); omit to list everyone", json_schema_extra={"pos": 0})
    rename: str | None = Field(None, description="New name (the old one becomes an alias)")
    alias: str | None = Field(None, description="Add an alias (another spelling, a character's other name)")
    note: str | None = Field(None, description="A note: who they are, the actor who plays them")
    remove: bool = Field(False, description="Delete the person (their lines keep their voice label)")


@verb("speaker.people", PeopleIn, effect="write",
      examples=["recomp speaker people", 'recomp speaker people P2 --rename "Michael Pollan" --alias "Pollan"',
                'recomp speaker people "The Joker" --note "played by Heath Ledger"'])
def speaker_people(ctx: Ctx, inp: PeopleIn):
    """List people and characters (lines, sources, aliases), or rename, alias, annotate or remove one."""
    db = ctx.db
    if inp.person:
        if re.fullmatch(r"P\d+", inp.person):
            p = refs.resolve(db, inp.person, "person")[1]
        else:
            rows = db.rows("person", "WHERE lower(name)=lower(?)", (inp.person,))
            if not rows:
                raise RecompError("E_NOT_FOUND", f"no person named {inp.person!r}", hint="`recomp speaker people`")
            p = rows[0]
        with ctx.op(f"person {p['ref']}") as tx:
            if inp.remove:
                for s in db.all("SELECT id FROM segment WHERE person_id=?", (p["id"],)):
                    tx.update("segment", s[0], {"person_id": None})
                tx.delete("person", p["id"])
                return {"removed": p["ref"]}
            fields = {}
            if inp.rename:
                fields["name"] = inp.rename
                fields["aliases"] = sorted(set(p["aliases"] or []) | {p["name"]})
            if inp.alias:
                fields["aliases"] = sorted(set(fields.get("aliases", p["aliases"] or [])) | {inp.alias})
            if inp.note is not None:
                fields["note"] = inp.note
            if fields:
                tx.update("person", p["id"], fields)
    out = []
    for r in db.rows("person", "ORDER BY name"):
        lines = db.scalar("SELECT COUNT(*) FROM segment s JOIN transcript t ON t.id=s.transcript_id "
                          "WHERE t.is_primary=1 AND s.person_id=?", (r["id"],))
        srcs = [x[0] for x in db.all("SELECT DISTINCT so.ref FROM speaker_label sl JOIN source so ON so.id=sl.source_id "
                                     "WHERE sl.person_id=? ORDER BY so.ref", (r["id"],))]
        out.append({"ref": r["ref"], "name": r["name"], "aliases": r["aliases"], "note": r["note"], "lines": lines,
                    "sources": srcs})
    return {"people": out}
