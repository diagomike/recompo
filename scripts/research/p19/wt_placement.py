"""P19 worktree `placement`: put a sentence's words into a speaker's speech segments (prosodic alignment).

Given the words of a line and the durations of k speech segments (separated by pauses), choose k−1 break points.
This is the no-training core of dubbing placement (Öktem 2019; Federico 2020; Virkar 2021–22). We test how often each
method puts the breaks exactly where a real speaker paused, on real English speech (MFA on Common Voice):

  P0 uniform     words shared in proportion to segment durations
  P1 rate DP     dynamic programme: each phrase's predicted duration (phone-mean model) matches its segment
  P2 rate+rules  P1 + a hand-written break prior (before conjunctions/relatives/prepositions, never after a determiner)
  P3 rate+learn  P1 + a logistic-regression break model trained on pauses in other utterances (no punctuation)
  P4 learn only  the k−1 most likely boundaries, ignoring durations

    python scripts/research/p19/wt_placement.py --mfa MFA_DIR --iwslt IWSLT_DIR --n 30000 --out results.json
"""

from __future__ import annotations

import argparse
import json
import math
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import bench as B  # noqa: E402

CONJ = set("and but or so because which who whom whose that when while where although though if unless until since "
           "after before as then whereas".split())
PREP = set("in on at by for with from to of about into over under through between during without within".split())
DET = set("a an the this that these those my your his her its our their some any no every each".split())
AUX = set("is are was were be been am do does did have has had will would can could should may might must".split())


def cmu():
    import cmudict
    return cmudict.dict()


