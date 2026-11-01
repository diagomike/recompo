"""A word trigram language model with stupid backoff (Brants et al. 2007), from any plain text corpus.

Language-agnostic: it needs only text in the target language (here: the ~1.1 M English Common Voice sentences of
the IWSLT release, read from the MFA word tiers). Used as the fluency judge for algorithmic rephrasing.

    python ngram_lm.py build --mfa MFA_DIR --n 400000 --exclude ids.txt --out lm.pkl
"""
from __future__ import annotations

import argparse
import json
import math
import pickle
import re
from collections import Counter
from pathlib import Path

BOS, EOS = "<s>", "</s>"


def tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


class LM:
    def __init__(self, uni: Counter, bi: Counter, tri: Counter):
        self.uni, self.bi, self.tri = uni, bi, tri
        self.total = sum(uni.values())

    def logp(self, w: str, h2: str, h1: str) -> float:
        t = self.tri.get((h2, h1, w))
        if t:
            return math.log(t / self.bi[(h2, h1)])
        b = self.bi.get((h1, w))
        if b:
            return math.log(0.4 * b / self.uni[h1])
        return math.log(0.16 * (self.uni.get(w, 0) + 0.5) / self.total)

    def score(self, text: str) -> tuple[float, int]:
        """Total log-probability and token count (with sentence boundaries)."""
        ws = [BOS, BOS] + tokens(text) + [EOS]
        lp = sum(self.logp(ws[i], ws[i - 2], ws[i - 1]) for i in range(2, len(ws)))
        return lp, len(ws) - 2

    def freq(self, w: str) -> int:
        return self.uni.get(w.lower(), 0)


def build(mfa: Path, n: int, exclude: set[str], banned: set[str] | None = None) -> LM:
    uni, bi, tri = Counter(), Counter(), Counter()
    k = skipped = 0
    for p in sorted(mfa.glob("*.json")):
        if p.stem in exclude:
            continue
        try:
            ws = [w for _, _, w in json.loads(p.read_text())["tiers"]["words"]["entries"] if w and w not in ("sil", "sp", "spn")]
        except Exception:
            continue
        if banned and " ".join(tokens(" ".join(ws))) in banned:
            skipped += 1
            continue  # the same sentence as a test reference (Common Voice reuses sentences across speakers)
        ws = [BOS, BOS] + [w.lower() for w in ws] + [EOS]
        uni.update(ws[2:])
        uni[BOS] += 1
        bi.update(zip(ws[1:], ws[2:]))
        bi[(BOS, BOS)] += 1
        tri.update(zip(ws, ws[1:], ws[2:]))
        k += 1
        if k >= n:
            break
    print(f"skipped {skipped} sentences identical to a test reference")
    return LM(uni, bi, tri)


def load(path: Path) -> LM:
    u, b, t = pickle.load(open(path, "rb"))
    return LM(u, b, t)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build"])
    ap.add_argument("--mfa", type=Path, required=True)
    ap.add_argument("--n", type=int, default=400000)
    ap.add_argument("--exclude", type=Path)
    ap.add_argument("--ban-text", type=Path, nargs="*", default=[], help="Files of sentences to keep out (test refs)")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    banned = {" ".join(tokens(l)) for f in a.ban_text for l in f.read_text(encoding="utf-8").splitlines()}
    ex = set()
    if a.exclude:
        ex = {l.split(".")[0] for l in a.exclude.read_text().split()}
    lm = build(a.mfa, a.n, ex, banned)
    pickle.dump((lm.uni, lm.bi, lm.tri), open(a.out, "wb"))
    print(f"unigrams {len(lm.uni)}, bigrams {len(lm.bi)}, trigrams {len(lm.tri)}, tokens {lm.total}")
