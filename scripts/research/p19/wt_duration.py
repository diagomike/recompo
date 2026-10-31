"""P19 worktree `duration`: how well can we predict how long a phrase takes to say, from its text?

Every timed-rephrasal mechanism needs this ruler (budgets before writing, checks after). Predictors, simplest first:

  D0  syllables × seconds/syllable (one number fitted)            — what `timing.py` does today
  D1  CMUdict phones × seconds/phone (one number fitted)
  D2  sum of learned mean durations per phone (with stress) + a per-word constant
  D3  ridge regression on counts (syllables, phones by class, words, function words, final lengthening)
  D4  gradient boosting on the same features

Data: real English speech (Montreal Forced Aligner on Common Voice, from the IWSLT 2023 dubbing task). Unit: a speech
segment between pauses ≥ 0.3 s. Train on N utterances, test on held-out utterances (different files) and on the 192
IWSLT test items. Error: MAPE and median absolute percentage error. "Oracle tempo" rescales each prediction by the
speaker's own rate over the rest of the utterance — what we have in dubbing, where the source speaker is heard.

    python scripts/research/p19/wt_duration.py --mfa MFA_DIR --iwslt IWSLT_DIR --n 30000 --out results.json
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import bench as B  # noqa: E402
import timing as T  # noqa: E402

FUNCTION = set("a an the and or but of to in on at by for with from as is are was were be been am i you he she it we they "
               "me him her us them my your his its our their this that these those there here not no do does did have has "
               "had will would can could shall should may might must so if then than".split())
VOWEL = re.compile(r"[AEIOU]")


def cmu():
    import cmudict
    return cmudict.dict()


_G2P_CACHE: dict[str, list[str]] = {}


def phones_of(word: str, d) -> list[str]:
    w = re.sub(r"[^a-z']", "", word.lower())
    if not w:
        return []
    if w in _G2P_CACHE:
        return _G2P_CACHE[w]
    if w in d:
        p = d[w][0]
    else:  # crude letter fallback: a vowel group is a vowel phone, other letters consonants
        p = []
        for g in re.findall(r"[aeiouy]+|[^aeiouy]", w):
            p.append("AH0" if g[0] in "aeiouy" else g.upper())
    _G2P_CACHE[w] = p
    return p


def features(words: list[str], d) -> np.ndarray:
    ph = [p for w in words for p in phones_of(w, d)]
    vow = [p for p in ph if VOWEL.match(p)]
    stressed = sum(1 for p in vow if p.endswith(("1", "2")))
    fn = sum(1 for w in words if w.lower().strip("'") in FUNCTION)
    syl = sum(T.syllables(w, "en") for w in words)
    last = phones_of(words[-1], d) if words else []
    plosive = sum(1 for p in ph if p[:2] in ("P", "B", "T", "D", "K", "G"))
    fric = sum(1 for p in ph if p[:2] in ("F", "V", "S", "Z", "SH", "ZH", "TH", "DH", "HH"))
    nasal = sum(1 for p in ph if p[:2] in ("M", "N", "NG"))
    long_v = sum(1 for p in vow if p[:2] in ("AA", "AE", "AO", "AW", "AY", "EY", "OW", "OY", "IY", "UW", "ER"))
    return np.array([syl, len(ph), len(vow), stressed, len(words), fn, len(last), plosive, fric, nasal, long_v,
                     sum(len(w) for w in words)], dtype=float)


def collect(paths: list[Path], d) -> list[dict]:
    out = []
    for p in paths:
        try:
            mfa = B.read_mfa(p)
        except Exception:
            continue
        seg = B.segments(mfa)
        pw = B.phones_by_word(mfa)
        segs = seg["segments"]
        tot_syl = sum(T.syllables(s["text"], "en") for s in segs)
        tot_dur = sum(s["dur"] for s in segs)
        for k, s in enumerate(segs):
            words = [seg["words"][i]["text"] for i in s["words"]]
            if s["dur"] < 0.25 or not words:
                continue
            # rest-of-utterance tempo (excludes this segment), for the oracle-tempo variant
            o_syl = tot_syl - T.syllables(s["text"], "en")
            o_dur = tot_dur - s["dur"]
            out.append({"file": p.stem, "words": words, "dur": s["dur"],
                        "phones": [x for i in s["words"] for x in pw[i]],
                        "rest_rate": (o_syl / o_dur) if o_dur > 1.0 and o_syl > 3 else None})
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mfa", type=Path, required=True)
    ap.add_argument("--iwslt", type=Path, required=True)
    ap.add_argument("--n", type=int, default=30000)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    d = cmu()
    test_names = set()
    for sub in ("subset1", "subset2"):
        test_names |= {n.split(".")[0] for n in (a.iwslt / "data/test" / f"{sub}.filenames.txt").read_text().split()}
    allp = sorted(a.mfa.glob("*.json"))
    random.Random(0).shuffle(allp)
    pool = [p for p in allp if p.stem not in test_names]
    train = collect(pool[: a.n], d)
    held = collect(pool[a.n: a.n + 5000], d)
    test = collect([a.mfa / f"{n}.json" for n in sorted(test_names)], d)
    print(f"segments: train {len(train)}, held-out {len(held)}, iwslt-test {len(test)}", file=sys.stderr)

    # D2 phone means (from the aligned phones of the training segments)
    sums, cnts = defaultdict(float), defaultdict(int)
    for s in train:
        for p, du in s["phones"]:
            sums[p] += du
            cnts[p] += 1
    pmean = {p: sums[p] / cnts[p] for p in sums}
    pdefault = float(np.mean(list(pmean.values())))

    def d2_raw(words):
        return sum(pmean.get(p, pmean.get(p.rstrip("012") + "0", pdefault)) for w in words for p in phones_of(w, d))

    Xtr = np.stack([features(s["words"], d) for s in train])
    ytr = np.array([s["dur"] for s in train])
    syl_tr, ph_tr = Xtr[:, 0], Xtr[:, 1]
    k0 = float((ytr * syl_tr).sum() / (syl_tr ** 2).sum())
    k1 = float((ytr * ph_tr).sum() / (ph_tr ** 2).sum())
    d2tr = np.array([d2_raw(s["words"]) for s in train])
    A = np.stack([d2tr, Xtr[:, 4]], 1)
    c2, *_ = np.linalg.lstsq(A, ytr, rcond=None)
    from sklearn.ensemble import HistGradientBoostingRegressor
    from sklearn.linear_model import Ridge
    X3 = np.column_stack([Xtr, d2tr])
    r3 = Ridge(alpha=1.0).fit(X3, ytr)
    g4 = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.08, random_state=0).fit(X3, ytr)

    def predict(words):
        f = features(words, d)
        x2 = d2_raw(words)
        xx = np.concatenate([f, [x2]])[None]
        return {"D0_syllables": k0 * f[0], "D1_phones": k1 * f[1], "D2_phone_means": float(c2[0] * x2 + c2[1] * f[4]),
                "D3_ridge": float(r3.predict(xx)[0]), "D4_gbm": float(g4.predict(xx)[0])}

    mean_rate = float(syl_tr.sum() / ytr.sum())

    def evaluate(rows):
        res = {}
        preds = [predict(s["words"]) for s in rows]
        for m in preds[0]:
            e = np.array([abs(p[m] - s["dur"]) / s["dur"] for p, s in zip(preds, rows)])
            res[m] = {"mape": round(float(e.mean()), 3), "median_ape": round(float(np.median(e)), 3),
                      "within_20pct": round(float((e <= 0.2).mean()), 3)}
            ot = [(p[m] * mean_rate / s["rest_rate"], s["dur"]) for p, s in zip(preds, rows) if s["rest_rate"]]
            if ot:
                e2 = np.array([abs(x - y) / y for x, y in ot])
                res[m]["oracle_tempo_mape"] = round(float(e2.mean()), 3)
                res[m]["oracle_tempo_within_20pct"] = round(float((e2 <= 0.2).mean()), 3)
        return res

    out = {"train_segments": len(train), "seconds_per_syllable": round(k0, 4), "seconds_per_phone": round(k1, 4),
           "dialogue_rate_syl_per_s": round(mean_rate, 2), "held_out": evaluate(held), "iwslt_test": evaluate(test),
           "phone_means_ms": {p: round(v * 1000, 1) for p, v in sorted(pmean.items())}}
    a.out.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "phone_means_ms"}, indent=1))


if __name__ == "__main__":
    main()
