"""The studio server: the verbs over HTTP (as the *user*), live events, media streaming, the viewer.

    recomp serve [--port 8770] [--host 127.0.0.1]

* ``POST /api/verb/{name}`` with ``{"args": {...}, "project": "..."}`` → the verb's envelope.
* ``GET /api/events?project=P&after=SEQ`` → Server-Sent Events tailing the project's event table.
* ``GET /api/room/{ref}?project=P`` → everything the Source room draws, in one response.
* ``GET /media/source/{ref}``, ``/media/peaks/{ref}``, ``/media/thumbs/{ref}/{file}``, ``/media/file`` → range-served files.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import mimetypes
import os
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse

from .. import registry
from ..core import config, refs
from ..core.project import Project, resolve
from ..transcript.store import primary

STATIC = Path(__file__).resolve().parent.parent / "static" / "app"

app = FastAPI(title="Recomposer studio", docs_url="/api/docs")
app.add_middleware(CORSMiddleware, allow_origins=["http://127.0.0.1:5180", "http://localhost:5180"],
                   allow_methods=["*"], allow_headers=["*"])

_projects: dict[str, Project] = {}


def project(name: str | None) -> Project:
    key = name or "__current__"
    p = _projects.get(key)
    if p is None:
        try:
            p = resolve(name)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(404, str(exc)) from exc
        _projects[key] = p
    return p


@app.get("/api/health")
def health():
    return {"ok": True, "time": time.time()}


@app.post("/api/verb/{name}")
async def run_verb(name: str, request: Request):
    body = await request.json() if await request.body() else {}
    args = body.get("args") or {}
    proj = body.get("project")
    actor = body.get("actor") or "user"
    if actor not in ("user", "agent"):
        actor = "user"
    env = await asyncio.to_thread(registry.run, name, args, actor, proj)
    return JSONResponse(env)


@app.get("/api/verbs")
def verbs():
    from ..cli import help_payload
    return help_payload()


@app.get("/api/events")
async def events(request: Request, project_name: str | None = None, after: int | None = None):
    p = project(project_name or request.query_params.get("project"))
    db_path = p.root / "recomp.db"

    async def stream():
        from ..core.store import connect
        conn = connect(db_path)
        try:
            last = after
            if last is None:
                last = conn.execute("SELECT COALESCE(MAX(seq), 0) FROM event").fetchone()[0]
            yield f"event: hello\ndata: {json.dumps({'seq': last})}\n\n"
            idle = 0
            while True:
                if await request.is_disconnected():
                    break
                rows = conn.execute("SELECT seq, time, kind, payload FROM event WHERE seq > ? ORDER BY seq LIMIT 200",
                                    (last,)).fetchall()
                for r in rows:
                    last = r[0]
                    yield f"id: {r[0]}\nevent: {r[2]}\ndata: {r[3]}\n\n"
                if not rows:
                    idle += 1
                    if idle % 50 == 0:
                        yield ": keepalive\n\n"
                    await asyncio.sleep(0.3)
                else:
                    idle = 0
        finally:
            conn.close()

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/room/{ref}")
def room(ref: str, request: Request):
    """Everything the Source room draws for one source."""
    p = project(request.query_params.get("project"))
    db = p.db
    src = refs.source(db, ref)
    tr = primary(db, src["id"])
    segs, words = [], {}
    if tr:
        segs = [dict(r) for r in db.all('SELECT id, idx, start, "end", text, speaker, person_id FROM segment '
                                        "WHERE transcript_id=? ORDER BY idx", (tr["id"],))]
        if tr["has_words"]:
            for r in db.all('SELECT segment_id, start, "end", text FROM word WHERE segment_id IN '
                            "(SELECT id FROM segment WHERE transcript_id=?) ORDER BY segment_id, idx", (tr["id"],)):
                words.setdefault(r[0], []).append([round(r[1], 3), round(r[2], 3), r[3]])
    for s in segs:
        s["words"] = words.get(s.pop("id"), None)
    chapters = [{"ref": c["ref"], "start": c["start"], "end": c["end"], "title": c["title"], "summary": c["summary"],
                 "tags": c["tags"], "by": c["created_by"]} for c in db.rows("chapter", "WHERE source_id=? ORDER BY start", (src["id"],))]
    cuts = [{"ref": c["ref"], "start": c["start"], "end": c["end"], "title": c["title"], "why": c["why"],
             "tags": c["tags"], "by": c["created_by"]} for c in db.rows("cut", "WHERE source_id=? ORDER BY start", (src["id"],))]
    shots = [r[0] for r in db.all("SELECT t FROM shot WHERE source_id=? ORDER BY t", (src["id"],))]
    turns = [dict(r) for r in db.all('SELECT start, "end", label, person_id FROM speaker_turn WHERE source_id=? ORDER BY start',
                                     (src["id"],))]
    thumbs = None
    idx = p.root / "cache" / "thumbs" / src["ref"] / "index.json"
    if idx.exists():
        thumbs = json.loads(idx.read_text(encoding="utf-8"))
    peaks = None
    pj = p.root / "cache" / "peaks" / f"{src['ref']}.json"
    if pj.exists():
        peaks = json.loads(pj.read_text(encoding="utf-8"))
    meta = src["meta"] or {}
    return {"source": {"ref": src["ref"], "title": src["title"], "year": src["year"], "creator": src["creator"],
                       "kind": src["kind"], "duration": src["duration"], "platform": src["platform"],
                       "platform_id": src["platform_id"], "uri": src["uri"], "status": src["status"],
                       "has_media": bool(src["path"] and Path(src["path"]).exists()),
                       "video": (meta.get("probe") or {}).get("video")},
            "transcript": {"ref": tr["ref"], "origin": tr["origin"], "language": tr["language"],
                           "has_words": bool(tr["has_words"])} if tr else None,
            "segments": segs, "chapters": chapters, "cuts": cuts, "shots": shots, "turns": turns,
            "thumbs": thumbs, "peaks": peaks}


# ---- media ---------------------------------------------------------------------------------

def _range_file(path: Path, request: Request, media_type: str | None = None) -> Response:
    if not path.exists():
        raise HTTPException(404, "file not found")
    size = path.stat().st_size
    media_type = media_type or mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    rng = request.headers.get("range")
    if not rng or not rng.startswith("bytes="):
        return FileResponse(path, media_type=media_type, headers={"Accept-Ranges": "bytes"})
    start_s, _, end_s = rng[6:].split(",")[0].partition("-")
    start = int(start_s) if start_s else max(0, size - int(end_s))
    end = int(end_s) if end_s and start_s else size - 1
    end = min(end, size - 1, start + 8 * 1024 * 1024 - 1)
    if start >= size:
        return Response(status_code=416, headers={"Content-Range": f"bytes */{size}"})

    def chunks():
        with path.open("rb") as f:
            f.seek(start)
            left = end - start + 1
            while left > 0:
                data = f.read(min(1024 * 256, left))
                if not data:
                    break
                left -= len(data)
                yield data

    return StreamingResponse(chunks(), status_code=206, media_type=media_type, headers={
        "Content-Range": f"bytes {start}-{end}/{size}", "Accept-Ranges": "bytes",
        "Content-Length": str(end - start + 1)})


@app.get("/media/source/{ref}")
def media_source(ref: str, request: Request):
    p = project(request.query_params.get("project"))
    src = refs.source(p.db, ref)
    path = Path(src["path"]) if src["path"] else None
    if not path or not path.exists():
        alt = p.db.one("SELECT path FROM asset WHERE source_id=? AND role IN ('video','preview') ORDER BY created_at DESC",
                       (src["id"],))
        if alt is None:
            raise HTTPException(404, "no local media for this source")
        path = Path(alt[0])
    return _range_file(path, request)


@app.get("/media/peaks/{ref}")
def media_peaks(ref: str, request: Request):
    p = project(request.query_params.get("project"))
    return _range_file(p.root / "cache" / "peaks" / f"{ref}.u8", request, "application/octet-stream")


@app.get("/media/thumbs/{ref}/{name}")
def media_thumbs(ref: str, name: str, request: Request):
    p = project(request.query_params.get("project"))
    path = (p.root / "cache" / "thumbs" / ref / name).resolve()
    if p.root.resolve() not in path.parents:
        raise HTTPException(403)
    return _range_file(path, request)


@app.get("/media/frame/{ref}")
def media_frame(ref: str, request: Request, t: float = 0.0, w: int = 240):
    """One still frame (cached): slot and cut thumbnails."""
    from ..media import ff
    p = project(request.query_params.get("project"))
    src = refs.source(p.db, ref)
    path = Path(src["path"]) if src["path"] else None
    if not path or not path.exists():
        raise HTTPException(404, "no local media")
    w = max(80, min(640, int(w)))
    out = p.dir("cache", "frames") / f"{ref}_{t:.1f}_{w}.jpg"
    if not out.exists():
        try:
            ff.run_simple(["-ss", f"{max(0.0, t):.2f}", "-i", str(path), "-frames:v", "1",
                           "-vf", f"scale={w}:-2", "-q:v", "5", str(out)], timeout=30)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(500, str(exc)) from exc
    return _range_file(out, request, "image/jpeg")


@app.get("/media/file")
def media_file(request: Request, path: str):
    """A file inside the project folder (exports, previews, music)."""
    p = project(request.query_params.get("project"))
    target = (p.root / path).resolve() if not os.path.isabs(path) else Path(path).resolve()
    if p.root.resolve() not in target.parents:
        raise HTTPException(403, "outside the project")
    return _range_file(target, request)


# ---- the viewer ----------------------------------------------------------------------------

@app.get("/{full_path:path}")
def spa(full_path: str):
    if full_path.startswith(("api/", "media/")):
        raise HTTPException(404)
    target = (STATIC / full_path).resolve() if full_path else None
    if target and target.is_file() and STATIC.resolve() in target.parents:
        return FileResponse(target)
    index = STATIC / "index.html"
    if index.exists():
        return FileResponse(index, headers={"Cache-Control": "no-cache"})
    return HTMLResponse("<h1>Recomposer studio</h1><p>The viewer is not built. Run <code>npm --prefix web run build</code>.</p>")


def main(argv: list[str], project_arg: str | None = None) -> int:
    import uvicorn

    ap = argparse.ArgumentParser(prog="recomp serve")
    ap.add_argument("--port", type=int, default=int(config.get("studio.port") or 8770))
    ap.add_argument("--host", default=config.get("studio.host") or "127.0.0.1")
    a = ap.parse_args(argv)
    if project_arg:
        os.environ["RECOMP_PROJECT"] = project_arg
    print(f"Recomposer studio on http://{a.host}:{a.port}")
    uvicorn.run(app, host=a.host, port=a.port, log_level="warning")
    return 0
