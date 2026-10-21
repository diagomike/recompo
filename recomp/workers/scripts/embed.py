"""Sentence embeddings with multilingual-e5 (transformers, mean pooling, unit length), under the worker python.

    python embed.py --model intfloat/multilingual-e5-small --input texts.json --kind passage --out vectors.npy
texts.json is a list of strings; vectors.npy is float16 [n, dim]. e5 wants "passage: " / "query: " prefixes.

    python embed.py --model … --serve --state embed.json --idle 600
The resident form for queries: loads the model once, listens on 127.0.0.1 (a free port) and writes
{"pid", "port", "token", "model", "tag"} to the state file when ready. Each connection is one JSON line in,
{"token", "op": "embed", "kind", "texts"} (or "ping" / "stop"), and one JSON line out, {"ok", "dim", "vectors"}.
It exits after `--idle` seconds without a request, or when the state file no longer names it.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import socket
import sys
import time


def load(name: str):
    import torch
    from transformers import AutoModel, AutoTokenizer

    torch.set_num_threads(max(1, (torch.get_num_threads() or 4)))
    return AutoTokenizer.from_pretrained(name), AutoModel.from_pretrained(name).eval()


def encode(tok, model, texts: list[str], kind: str, batch: int = 32, progress=None):
    import numpy as np
    import torch

    texts = [f"{kind}: {t}" for t in texts]
    out = []
    with torch.inference_mode():
        for i in range(0, len(texts), batch):
            enc = tok(texts[i:i + batch], padding=True, truncation=True, max_length=256, return_tensors="pt")
            hidden = model(**enc).last_hidden_state
            mask = enc["attention_mask"].unsqueeze(-1).float()
            vec = (hidden * mask).sum(1) / mask.sum(1).clamp(min=1e-9)
            out.append(torch.nn.functional.normalize(vec, dim=-1).numpy().astype(np.float16))
            if progress and len(texts) > batch:
                progress(min(len(texts), i + batch), len(texts))
    return np.concatenate(out) if out else np.zeros((0, model.config.hidden_size), np.float16)


def _write_state(path: str, state: dict) -> None:
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f)
    os.replace(tmp, path)


def _names_me(path: str) -> bool:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f).get("pid") == os.getpid()
    except (OSError, ValueError):
        return False


def _reply(conn: socket.socket, msg: dict) -> None:
    conn.sendall((json.dumps(msg) + "\n").encode("utf-8"))


def serve(a) -> None:
    tok, model = load(a.model)
    encode(tok, model, ["warm up"], "query")
    token = secrets.token_hex(16)
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    srv.listen(8)
    srv.settimeout(5.0)
    _write_state(a.state, {"pid": os.getpid(), "port": srv.getsockname()[1], "token": token, "model": a.model,
                           "tag": a.tag, "started": time.time()})
    print(json.dumps({"message": f"serving {a.model} on port {srv.getsockname()[1]}"}), flush=True)
    last = time.time()
    while time.time() - last < a.idle and _names_me(a.state):
        try:
            conn, _ = srv.accept()
        except socket.timeout:
            continue
        with conn:
            conn.settimeout(30.0)
            try:
                buf = b""
                while not buf.endswith(b"\n"):
                    chunk = conn.recv(65536)
                    if not chunk:
                        break
                    buf += chunk
                req = json.loads(buf.decode("utf-8"))
                if req.get("token") != token:
                    _reply(conn, {"ok": False, "error": "bad token"})
                    continue
                last = time.time()
                op = req.get("op")
                if op == "stop":
                    _reply(conn, {"ok": True})
                    break
                if op == "ping":
                    _reply(conn, {"ok": True, "model": a.model})
                    continue
                vecs = encode(tok, model, [str(t) for t in req["texts"]], req.get("kind", "query"), a.batch)
                _reply(conn, {"ok": True, "dim": int(vecs.shape[1]), "vectors": vecs.astype(float).round(5).tolist()})
            except Exception as exc:  # one bad request must not take the resident down
                try:
                    _reply(conn, {"ok": False, "error": f"{type(exc).__name__}: {exc}"})
                except OSError:
                    pass
    srv.close()
    if _names_me(a.state):
        try:
            os.unlink(a.state)
        except OSError:
            pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--input")
    ap.add_argument("--kind", choices=["passage", "query"], default="passage")
    ap.add_argument("--out")
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--serve", action="store_true")
    ap.add_argument("--state")
    ap.add_argument("--idle", type=float, default=600.0)
    ap.add_argument("--tag", default="", help="Echoed in the state file, so the caller knows its own start")
    a = ap.parse_args()
    if a.serve:
        return serve(a)
    import numpy as np

    tok, model = load(a.model)
    with open(a.input, encoding="utf-8") as f:
        texts = json.load(f)

    def progress(done, total):
        sys.stdout.write(json.dumps({"progress": min(0.99, done / total), "message": f"{done}/{total}"}) + "\n")
        sys.stdout.flush()

    vecs = encode(tok, model, texts, a.kind, a.batch, progress)
    np.save(a.out, vecs)
    dim = model.config.hidden_size
    sys.stdout.write(json.dumps({"progress": 1.0, "message": f"{len(texts)} embedded", "n": len(texts), "dim": dim}) + "\n")


if __name__ == "__main__":
    main()
