"""Semantic search over transcripts in any language (multilingual-e5, so Amharic and Oromo too).

Each primary transcript is cut into overlapping windows of a few lines (about 40 words or 30 s); the windows
are embedded once under the worker python (`transcript embed`, a job) and kept in the project cache with a hash
of the text, so an edited transcript is noticed. A query is embedded the same way and ranked by cosine, so
"the fear of dying" finds a line about mortality, in whatever language it was said. Queries go to a resident
embedder that keeps the model loaded (see below), so only the first one waits for it.
"""

from __future__ import annotations

import hashlib
import json
import os
import socket
import subprocess
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
    """Queries go to the resident embedder (about a second once it is up); passages, and queries when it cannot
    start, run the one-shot script (which loads the model each time)."""
    global last_via
    if kind == "query" and config.get("search.resident", True):
        try:
            vecs = resident_embed(texts, kind)
            last_via = "resident"
            return vecs
        except (OSError, ValueError, KeyError, RuntimeError, RecompError):
            pass
    last_via = "script"
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


# ---- the resident embedder ------------------------------------------------------------------
# One detached `embed.py --serve` per studio home, shared by the CLI, the MCP server and the studio: the first query
# starts it (and waits for the model, as long as a one-shot run), later ones reach it on 127.0.0.1 through the state
# file in <home>/run/. It exits after `search.embed_idle_s` (default 600) without a query.

START_WAIT_S = 120.0
last_via = ""  # "resident" or "script": how the last embed() ran (tests, timing)


def _run_dir() -> Path:
    d = config.home() / "run"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _state() -> dict | None:
    try:
        return json.loads((_run_dir() / "embed.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _ask(state: dict, req: dict, timeout: float = 30.0) -> dict:
    with socket.create_connection(("127.0.0.1", int(state["port"])), timeout=timeout) as s:
        s.sendall((json.dumps({"token": state["token"], **req}, ensure_ascii=False) + "\n").encode("utf-8"))
        buf = b""
        while not buf.endswith(b"\n"):
            chunk = s.recv(1 << 16)
            if not chunk:
                break
            buf += chunk
    msg = json.loads(buf.decode("utf-8"))
    if not msg.get("ok"):
        raise RuntimeError(f"resident embedder: {msg.get('error')}")
    return msg


def _alive(state: dict | None) -> bool:
    if not state or state.get("model") != model_name():
        return False
    try:
        _ask(state, {"op": "ping"}, timeout=2.0)
        return True
    except (OSError, ValueError, KeyError, RuntimeError):
        return False


def _spawn(tag: str):
    from ..workers.worker_env import CREATE_NO_WINDOW, SCRIPTS, worker_python
    env = dict(os.environ)
    env["HF_HOME"] = config.get("worker.hf_home") or env.get("HF_HOME", "")
    env["HF_HUB_OFFLINE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUNBUFFERED"] = "1"
    idle = float(config.get("search.embed_idle_s") or 600)
    cmd = [worker_python(), "-I", str(SCRIPTS / "embed.py"), "--model", model_name(), "--serve",
           "--state", str(_run_dir() / "embed.json"), "--idle", str(idle), "--tag", tag]
    flags = 0x00000008 | 0x00000200 | CREATE_NO_WINDOW if os.name == "nt" else 0  # DETACHED | NEW_PROCESS_GROUP
    with (_run_dir() / "embed.log").open("a", encoding="utf-8") as log:
        return subprocess.Popen(cmd, stdout=log, stderr=log, stdin=subprocess.DEVNULL, env=env, creationflags=flags,
                                close_fds=True, cwd=str(_run_dir()), start_new_session=os.name != "nt")


def resident(start: bool = True) -> dict | None:
    """The running resident's state ({pid, port, token, model}); starts one (and waits for it) if asked."""
    st = _state()
    if _alive(st):
        return st
    if not start:
        return None
    lock = _run_dir() / "embed.spawn"
    try:
        os.close(os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
        tag = os.urandom(8).hex()  # the venv's python.exe re-launches the real one: the pid differs, the tag does not
        proc = _spawn(tag)  # ours to start; another caller starting one at the same time waits for it below
    except FileExistsError:
        if time.time() - lock.stat().st_mtime > START_WAIT_S:
            lock.unlink(missing_ok=True)
            return resident(start)
        proc = None
    except BaseException:
        lock.unlink(missing_ok=True)
        raise
    try:
        deadline = time.time() + START_WAIT_S
        while time.time() < deadline:
            st = _state()
            if st and (proc is None or st.get("tag") == tag) and _alive(st):
                return st
            if proc is not None and proc.poll() is not None:
                return None  # it died (no torch, no model in the cache…): embed.log says why
            time.sleep(0.2)
        if proc is not None:
            proc.kill()
        return None
    finally:
        if proc is not None:
            lock.unlink(missing_ok=True)


def resident_embed(texts: list[str], kind: str = "query") -> np.ndarray:
    st = resident()
    if st is None:
        raise RuntimeError("the resident embedder did not start")
    msg = _ask(st, {"op": "embed", "kind": kind, "texts": texts}, timeout=60.0)
    return np.asarray(msg["vectors"], dtype=np.float32).reshape(len(texts), int(msg["dim"]))


def stop_resident() -> bool:
    """Stop the resident embedder now (it also stops by itself after idling). True if one was running."""
    st = _state()
    if not st:
        return False
    try:
        _ask(st, {"op": "stop"}, timeout=5.0)
        return True
    except (OSError, ValueError, KeyError, RuntimeError):
        return False


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
