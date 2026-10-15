"""Transcript editing in bulk: replace, edit many lines, clean, delete, merge, split, resegment, export.

Every verb is op-logged (`recomp op undo` reverts the whole edit) and the bulk ones take --dry-run.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from ..core.timecode import clock, parse, srt_clock
from ..envelope import RecompError, Result
from ..registry import Ctx, verb
from ..transcript import edit as E
from ..transcript.store import add_transcript, primary
from .transcript import transcript_for

PREVIEW = 40


def _targets(db, ref: str) -> list[tuple[dict, dict]]:
    """A source/transcript ref, or 'all' (every source's primary transcript)."""
    if ref == "all":
        out = []
        for s in db.rows("source", "ORDER BY ref"):
            tr = primary(db, s["id"])
            if tr:
                out.append((s, tr))
        return out
    return [transcript_for(db, ref)]


def _change(tr: dict, seg: dict, after: str | None, **extra) -> dict:
    out = {"line": f"{tr['ref']}#{seg['idx']}", "at": clock(seg["start"]), "before": seg["text"]}
    if after is not None:
        out["after"] = after
    out.update(extra)
    return out


def _report(changes: list[dict], dry: bool, what: str, next_: list[str] | None = None, **data) -> Result:
    data = {"dry_run": dry, what: len(changes), "changes": changes[:PREVIEW], **data}
    if len(changes) > PREVIEW:
        data["more"] = len(changes) - PREVIEW
    nxt = list(next_ or [])
    if dry and changes:
        nxt.insert(0, "run again without --dry-run to apply")
    elif changes:
        nxt.append("recomp op undo   # reverts the whole edit")
    return Result(data=data, next=nxt)


class Selector(BaseModel):
    lines: str | None = Field(None, description="Line indices: 12, 12-40 or 3,7,9-11 (the #idx from `transcript read`)")
    from_: str | None = Field(None, alias="from", description="Only lines ending after this time")
    to: str | None = Field(None, description="Only lines starting before this time")
    dry_run: bool = Field(False, description="Show what would change without changing anything")
    model_config = {"populate_by_name": True}


class ReplaceIn(Selector):
    ref: str = Field(..., description="Source or transcript ref, or `all` (every source's primary transcript)",
                     json_schema_extra={"pos": 0})
    find: str = Field(..., description="Text (or --regex pattern) to find", json_schema_extra={"pos": 1})
    replace: str = Field(..., description="Replacement (regex groups as \\1)", json_schema_extra={"pos": 2})
    regex: bool = False
    case: bool = Field(False, description="Case-sensitive")
    whole: bool = Field(False, description="Whole words only")


@verb("transcript.replace", ReplaceIn, effect="write",
      examples=['recomp transcript replace all "Anil Seth" "Anil Seth" --whole --dry-run',
                'recomp transcript replace S4 "conscious ness" "consciousness"',
                'recomp transcript replace S1 "^- " "" --regex'])
def transcript_replace(ctx: Ctx, inp: ReplaceIn):
    """Find and replace across a transcript (or all of them): names, misheard words, punctuation. Word timings follow."""
    pat = E.compile_pattern(inp.find, inp.regex, inp.case, inp.whole)
    repl = inp.replace if inp.regex else inp.replace.replace("\\", "\\\\")
    plan = []
    for _, tr in _targets(ctx.db, inp.ref):
        for seg in E.select(ctx.db, tr, inp.lines, inp.from_, inp.to, pat):
            new = " ".join(pat.sub(repl, seg["text"]).split())
            if new != seg["text"]:
                plan.append((tr, seg, new))
    changes = [_change(tr, seg, new) for tr, seg, new in plan]
    if not inp.dry_run and plan:
        with ctx.op(f"replace {inp.find!r} → {inp.replace!r} in {inp.ref}") as tx:
            for _, seg, new in plan:
                if new:
                    E.set_text(tx, seg, new)
                else:
                    tx.delete("segment", seg["id"])
    return _report(changes, inp.dry_run, "replaced")


class LineEdit(BaseModel):
    idx: int = Field(..., description="Line index")
    text: str | None = None
    start: str | None = None
    end: str | None = None
    speaker: str | None = Field(None, description="Voice label (use `speaker assign` to name a person)")


class EditIn(BaseModel):
    ref: str = Field(..., description="Source or transcript ref", json_schema_extra={"pos": 0})
    edits: list[LineEdit] = Field(..., description="Lines to change (use --input edits.json: {edits: [{idx, text, …}]})")
    dry_run: bool = False


@verb("transcript.edit", EditIn, effect="write", examples=["recomp transcript edit S1 --input edits.json"])
def transcript_edit(ctx: Ctx, inp: EditIn):
    """Change many lines at once (text, start, end, speaker) from one JSON input; one undo reverts them all."""
    db = ctx.db
    _, tr = transcript_for(db, inp.ref)
    plan = []
    for e in inp.edits:
        row = db.one('SELECT id, idx, start, "end", text, speaker FROM segment WHERE transcript_id=? AND idx=?', (tr["id"], e.idx))
        if row is None:
            raise RecompError("E_NOT_FOUND", f"line #{e.idx} not in {tr['ref']}", hint=f"`recomp transcript read {tr['ref']}`")
        seg = dict(row)
        fields = {}
        if e.text is not None and e.text.strip() != seg["text"]:
            fields["text"] = " ".join(e.text.split())
        if e.start is not None:
            fields["start"] = parse(e.start)
        if e.end is not None:
            fields["end"] = parse(e.end)
        if e.speaker is not None:
            fields["speaker"] = e.speaker or None
        a, b = fields.get("start", seg["start"]), fields.get("end", seg["end"])
        if b <= a:
            raise RecompError("E_INVALID", f"line #{e.idx}: end must be after start")
        if fields:
            plan.append((seg, fields))
    changes = [_change(tr, seg, f.get("text"), **{k: v for k, v in f.items() if k != "text"}) for seg, f in plan]
    if not inp.dry_run and plan:
        with ctx.op(f"edit {len(plan)} line(s) of {tr['ref']}") as tx:
            for seg, f in plan:
                timing = {k: v for k, v in f.items() if k != "text"}
                if timing:
                    tx.update("segment", seg["id"], timing)
                    if "start" in timing or "end" in timing:  # keep words inside the line's new span
                        tx.conn.execute('UPDATE word SET start=max(start, ?), "end"=min("end", ?) WHERE segment_id=?',
                                        (timing.get("start", seg["start"]), timing.get("end", seg["end"]), seg["id"]))
                if "text" in f:
                    E.set_text(tx, dict(seg, **timing), f["text"])
    return _report(changes, inp.dry_run, "edited")


class CleanIn(Selector):
    ref: str = Field(..., description="Source or transcript ref, or `all`", json_schema_extra={"pos": 0})
    rules: str | None = Field(None, description="Comma list; default marks,tags,notes,doubles,spacing. "
                                                "Also: fillers, case. `--rules list` shows them all")


@verb("transcript.clean", CleanIn, effect="write",
      examples=["recomp transcript clean S2 --dry-run", "recomp transcript clean all --rules tags,notes,spacing",
                "recomp transcript clean S1 --rules list"])
def transcript_clean(ctx: Ctx, inp: CleanIn):
    """Tidy transcript text with presets (sound tags, >> marks, ♪, doubled words, fillers, spacing, casing). Empty lines are removed."""
    if inp.rules == "list":
        return {"rules": {k: v[0] for k, v in E.CLEAN_RULES.items()}, "default": E.DEFAULT_CLEAN}
    rules = [r.strip() for r in inp.rules.split(",")] if inp.rules else E.DEFAULT_CLEAN
    bad = [r for r in rules if r not in E.CLEAN_RULES]
    if bad:
        raise RecompError("E_INVALID", f"unknown rule(s): {bad}", hint="`recomp transcript clean S1 --rules list`")
    warnings = []
    plan = []
    for _, tr in _targets(ctx.db, inp.ref):
        segs = E.select(ctx.db, tr, inp.lines, inp.from_, inp.to)
        if "marks" in rules and any(">>" in s["text"] for s in segs) and not any(s["speaker"] for s in segs):
            warnings.append(f"{tr['ref']}: '>>' marks speaker turns and no speakers are set; "
                            f"`recomp speaker assign {tr['ref']} --by marks --names \"A,B\"` first keeps them")
        for seg in segs:
            new = E.clean_text(seg["text"], rules)
            if new != seg["text"]:
                plan.append((tr, seg, new))
    changes = [_change(tr, seg, new or "(removed)") for tr, seg, new in plan]
    if not inp.dry_run and plan:
        with ctx.op(f"clean {inp.ref} ({','.join(rules)})") as tx:
            for _, seg, new in plan:
                if new:
                    E.set_text(tx, seg, new)
                else:
                    tx.delete("segment", seg["id"])
    r = _report(changes, inp.dry_run, "cleaned", rules=rules)
    r.warnings = warnings
    return r


class DeleteIn(Selector):
    ref: str = Field(..., description="Source or transcript ref", json_schema_extra={"pos": 0})
    match: str | None = Field(None, description="Only lines containing this text (or --regex pattern)")
    regex: bool = False


@verb("transcript.delete", DeleteIn, effect="write",
      examples=["recomp transcript delete S1 --lines 0-3 --dry-run", 'recomp transcript delete S1 --match "^\\[.*\\]$" --regex'])
def transcript_delete(ctx: Ctx, inp: DeleteIn):
    """Remove lines (credits, sound-only lines, a subtitle file's ads) by range, time or pattern."""
    if not (inp.lines or inp.from_ or inp.to or inp.match):
        raise RecompError("E_INVALID", "say which lines: --lines, --from/--to or --match")
    _, tr = transcript_for(ctx.db, inp.ref)
    pat = E.compile_pattern(inp.match, inp.regex) if inp.match else None
    segs = E.select(ctx.db, tr, inp.lines, inp.from_, inp.to, pat)
    if not inp.dry_run and segs:
        with ctx.op(f"delete {len(segs)} line(s) of {tr['ref']}") as tx:
            for seg in segs:
                tx.delete("segment", seg["id"])
    return _report([_change(tr, s, None) for s in segs], inp.dry_run, "deleted")


class MergeIn(BaseModel):
    ref: str = Field(..., description="Source or transcript ref", json_schema_extra={"pos": 0})
    lines: str = Field(..., description="Consecutive lines to join, e.g. 12-14", json_schema_extra={"pos": 1})


@verb("transcript.merge", MergeIn, effect="write", examples=["recomp transcript merge S1 12-14"])
def transcript_merge(ctx: Ctx, inp: MergeIn):
    """Join consecutive lines into one (a sentence the subtitles broke apart). Words keep their timings."""
    _, tr = transcript_for(ctx.db, inp.ref)
    segs = E.select(ctx.db, tr, inp.lines)
    if len(segs) < 2:
        raise RecompError("E_INVALID", "give at least two existing lines, e.g. 12-14")
    first, rest = segs[0], segs[1:]
    text = " ".join(s["text"] for s in segs)
    with ctx.op(f"merge {tr['ref']}#{inp.lines}") as tx:
        for s in rest:
            tx.conn.execute("UPDATE word SET segment_id=?, idx=idx+? WHERE segment_id=?", (first["id"], 1000 * s["idx"], s["id"]))
        for s in rest:
            tx.delete("segment", s["id"])
        tx.update("segment", first["id"], {"text": text, "end": max(s["end"] for s in segs)})
    return {"line": f"{tr['ref']}#{first['idx']}", "start": first["start"], "end": max(s["end"] for s in segs),
            "text": text, "merged": len(segs)}


class SplitIn(BaseModel):
    ref: str = Field(..., description="Source or transcript ref", json_schema_extra={"pos": 0})
    idx: int = Field(..., description="Line to split", json_schema_extra={"pos": 1})
    after: str | None = Field(None, description="Split after these words (the end of the first part)")
    at: str | None = Field(None, description="Or split at this time (words decide the text)")


@verb("transcript.split", SplitIn, effect="write",
      examples=['recomp transcript split S1 412 --after "Why so serious?"', "recomp transcript split S1 412 --at 1:02:03.4"])
def transcript_split(ctx: Ctx, inp: SplitIn):
    """Split one line in two, after given words or at a time. Later lines are renumbered."""
    db = ctx.db
    _, tr = transcript_for(db, inp.ref)
    row = db.one('SELECT id, idx, start, "end", text, speaker, person_id FROM segment WHERE transcript_id=? AND idx=?',
                 (tr["id"], inp.idx))
    if row is None:
        raise RecompError("E_NOT_FOUND", f"line #{inp.idx} not in {tr['ref']}")
    seg = dict(row)
    words = [dict(r) for r in db.all('SELECT id, start, "end", text FROM word WHERE segment_id=? ORDER BY idx', (seg["id"],))]
    toks = E.tokens(seg["text"])
    if inp.after:
        cut = len(E.tokens(inp.after))
        if " ".join(toks[:cut]).lower() != " ".join(E.tokens(inp.after)).lower():
            raise RecompError("E_INVALID", "--after must be the exact first words of the line",
                              hint=f"the line reads: {seg['text'][:80]}")
    elif inp.at:
        t = parse(inp.at)
        if not seg["start"] < t < seg["end"]:
            raise RecompError("E_INVALID", f"--at must fall inside the line ({clock(seg['start'])}–{clock(seg['end'])})")
        timed = E.sync_words(seg["text"], [(w["start"], w["end"], w["text"]) for w in words]) or \
            [(w["start"], w["end"], w["text"]) for w in E.proportional_words(seg)]
        cut = sum(1 for w in timed if (w[0] + w[1]) / 2 < t)
    else:
        raise RecompError("E_INVALID", "say where: --after \"words\" or --at time")
    if not 0 < cut < len(toks):
        raise RecompError("E_INVALID", "both parts need at least one word")
    timed = E.sync_words(seg["text"], [(w["start"], w["end"], w["text"]) for w in words]) or \
        [(w["start"], w["end"], w["text"]) for w in E.proportional_words(seg)]
    t_split = parse(inp.at) if inp.at else round((timed[cut - 1][1] + timed[cut][0]) / 2, 3)
    a_text, b_text = " ".join(toks[:cut]), " ".join(toks[cut:])
    with ctx.op(f"split {tr['ref']}#{inp.idx}") as tx:
        tx.conn.execute("UPDATE segment SET idx=idx+1 WHERE transcript_id=? AND idx>?", (tr["id"], inp.idx))
        tx.update("segment", seg["id"], {"text": a_text, "end": t_split})
        new = tx.insert("segment", {"transcript_id": tr["id"], "idx": inp.idx + 1, "start": t_split, "end": seg["end"],
                                    "text": b_text, "speaker": seg["speaker"], "person_id": seg["person_id"]})
        tx.conn.execute("DELETE FROM word WHERE segment_id=?", (seg["id"],))
        rows = [(seg["id"], j, w[0], w[1], w[2]) for j, w in enumerate(timed[:cut])]
        rows += [(new["id"], j, w[0], w[1], w[2]) for j, w in enumerate(timed[cut:])]
        if words:
            tx.conn.executemany('INSERT INTO word(segment_id, idx, start, "end", text) VALUES(?,?,?,?,?)', rows)
    return {"first": {"idx": inp.idx, "text": a_text, "end": t_split},
            "second": {"idx": inp.idx + 1, "text": b_text, "start": t_split}}


class ResegIn(BaseModel):
    ref: str = Field(..., description="Source or transcript ref (needs word timings)", json_schema_extra={"pos": 0})
    max_chars: int = Field(84, description="Longest line in characters (two caption rows ≈ 84)")
    max_dur: float = Field(7.0, description="Longest line in seconds")
    gap: float = Field(0.8, description="A pause this long always starts a new line")
    primary: bool = Field(True, description="Make the result the primary transcript")
    dry_run: bool = False


@verb("transcript.resegment", ResegIn, effect="write",
      examples=["recomp transcript resegment S2 --dry-run", "recomp transcript resegment S2 --max-chars 70"])
def transcript_resegment(ctx: Ctx, inp: ResegIn):
    """Rebuild lines from word timings (rolling auto captions → sentence-like lines). Writes a new transcript; the old one stays."""
    db = ctx.db
    src, tr = transcript_for(db, inp.ref)
    if not tr["has_words"]:
        raise RecompError("E_INVALID", f"{tr['ref']} has no word timings",
                          hint=f"`recomp transcript align {tr['ref']}` first, or use merge/split by hand")
    words = []
    for r in db.all('SELECT w.start, w."end", w.text, s.speaker, s.text AS line FROM word w JOIN segment s ON s.id=w.segment_id '
                    "WHERE s.transcript_id=? ORDER BY s.idx, w.idx", (tr["id"],)):
        words.append({"start": r["start"], "end": r["end"], "text": r["text"], "speaker": r["speaker"]})
    words = [w for w in words if w["text"].strip(">").strip()]
    segs = E.resegment(words, inp.max_chars, inp.max_dur, inp.gap)
    before = db.scalar("SELECT COUNT(*) FROM segment WHERE transcript_id=?", (tr["id"],))
    sample = [{"at": clock(s["start"]), "text": s["text"]} for s in segs[:12]]
    data = {"dry_run": inp.dry_run, "from": tr["ref"], "lines_before": before, "lines_after": len(segs), "sample": sample}
    warnings = []
    used = db.scalar("SELECT COUNT(*) FROM translation WHERE kind='segment' AND target_id IN "
                     "(SELECT CAST(id AS TEXT) FROM segment WHERE transcript_id=?)", (tr["id"],))
    if used:
        warnings.append(f"{used} translated line(s) belong to {tr['ref']}; after the switch, translate again "
                        "(`recomp lang translate J… --to …`)")
    if inp.dry_run:
        return Result(data=data, warnings=warnings, next=["run again without --dry-run to write the new transcript"])
    with ctx.op(f"resegment {tr['ref']}") as tx:
        new = add_transcript(tx, src, segs, origin="edit", language=tr["language"], label=f"resegmented {tr['ref']}",
                             make_primary=inp.primary, stats={"resegmented_from": tr["ref"]})
    data["transcript"] = new["ref"]
    return Result(data=data, warnings=warnings, refs=[new["ref"]],
                  next=[f"recomp transcript read {new['ref']} --limit 30",
                        f"recomp transcript set-primary {tr['ref']}   # to go back"])


class ExportIn(BaseModel):
    ref: str = Field(..., description="Source or transcript ref", json_schema_extra={"pos": 0})
    format: str = Field("srt", description="srt | vtt | txt | json (json keeps words and speakers; import reads it back)")
    out: str | None = Field(None, description="File to write (default: <project>/exports/transcripts/<ref>.<format>)")
    from_: str | None = Field(None, alias="from")
    to: str | None = None
    model_config = {"populate_by_name": True}


@verb("transcript.export", ExportIn, effect="write",
      examples=["recomp transcript export S1 --format srt", "recomp transcript export S4 --format json --out s4.json"])
def transcript_export(ctx: Ctx, inp: ExportIn):
    """Write a transcript to a file (srt, vtt, txt, json) for an outside editor; `transcript import` reads it back."""
    db = ctx.db
    _, tr = transcript_for(db, inp.ref)
    segs = E.select(db, tr, None, inp.from_, inp.to)
    fmt = inp.format.lower()
    if fmt not in ("srt", "vtt", "txt", "json"):
        raise RecompError("E_INVALID", "format must be srt, vtt, txt or json")
    out = Path(inp.out) if inp.out else ctx.project.root / "exports" / "transcripts" / f"{tr['ref']}.{fmt}"
    out.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "json":
        rows = []
        for s in segs:
            r = {"start": s["start"], "end": s["end"], "text": s["text"]}
            if s["speaker"]:
                r["speaker"] = s["speaker"]
            ws = db.all('SELECT start, "end", text FROM word WHERE segment_id=? ORDER BY idx', (s["id"],))
            if ws:
                r["words"] = [{"start": w[0], "end": w[1], "text": w[2]} for w in ws]
            rows.append(r)
        body = json.dumps({"transcript": tr["ref"], "language": tr["language"], "segments": rows}, ensure_ascii=False, indent=1)
    elif fmt == "txt":
        body = "\n".join(f"[{clock(s['start'])}] " + (f"{s['speaker']}: " if s["speaker"] else "") + s["text"] for s in segs)
    else:
        cues = []
        for k, s in enumerate(segs, 1):
            a, b = srt_clock(s["start"]), srt_clock(s["end"])
            if fmt == "vtt":
                a, b = a.replace(",", "."), b.replace(",", ".")
            cues.append((f"{k}\n" if fmt == "srt" else "") + f"{a} --> {b}\n{s['text']}\n")
        body = ("WEBVTT\n\n" if fmt == "vtt" else "") + "\n".join(cues)
    out.write_text(body + "\n", encoding="utf-8")
    return {"file": str(out), "format": fmt, "lines": len(segs)}

