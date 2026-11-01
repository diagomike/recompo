"""Sources: local media files (referenced in place) and links."""

from __future__ import annotations

import glob as globlib
import os
import re
import time
from pathlib import Path

from pydantic import BaseModel, Field

from ..core import refs
from ..core.timecode import clock
from ..envelope import RecompError, Result
from ..media import ff, identity
from ..registry import Ctx, NoInput, verb
from ..transcript import parse as tparse
from ..transcript.store import add_transcript
from ..workers import jobs

DEFAULT_JOBS = ["audio", "peaks", "shots", "thumbs"]
URL = re.compile(r"^https?://", re.I)


def expand(target: str) -> list[Path]:
    p = Path(os.path.expandvars(os.path.expanduser(target)))
    if any(ch in target for ch in "*?["):
        found = [Path(x) for x in globlib.glob(str(p), recursive=True)]
    elif p.is_dir():
        found = [x for x in p.rglob("*") if x.is_file()]
    elif p.exists():
        found = [p]
    else:
        raise RecompError("E_NOT_FOUND", f"nothing at {target}", hint="Check the path; quote globs.")
    media = sorted(x.resolve() for x in found if x.suffix.lower() in ff.MEDIA_EXTS)
    return media


def find_sidecars(media: Path) -> list[Path]:
    stem = media.stem.lower()
    out = []
    for entry in media.parent.iterdir():
        if entry.is_file() and entry.suffix.lower() in ff.SUB_EXTS:
            name = entry.stem.lower()
            if name == stem or name.startswith(stem + "."):
                out.append(entry)
    return sorted(out, key=lambda x: (len(x.stem), x.name))


TEXT_SUB_CODECS = {"subrip", "ass", "ssa", "mov_text", "webvtt", "text"}


def embedded_subs(path: Path, info: ff.MediaInfo) -> list[tuple[ff.Stream, str]]:
    out = []
    for i, s in enumerate(info.subtitles):
        if s.codec_name not in TEXT_SUB_CODECS:
            continue
        try:
            res = ff.run(["-i", str(path), "-map", f"0:s:{i}", "-f", "srt", "pipe:1"], capture_stdout=True, timeout=300)
            out.append((s, res.stdout.decode("utf-8", "replace")))
        except RecompError:
            continue
    return out


def queue_processing(db, src: dict, which: list[str], force: bool = False) -> list[str]:
    queued = []
    audio_job = None
    for kind in which:
        deps = [audio_job] if kind == "peaks" and audio_job else []
        j = jobs.enqueue(db, kind, target=src["ref"], source_id=src["id"],
                         params={"force": True} if force else {}, depends_on=deps)
        if kind == "audio":
            audio_job = j["ref"]
        queued.append(j["ref"])
    return queued


class AddIn(BaseModel):
    target: str = Field("", description="File, folder, glob (quote it) or link (omit with --pick)", json_schema_extra={"pos": 0})
    title: str | None = Field(None, description="Title (default: parsed from the file name / link metadata)")
    year: int | None = None
    creator: str | None = Field(None, description="Director, channel, speaker…")
    language: str | None = Field(None, description="Spoken language code (default: project language)")
    subs: str | None = Field(None, description="Subtitle file to import (default: find sidecars and embedded)")
    subtitles: bool = Field(True, description="Import sidecar/embedded subtitles automatically")
    process: bool = Field(True, description="Queue audio, peaks, shots and thumbnails jobs")
    jobs: list[str] = Field(default_factory=lambda: list(DEFAULT_JOBS), description="Which processing jobs")
    limit: int | None = Field(None, description="Links: how many entries of a channel/playlist to list")
    match: str | None = Field(None, description="Links: only entries whose title matches (regex, case-insensitive)")
    since: str | None = Field(None, description="Links: only entries newer than e.g. 90d")
    pick: list[str] = Field(default_factory=list, description="Links: add these entries from the last pick list (numbers or ids)")
    dub_to: list[str] = Field(default_factory=list, description="Languages to dub this media into (shown by `dub settings`)")
    dub_route: str | None = Field(None, description="LLM dubber route: auto, direct, source (src-en), target (tgt-en), "
                                                     "middle (mid-en), multi")
    dub_middle: list[str] | None = Field(None, description="LLM dubber middle languages, e.g. en or en,es")
    dub_budget: str | None = Field(None, description="LLM dubber budget: economy (one writing language) or quality (two)")
    dub_views_mt: list[str] | None = Field(None, description="MT systems for the understanding views: nllb, m2m100, bergamot, google")
    dub_mt: str | None = Field(None, description="MT system into the dub language: nllb, m2m100, bergamot (offline) or google (online)")
    dub_online: bool | None = Field(None, description="Allow online engines (google MT, edge voices) for this media; default offline")


