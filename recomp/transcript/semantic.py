"""Semantic search over transcripts in any language (multilingual-e5, so Amharic and Oromo too).

Each primary transcript is cut into overlapping windows of a few lines (about 40 words or 30 s); the windows
are embedded once under the worker python (`transcript embed`, a job) and kept in the project cache with a hash
of the text, so an edited transcript is noticed. A query is embedded the same way and ranked by cosine, so
"the fear of dying" finds a line about mortality, in whatever language it was said.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import numpy as np

from ..core import config
from ..envelope import RecompError

WORDS = 40
SECONDS = 30.0


def model_name() -> str:
    return config.get("search.embed_model") or "intfloat/multilingual-e5-small"


def segments(db, transcript_id: str) -> list[dict]:
    return [dict(r) for r in db.all('SELECT idx, start, "end", text FROM segment WHERE transcript_id=? ORDER BY idx',
                                    (transcript_id,))]


def windows(segs: list[dict]) -> list[dict]:
    """Overlapping runs of lines: each starts halfway through the previous one."""
    out, i = [], 0
    while i < len(segs):
        j, words = i, 0
        while j < len(segs) and (j == i or (words < WORDS and segs[j]["end"] - segs[i]["start"] < SECONDS)):
            words += len(segs[j]["text"].split())
            j += 1
        out.append({"i0": segs[i]["idx"], "i1": segs[j - 1]["idx"], "start": segs[i]["start"], "end": segs[j - 1]["end"],
                    "text": " ".join(s["text"] for s in segs[i:j])})
        if j >= len(segs):
            break
        i += max(1, (j - i) // 2)
    return out


def text_hash(segs: list[dict]) -> str:
    return hashlib.sha256("\n".join(s["text"] for s in segs).encode("utf-8")).hexdigest()[:16]


def embed(project, texts: list[str], kind: str, ctx=None) -> np.ndarray:
    from ..workers.worker_env import run_script
    tmp = project.dir("cache", "semantic", "tmp")
    stamp = f"{time.time_ns()}"
    src, out = tmp / f"{stamp}.json", tmp / f"{stamp}.npy"
    src.write_text(json.dumps(texts, ensure_ascii=False), encoding="utf-8")
    try:
        run_script("embed", ["--model", model_name(), "--input", str(src), "--kind", kind, "--out", str(out)], ctx)
        return np.load(out).astype(np.float32)
    finally:
        src.unlink(missing_ok=True)
        out.unlink(missing_ok=True)


def index_path(project, transcript_id: str) -> Path:
    return project.dir("cache", "semantic") / f"{transcript_id}.npz"


def build_index(project, db, transcript_id: str, ctx=None) -> dict:
    segs = segments(db, transcript_id)
    wins = windows(segs)
    vecs = embed(project, [w["text"] for w in wins], "passage", ctx) if wins else np.zeros((0, 384), np.float32)
    meta = {"model": model_name(), "hash": text_hash(segs), "windows": [{k: w[k] for k in ("i0", "i1", "start", "end")} for w in wins]}
    np.savez(index_path(project, transcript_id), vecs=vecs.astype(np.float16), meta=json.dumps(meta))
    return {"windows": len(wins), "dim": int(vecs.shape[1]) if len(vecs) else 0}


def load_index(project, transcript_id: str) -> tuple[np.ndarray, dict] | None:
    p = index_path(project, transcript_id)
    if not p.exists():
        return None
    z = np.load(p)
    return z["vecs"].astype(np.float32), json.loads(str(z["meta"]))


def search(project, db, query: str, source_ids: list[str] | None, limit: int) -> dict:
    """Ranked windows across the project's primary transcripts that have an index."""
    rows = db.all("SELECT t.id, t.source_id, src.ref, src.title FROM transcript t JOIN source src ON src.id=t.source_id "
                  "WHERE t.is_primary=1" + (f" AND t.source_id IN ({','.join('?' * len(source_ids))})" if source_ids else ""),
                  tuple(source_ids or ()))
    found, missing, stale = [], [], []
    for r in rows:
        ix = load_index(project, r["id"])
        if ix is None or ix[1].get("model") != model_name():
            missing.append(r["ref"])
            continue
        if ix[1]["hash"] != text_hash(segments(db, r["id"])):
            stale.append(r["ref"])
        found.append((r, ix))
    if not found:
        raise RecompError("E_NOT_FOUND", "no transcript has a semantic index yet",
                          hint="`recomp transcript embed` (all sources, a job; a few minutes per long film on CPU).")
    q = embed(project, [query], "query")[0]
    scored = []
    for r, (vecs, meta) in found:
        if not len(vecs):
            continue
        sims = vecs @ q
        for k in np.argsort(-sims)[: limit * 2]:
            scored.append((float(sims[k]), r, meta["windows"][int(k)]))
    scored.sort(key=lambda x: -x[0])
    hits, taken = [], []
    for score, r, w in scored:
        if any(t[0] == r["ref"] and w["start"] < t[2] and t[1] < w["end"] for t in taken):
            continue  # overlapping windows of one place count once
        taken.append((r["ref"], w["start"], w["end"]))
        hits.append({"score": round(score, 3), "source_id": r["source_id"], "transcript_id": r["id"], "sref": r["ref"],
                     "stitle": r["title"], **w})
        if len(hits) >= limit:
            break
    return {"hits": hits, "missing": missing, "stale": stale}
