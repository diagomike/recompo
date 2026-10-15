"""Jobs: queued work with progress, dependencies, cancel, retry and takeover.

A per-project runner process (``recomp worker run``) drains the queue with two lanes: ``cpu``
(one heavy job at a time: ASR, renders, shots) and ``net`` (downloads, TTS) running alongside.
Enqueueing starts the runner if none is alive (its lock file carries a heartbeat).

``RECOMP_JOBS=inline`` runs jobs synchronously in the calling process (tests);
``RECOMP_JOBS=off`` only queues them (``recomp job run`` drains later).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path
from typing import Callable

from ..core.ids import ulid
from ..core.project import Project
from ..envelope import RecompError
from ..media.ff import Cancelled

TASKS: dict[str, tuple[Callable, str]] = {}
LOCK = "runner.lock"
STALE_S = 20
RUNNING_STALE_S = 90


def task(type_: str, lane: str = "cpu"):
    def deco(fn):
        TASKS[type_] = (fn, lane)
        return fn
    return deco


def _load_tasks() -> None:
    from . import tasks_media  # noqa: F401
    for mod in ("tasks_speech", "tasks_links", "tasks_render", "tasks_lang", "tasks_speakers"):
        try:
            __import__(f"recomp.workers.{mod}")
        except ModuleNotFoundError as exc:
            if exc.name != f"recomp.workers.{mod}":
                raise


def lane_of(type_: str) -> str:
    _load_tasks()
    return TASKS.get(type_, (None, "cpu"))[1]


def enqueue(db, type_: str, target: str | None = None, source_id: str | None = None,
            params: dict | None = None, depends_on: list[str] | None = None, backend: str = "local",
            dedupe: bool = True) -> dict:
    """Queue a job (not op-logged: jobs are machine work, their *results* are ops)."""
    if dedupe:
        row = db.one("SELECT id FROM job WHERE type=? AND COALESCE(target,'')=? AND COALESCE(params,'')=? "
                     "AND status IN ('queued','running')", (type_, target or "", json.dumps(params or {}, sort_keys=True)))
        if row:
            return db.get("job", row["id"])
    n = (db.scalar("SELECT next FROM refseq WHERE kind='job'") or 1)
    db.conn.execute("INSERT INTO refseq(kind, next) VALUES('job', ?) ON CONFLICT(kind) DO UPDATE SET next=?", (n + 1, n + 1))
    jid = ulid()
    db.conn.execute(
        "INSERT INTO job(id, ref, type, status, backend, source_id, target, params, depends_on, created_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?)",
        (jid, f"job{n}", type_, "queued", backend, source_id, target, json.dumps(params or {}, sort_keys=True),
         json.dumps(depends_on or []), time.time()))
    db.emit("job", {"job": f"job{n}", "type": type_, "status": "queued", "target": target})
    return db.get("job", jid)


def brief(job: dict) -> dict:
    out = {"ref": job["ref"], "type": job["type"], "status": job["status"], "target": job["target"],
           "progress": round(job["progress"] or 0, 3), "message": job["message"]}
    if job.get("error"):
        out["error"] = job["error"]
    if job.get("result") is not None and job["status"] == "done":
        out["result"] = job["result"]
    if job.get("started_at"):
        end = job.get("finished_at") or time.time()
        out["elapsed_s"] = round(end - job["started_at"], 1)
    return out


# ---- the runner ---------------------------------------------------------------------------

class JobCtx:
    def __init__(self, project: Project, job: dict):
        self.project = project
        self.db = project.db
        self.job = job
        self.params = job.get("params") or {}
        self._last = 0.0
        self.folder = project.dir("jobs", job["ref"])
        self.log_path = self.folder / "log.txt"

    def log(self, msg: str) -> None:
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(time.strftime("%H:%M:%S ") + msg + "\n")

    def progress(self, frac: float, msg: str = "") -> None:
        now = time.time()
        if now - self._last < 1.0 and frac < 1.0:
            return
        self._last = now
        self.db.conn.execute("UPDATE job SET progress=?, message=?, heartbeat=? WHERE id=?",
                             (float(frac), msg[:200], now, self.job["id"]))
        self.db.emit("job", {"job": self.job["ref"], "type": self.job["type"], "status": "running",
                             "progress": round(frac, 3), "message": msg[:200], "target": self.job["target"]})

    def cancelled(self) -> bool:
        row = self.db.one("SELECT status FROM job WHERE id=?", (self.job["id"],))
        return bool(row and row[0] == "cancelling")

    def source(self) -> dict:
        return self.db.get("source", self.job["source_id"])

    def set_status(self, stage: str, value: str) -> None:
        src = self.source()
        if src is None:
            return
        status = dict(src.get("status") or {})
        status[stage] = value
        with self.db.op(f"job.{self.job['type']}", "machine") as tx:
            tx.update("source", src["id"], {"status": status}, log=False)
            tx.event("source", {"ref": src["ref"], "stage": stage, "value": value})


def _claim(db, lanes: tuple[str, ...]) -> dict | None:
    for row in db.rows("job", "WHERE status='queued' ORDER BY created_at"):
        if lane_of(row["type"]) not in lanes:
            continue
        deps = row.get("depends_on") or []
        if deps:
            states = {r["ref"]: r["status"] for r in db.all(
                f"SELECT ref, status FROM job WHERE ref IN ({','.join('?' * len(deps))})", deps)}
            if any(s in ("failed", "cancelled") for s in states.values()):
                db.conn.execute("UPDATE job SET status='failed', error=?, finished_at=? WHERE id=?",
                                ("a job it depends on failed", time.time(), row["id"]))
                db.emit("job", {"job": row["ref"], "status": "failed"})
                continue
            if any(states.get(d) != "done" for d in deps):
                continue
        cur = db.conn.execute("UPDATE job SET status='running', started_at=?, heartbeat=?, pid=? "
                              "WHERE id=? AND status='queued'", (time.time(), time.time(), os.getpid(), row["id"]))
        if cur.rowcount == 1:
            return db.get("job", row["id"])
    return None


def execute(project: Project, job: dict) -> dict:
    _load_tasks()
    db = project.db
    ctx = JobCtx(project, job)
    fn = TASKS.get(job["type"], (None, None))[0]
    db.emit("job", {"job": job["ref"], "type": job["type"], "status": "running", "target": job["target"]})
    try:
        if fn is None:
            raise RecompError("E_INTERNAL", f"no task for job type {job['type']!r}")
        ctx.log(f"start {job['type']} {job['target'] or ''} {json.dumps(ctx.params)}")
        result = fn(ctx) or {}
        db.conn.execute("UPDATE job SET status='done', progress=1, result=?, finished_at=?, message=? WHERE id=?",
                        (json.dumps(result, default=str), time.time(), "done", job["id"]))
        ctx.log("done " + json.dumps(result, default=str)[:500])
        db.emit("job", {"job": job["ref"], "type": job["type"], "status": "done", "target": job["target"]})
    except (Cancelled, KeyboardInterrupt):
        db.conn.execute("UPDATE job SET status='cancelled', finished_at=? WHERE id=?", (time.time(), job["id"]))
        db.emit("job", {"job": job["ref"], "status": "cancelled"})
        ctx.log("cancelled")
    except Exception as exc:  # noqa: BLE001
        msg = exc.message if isinstance(exc, RecompError) else f"{type(exc).__name__}: {exc}"
        ctx.log("FAILED " + msg + "\n" + traceback.format_exc())
        db.conn.execute("UPDATE job SET status='failed', error=?, finished_at=? WHERE id=?",
                        (msg[:2000], time.time(), job["id"]))
        db.emit("job", {"job": job["ref"], "type": job["type"], "status": "failed", "error": msg[:300]})
        if job.get("source_id") and job["type"] in ("audio", "shots", "peaks", "thumbs", "asr", "captions", "fetch"):
            try:
                ctx.set_status(job["type"], "failed")
            except Exception:  # noqa: BLE001
                pass
    return db.get("job", job["id"])


def run_pending(project: Project, lanes: tuple[str, ...] = ("cpu", "net"), idle_exit: float = 0.0,
                heartbeat: Callable[[], None] | None = None) -> int:
    """Drain jobs in the given lanes. Returns how many ran. ``idle_exit`` > 0 waits that long for more."""
    count = 0
    idle_since = time.time()
    while True:
        if heartbeat:
            heartbeat()
        job = _claim(project.db, lanes)
        if job is None:
            if idle_exit <= 0 or time.time() - idle_since > idle_exit:
                return count
            time.sleep(0.5)
            continue
        execute(project, job)
        count += 1
        idle_since = time.time()


def requeue_stale(db) -> int:
    cur = db.conn.execute("UPDATE job SET status='queued', pid=NULL, message='taken over' "
                          "WHERE status IN ('running','cancelling') AND COALESCE(heartbeat, started_at, 0) < ?",
                          (time.time() - RUNNING_STALE_S,))
    return cur.rowcount


def lock_path(project: Project) -> Path:
    return project.dir("jobs") / LOCK


def runner_alive(project: Project) -> bool:
    p = lock_path(project)
    try:
        return time.time() - p.stat().st_mtime < STALE_S
    except FileNotFoundError:
        return False


def kick(project: Project) -> str:
    """Make sure queued jobs will run: inline (tests), a live runner, or a new detached one."""
    mode = os.environ.get("RECOMP_JOBS", "spawn")
    if mode == "off":
        return "queued"
    if mode == "inline":
        run_pending(project)
        return "inline"
    if runner_alive(project):
        return "runner"
    exe = Path(sys.executable).parent / ("recomp.exe" if os.name == "nt" else "recomp")
    cmd = [str(exe), "worker", "run", "--project", str(project.root)] if exe.exists() else \
          [sys.executable, "-m", "recomp.cli", "worker", "run", "--project", str(project.root)]
    log = (project.dir("jobs") / "runner.log").open("a", encoding="utf-8")
    flags = 0
    if os.name == "nt":
        flags = 0x00000008 | 0x00000200 | 0x08000000  # DETACHED | NEW_PROCESS_GROUP | NO_WINDOW
    subprocess.Popen(cmd, stdout=log, stderr=log, stdin=subprocess.DEVNULL, creationflags=flags,
                     close_fds=True, cwd=str(project.root))
    lock_path(project).touch()
    return "spawned"


def serve(project_root: str, idle_exit: float = 30.0) -> int:
    """The runner process: two lanes, a heartbeat, takeover of jobs whose runner died."""
    root = Path(project_root)
    lock = Project(root).dir("jobs") / LOCK
    if lock.exists() and time.time() - lock.stat().st_mtime < STALE_S and os.environ.get("RECOMP_RUNNER_FORCE") != "1":
        content = lock.read_text(encoding="utf-8", errors="ignore").strip()
        if content and content != str(os.getpid()):
            return 0  # someone else is running
    lock.write_text(str(os.getpid()), encoding="utf-8")
    stop = threading.Event()

    def beat():
        while not stop.is_set():
            try:
                lock.write_text(str(os.getpid()), encoding="utf-8")
            except OSError:
                pass
            stop.wait(3)

    hb = threading.Thread(target=beat, daemon=True)
    hb.start()
    first = Project(root)
    requeue_stale(first.db)
    first.close()
    totals = {"cpu": 0, "net": 0}

    def lane_loop(lane: str):
        proj = Project(root)
        try:
            totals[lane] = run_pending(proj, (lane,), idle_exit=idle_exit)
        finally:
            proj.close()

    threads = [threading.Thread(target=lane_loop, args=(lane,)) for lane in ("cpu", "net")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    stop.set()
    try:
        lock.unlink()
    except OSError:
        pass
    return totals["cpu"] + totals["net"]