@verb("source.add", AddIn, effect="write",
      examples=[r'recomp source add "D:\Recomp\Video\The.Dark.Knight*.mp4"',
                r"recomp source add D:\Movies --jobs audio,peaks",
                "recomp source add https://www.youtube.com/@CosmicSkeptic/videos --limit 30",
                "recomp source add --pick 2,5,9"])
def source_add(ctx: Ctx, inp: AddIn):
    """Add media: files are referenced in place (never copied); subtitles beside them are imported; processing jobs are queued. Links and channels: see the recomp-ingest skill."""
    if inp.pick or URL.match(inp.target or ""):
        from ..ingest import links
        return links.add(ctx, inp)
    if not inp.target:
        raise RecompError("E_INVALID", "give a file, folder, glob or link (or --pick from the last list)")
    files = expand(inp.target)
    if not files:
        raise RecompError("E_NOT_FOUND", f"no media files at {inp.target}",
                          hint=f"Recognised extensions: {', '.join(sorted(ff.MEDIA_EXTS))}")
    db = ctx.db
    lang_default = inp.language or (ctx.project.meta.get("languages") or ["en"])[0]
    from ..lang import llmdub
    dub = llmdub.normalise({"route": inp.dub_route, "middle": inp.dub_middle, "budget": inp.dub_budget,
                            "views_mt": inp.dub_views_mt, "mt": inp.dub_mt, "online": inp.dub_online})
    if inp.dub_to:
        dub["targets"] = [x.strip() for x in inp.dub_to if x.strip()]
    added, skipped, warnings, queued = [], [], [], []
    for path in files:
        fp = identity.fingerprint(path)
        existing = db.one("SELECT ref FROM source WHERE fingerprint=?", (fp,))
        if existing:
            skipped.append({"path": str(path), "ref": existing["ref"], "why": "already in the project"})
            continue
        info = ff.probe(path)
        title, year = identity.title_from_filename(path.name)
        if len(files) == 1 and inp.title:
            title = inp.title
        tags_title = info.tags.get("title") or info.tags.get("TITLE")
        if tags_title and not inp.title and len(tags_title) > 3 and not re.search(r"\.(mp4|mkv)$", tags_title, re.I):
            title = tags_title if len(title) < 3 else title
        year = inp.year or year
        p = info.to_dict()
        sub_files = [Path(inp.subs)] if inp.subs else (find_sidecars(path) if inp.subtitles else [])
        emb = embedded_subs(path, info) if inp.subtitles and not inp.subs and not sub_files else []
        with ctx.op(f"add {path.name}") as tx:
            src = tx.insert("source", {
                "kind": "file", "uri": path.as_uri(), "path": str(path), "title": title, "year": year,
                "creator": inp.creator or "", "language": lang_default, "duration": info.duration,
                "size": info.size, "fingerprint": fp,
                "rights": {"kind": "file", "notice": f"{title}" + (f" ({year})" if year else ""), "owner": "",
                           "licence": "all rights reserved (owner's copy)"},
                "status": {"probe": "done"},
                "meta": {"probe": p, "filename": path.name, "embedded_chapters": info.chapters[:200],
                         **({"dub": dub} if dub else {})}})
            imported = []
            for sf in sub_files:
                segs, problems = tparse.parse_file(sf)
                if not segs:
                    warnings.append(f"{sf.name}: no readable cues")
                    continue
                lang = tparse.guess_language(sf, segs, lang_default)
                tr = add_transcript(tx, src, segs, origin="sidecar", language=lang, label=sf.name,
                                    stats={"problems": len(problems), "problem_examples": problems[:5]})
                imported.append({"ref": tr["ref"], "file": sf.name, "segments": len(segs), "language": lang,
                                 "problems": len(problems)})
            for stream, text in emb:
                segs, problems = tparse.parse_cues(text)
                if segs:
                    lang = (stream.language[:2] if stream.language else None) or tparse.guess_language(path, segs, lang_default)
                    tr = add_transcript(tx, src, segs, origin="embedded", language=lang,
                                        label=f"stream {stream.index} {stream.title}".strip())
                    imported.append({"ref": tr["ref"], "stream": stream.index, "segments": len(segs), "language": lang})
            if imported:
                status = dict(src["status"])
                status["transcript"] = "done"
                tx.update("source", src["id"], {"status": status}, log=False)
        if inp.process:
            queued += queue_processing(db, src, inp.jobs)
        added.append({"ref": src["ref"], "title": title, "year": year, "duration": clock(info.duration),
                      "kind": info.kind, "transcripts": imported})
    mode = jobs.kick(ctx.project) if queued else None
    nxt = []
    for a in added:
        if a["transcripts"]:
            nxt.append(f"recomp transcript sync-check {a['ref']}")
            nxt.append(f"recomp transcript outline {a['ref']}")
        else:
            nxt.append(f"recomp transcript asr {a['ref']}")
    return Result(data={"added": added, "skipped": skipped, "jobs": queued, "runner": mode},
                  refs=[a["ref"] for a in added], warnings=warnings, next=nxt[:4])


