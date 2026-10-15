"""Running a worker script under the configured worker python, with progress, cancel and logs."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from ..core import config
from ..envelope import RecompError

SCRIPTS = Path(__file__).resolve().parent / "scripts"
CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


def worker_python() -> str:
    py = config.get("worker.python")
    if not py or not Path(py).exists():
        raise RecompError("E_TOOL", f"worker python not found: {py}",
                          hint="recomp config set worker.python <python with faster-whisper>; then `recomp doctor`.")
    return py


def run_script(name: str, args: list[str], ctx=None, allow_download: bool = False, env_extra: dict | None = None) -> dict:
    """Run ``scripts/<name>.py``; JSON lines on stdout become job progress. Returns the last line.
    Jobs queued with ``backend='remote'`` run in the remote worker's folder instead."""
    if ctx is not None and (ctx.job.get("backend") == "remote"):
        from . import remote
        return remote.run_script(name, args, ctx, env={})  # a fresh notebook has no model cache: let it download
    env = dict(os.environ)
    env["HF_HOME"] = config.get("worker.hf_home") or env.get("HF_HOME", "")
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUNBUFFERED"] = "1"
    if not allow_download:
        env["HF_HUB_OFFLINE"] = "1"
    env.update(env_extra or {})
    cmd = [worker_python(), "-I", str(SCRIPTS / f"{name}.py"), *args]
    log = open(ctx.folder / "worker.stderr.txt", "a", encoding="utf-8") if ctx else subprocess.DEVNULL
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=log, env=env, creationflags=CREATE_NO_WINDOW)
    last: dict = {}
    assert proc.stdout is not None
    try:
        for raw in iter(proc.stdout.readline, b""):
            line = raw.decode("utf-8", "replace").strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                if ctx:
                    ctx.log(line)
                continue
            last = msg
            if ctx:
                if "progress" in msg:
                    ctx.progress(float(msg["progress"]), str(msg.get("message", "")))
                elif msg.get("message"):
                    ctx.log(str(msg["message"]))
                if ctx.cancelled():
                    proc.kill()
                    from ..media.ff import Cancelled
                    raise Cancelled()
        code = proc.wait()
    finally:
        if ctx and log is not subprocess.DEVNULL:
            log.close()
    if code != 0:
        tail = ""
        if ctx:
            try:
                tail = (ctx.folder / "worker.stderr.txt").read_text(encoding="utf-8", errors="replace")[-1200:]
            except OSError:
                pass
        raise RecompError("E_TOOL", f"worker script {name} failed (exit {code}): {tail.strip()[-600:]}")
    return last
