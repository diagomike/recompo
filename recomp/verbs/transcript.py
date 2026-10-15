"""Transcripts: import, read (economically), outline, ASR, sync, alignment, edits."""

from __future__ import annotations

import time
from pathlib import Path

from pydantic import BaseModel, Field

from ..core import refs
from ..core.timecode import clock, parse
from ..envelope import RecompError, Result
from ..registry import Ctx, verb
from ..transcript import align
from ..transcript import parse as tparse
from ..transcript.store import add_transcript, primary, write_segments
from ..workers import jobs


def transcript_for(db, ref: str) -> tuple[dict, dict]:
    """Accept a source ref (→ its primary transcript) or a transcript ref."""
    table, row = refs.resolve(db, ref, ("source", "transcript"))
    if table == "transcript":
        return db.get("source", row["source_id"]), row
    tr = primary(db, row["id"])
    if tr is None:
        raise RecompError("E_NOT_FOUND", f"{ref} has no transcript yet",
                          hint=f"`recomp transcript import {ref} <file>` or `recomp transcript asr {ref}`")
    return row, tr


def segments(db, tr_id: str, a: float | None = None, b: float | None = None) -> list[dict]:
    sql = 'SELECT id, idx, start, "end", text, speaker, person_id FROM segment WHERE transcript_id=?'
    params: list = [tr_id]
    if a is not None:
        sql += ' AND "end" > ?'
        params.append(a)
    if b is not None:
        sql += " AND start < ?"
        params.append(b)
    return [dict(r) for r in db.all(sql + " ORDER BY idx", params)]


class ImportIn(BaseModel):
    ref: str = Field(..., description="Source ref", json_schema_extra={"pos": 0})
    file: str = Field(..., description="Subtitle/caption file (.srt .vtt .ass .json3)", json_schema_extra={"pos": 1})
    language: str | None = None
    primary: bool | None = Field(None, description="Make it the primary transcript (default: only if none)")
    offset: str | None = Field(None, description="Shift all times by this much on import (e.g. -1.5)")


@verb("transcript.import", ImportIn, effect="write", examples=["recomp transcript import S1 film.en.srt"])
def transcript_import(ctx: Ctx, inp: ImportIn):
    """Import a subtitle or caption file as a transcript of a source."""
    src = refs.source(ctx.db, inp.ref)
    path = Path(inp.file)
    if not path.exists():
        raise RecompError("E_NOT_FOUND", f"no such file: {path}")
    segs, problems = tparse.parse_file(path)
    if not segs:
        raise RecompError("E_INVALID", f"{path.name}: no readable cues", data=problems[:10])
    off = parse(inp.offset) or 0.0
    if off:
        segs = [_shift_seg(s, off) for s in segs]
    lang = inp.language or tparse.guess_language(path, segs, src.get("language") or "en")
    with ctx.op(f"import {path.name}") as tx:
        tr = add_transcript(tx, src, segs, origin="import", language=lang, label=path.name,
                            make_primary=inp.primary, stats={"problems": len(problems), "problem_examples": problems[:5]})
        if off:
            tx.update("transcript", tr["id"], {"offset_s": off})
        status = dict(src["status"] or {})
        status["transcript"] = "done"
        tx.update("source", src["id"], {"status": status}, log=False)
    return Result(data={"ref": tr["ref"], "segments": len(segs), "language": lang, "problems": problems[:10]},
                  refs=[tr["ref"]], next=[f"recomp transcript sync-check {src['ref']}"])


def _shift_seg(s: dict, by: float) -> dict:
    out = dict(s, start=round(s["start"] + by, 3), end=round(s["end"] + by, 3))
    if s.get("words"):
        out["words"] = [dict(w, start=round(w["start"] + by, 3), end=round(w["end"] + by, 3)) for w in s["words"]]
    return out


class SrcIn(BaseModel):
    ref: str = Field(..., description="Source ref (or a transcript ref)", json_schema_extra={"pos": 0})