class ListIn(BaseModel):
    kind: str | None = Field(None, description="file or link")
    match: str | None = Field(None, description="Title contains")


@verb("source.list", ListIn)
def source_list(ctx: Ctx, inp: ListIn):
    """Sources with duration, transcript and counts."""
    from .system import source_brief
    where, params = [], []
    if inp.kind:
        where.append("kind=?")
        params.append(inp.kind)
    if inp.match:
        where.append("title LIKE ?")
        params.append(f"%{inp.match}%")
    rows = ctx.db.rows("source", ("WHERE " + " AND ".join(where) if where else "") + " ORDER BY created_at", params)
    return [source_brief(ctx.db, s) for s in rows]


class RefIn(BaseModel):
    ref: str = Field(..., description="Source ref, e.g. S1", json_schema_extra={"pos": 0})


@verb("source.show", RefIn)
def source_show(ctx: Ctx, inp: RefIn):
    """Everything about one source: media facts, rights, transcripts, stages, counts, files."""
    db = ctx.db
    s = refs.source(db, inp.ref)
    trs = [{"ref": t["ref"], "origin": t["origin"], "language": t["language"], "label": t["label"],
            "primary": bool(t["is_primary"]), "words": bool(t["has_words"]), "offset_s": t["offset_s"],
            "stats": t["stats"]} for t in db.rows("transcript", "WHERE source_id=? ORDER BY created_at", (s["id"],))]
    assets = [{"role": a["role"], "path": a["path"], "range": [a["range_start"], a["range_end"]]}
              for a in db.rows("asset", "WHERE source_id=?", (s["id"],))]
    return {"ref": s["ref"], "title": s["title"], "year": s["year"], "creator": s["creator"], "kind": s["kind"],
            "uri": s["uri"], "path": s["path"], "platform": s["platform"], "platform_id": s["platform_id"],
            "language": s["language"], "duration": s["duration"], "clock": clock(s["duration"]),
            "rights": s["rights"], "status": s["status"], "probe": (s["meta"] or {}).get("probe"),
            "transcripts": trs, "assets": assets,
            "counts": {t: db.scalar(f"SELECT COUNT(*) FROM {t} WHERE source_id=?", (s["id"],))
                       for t in ("chapter", "cut", "shot")},
            "meta": {k: v for k, v in (s["meta"] or {}).items() if k not in ("probe",)}}


