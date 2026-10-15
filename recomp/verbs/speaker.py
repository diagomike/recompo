"""Speakers and people: diarise sources, name voices, recognise the same person across sources."""

from __future__ import annotations

import json

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