@verb("transcript.list", SrcIn)
def transcript_list(ctx: Ctx, inp: SrcIn):
    """Transcripts of a source: origin, language, primary, word timing, sync result."""
    src = refs.source(ctx.db, inp.ref)
    return [{"ref": t["ref"], "origin": t["origin"], "language": t["language"], "label": t["label"],
             "primary": bool(t["is_primary"]), "words": bool(t["has_words"]), "offset_s": t["offset_s"],
             "segments": (t["stats"] or {}).get("segments"), "sync": (t["stats"] or {}).get("sync", {}).get("verdict")}
            for t in ctx.db.rows("transcript", "WHERE source_id=? ORDER BY created_at", (src["id"],))]


class ReadIn(BaseModel):
    ref: str = Field(..., description="Source (primary transcript) or transcript ref", json_schema_extra={"pos": 0})
    from_: str | None = Field(None, alias="from", description="Start time")
    to: str | None = Field(None, description="End time")
    chapter: str | None = Field(None, description="Read one chapter, e.g. S1.c4")
    around: str | None = Field(None, description="Centre time; reads ± --span seconds")
    span: float = Field(45, description="Half-width for --around")
    limit: int = Field(250, description="Max segments")
    cursor: int | None = Field(None, description="Continue from this segment index (from next_cursor)")
    words: bool = Field(False, description="Include per-word timings")
    model_config = {"populate_by_name": True}


@verb("transcript.read", ReadIn,
      examples=["recomp transcript read S1 --from 10:00 --to 15:00", "recomp transcript read S1 --chapter S1.c4",
                "recomp transcript read S1 --around 1:02:10 --span 30"])
def transcript_read(ctx: Ctx, inp: ReadIn):
    """Read a window of a transcript as compact timed lines `#idx [hh:mm:ss.s] text` (cheap on context)."""
    db = ctx.db
    src, tr = transcript_for(db, inp.ref)
    a = parse(inp.from_)
    b = parse(inp.to)
    if inp.chapter:
        ch = refs.resolve(db, inp.chapter, "chapter")[1]
        a, b = ch["start"], ch["end"]
    if inp.around:
        c = parse(inp.around)
        a, b = c - inp.span, c + inp.span
    sql = 'SELECT id, idx, start, "end", text, speaker FROM segment WHERE transcript_id=?'
    params: list = [tr["id"]]
    if inp.cursor is not None:
        sql += " AND idx >= ?"
        params.append(inp.cursor)
    if a is not None:
        sql += ' AND "end" > ?'
        params.append(a)
    if b is not None:
        sql += " AND start < ?"
        params.append(b)
    rows = db.all(sql + " ORDER BY idx LIMIT ?", (*params, inp.limit + 1))
    more = len(rows) > inp.limit
    rows = rows[:inp.limit]
    lines = []
    word_map = {}
    for r in rows:
        spk = f"{r['speaker']}: " if r["speaker"] else ""
        lines.append(f"#{r['idx']} [{clock(r['start'])}] {spk}{r['text']}")
        if inp.words:
            word_map[r["idx"]] = [[round(w["start"], 2), round(w["end"], 2), w["text"]] for w in
                                  db.all('SELECT start, "end", text FROM word WHERE segment_id=? ORDER BY idx', (r["id"],))]
    out = {"source": src["ref"], "transcript": tr["ref"], "language": tr["language"],
           "range": [clock(rows[0]["start"]), clock(rows[-1]["end"])] if rows else None,
           "segments": len(rows), "text": "\n".join(lines)}
    if inp.words:
        out["words"] = word_map
    if more:
        out["next_cursor"] = rows[-1]["idx"] + 1
    return out


