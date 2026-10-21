"""Speech jobs: ASR (whole source or windows) and the subtitle sync check."""

from __future__ import annotations

import json

from ..core import config
from ..envelope import RecompError
from ..transcript import align
from ..transcript.parse import segments_from_words
from ..transcript.refine import refine_segments
from ..transcript.store import add_transcript, primary
from .jobs import JobCtx, task
from .tasks_media import audio_path
from .worker_env import run_script


def ensure_audio(ctx: JobCtx, src: dict):
    wav = audio_path(ctx.project, src)
    if not wav.exists():
        from .tasks_media import job_audio
        ctx.log("extracting audio first")
        job_audio(ctx)
    return wav


def _asr(ctx: JobCtx, src: dict, ranges: list[list[float]] | None, language: str | None,
         model: str | None = None, engine: str = "whisper") -> dict:
    wav = ensure_audio(ctx, src)
    out = ctx.folder / "asr.json"
    args = ["--wav", str(wav), "--out", str(out), "--model", model or config.get("worker.asr_model"),
            "--compute-type", config.get("worker.asr_compute_type") or "int8", "--engine", engine]
    if config.get("worker.threads"):
        args += ["--threads", str(config.get("worker.threads"))]
    if language:
        args += ["--language", language]
    if ranges:
        args += ["--ranges", ",".join(f"{a:.2f}-{b:.2f}" for a, b in ranges)]
    run_script("asr", args, ctx, allow_download=bool(ctx.params.get("allow_download")))
    return json.loads(out.read_text(encoding="utf-8"))


@task("asr", lane="cpu")
def job_asr(ctx: JobCtx):
    src = ctx.source()
    p = ctx.params
    lang = p.get("language") or None
    result = _asr(ctx, src, p.get("ranges"), lang, p.get("model"), p.get("engine", "whisper"))
    segs = result["segments"]
    refine_stats = None
    if segs and p.get("engine", "whisper") == "whisper" and p.get("refine", True):
        refine_stats = refine_segments(segs, audio_path(ctx.project, src))
        ctx.log(f"onset refinement: {refine_stats}")
    if p.get("resegment", True) and segs and all(s.get("words") for s in segs):
        words = [w for s in segs for w in s["words"]]
        segs = segments_from_words(words, gap=0.6, max_len=14.0)
    result["refine"] = refine_stats
    label = "ASR " + result["model"].split("/")[-1] + (" (windows)" if p.get("ranges") else "")
    with ctx.db.op("transcript.asr", "machine") as tx:
        tr = add_transcript(tx, src, segs, origin="asr", language=result.get("language") or lang,
                            label=label, model=result["model"], make_primary=p.get("primary"),
                            stats={"audio_s": result["audio_s"], "elapsed_s": result["elapsed_s"],
                                   "rtf": round(result["elapsed_s"] / max(1.0, result["audio_s"]), 3),
                                   "ranges": result.get("ranges"), "refine": result.get("refine")})
    ctx.set_status("transcript", "done")
    return {"transcript": tr["ref"], "segments": len(segs), "language": result.get("language"),
            "audio_s": result["audio_s"], "elapsed_s": result["elapsed_s"]}


def pick_windows(segments: list[dict], duration: float, n: int = 3, length: float = 60.0) -> list[list[float]]:
    """Windows at ~20/50/80 % that contain the most subtitle text nearby."""
    out = []
    for frac in [0.2, 0.5, 0.8][:n]:
        centre = duration * frac
        best, best_words = centre, -1
        for shift in range(-180, 181, 30):
            a = max(0.0, centre + shift - length / 2)
            words = sum(len(s["text"].split()) for s in segments if a <= s["start"] < a + length)
            if words > best_words:
                best, best_words = a, words
        out.append([round(best, 2), round(min(duration, best + length), 2)])
    return out


@task("synccheck", lane="cpu")
def job_synccheck(ctx: JobCtx):
    src = ctx.source()
    db = ctx.db
    tr = db.by_ref("transcript", ctx.params["transcript"])
    segs = [dict(r) for r in db.all('SELECT start, "end", text FROM segment WHERE transcript_id=? ORDER BY idx', (tr["id"],))]
    if not segs:
        raise RecompError("E_INVALID", "transcript has no segments")
    windows = pick_windows(segs, src["duration"] or segs[-1]["end"])
    result = _asr(ctx, src, windows, tr.get("language"))
    words = [w for s in result["segments"] for w in s.get("words", [])]
    per = [dict(align.estimate_offset(segs, words, (a, b)), window=[a, b]) for a, b in windows]
    overall = align.estimate_offset(segs, words)
    verdict = sync_verdict(overall, per)
    stats = dict(tr["stats"] or {})
    stats["sync"] = {"offset_s": overall["offset_s"], "per_window": per, "verdict": verdict}
    with db.op("transcript.sync-check", "machine") as tx:
        tx.update("transcript", tr["id"], {"stats": stats}, log=False)
    return {"transcript": tr["ref"], "offset_s": overall["offset_s"], "confidence": overall["confidence"],
            "verdict": verdict, "windows": per}


def sync_verdict(overall: dict, per: list[dict]) -> str:
    off = overall.get("offset_s")
    if off is None:
        return "unknown: too few words matched (different language or very loose subtitles?)"
    offs = [p["offset_s"] for p in per if p.get("offset_s") is not None]
    drift = (max(offs) - min(offs)) if len(offs) > 1 else 0.0
    if drift > 1.0:
        return f"drifting: offsets differ by {drift:.1f}s across the film (a different frame rate or cut)"
    if abs(off) <= 0.3:
        return "in sync"
    return f"offset by {off:+.2f}s (subtitles {'late' if off > 0 else 'early'}): run with --fix to shift"


@task("embed", lane="cpu")
def job_embed(ctx: JobCtx):
    """Semantic index of the source's primary transcript (transcript/semantic.py)."""
    from ..transcript import semantic
    src = ctx.source()
    tr = primary(ctx.db, src["id"])
    if tr is None:
        raise RecompError("E_NOT_FOUND", f"{src['ref']} has no transcript", hint=f"`recomp transcript asr {src['ref']}`")
    return {"transcript": tr["ref"], **semantic.build_index(ctx.project, ctx.db, tr["id"], ctx)}
