"""Jobs: list, inspect, wait (returns early with progress), tail, cancel, retry, run inline."""

from __future__ import annotations

import json
import time
from pathlib import Path

from pydantic import BaseModel, Field

from ..core import refs
from ..envelope import RecompError, Result
from ..registry import Ctx, NoInput, verb
from ..workers import jobs


class ListIn(BaseModel):
    status: str | None = Field(None, description="queued, running, done, failed, cancelled")
    all: bool = Field(False, description="Include finished jobs older than an hour")
    limit: int = 30


@verb("job.list", ListIn)
def job_list(ctx: Ctx, inp: ListIn):
    """Jobs, newest first: open ones plus anything finished in the last hour."""
    where, params = [], []
    if inp.status:
        where.append("status=?")
        params.append(inp.status)
    elif not inp.all:
        where.append("(status IN ('queued','running','cancelling') OR COALESCE(finished_at,0) > ?)")
        params.append(time.time() - 3600)
    rows = ctx.db.rows("job", ("WHERE " + " AND ".join(where) if where else "") + " ORDER BY created_at DESC LIMIT ?",
                       (*params, inp.limit))
    return {"runner": jobs.runner_alive(ctx.project), "jobs": [jobs.brief(r) for r in rows]}


class RefIn(BaseModel):
    ref: str = Field(..., description="Job ref, e.g. job7", json_schema_extra={"pos": 0})


def _job(ctx, ref):
    return refs.resolve(ctx.db, ref, "job")[1]


@verb("job.show", RefIn)
def job_show(ctx: Ctx, inp: RefIn):
    """One job in full: params, progress, result or error."""
    j = _job(ctx, inp.ref)
    out = jobs.brief(j)
    out.update({"params": j["params"], "depends_on": j["depends_on"], "backend": j["backend"],
                "result": j["result"], "log": str(ctx.project.root / "jobs" / j["ref"] / "log.txt")})
    return out


class WaitIn(BaseModel):
    refs: list[str] = Field(..., description="Job ref(s)", json_schema_extra={"pos": 0})
    timeout: float = Field(60, description="Return after this many seconds even if not finished")


@verb("job.wait", WaitIn, examples=["recomp job wait job7 --timeout 90"])
def job_wait(ctx: Ctx, inp: WaitIn):
    """Wait for job(s) to finish, returning early at the timeout with their progress."""
    deadline = time.time() + max(0.0, inp.timeout)
    rows = [_job(ctx, r) for r in inp.refs]
    if any(r["status"] == "queued" for r in rows) and not jobs.runner_alive(ctx.project):
        jobs.kick(ctx.project)
    while True:
        rows = [ctx.db.get("job", r["id"]) for r in rows]
        if all(r["status"] in ("done", "failed", "cancelled") for r in rows) or time.time() >= deadline:
            break
        time.sleep(0.5)
    finished = all(r["status"] in ("done", "failed", "cancelled") for r in rows)
    data = {"finished": finished, "jobs": [jobs.brief(r) for r in rows]}
    if not finished:
        return Result(data=data, next=[f"recomp job wait {' '.join(inp.refs)} --timeout 90"])
    return data


class TailIn(BaseModel):
    ref: str = Field(..., json_schema_extra={"pos": 0})
    lines: int = 30


@verb("job.tail", TailIn)
def job_tail(ctx: Ctx, inp: TailIn):
    """The end of a job's log."""
    j = _job(ctx, inp.ref)
    p = ctx.project.root / "jobs" / j["ref"] / "log.txt"
    text = p.read_text(encoding="utf-8", errors="replace").splitlines() if p.exists() else []
    return {"ref": j["ref"], "status": j["status"], "log": text[-inp.lines:]}


@verb("job.cancel", RefIn, effect="write")
def job_cancel(ctx: Ctx, inp: RefIn):
    """Cancel a queued or running job."""
    j = _job(ctx, inp.ref)
    if j["status"] == "queued":
        ctx.db.conn.execute("UPDATE job SET status='cancelled', finished_at=? WHERE id=?", (time.time(), j["id"]))
    elif j["status"] == "running":
        ctx.db.conn.execute("UPDATE job SET status='cancelling' WHERE id=?", (j["id"],))
    else:
        raise RecompError("E_CONFLICT", f"{j['ref']} is already {j['status']}")
    ctx.db.emit("job", {"job": j["ref"], "status": "cancelling"})
    return jobs.brief(ctx.db.get("job", j["id"]))


@verb("job.retry", RefIn, effect="heavy")
def job_retry(ctx: Ctx, inp: RefIn):
    """Queue a failed or cancelled job again."""
    j = _job(ctx, inp.ref)
    if j["status"] not in ("failed", "cancelled", "done"):
        raise RecompError("E_CONFLICT", f"{j['ref']} is {j['status']}")
    new = jobs.enqueue(ctx.db, j["type"], target=j["target"], source_id=j["source_id"], params=j["params"],
                       backend=j["backend"], dedupe=False)
    mode = jobs.kick(ctx.project)
    return Result(data={"job": new["ref"], "runner": mode}, job=new["ref"])


@verb("worker.status", NoInput)
def worker_status(ctx: Ctx, inp: NoInput):
    """The local job runner, and the remote folder: live remote workers and jobs waiting there."""
    from ..core import config
    from ..workers import remote
    out = {"local_runner": jobs.runner_alive(ctx.project), "default_backend": config.get("worker.default_backend"),
           "worker_python": config.get("worker.python"), "remote_folder": config.get("worker.remote_folder") or None}
    if out["remote_folder"]:
        root = Path(out["remote_folder"])
        out["remote_workers"] = remote.workers_alive(root) if root.exists() else []
        waiting = []
        for j in sorted((root / "jobs").glob("*")) if (root / "jobs").exists() else []:
            st = {}
            try:
                st = json.loads((j / "status.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                pass
            if st.get("state") not in ("done", "failed"):
                waiting.append({"job": j.name, "state": st.get("state", "queued"), "progress": st.get("progress", 0)})
        out["remote_jobs_open"] = waiting
    return out


class RunIn(BaseModel):
    lanes: list[str] = Field(default_factory=lambda: ["cpu", "net"])


@verb("job.run", RunIn, effect="heavy", hidden=True)
def job_run(ctx: Ctx, inp: RunIn):
    """Drain queued jobs in this process now (normally a background runner does this)."""
    n = jobs.run_pending(ctx.project, tuple(inp.lanes))
    return {"ran": n}
