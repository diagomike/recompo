"""MT adapter for the user's PC: Google Translate's public web endpoint through Recomposer's own client
(`recomp/lang/google.py`), for MT-only targets such as Amharic (am) and Oromo (om). Same JSONL contract as
mt_sockeye.py, so twosided.py works unchanged:

    python mt_google.py --src en --tgt am --in chunks.jsonl --out out.jsonl          # forward MT of every option
    python mt_google.py --src am --tgt en --in back.jsonl --out back_out.jsonl       # back-translation for checking

Each chunk is translated on its own (`Translator.raw`), never batched with its neighbours, so a chunk stays one
speech segment. Not run in the research sandbox (Google answers its bot check there); run it on the PC.
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # the repository root


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--tgt", required=True)
    ap.add_argument("--in", dest="inp", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--pause", type=float, default=0.4)
    a = ap.parse_args()
    from recomp.lang.google import Translator
    tr = Translator(a.src, a.tgt)
    rows = [json.loads(l) for l in a.inp.read_text(encoding="utf-8").splitlines() if l.strip()]
    with open(a.out, "a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps({"key": r["key"], "text": tr.raw(r["text"])}, ensure_ascii=False) + "\n")
            time.sleep(a.pause)
    print(f"translated {len(rows)} chunks {a.src}→{a.tgt}")


if __name__ == "__main__":
    main()