@verb("source.status", NoInput)
def source_status(ctx: Ctx, inp: NoInput):
    """Pipeline stage per source (probe, audio, peaks, shots, thumbs, transcript…) and running jobs."""
    out = []
    for s in ctx.db.rows("source", "ORDER BY created_at"):
        running = [jobs.brief(j) for j in ctx.db.rows("job", "WHERE source_id=? AND status IN ('queued','running')",
                                                      (s["id"],))]
        out.append({"ref": s["ref"], "title": s["title"], "status": s["status"], "jobs": running})
    return out


class ProcessIn(BaseModel):
    ref: str = Field(..., json_schema_extra={"pos": 0})
    jobs: list[str] = Field(default_factory=lambda: list(DEFAULT_JOBS))
    force: bool = Field(False, description="Redo even if already done")


@verb("source.process", ProcessIn, effect="heavy", examples=["recomp source process S1 --jobs shots --force"])
def source_process(ctx: Ctx, inp: ProcessIn):
    """(Re)queue processing jobs for a source: audio, peaks, shots, thumbs."""
    s = refs.source(ctx.db, inp.ref)
    bad = [j for j in inp.jobs if j not in DEFAULT_JOBS]
    if bad:
        raise RecompError("E_INVALID", f"unknown job(s) {bad}; choose from {DEFAULT_JOBS}")
    q = queue_processing(ctx.db, s, inp.jobs, force=inp.force)
    mode = jobs.kick(ctx.project)
    return Result(data={"jobs": q, "runner": mode}, job=q[0] if q else None)


@verb("source.refresh", RefIn, effect="network", examples=["recomp source refresh S2"])
def source_refresh(ctx: Ctx, inp: RefIn):
    """Complete a link source's metadata (creator chapters, caption languages, date) and fetch captions if missing."""
    from ..ingest import links
    s = refs.source(ctx.db, inp.ref)
    if s["kind"] != "link":
        raise RecompError("E_INVALID", f"{s['ref']} is a local file")
    return links.refresh(ctx, s)


class FetchVideoIn(BaseModel):
    ref: str = Field(..., json_schema_extra={"pos": 0})
    height: int = Field(720, description="Maximum height (720 is plenty for talks and shorts)")


@verb("source.fetch-video", FetchVideoIn, effect="network", examples=["recomp source fetch-video S2"])
def source_fetch_video(ctx: Ctx, inp: FetchVideoIn):
    """Download a link source's whole video once (≤720p by default) so its cuts render and play locally."""
    from ..ingest import links
    s = refs.source(ctx.db, inp.ref)
    if s["kind"] != "link":
        raise RecompError("E_INVALID", f"{s['ref']} is a local file")
    j = jobs.enqueue(ctx.db, "fetch-video", target=s["ref"], source_id=s["id"], params={"height": inp.height})
    mode = jobs.kick(ctx.project)
    return Result(data={"job": j["ref"], "runner": mode}, job=j["ref"])


