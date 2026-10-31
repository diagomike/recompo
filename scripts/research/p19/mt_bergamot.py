"""Offline MT with Mozilla's Firefox Translations models (bergamot engine), as a second, independent MT system.

Jobs are JSONL {key, text}; a chain of model folders is applied in order (de-en, then en-es gives a Spanish view
through Mozilla's own English). Output JSONL {key, text}.

    python mt_bergamot.py --models M --chain de-en,en-es --in jobs.jsonl --out out.jsonl

Model folders hold model.*.intgemm.alphas.bin, vocab.*.spm and lex.*.s2t.bin from Mozilla's public model registry
(storage.googleapis.com/moz-fx-translations-data--303e-prod-translations-data/db/models.json, base-memory).
Runs under its own Python 3.10 env with `bergamot==0.4.5`.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

CFG = """models:
  - {model}
vocabs:
  - {vocab}
  - {vocab}
shortlist:
  - {lex}
  - false
beam-size: 1
normalize: 1.0
word-penalty: 0
max-length-break: 128
mini-batch-words: 1024
workspaces: 128
max-length-factor: 2.0
skip-cost: true
cpu-threads: 0
quiet: true
quiet-translation: true
gemm-precision: int8shiftAlphaAll
alignment: soft
"""


def load(service, folder: Path):
    import bergamot
    cfg = CFG.format(model=next(folder.glob("model.*.bin")), vocab=next(folder.glob("vocab.*.spm")),
                     lex=next(folder.glob("lex.*.bin")))
    return service.modelFromConfig(cfg)


def translate(service, model, texts: list[str]) -> list[str]:
    import bergamot
    opts = bergamot.VectorResponseOptions([bergamot.ResponseOptions() for _ in texts])
    out = service.translate(model, bergamot.VectorString(texts), opts)
    return [r.target.text for r in out]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", type=Path, required=True)
    ap.add_argument("--chain", required=True)
    ap.add_argument("--in", dest="inp", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    import bergamot
    service = bergamot.Service(bergamot.ServiceConfig(numWorkers=4, cacheSize=0, logLevel="off"))
    jobs = [json.loads(l) for l in a.inp.read_text(encoding="utf-8").splitlines() if l.strip()]
    texts = [j["text"] for j in jobs]
    for pair in a.chain.split(","):
        texts = translate(service, load(service, a.models / pair), texts)
    with a.out.open("w", encoding="utf-8") as f:
        for j, t in zip(jobs, texts):
            f.write(json.dumps({"key": j["key"], "text": t}, ensure_ascii=False) + "\n")
    print(f"translated {len(jobs)} chunks via {a.chain}")


if __name__ == "__main__":
    main()
