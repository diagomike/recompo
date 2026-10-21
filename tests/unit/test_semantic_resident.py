"""The resident embedder client (transcript/semantic.py): queries reach a running resident, and fall back to the
one-shot script when none can start. A stand-in resident speaks the protocol; no model is loaded."""

import json
import socket
import threading

import numpy as np

from recomp.core import config
from recomp.transcript import semantic


class Stub:
    """Speaks embed.py --serve's protocol: one JSON line in, one out; vectors are [len(text), 1, 0]."""

    def __init__(self):
        self.srv = socket.socket()
        self.srv.bind(("127.0.0.1", 0))
        self.srv.listen(4)
        self.requests = []
        threading.Thread(target=self.loop, daemon=True).start()

    def loop(self):
        while True:
            try:
                conn, _ = self.srv.accept()
            except OSError:
                return
            with conn:
                buf = b""
                while not buf.endswith(b"\n"):
                    buf += conn.recv(4096)
                req = json.loads(buf)
                self.requests.append(req)
                if req["token"] != "t0k":
                    out = {"ok": False, "error": "bad token"}
                elif req["op"] == "embed":
                    out = {"ok": True, "dim": 3, "vectors": [[len(t), 1.0, 0.0] for t in req["texts"]]}
                else:
                    out = {"ok": True}
                conn.sendall((json.dumps(out) + "\n").encode())

    def state(self, **kw):
        return {"pid": 1, "port": self.srv.getsockname()[1], "token": "t0k", "model": semantic.model_name(), **kw}


def test_query_goes_to_the_running_resident():
    stub = Stub()
    (semantic._run_dir() / "embed.json").write_text(json.dumps(stub.state()), encoding="utf-8")
    vecs = semantic.embed(None, ["hello", "a"], "query")
    assert semantic.last_via == "resident"
    assert vecs.dtype == np.float32 and vecs.tolist() == [[5, 1, 0], [1, 1, 0]]
    assert [r["op"] for r in stub.requests] == ["ping", "embed"] and stub.requests[1]["kind"] == "query"
    assert semantic.stop_resident() and stub.requests[-1]["op"] == "stop"
    stub.srv.close()


def test_falls_back_to_the_script_when_no_resident_can_start(tmp_path, monkeypatch):
    from recomp.workers import worker_env
    config.set_value("worker.python", str(tmp_path / "missing" / "python.exe"))
    stub = Stub()  # a resident for another model, or a dead one, is not used
    (semantic._run_dir() / "embed.json").write_text(json.dumps(stub.state(model="other/model")), encoding="utf-8")
    calls = []

    def fake_run(name, args, ctx=None, **kw):
        calls.append(args)
        np.save(args[args.index("--out") + 1], np.ones((1, 3), np.float16))
        return {}

    monkeypatch.setattr(worker_env, "run_script", fake_run)

    class P:
        def dir(self, *parts):
            d = tmp_path.joinpath(*parts)
            d.mkdir(parents=True, exist_ok=True)
            return d

    vecs = semantic.embed(P(), ["hello"], "query")
    assert semantic.last_via == "script" and vecs.shape == (1, 3) and calls[0][calls[0].index("--kind") + 1] == "query"
    assert not (semantic._run_dir() / "embed.spawn").exists()           # the start lock is released
    semantic.embed(P(), ["passage text"], "passage")                      # passages never use the resident
    assert semantic.last_via == "script" and not any(r["op"] == "embed" for r in stub.requests)
    stub.srv.close()
