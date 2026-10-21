"""Sentence embeddings with multilingual-e5 (transformers, mean pooling, unit length), under the worker python.

    python embed.py --model intfloat/multilingual-e5-small --input texts.json --kind passage --out vectors.npy
texts.json is a list of strings; vectors.npy is float16 [n, dim]. e5 wants "passage: " / "query: " prefixes.
"""

from __future__ import annotations

import argparse
import json
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--input", required=True)
    ap.add_argument("--kind", choices=["passage", "query"], default="passage")
    ap.add_argument("--out", required=True)
    ap.add_argument("--batch", type=int, default=32)
    a = ap.parse_args()
    import numpy as np
    import torch
    from transformers import AutoModel, AutoTokenizer

    torch.set_num_threads(max(1, (torch.get_num_threads() or 4)))
    tok = AutoTokenizer.from_pretrained(a.model)
    model = AutoModel.from_pretrained(a.model).eval()
    with open(a.input, encoding="utf-8") as f:
        texts = [f"{a.kind}: {t}" for t in json.load(f)]
    out = []
    with torch.inference_mode():
        for i in range(0, len(texts), a.batch):
            enc = tok(texts[i:i + a.batch], padding=True, truncation=True, max_length=256, return_tensors="pt")
            hidden = model(**enc).last_hidden_state
            mask = enc["attention_mask"].unsqueeze(-1).float()
            vec = (hidden * mask).sum(1) / mask.sum(1).clamp(min=1e-9)
            out.append(torch.nn.functional.normalize(vec, dim=-1).numpy().astype(np.float16))
            if len(texts) > a.batch:
                sys.stdout.write(json.dumps({"progress": min(0.99, (i + a.batch) / len(texts)),
                                             "message": f"{min(len(texts), i + a.batch)}/{len(texts)}"}) + "\n")
                sys.stdout.flush()
    dim = model.config.hidden_size
    np.save(a.out, np.concatenate(out) if out else np.zeros((0, dim), np.float16))
    sys.stdout.write(json.dumps({"progress": 1.0, "message": f"{len(texts)} embedded", "n": len(texts), "dim": dim}) + "\n")


if __name__ == "__main__":
    main()
