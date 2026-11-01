"""Mozilla Firefox Translations models (bergamot engine) under the worker python: offline MT, English-centric.

    python mt_bergamot.py --models <folder> --src de --tgt es --in jobs.jsonl --out out.jsonl

``<folder>`` holds one sub-folder per pair (``de-en``, ``en-es``, …) with model.*.intgemm.alphas.bin, vocab.*.spm
and lex.*.s2t.bin (base-memory models from Mozilla's public registry,
storage.googleapis.com/moz-fx-translations-data--303e-prod-translations-data/db/models.json). A pair without its own
model is chained through English. Needs ``pip install bergamot==0.4.5`` in the worker env; only the compiled engine
is loaded (the package's import fetches online model catalogues).
"""

from __future__ import annotations

import argparse
import importlib.machinery
import importlib.util
import json
import site
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


def engine():
    for d in site.getsitepackages():
        for so in Path(d, "bergamot").glob("_bergamot*.so") if Path(d, "bergamot").exists() else []:
            spec = importlib.util.spec_from_loader("_bergamot", importlib.machinery.ExtensionFileLoader("_bergamot", str(so)))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
        for so in Path(d, "bergamot").glob("_bergamot*.pyd") if Path(d, "bergamot").exists() else []:
            spec = importlib.util.spec_from_loader("_bergamot", importlib.machinery.ExtensionFileLoader("_bergamot", str(so)))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    raise SystemExit("bergamot is not installed in the worker env (pip install bergamot==0.4.5)")


def chain(models: Path, src: str, tgt: str) -> list[str]:
    if (models / f"{src}-{tgt}").exists():
        return [f"{src}-{tgt}"]
    hops = [f"{src}-en", f"en-{tgt}"]
    missing = [h for h in hops if not (models / h).exists()]
    if missing:
        raise SystemExit(f"no bergamot model for {', '.join(missing)} in {models}")
    return hops


def main():
    ap = argparse.ArgumentParser()
    for k in ("models", "src", "tgt", "in", "out"):
        ap.add_argument("--" + k, required=True)
    a = ap.parse_args()
    B = engine()
    models = Path(a.models)
    service = B.Service(B.ServiceConfig(numWorkers=4, cacheSize=0, logLevel="off"))
    jobs = [json.loads(l) for l in open(getattr(a, "in"), encoding="utf-8") if l.strip()]
    texts = [j["text"] for j in jobs]
    for pair in chain(models, a.src, a.tgt):
        f = models / pair
        cfg = CFG.format(model=next(f.glob("model.*.bin")), vocab=next(f.glob("vocab.*.spm")), lex=next(f.glob("lex.*.bin")))
        texts = [r.target.text for r in service.translate(service.modelFromConfig(cfg), B.VectorString(texts), B.ResponseOptions())]
    with open(a.out, "w", encoding="utf-8") as out:
        for j, t in zip(jobs, texts):
            out.write(json.dumps({"key": j["key"], "text": t}, ensure_ascii=False) + "\n")
    print(json.dumps({"done": len(jobs)}))


if __name__ == "__main__":
    main()
