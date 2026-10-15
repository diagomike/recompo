"""Studio side of remote workers: package a worker-script call into a job folder, wait, bring outputs back."""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

from ..core import config
from ..envelope import RecompError
from ..media.ff import Cancelled

OUT_FLAGS = {"--out", "--outdir"}


def folder() -> Path:
    f = config.get("worker.remote_folder")
    if not f:
        raise RecompError("E_INVALID", "no remote folder configured",
                          hint="`recomp config set worker.remote_folder <a folder the remote worker also sees>`")
    p = Path(f)
    (p / "jobs").mkdir(parents=True, exist_ok=True)
    return p


def workers_alive(root: Path | None = None, within: float = 120) -> list[dict]:
    root = root or folder()
    out = []
    for f in (root / "workers").glob("*.json"):
        try:
            w = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if time.time() - w.get("heartbeat", 0) < within:
            out.append(w)
    return out


def run_script(name: str, args: list[str], ctx, env: dict | None = None, timeout: float = 6 * 3600) -> dict:
    root = folder()
    job_id = f"{ctx.project.meta.get('id', 'p')[:10]}-{ctx.job['ref']}-{int(time.time())}"
    job = root / "jobs" / job_id
    (job / "in").mkdir(parents=True)
    (job / "out").mkdir()
    remote_args, outputs = [], []
    expect_out = False
    for a in args:
        if expect_out:
            rel = f"out/{Path(a).name}"
            outputs.append((rel, Path(a)))
            remote_args.append(rel)
            expect_out = False
            continue
        if a in OUT_FLAGS:
            expect_out = True
            remote_args.append(a)
            continue
        p = Path(a)
        if len(a) < 400 and p.exists() and p.is_file():
            shutil.copy(p, job / "in" / p.name)
            remote_args.append(f"in/{p.name}")
        else:
            remote_args.append(a)
    spec = {"script": name, "args": remote_args, "created": time.time(), "env": env or {}}
    (job / "job.json").write_text(json.dumps(spec), encoding="utf-8")
    ctx.log(f"remote job {job_id} submitted to {root}")
    start = time.time()
    warned = False
    while True:
        st = None
        try:
            st = json.loads((job / "status.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
        if st:
            if st.get("state") == "done":
                break
            if st.get("state") == "failed":
                raise RecompError("E_JOB_FAILED", f"remote worker failed: {str(st.get('message'))[-400:]}")
            ctx.progress(float(st.get("progress") or 0), f"remote: {st.get('message', '')}"[:120])
        elif not warned and time.time() - start > 60 and not workers_alive(root):
            ctx.log("no remote worker has a heartbeat yet: start the notebook (or `recomp worker serve`)")
            warned = True
        if ctx.cancelled():
            (job / "cancel").write_text("cancel", encoding="utf-8")
            raise Cancelled()
        if time.time() - start > timeout:
            raise RecompError("E_JOB_FAILED", "remote job timed out")
        ctx.progress(ctx.job.get("progress") or 0.0, "waiting for the remote worker")
        time.sleep(3)
    for rel, dest in outputs:
        src = job / rel
        if src.is_dir():
            shutil.copytree(src, dest, dirs_exist_ok=True)
        elif src.exists():
            shutil.copy(src, dest)
        else:
            raise RecompError("E_JOB_FAILED", f"remote job produced no {rel}")
    shutil.rmtree(job / "in", ignore_errors=True)
    return {"remote": job_id}