@verb("source.fetch-audio", RefIn, effect="network", examples=["recomp source fetch-audio S2"])
def source_fetch_audio(ctx: Ctx, inp: RefIn):
    """Download only the audio of a link source (about 1 MB a minute), then make its 16 kHz audio and waveform."""
    s = refs.source(ctx.db, inp.ref)
    if s["kind"] != "link":
        raise RecompError("E_INVALID", f"{s['ref']} is a local file")
    j1 = jobs.enqueue(ctx.db, "fetch-audio", target=s["ref"], source_id=s["id"])
    j2 = jobs.enqueue(ctx.db, "audio", target=s["ref"], source_id=s["id"], depends_on=[j1["ref"]])
    j3 = jobs.enqueue(ctx.db, "peaks", target=s["ref"], source_id=s["id"], depends_on=[j2["ref"]])
    mode = jobs.kick(ctx.project)
    return Result(data={"jobs": [j1["ref"], j2["ref"], j3["ref"]], "runner": mode}, job=j1["ref"])


class RelinkIn(BaseModel):
    ref: str = Field(..., json_schema_extra={"pos": 0})
    path: str = Field(..., json_schema_extra={"pos": 1})
    force: bool = Field(False, description="Accept a file whose fingerprint differs")


@verb("source.relink", RelinkIn, effect="write")
def source_relink(ctx: Ctx, inp: RelinkIn):
    """Point a source at its file's new location (checked by fingerprint)."""
    s = refs.source(ctx.db, inp.ref)
    p = Path(inp.path).resolve()
    fp = identity.fingerprint(p)
    if s["fingerprint"] and fp != s["fingerprint"] and not inp.force:
        raise RecompError("E_CONFLICT", "that file's fingerprint differs from the original",
                          hint="If it is the same work in another release, pass --force (timings may shift).")
    with ctx.op(f"relink {s['ref']}") as tx:
        tx.update("source", s["id"], {"path": str(p), "uri": p.as_uri(), "fingerprint": fp})
    nxt = []
    if (s.get("meta") or {}).get("release_anchors") and fp != (s["meta"].get("release_fingerprint") or fp):
        nxt.append(f"recomp source match-release {s['ref']}  (after its transcript is in: lines imported cuts up with this copy)")
    return Result(data={"ref": s["ref"], "path": str(p)}, next=nxt)


class MatchReleaseIn(BaseModel):
    ref: str = Field(..., json_schema_extra={"pos": 0})
    dry_run: bool = Field(False, description="Measure and report; move nothing")


@verb("source.match-release", MatchReleaseIn, effect="write",
      examples=["recomp source match-release S2", "recomp source match-release S2 --dry-run"])
def source_match_release(ctx: Ctx, inp: MatchReleaseIn):
    """Line up cuts imported from a recipe with this copy of the film (another release, a cut scene, PAL speed).
    Finds the recipe's anchor lines in this copy's transcript, measures the offset near each cut and shifts the
    imported cuts by it. Running it again after a better transcript moves them by the difference only."""
    from ..compose import release
    db = ctx.db
    s = refs.source(db, inp.ref)
    meta = s.get("meta") or {}
    anchors = meta.get("release_anchors")
    if not anchors:
        raise RecompError("E_NOT_FOUND", f"{s['ref']} has no recipe anchors to match",
                          hint="They come with a recipe imported or pulled for a copy whose fingerprint differs.")
    segs = release.segments(db, s["id"])
    if not segs:
        raise RecompError("E_NOT_FOUND", f"{s['ref']} has no transcript yet",
                          hint=f"Import its subtitles (`recomp transcript import {s['ref']} <file.srt>`) or run ASR first.")
    m = release.match(anchors, segs)
    if m["offset_s"] is None:
        raise RecompError("E_NOT_FOUND", f"none of the {len(anchors)} anchor lines were found in {s['ref']}'s transcript",
                          hint="Is it the same work? Check its language and transcript; or move the cuts by eye.")
    imported = set(meta.get("release_cuts") or [])
    cuts = [c for c in db.rows("cut", "WHERE source_id=?", (s["id"],))
            if (c["ref"] in imported if imported else "imported" in (c.get("tags") or []))]
    cut_ids = [c["id"] for c in cuts]
    summary = {k: m[k] for k in ("offset_s", "matched", "anchors", "coverage", "spread_s", "edit", "confidence")}
    if inp.dry_run:
        applied = (meta.get("release_match") or {}).get("applied") or {}
        per = [{"cut": c["ref"], "offset_s": release.offset_near(m, c["start"] - float(applied.get(c["id"], 0.0)))} for c in cuts]
        return {**summary, "cuts": per, "dry_run": True}
    with ctx.op(f"match {s['ref']} to the recipe's release") as tx:
        moved = release.apply(tx, db, s, m, cut_ids)
    warn = ["the offset changes along the film (a scene cut or added, or another speed): each cut took the offset "
            "measured near it; check the cuts around the change"] if m["edit"] else []
    return Result(data={**summary, "cuts": moved}, refs=[x["cut"] for x in moved], warnings=warn)


