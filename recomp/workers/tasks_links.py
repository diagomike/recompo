"""Link jobs: captions (net lane) and audio-only downloads (net lane)."""

from __future__ import annotations

import json
import time

from ..core.ids import ulid
from ..ingest import links
from ..transcript import parse as tparse
from ..transcript.store import add_transcript
from .jobs import JobCtx, task


@task("captions", lane="net")
def job_captions(ctx: JobCtx):
    src = ctx.source()
    lang = ctx.params.get("language") or src.get("language")
    try:
        path = links.fetch_captions(ctx.project, src, lang, log=ctx.log)
    except Exception:
        ctx.set_status("transcript", "captions-blocked")
        raise
    segs, problems = tparse.parse_file(path)
    if not segs:
        ctx.set_status("transcript", "captions-empty")
        return {"segments": 0, "note": "caption file had no readable lines"}
    code, is_auto = links.pick_caption_lang(src.get("meta") or {}, lang)
    with ctx.db.op("transcript.fetch-captions", "machine") as tx:
        tr = add_transcript(tx, src, segs, origin="platform", language=(code or lang or "en").split("-")[0],
                            label=f"{src['platform']} captions {code}" + (" (auto)" if is_auto else ""),
                            stats={"auto": is_auto, "problems": len(problems)})
    ctx.set_status("transcript", "done")
    return {"transcript": tr["ref"], "segments": len(segs), "auto": is_auto, "words": any(s.get("words") for s in segs)}


@task("fetch-audio", lane="net")
def job_fetch_audio(ctx: JobCtx):
    src = ctx.source()
    path = links.fetch_audio(ctx.project, src, progress=ctx.progress, log=ctx.log)
    with ctx.db.op("source.fetch-audio", "machine") as tx:
        tx.conn.execute("DELETE FROM asset WHERE source_id=? AND role='audio_full'", (src["id"],))
        tx.conn.execute("INSERT INTO asset(id, source_id, role, path, info, created_at) VALUES(?,?,?,?,?,?)",
                        (ulid(), src["id"], "audio_full", str(path), json.dumps({}), time.time()))
    ctx.set_status("fetch-audio", "done")
    return {"path": str(path), "mb": round(path.stat().st_size / 1e6, 1)}
