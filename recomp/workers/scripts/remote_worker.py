"""Remote worker: serve job folders from a shared folder (Drive, a bucket mount, or a local stand-in).

Standalone (standard library only), so a Kaggle/Colab notebook can run it next to the other scripts.

    python remote_worker.py --folder /content/drive/MyDrive/RecompRemote [--python python3] [--once]

Protocol, one writer per file:
  jobs/<id>/job.json        written by the studio: {"script": "asr", "args": [...], "created": t}
  jobs/<id>/in/…            inputs (paths in args are relative to the job folder)
  jobs/<id>/status.json     written by the worker: {"state": queued|running|done|failed, "progress", "message",
                            "worker", "heartbeat"}
  jobs/<id>/out/…           outputs
  jobs/<id>/cancel          written by the studio to ask for a stop
  workers/<name>.json       worker heartbeat {"name", "heartbeat", "host"}
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def write_json(path: Path, data: dict) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    os.replace(tmp, path)


def read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def claim(job: Path, name: str) -> bool:
    st = read_json(job / "status.json")
    if st and st.get("state") in ("running", "done", "failed"):
        if st.get("state") == "running" and time.time() - st.get("heartbeat", 0) > 180:
            pass  # its worker died: take it over
        else:
            return False
    write_json(job / "status.json", {"state": "running", "progress": 0, "worker": name, "heartbeat": time.time(), "message": "claimed"})
    time.sleep(0.5)
    st = read_json(job / "status.json")
    return bool(st and st.get("worker") == name)


def run_job(job: Path, name: str, python: str) -> None:
    spec = read_json(job / "job.json") or {}
    script = HERE / f"{spec.get('script')}.py"
    (job / "out").mkdir(exist_ok=True)
    log = open(job / "log.txt", "a", encoding="utf-8")
    env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8", **(spec.get("env") or {}))
    proc = subprocess.Popen([python, str(script), *spec.get("args", [])], cwd=str(job), stdout=subprocess.PIPE,
                            stderr=log, env=env, text=True, encoding="utf-8", errors="replace")
    progress, message = 0.0, ""
    last_beat = 0.0
    assert proc.stdout is not None
    for line in proc.stdout:
        try:
            msg = json.loads(line)
            progress = float(msg.get("progress", progress))
            message = str(msg.get("message", message))
        except (ValueError, TypeError):
            log.write(line)
        if time.time() - last_beat > 2:
            last_beat = time.time()
            write_json(job / "status.json", {"state": "running", "progress": progress, "message": message, "worker": name,
                                             "heartbeat": last_beat})
        if (job / "cancel").exists():
            proc.kill()
            write_json(job / "status.json", {"state": "failed", "message": "cancelled", "worker": name, "heartbeat": time.time()})
            return
    code = proc.wait()
    log.close()
    state = "done" if code == 0 else "failed"
    tail = ""
    if code:
        try:
            tail = (job / "log.txt").read_text(encoding="utf-8", errors="replace")[-800:]
        except OSError:
            pass
    write_json(job / "status.json", {"state": state, "progress": 1.0 if code == 0 else progress, "message": tail or "done",
                                     "worker": name, "heartbeat": time.time(), "exit": code})


def serve(folder: Path, python: str, once: bool = False, idle_exit: float = 0.0) -> int:
    name = f"{socket.gethostname()}-{os.getpid()}"
    (folder / "jobs").mkdir(parents=True, exist_ok=True)
    (folder / "workers").mkdir(parents=True, exist_ok=True)
    done = 0
    idle_since = time.time()
    while True:
        write_json(folder / "workers" / f"{name}.json", {"name": name, "heartbeat": time.time(), "host": socket.gethostname()})
        ran = False
        for job in sorted((folder / "jobs").iterdir()):
            if not (job / "job.json").exists() or (job / "cancel").exists():
                continue
            if claim(job, name):
                print(f"[{time.strftime('%H:%M:%S')}] running {job.name}", flush=True)
                run_job(job, name, python)
                done += 1
                ran = True
                break
        if ran:
            idle_since = time.time()
            continue
        if once or (idle_exit and time.time() - idle_since > idle_exit):
            return done
        time.sleep(3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder", required=True)
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--idle-exit", type=float, default=0.0)
    a = ap.parse_args()
    n = serve(Path(a.folder), a.python, a.once, a.idle_exit)
    print(f"served {n} job(s)")


if __name__ == "__main__":
    main()
