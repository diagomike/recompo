"""Media jobs for a source: 16 kHz audio, waveform peaks, shot boundaries, thumbnail sprites."""

from __future__ import annotations

import json
import time
from pathlib import Path

from ..core.ids import ulid
from ..envelope import RecompError
from ..media import audio, ff, shots
from .jobs import JobCtx, task


def media_path(ctx: JobCtx, src: dict) -> Path:
    if src.get("path") and Path(src["path"]).exists():
        return Path(src["path"])
    raise RecompError("E_NOT_FOUND", f"{src['ref']}: media file not available locally",
                      hint=f"`recomp source relink {src['ref']} <path>` or fetch it (links: `recomp source fetch-audio`).")


def audio_path(project, src: dict) -> Path:
    return project.root / "sources" / src["ref"] / "audio16k.wav"


@task("audio", lane="cpu")
def job_audio(ctx: JobCtx):
    src = ctx.source()
    meta = src.get("meta") or {}
    a = (meta.get("probe") or {}).get("audio") or {}
    dest = audio_path(ctx.project, src)
    if not dest.exists() or ctx.params.get("force"):
        if not src.get("path") and src.get("kind") == "link":
            raise RecompError("E_NOT_FOUND", f"{src['ref']} has no local media yet",
                              hint=f"`recomp source fetch-audio {src['ref']}`")
        audio.extract_16k(media_path(ctx, src), dest, a.get("channels"), a.get("layout", ""),
                          duration=src.get("duration"), progress=ctx.progress, cancelled=ctx.cancelled)
    with ctx.db.op("job.audio", "machine") as tx:
        tx.conn.execute("DELETE FROM asset WHERE source_id=? AND role='audio16k'", (src["id"],))
        tx.conn.execute("INSERT INTO asset(id, source_id, role, path, info, created_at) VALUES(?,?,?,?,?,?)",
                        (ulid(), src["id"], "audio16k", str(dest), json.dumps({"sr": 16000}), time.time()))
    ctx.set_status("audio", "done")
    return {"path": str(dest), "bytes": dest.stat().st_size}


@task("peaks", lane="cpu")
def job_peaks(ctx: JobCtx):
    src = ctx.source()
    wav = audio_path(ctx.project, src)
    if not wav.exists():
        raise RecompError("E_NOT_FOUND", "audio not extracted yet", hint=f"`recomp source process {src['ref']}`")
    out = ctx.project.dir("cache", "peaks") / f"{src['ref']}.u8"
    meta = audio.peaks_from_wav(wav, out)
    ctx.set_status("peaks", "done")
    return meta


@task("shots", lane="cpu")
def job_shots(ctx: JobCtx):
    src = ctx.source()
    probe = (src.get("meta") or {}).get("probe") or {}
    if not probe.get("video"):
        ctx.set_status("shots", "n/a")
        return {"shots": 0, "note": "no video stream"}
    cuts = shots.detect(media_path(ctx, src), src.get("duration"), threshold=float(ctx.params.get("threshold", 0.3)),
                        progress=ctx.progress, cancelled=ctx.cancelled)
    with ctx.db.op("job.shots", "machine") as tx:
        tx.conn.execute("DELETE FROM shot WHERE source_id=?", (src["id"],))
        tx.conn.executemany("INSERT OR IGNORE INTO shot(source_id, t, score) VALUES(?,?,?)",
                            [(src["id"], c["t"], c["score"]) for c in cuts])
    dur = src.get("duration") or 0
    static = len(cuts) <= 1 and dur > 120
    ctx.set_status("shots", "done")
    return {"shots": len(cuts), "static_image": static}


@task("thumbs", lane="cpu")
def job_thumbs(ctx: JobCtx):
    """Sprite sheets: one 160 px frame every N seconds, 10×10 per sheet (the viewer's filmstrip)."""
    src = ctx.source()
    probe = (src.get("meta") or {}).get("probe") or {}
    if not probe.get("video"):
        ctx.set_status("thumbs", "n/a")
        return {"sheets": 0}
    dur = src.get("duration") or 60
    every = float(ctx.params.get("every") or (10 if dur > 1200 else 5 if dur > 300 else 2))
    folder = ctx.project.dir("cache", "thumbs", src["ref"])
    for old in folder.glob("sheet_*.jpg"):
        old.unlink()
    ff.run(["-i", str(media_path(ctx, src)), "-an", "-sn", "-map", "0:v:0",
            "-vf", f"fps=1/{every},scale=160:-2,tile=10x10", "-q:v", "5", str(folder / "sheet_%03d.jpg")],
           duration=dur, progress=ctx.progress, cancelled=ctx.cancelled)
    sheets = sorted(p.name for p in folder.glob("sheet_*.jpg"))
    info = {"every": every, "cols": 10, "rows": 10, "width": 160, "sheets": sheets}
    (folder / "index.json").write_text(json.dumps(info), encoding="utf-8")
    ctx.set_status("thumbs", "done")
    return {"sheets": len(sheets), "every": every}