def phone_model(train_rows, d):
    sums, cnts = defaultdict(float), defaultdict(int)
    for r in train_rows:
        for p, du in r["phones"]:
            sums[p] += du
            cnts[p] += 1
    pm = {p: sums[p] / cnts[p] for p in sums}
    default = float(np.mean(list(pm.values())))
    cache = {}

    def dur(word):
        w = re.sub(r"[^a-z']", "", word.lower())
        if w not in cache:
            ph = d[w][0] if w in d else ["AH0"] * max(1, len(re.findall(r"[aeiouy]+", w))) + ["T"] * max(0, len(w) // 3)
            cache[w] = sum(pm.get(p, default) for p in ph)
        return cache[w]
    return dur


def boundary_feats(words: list[str], i: int) -> list[float]:
    """Features of the boundary after words[i] (lexical only: the training text has no punctuation)."""
    a, b = words[i].lower(), words[i + 1].lower()
    n = len(words)
    return [a in DET, a in PREP, a in AUX, a in CONJ, b in CONJ, b in PREP, b in DET, b in AUX,
            len(a), len(b), (i + 1) / n, a.endswith("ing"), a.endswith("ly"), a.endswith("s"),
            b in ("i", "you", "he", "she", "we", "they", "it"), 1.0]


def rule_prior(words: list[str], i: int) -> float:
    a, b = words[i].lower(), words[i + 1].lower()
    s = 0.0
    if b in CONJ:
        s += 1.0
    if b in PREP:
        s += 0.4
    if a in DET or a in PREP or a in AUX:
        s -= 1.5
    if re.search(r"[,.;:!?]$", words[i]):
        s += 1.5
    return s


def place(words, durs, wdur, prior=None, lam=1.0):
    """DP: split words into len(durs) phrases, cost = Σ log²(pred/real) − lam·Σ prior(boundary)."""
    k, n = len(durs), len(words)
    if k <= 1:
        return []
    if n < k:
        return list(range(n - 1))[: k - 1]
    cum = np.concatenate([[0.0], np.cumsum([wdur(w) for w in words])])
    INF = 1e18
    cost = np.full((k + 1, n + 1), INF)
    back = np.zeros((k + 1, n + 1), int)
    cost[0, 0] = 0.0
    for p in range(1, k + 1):
        for j in range(p, n - (k - p) + 1):
            bon = lam * prior[j - 1] if (prior is not None and p < k) else 0.0
            for i in range(p - 1, j):
                if cost[p - 1, i] >= INF:
                    continue
                est = max(0.05, cum[j] - cum[i])
                c = cost[p - 1, i] + math.log(est / max(0.1, durs[p - 1])) ** 2 - bon
                if c < cost[p, j]:
                    cost[p, j], back[p, j] = c, i
    cuts, j = [], n
    for p in range(k, 0, -1):
        i = back[p, j]
        if p > 1:
            cuts.append(i - 1)
        j = i
    return sorted(cuts)


def uniform(words, durs):
    tot = sum(durs)
    acc, cuts = 0.0, []
    for d in durs[:-1]:
        acc += d
        cuts.append(min(len(words) - 2, max(0, round(acc / tot * len(words)) - 1)))
    return sorted(set(cuts))[: len(durs) - 1]


def rows_from(paths):
    out = []
    for p in paths:
        try:
            mfa = B.read_mfa(p)
        except Exception:
            continue
        seg = B.segments(mfa)
        words = [w["text"] for w in seg["words"]]
        if len(words) < 3:
            continue
        pw = B.phones_by_word(mfa)
        breaks = [s["words"][-1] for s in seg["segments"][:-1]]
        out.append({"file": p.stem, "words": words, "durs": [s["dur"] for s in seg["segments"]], "breaks": breaks,
                    "phones": [x for ph in pw for x in ph]})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mfa", type=Path, required=True)
    ap.add_argument("--iwslt", type=Path, required=True)
    ap.add_argument("--n", type=int, default=30000)
    ap.add_argument("--eval", type=int, default=8000)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    d = cmu()
    test_names = set()
    for sub in ("subset1", "subset2"):
        test_names |= {n.split(".")[0] for n in (a.iwslt / "data/test" / f"{sub}.filenames.txt").read_text().split()}
    allp = sorted(a.mfa.glob("*.json"))
    random.Random(1).shuffle(allp)
    pool = [p for p in allp if p.stem not in test_names]
    train = rows_from(pool[: a.n])
    held = [r for r in rows_from(pool[a.n: a.n + a.eval]) if r["breaks"]]
    wdur = phone_model(train, d)
    # learned break model
    from sklearn.linear_model import LogisticRegression
    X, y = [], []
    for r in train:
        bs = set(r["breaks"])
        for i in range(len(r["words"]) - 1):
            X.append(boundary_feats(r["words"], i))
            y.append(i in bs)
    lr = LogisticRegression(max_iter=500, class_weight="balanced").fit(np.array(X, float), np.array(y))
    base_rate = float(np.mean(y))

    def logit_prior(words):
        p = lr.predict_proba(np.array([boundary_feats(words, i) for i in range(len(words) - 1)], float))[:, 1]
        return np.log(p / (1 - p))

    methods = {
        "P0_uniform": lambda r: uniform(r["words"], r["durs"]),
        "P1_rate_dp": lambda r: place(r["words"], r["durs"], wdur),
        "P2_rate_rules": lambda r: place(r["words"], r["durs"], wdur,
                                         [rule_prior(r["words"], i) for i in range(len(r["words"]) - 1)], 0.5),
        "P3_rate_learned": lambda r: place(r["words"], r["durs"], wdur, logit_prior(r["words"]), 0.5),
        "P4_learned_only": lambda r: sorted(np.argsort(-logit_prior(r["words"]))[: len(r["durs"]) - 1].tolist()),
    }

    def evaluate(rows):
        res = {}
        for name, fn in methods.items():
            ex = near = tot = 0
            for r in rows:
                pred = fn(r)
                for p, q in zip(sorted(pred), r["breaks"]):
                    tot += 1
                    ex += p == q
                    near += abs(p - q) <= 1
            res[name] = {"breaks": tot, "exact": round(ex / tot, 3), "within_1_word": round(near / tot, 3)}
        return res

    out = {"train_utterances": len(train), "pause_rate_per_boundary": round(base_rate, 4),
           "held_out_utterances_with_pauses": len(held), "held_out": evaluate(held),
           "lr_coef": dict(zip(["a_det", "a_prep", "a_aux", "a_conj", "b_conj", "b_prep", "b_det", "b_aux", "len_a",
                                "len_b", "pos", "a_ing", "a_ly", "a_s", "b_pron", "bias"],
                               [round(float(c), 2) for c in lr.coef_[0]]))}
    # The IWSLT test lines, with punctuation from the reference text (rules may use it; learned model cannot)
    tests = []
    for sub in ("subset1", "subset2"):
        names = (a.iwslt / "data/test" / f"{sub}.filenames.txt").read_text().split()
        ens = (a.iwslt / "data/test" / f"{sub}.en").read_text(encoding="utf-8").splitlines()
        for n, en in zip(names, ens):
            rr = rows_from([a.mfa / (n.split(".")[0] + ".json")])
            if rr and rr[0]["breaks"]:
                toks = en.split()
                if len(toks) == len(rr[0]["words"]):
                    rr[0]["words"] = toks  # same words with punctuation attached
                tests.append(rr[0])
    out["iwslt_test_utterances_with_pauses"] = len(tests)
    if tests:
        out["iwslt_test"] = evaluate(tests)
    a.out.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