class RightsIn(BaseModel):
    ref: str = Field(..., json_schema_extra={"pos": 0})
    owner: str | None = Field(None, description="Rights holder, e.g. the studio or channel")
    notice: str | None = Field(None, description="Credit line shown in exports")
    licence: str | None = None
    url: str | None = Field(None, description="Canonical page for the work")
    title: str | None = None
    year: int | None = None
    creator: str | None = None
    status: str | None = Field(None, description="campaign (a clipping program by the rights holder covers it), permitted "
                                                 "(the creator's permission is verified) or private (everything else)")
    evidence: str | None = Field(None, description="Link to the program's terms or the creator's permission")


@verb("source.rights", RightsIn, effect="write",
      examples=['recomp source rights S1 --owner "Warner Bros." --notice "The Dark Knight (2008), Warner Bros."',
                "recomp source rights S3 --status permitted --evidence https://…/permission-email",
                "recomp source rights S3 --status private"])
def source_rights(ctx: Ctx, inp: RightsIn):
    """Set a source's credit and rights details (used for attribution in every export) and its rights status (D-23):
    only campaign and permitted sources can enter the posting queue; private ones work for everything else."""
    from ..core import rights as RS
    s = refs.source(ctx.db, inp.ref)
    rights = dict(s["rights"] or {})
    for k in ("owner", "notice", "licence", "url", "evidence"):
        v = getattr(inp, k)
        if v is not None:
            rights[k] = v
    if inp.status is not None:
        if inp.status not in RS.STATUSES:
            raise RecompError("E_INVALID", f"status: {', '.join(RS.STATUSES)}")
        if inp.status != "private" and not rights.get("evidence"):
            raise RecompError("E_INVALID", f"{inp.status} needs --evidence (the program's terms or the creator's permission)",
                              hint="Without evidence the source stays private: everything works except the posting queue.")
        rights["status"] = inp.status
        rights["status_at"] = time.time()
    fields = {"rights": rights}
    for k in ("title", "year", "creator"):
        v = getattr(inp, k)
        if v is not None:
            fields[k] = v
    with ctx.op(f"rights {s['ref']}") as tx:
        row = tx.update("source", s["id"], fields)
    return {"ref": row["ref"], "title": row["title"], "year": row["year"], "creator": row["creator"],
            "rights": row["rights"]}


@verb("source.remove", RefIn, effect="write")
def source_remove(ctx: Ctx, inp: RefIn):
    """Remove a source from the project (the media file itself is never touched). Its chapters and cuts go too; undo restores those, but transcripts/shots must be re-imported."""
    s = refs.source(ctx.db, inp.ref)
    used = ctx.db.scalar("SELECT COUNT(*) FROM slot sl JOIN cut c ON c.id=sl.cut_id WHERE c.source_id=?", (s["id"],))
    if used:
        raise RecompError("E_CONFLICT", f"{s['ref']} has cuts used in {used} journey slot(s)",
                          hint="Remove those slots first (`recomp journey remove`).")
    with ctx.op(f"remove {s['ref']}") as tx:
        tx.delete("source", s["id"])
    return Result(data={"removed": s["ref"]}, warnings=["Transcripts, shots and peaks are not restored by undo."])
