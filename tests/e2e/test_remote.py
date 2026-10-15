"""Remote job folders: the studio packages a script call, a worker serves it, outputs come back."""

import sys
import threading
from pathlib import Path

import pytest

from recomp.core import config
from recomp.envelope import RecompError
from recomp.workers import remote
from recomp.workers.scripts import remote_worker

pytestmark = pytest.mark.e2e


class Ctx:
    def __init__(self, root):
        self.project = type("P", (), {"meta": {"id": "testproj"}})()
        self.job = {"ref": "job1", "backend": "remote", "progress": 0}
        self.logs, self.progressed = [], []
        self._cancel = False

    def log(self, m):
        self.logs.append(m)

    def progress(self, f, m=""):
        self.progressed.append(f)

    def cancelled(self):
        return self._cancel


def test_remote_roundtrip(tmp_path):
    root = tmp_path / "remote"
    config.set_value("worker.remote_folder", str(root))
    src = tmp_path / "in.txt"
    src.write_text("hello remote", encoding="utf-8")
    out = tmp_path / "result" / "out.txt"
    out.parent.mkdir()
    t = threading.Thread(target=remote_worker.serve, args=(root, sys.executable), kwargs={"idle_exit": 8}, daemon=True)
    t.start()
    ctx = Ctx(root)
    res = remote.run_script("selftest", ["--in", str(src), "--out", str(out)], ctx)
    assert out.read_text(encoding="utf-8") == "HELLO REMOTE"
    assert res["remote"].startswith("testproj")
    assert remote.workers_alive(root)
    job = root / "jobs" / res["remote"]
    assert (job / "status.json").exists() and not (job / "in").exists()  # inputs cleaned up


def test_remote_failure_is_reported(tmp_path):
    root = tmp_path / "remote"
    config.set_value("worker.remote_folder", str(root))
    t = threading.Thread(target=remote_worker.serve, args=(root, sys.executable), kwargs={"idle_exit": 8}, daemon=True)
    t.start()
    with pytest.raises(RecompError) as e:
        remote.run_script("selftest", ["--in", str(tmp_path / "missing.txt"), "--out", str(tmp_path / "o.txt")], Ctx(root))
    assert e.value.code == "E_JOB_FAILED"


def test_backend_choice_requires_folder(OK, R, proj):
    from recomp.workers import jobs
    with pytest.raises(RecompError):
        jobs.backend("remote")
    assert jobs.backend(None) == "local"