@verb("transcript.outline", SrcIn, examples=["recomp transcript outline S1"])
def transcript_outline(ctx: Ctx, inp: SrcIn):
    """The shape of a source before reading it: speech density, long silences, shot rhythm, creator/embedded and existing chapters, in 5-minute buckets."""
    db = ctx.db
    src, tr = transcript_for(db, inp.ref)
    dur = src["duration"] or 0
    bucket = 300 if dur > 1800 else 120 if dur > 600 else 60
    segs = segments(db, tr["id"])
    shots = [r[0] for r in db.all("SELECT t FROM shot WHERE source_id=? ORDER BY t", (src["id"],))]
    n = int(dur // bucket) + 1 if dur else 1
    rows = []
    for i in range(n):
        a, b = i * bucket, (i + 1) * bucket
        ss = [s for s in segs if a <= s["start"] < b]
        words = sum(len(s["text"].split()) for s in ss)
        rows.append({"at": clock(a, 0), "words": words, "wpm": round(words / (bucket / 60), 0),
                     "shots": sum(1 for t in shots if a <= t < b),
                     "first_line": ss[0]["text"][:80] if ss else ""})
    gaps = []
    for x, y in zip(segs, segs[1:]):
        if y["start"] - x["end"] >= 8:
            gaps.append({"from": clock(x["end"]), "to": clock(y["start"]), "s": round(y["start"] - x["end"], 1)})
    gaps.sort(key=lambda g: -g["s"])
    chapters = [{"ref": c["ref"], "start": clock(c["start"]), "end": clock(c["end"]), "title": c["title"],
                 "by": c["created_by"]} for c in db.rows("chapter", "WHERE source_id=? ORDER BY start", (src["id"],))]
    meta = src.get("meta") or {}
    creator = meta.get("chapters") or meta.get("embedded_chapters") or []
    return {"source": src["ref"], "title": src["title"], "duration": clock(dur), "transcript": tr["ref"],
            "origin": tr["origin"], "segments": len(segs), "words": sum(len(s["text"].split()) for s in segs),
            "first_speech": clock(segs[0]["start"]) if segs else None, "bucket_s": bucket, "buckets": rows,
            "longest_silences": gaps[:12], "creator_chapters": creator[:60], "chapters": chapters,
            "reading_plan": f"~{max(1, round(dur / 900))} windows of 15 min: transcript read {src['ref']} --from A --to B"}


class AsrIn(BaseModel):
    ref: str = Field(..., description="Source ref", json_schema_extra={"pos": 0})
    language: str | None = Field(None, description="Spoken language (default: detect)")
    from_: str | None = Field(None, alias="from", description="Only this range: start")
    to: str | None = Field(None, description="Only this range: end")
    model: str | None = Field(None, description="Model repo/path (default: config worker.asr_model)")
    engine: str = Field("whisper", description="whisper or ctc (character models, e.g. badrex/Ethio-ASR-amharic)")
    primary: bool | None = Field(None, description="Make the result primary (default: only if none)")
    allow_download: bool = Field(False, description="Allow the worker to download a missing model")
    on: str | None = Field(None, description="local or remote (a GPU notebook watching worker.remote_folder); default: config")
    model_config = {"populate_by_name": True}


@verb("transcript.asr", AsrIn, effect="heavy",
      examples=["recomp transcript asr S3", "recomp transcript asr S1 --from 10:00 --to 20:00 --language en"])
def transcript_asr(ctx: Ctx, inp: AsrIn):
    """Transcribe a source locally (faster-whisper with word timings) as a job."""
    src = refs.source(ctx.db, inp.ref)
    ranges = None
    if inp.from_ or inp.to:
        ranges = [[parse(inp.from_) or 0.0, parse(inp.to) or (src["duration"] or 0)]]
    params = {k: v for k, v in {"language": inp.language, "ranges": ranges, "model": inp.model, "engine": inp.engine,
                                "primary": inp.primary, "allow_download": inp.allow_download}.items() if v is not None}
    j = jobs.enqueue(ctx.db, "asr", target=src["ref"], source_id=src["id"], params=params, backend=jobs.backend(inp.on))
    mode = jobs.kick(ctx.project)
    est = (src["duration"] or 0) * (0.25 if not ranges else 0)
    return Result(data={"job": j["ref"], "runner": mode, "estimate": f"~{est / 60:.0f} min on CPU" if est else None},
                  job=j["ref"], next=[f"recomp job wait {j['ref']} --timeout 90"])


class CaptionsIn(BaseModel):
    ref: str = Field(..., description="Link source ref", json_schema_extra={"pos": 0})
    language: str | None = Field(None, description="Caption language (default: the source's)")


@verb("transcript.fetch-captions", CaptionsIn, effect="network", examples=["recomp transcript fetch-captions S2"])
def transcript_fetch_captions(ctx: Ctx, inp: CaptionsIn):
    """Fetch a link's captions (manual first, then the original-language auto captions) as a job. On HTTP 429 fall back to `transcript asr`."""
    src = refs.source(ctx.db, inp.ref)
    if src["kind"] != "link":
        raise RecompError("E_INVALID", f"{src['ref']} is a file; import its subtitles with `transcript import`")
    j = jobs.enqueue(ctx.db, "captions", target=src["ref"], source_id=src["id"],
                     params={"language": inp.language or src.get("language")})
    mode = jobs.kick(ctx.project)
    return Result(data={"job": j["ref"], "runner": mode}, job=j["ref"], next=[f"recomp job wait {j['ref']} --timeout 60"])


class SyncIn(BaseModel):
    ref: str = Field(..., description="Source or transcript ref", json_schema_extra={"pos": 0})
    against: str | None = Field(None, description="Use this ASR transcript instead of running ASR on 3 windows")
    fix: bool = Field(False, description="Shift the transcript by the measured offset")


@verb("transcript.sync-check", SyncIn, effect="heavy",
      examples=["recomp transcript sync-check S1", "recomp transcript sync-check S1 --fix"])
def transcript_sync_check(ctx: Ctx, inp: SyncIn):
    """Measure whether subtitles match the speech (offset and drift); --fix shifts them. Uses an existing ASR transcript if there is one, otherwise runs ASR on three 60-second windows (a job)."""
    db = ctx.db
    src, tr = transcript_for(db, inp.ref)
    ref_tr = None
    if inp.against:
        ref_tr = refs.resolve(db, inp.against, "transcript")[1]
    else:
        cands = db.rows("transcript", "WHERE source_id=? AND origin='asr' AND id<>? ORDER BY created_at DESC",
                        (src["id"], tr["id"]))
        ref_tr = cands[0] if cands else None
    sync = (tr["stats"] or {}).get("sync")
    if ref_tr is None and sync is None:
        if tr["origin"] == "asr":
            return {"transcript": tr["ref"], "verdict": "this is an ASR transcript: in sync by construction"}
        j = jobs.enqueue(db, "synccheck", target=src["ref"], source_id=src["id"], params={"transcript": tr["ref"]})
        mode = jobs.kick(ctx.project)
        return Result(data={"job": j["ref"], "runner": mode}, job=j["ref"],
                      next=[f"recomp job wait {j['ref']} --timeout 120",
                            f"recomp transcript sync-check {tr['ref']}" + (" --fix" if inp.fix else "")])
    if ref_tr is not None:
        from ..workers.tasks_speech import sync_verdict
        segs = segments(db, tr["id"])
        words = [dict(r) for r in db.all(
            'SELECT w.start, w."end", w.text FROM word w JOIN segment s ON s.id=w.segment_id '
            "WHERE s.transcript_id=? ORDER BY w.start", (ref_tr["id"],))]
        dur = src["duration"] or (segs[-1]["end"] if segs else 0)
        per = []
        for frac in (0.2, 0.5, 0.8):
            a = max(0.0, dur * frac - 150)
            b = min(dur, a + 300)
            per.append(dict(align.estimate_offset(segs, words, (a, b)), window=[round(a, 1), round(b, 1)]))
        overall = align.estimate_offset(segs, words)
        sync = {"offset_s": overall["offset_s"], "per_window": per, "verdict": sync_verdict(overall, per),
                "against": ref_tr["ref"], "matched": overall.get("matched"), "confidence": overall.get("confidence")}
        stats = dict(tr["stats"] or {})
        stats["sync"] = sync
        with ctx.op("sync-check") as tx:
            tx.update("transcript", tr["id"], {"stats": stats}, log=False)
    out = {"transcript": tr["ref"], **sync}
    off = sync.get("offset_s")
    if inp.fix and off is not None and abs(off) > 0.05 and "drifting" not in sync.get("verdict", ""):
        shift(ctx, tr, -off)
        out["fixed"] = f"shifted by {-off:+.3f}s"
    return out


def shift(ctx: Ctx, tr: dict, by: float, scale: float = 1.0, frm: float | None = None, to: float | None = None) -> int:
    """t -> t * scale + by, for the whole transcript or only the lines that start inside [frm, to)."""
    where, params = "transcript_id=?", [tr["id"]]
    if frm is not None:
        where += " AND start >= ?"
        params.append(frm)
    if to is not None:
        where += " AND start < ?"
        params.append(to)
    whole = frm is None and to is None
    label = f"{by:+.3f}s" + (f" x{scale:g}" if scale != 1.0 else "") + ("" if whole else " (range)")
    with ctx.op(f"shift {tr['ref']} {label}") as tx:
        tx.conn.execute(f'UPDATE word SET start=start*?+?, "end"="end"*?+? WHERE segment_id IN '
                        f"(SELECT id FROM segment WHERE {where})", [scale, by, scale, by] + params)
        n = tx.conn.execute(f'UPDATE segment SET start=start*?+?, "end"="end"*?+? WHERE {where}',
                            [scale, by, scale, by] + params).rowcount
        stats = dict(tr["stats"] or {})
        if whole and "sync" in stats:
            stats["sync"] = dict(stats["sync"], applied=round(by, 3))
        fields = {"stats": stats}
        if whole and scale == 1.0:
            fields["offset_s"] = round((tr["offset_s"] or 0) + by, 3)
        else:
            stats["retimed"] = stats.get("retimed", []) + [{"by": by, "scale": scale, "from": frm, "to": to}]
        tx.update("transcript", tr["id"], fields)
        tx.redoable = False
    return n


class ShiftIn(BaseModel):
    ref: str = Field(..., json_schema_extra={"pos": 0})
    by: str = Field("0", description="Seconds to add to every time (negative = earlier)", json_schema_extra={"pos": 1})
    scale: float = Field(1.0, description="Multiply times first (frame-rate drift: 25/23.976 = 1.04271)")
    from_: str | None = Field(None, alias="from", description="Only lines starting at or after this time")
    to: str | None = Field(None, description="Only lines starting before this time")

    model_config = {"populate_by_name": True}


@verb("transcript.shift", ShiftIn, effect="write",
      examples=["recomp transcript shift S1.t1 -1.5", "recomp transcript shift S1 0 --scale 1.04271",
                "recomp transcript shift S1 0.8 --from 1:02:10   # only the lines after a reel change"])
def transcript_shift(ctx: Ctx, inp: ShiftIn):
    """Shift (and optionally stretch) a transcript's times, whole or from/to a point. Shift back to undo a whole shift."""
    _, tr = transcript_for(ctx.db, inp.ref)
    by = parse(inp.by) or 0.0
    if inp.scale <= 0:
        raise RecompError("E_INVALID", "scale must be positive", hint="e.g. 1.04271 for 23.976 → 25 fps")
    n = shift(ctx, tr, by, inp.scale, parse(inp.from_) if inp.from_ else None, parse(inp.to) if inp.to else None)
    return {"transcript": tr["ref"], "shifted": by, "scale": inp.scale, "lines": n}


class AlignIn(BaseModel):
    ref: str = Field(..., description="Transcript (or source → primary) to give word timings", json_schema_extra={"pos": 0})
    using: str | None = Field(None, description="ASR transcript with word timings (default: newest ASR of the source)")
    method: str = Field("auto", description="auto (asr if available, else proportional), asr, proportional")


@verb("transcript.align", AlignIn, effect="write", examples=["recomp transcript align S1.t1 --using S1.t2"])
def transcript_align(ctx: Ctx, inp: AlignIn):
    """Give a subtitle transcript per-word timings: matched against ASR words, or spread proportionally."""
    db = ctx.db
    src, tr = transcript_for(db, inp.ref)
    ref_tr = None
    if inp.method in ("auto", "asr"):
        if inp.using:
            ref_tr = refs.resolve(db, inp.using, "transcript")[1]
        else:
            c = db.rows("transcript", "WHERE source_id=? AND origin='asr' AND has_words=1 AND id<>? "
                                      "ORDER BY created_at DESC", (src["id"], tr["id"]))
            ref_tr = c[0] if c else None
        if ref_tr is None and inp.method == "asr":
            raise RecompError("E_NOT_FOUND", "no ASR transcript with words to align against",
                              hint=f"`recomp transcript asr {src['ref']}` first")
    segs = segments(db, tr["id"])
    if ref_tr is not None:
        words = [dict(r) for r in db.all(
            'SELECT w.start, w."end", w.text, w.prob FROM word w JOIN segment s ON s.id=w.segment_id '
            "WHERE s.transcript_id=? ORDER BY w.start", (ref_tr["id"],))]
        per_seg, stat = align.words_from_reference(segs, words)
        method = "asr"
    else:
        per_seg = [align.proportional_words(s) for s in segs]
        stat = {"matched": 0, "words": sum(len(w) for w in per_seg), "ratio": 0.0}
        method = "proportional"
    with ctx.op(f"align {tr['ref']} ({method})") as tx:
        tx.conn.execute("DELETE FROM word WHERE segment_id IN (SELECT id FROM segment WHERE transcript_id=?)", (tr["id"],))
        for s, ws in zip(segs, per_seg):
            tx.conn.executemany('INSERT INTO word(segment_id, idx, start, "end", text, prob) VALUES(?,?,?,?,?,?)',
                                [(s["id"], j, w["start"], w["end"], w["text"], w.get("prob")) for j, w in enumerate(ws)])
        stats = dict(tr["stats"] or {})
        stats["align"] = dict(stat, method=method, using=ref_tr["ref"] if ref_tr else None)
        tx.update("transcript", tr["id"], {"has_words": 1, "stats": stats})
        tx.redoable = False
    return {"transcript": tr["ref"], "method": method, **stat}


class PrimaryIn(BaseModel):
    ref: str = Field(..., description="Transcript ref", json_schema_extra={"pos": 0})


@verb("transcript.set-primary", PrimaryIn, effect="write")
def transcript_set_primary(ctx: Ctx, inp: PrimaryIn):
    """Make a transcript the one search, reading and captions use for its source."""
    tr = refs.resolve(ctx.db, inp.ref, "transcript")[1]
    with ctx.op(f"primary {tr['ref']}") as tx:
        for other in tx.all("SELECT id FROM transcript WHERE source_id=? AND is_primary=1 AND id<>?",
                            (tr["source_id"], tr["id"])):
            tx.update("transcript", other["id"], {"is_primary": 0})
        tx.update("transcript", tr["id"], {"is_primary": 1})
    return {"primary": tr["ref"]}


class EditSegIn(BaseModel):
    ref: str = Field(..., description="Source or transcript ref", json_schema_extra={"pos": 0})
    idx: int = Field(..., description="Segment index (#idx in transcript read)", json_schema_extra={"pos": 1})
    text: str | None = None
    start: str | None = None
    end: str | None = None
    speaker: str | None = None


@verb("transcript.edit-segment", EditSegIn, effect="write",
      examples=['recomp transcript edit-segment S1 412 --text "Why so serious?"'])
def transcript_edit_segment(ctx: Ctx, inp: EditSegIn):
    """Correct one segment's text, timing or speaker (word timings are re-spread if the text changes)."""
    _, tr = transcript_for(ctx.db, inp.ref)
    row = ctx.db.one("SELECT id FROM segment WHERE transcript_id=? AND idx=?", (tr["id"], inp.idx))
    if row is None:
        raise RecompError("E_NOT_FOUND", f"segment #{inp.idx} not in {tr['ref']}")
    fields = {}
    if inp.text is not None:
        fields["text"] = inp.text
    if inp.start is not None:
        fields["start"] = parse(inp.start)
    if inp.end is not None:
        fields["end"] = parse(inp.end)
    if inp.speaker is not None:
        fields["speaker"] = inp.speaker
    with ctx.op(f"edit {tr['ref']}#{inp.idx}") as tx:
        seg = tx.update("segment", row["id"], fields)
        if "text" in fields and tr["has_words"]:
            tx.conn.execute("DELETE FROM word WHERE segment_id=?", (row["id"],))
            tx.conn.executemany('INSERT INTO word(segment_id, idx, start, "end", text, prob) VALUES(?,?,?,?,?,?)',
                                [(row["id"], j, w["start"], w["end"], w["text"], None)
                                 for j, w in enumerate(align.proportional_words(seg))])
    return {"idx": inp.idx, "start": seg["start"], "end": seg["end"], "text": seg["text"]}
