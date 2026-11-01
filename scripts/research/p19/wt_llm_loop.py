"""P19 worktree `llm-loop`: an LLM writes timed English for German speakers' lines, in measured rounds.

Conditions, all scored on the German speaker's real speech segments (bench_frames.py) with one duration ruler:

  R0        plain translation, no timing given; spoken as one phrase in the first segment
  R0+place  the same words, split across the segments by the placement DP (no rewording)
  R1        timing-aware: per-segment English written against syllable budgets
  R2        R1 after one revision round: lines the ruler measured outside ±20 % were rewritten with the numbers
  REF       the human reference translation (CoVoST), placed by the DP — a translation, not a dub

Sheets show only German and timing (the English references are never printed), so the LLM works blind.

    python wt_llm_loop.py sheet --frames frames.json --ids ids.txt [--ruler ruler.json]
    python wt_llm_loop.py score --frames frames.json --iwslt IWSLT --cands cands.json --ruler ruler.json
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import bench as B  # noqa: E402


def load_ruler(path: Path):
    """Phone-mean duration model (seconds) from wt-duration's results: Σ phone means × a + b × words."""
    import cmudict
    r = json.loads(path.read_text())
    pm = {p: v / 1000 for p, v in r["phone_means_ms"].items()}
    a, b = r.get("d2_coef", [1.0, 0.0])
    default = float(np.mean(list(pm.values())))
    d = cmudict.dict()

    def word(w):
        w = re.sub(r"[^a-z']", "", w.lower())
        if not w:
            return 0.0
        ph = d[w][0] if w in d else ["AH0"] * max(1, len(re.findall(r"[aeiouy]+", w))) + ["T"] * (len(w) // 3)
        return sum(pm.get(p, default) for p in ph)

    def dur(text):
        ws = re.findall(r"[A-Za-z']+|\d+", text)
        nums = sum(len(x) for x in ws if x.isdigit())
        return a * sum(word(w) for w in ws if not w.isdigit()) + b * len(ws) + 0.35 * nums
    return dur, r.get("dialogue_rate_syl_per_s", 4.5)


def place(words, durs, wdur):
    k, n = len(durs), len(words)
    if k <= 1 or n < k:
        return [" ".join(words)] + [""] * (k - 1)
    cum = np.concatenate([[0.0], np.cumsum([wdur(w) for w in words])])
    INF = 1e18
    cost = np.full((k + 1, n + 1), INF)
    back = np.zeros((k + 1, n + 1), int)
    cost[0, 0] = 0.0
    for p in range(1, k + 1):
        for j in range(p, n - (k - p) + 1):
            bon = 0.75 if (p < k and re.search(r"[,.;:!?]$", words[j - 1])) else 0.0
            for i in range(p - 1, j):
                if cost[p - 1, i] < INF:
                    c = cost[p - 1, i] + math.log(max(0.05, cum[j] - cum[i]) / max(0.1, durs[p - 1])) ** 2 - bon
                    if c < cost[p, j]:
                        cost[p, j], back[p, j] = c, i
    out, j = [], n
    for p in range(k, 0, -1):
        i = back[p, j]
        out.append(" ".join(words[i:j]))
        j = i
    return out[::-1]


def sheet(a):
    frames = json.loads(a.frames.read_text(encoding="utf-8"))
    ids = [x.strip() for x in a.ids.read_text().split() if x.strip()]
    rate = 4.5
    if a.ruler:
        _, rate = load_ruler(a.ruler)
    for i in ids:
        f = frames[i]
        segs = "  ".join(f"[{k + 1}] {s['dur']:.2f}s≈{s['dur'] * rate:.0f}syl" + (f" ‖{s['pause_after']:.2f}" if s["pause_after"] else "")
                         for k, s in enumerate(f["segments"]))
        print(f"{i}\tDE: {f['de']}\n\tSEGMENTS: {segs}")


def score(a):
    frames = json.loads(a.frames.read_text(encoding="utf-8"))
    cands = json.loads(a.cands.read_text(encoding="utf-8"))
    dur, _ = load_ruler(a.ruler)
    refs = {}
    for sub in ("subset1", "subset2"):
        for k, line in enumerate((a.iwslt / "data/test" / f"{sub}.en").read_text(encoding="utf-8").splitlines()):
            refs[f"{sub}-{k}"] = line
    ids = sorted(set().union(*[set(v) for v in cands.values()]), key=lambda x: (x.split("-")[0], int(x.split("-")[1])))
    items = [{"id": i, "en": refs[i], "segments": frames[i]["segments"]} for i in ids if i in frames]
    conds = dict(cands)
    if "R0" in cands:
        conds["R0+place"] = {i: place(" ".join(v).split(), [s["dur"] for s in frames[i]["segments"]], dur)
                             for i, v in cands["R0"].items()}
    conds["REF"] = {it["id"]: place(it["en"].split(), [s["dur"] for s in it["segments"]], dur) for it in items}
    res = {name: B.summary(items, outs, dur) for name, outs in conds.items()}
    res["_ruler_check"] = "duration ruler: phone means from real English speech (wt-duration)"
    detail = {}
    for it in items:
        detail[it["id"]] = {c: {"phrases": conds[c].get(it["id"]),
                                "ratio": B.score_item(it, conds[c][it["id"]], dur)["seg_ratio"]}
                            for c in conds if it["id"] in conds[c]}
    out = {"summary": res, "detail": detail}
    if a.out:
        a.out.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))


def feedback(a):
    """Per segment of a round's candidates: ruler duration vs real, for lines outside ±20 % (the revision prompt)."""
    frames = json.loads(a.frames.read_text(encoding="utf-8"))
    cands = json.loads(a.cands.read_text(encoding="utf-8"))[a.round]
    dur, rate = load_ruler(a.ruler)
    for i, phrases in cands.items():
        segs = frames[i]["segments"]
        bad = []
        for k, (s, t) in enumerate(zip(segs, phrases + [""] * len(segs))):
            d = dur(t) if t.strip() else 0.0
            if abs(d - s["dur"]) / s["dur"] > 0.2:
                bad.append(f"[{k + 1}] '{t}' ≈{d:.2f}s for {s['dur']:.2f}s ({'+' if d > s['dur'] else ''}{(d - s['dur']) * rate:.0f} syl)")
        if bad:
            print(f"{i}\tDE: {frames[i]['de']}\n\t" + "\n\t".join(bad))


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    s1 = sp.add_parser("sheet")
    s1.add_argument("--frames", type=Path, required=True)
    s1.add_argument("--ids", type=Path, required=True)
    s1.add_argument("--ruler", type=Path)
    s2 = sp.add_parser("score")
    s2.add_argument("--frames", type=Path, required=True)
    s2.add_argument("--iwslt", type=Path, required=True)
    s2.add_argument("--cands", type=Path, required=True)
    s2.add_argument("--ruler", type=Path, required=True)
    s2.add_argument("--out", type=Path)
    s3 = sp.add_parser("feedback")
    s3.add_argument("--frames", type=Path, required=True)
    s3.add_argument("--cands", type=Path, required=True)
    s3.add_argument("--ruler", type=Path, required=True)
    s3.add_argument("--round", default="R1")
    a = ap.parse_args()
    {"sheet": sheet, "score": score, "feedback": feedback}[a.cmd](a)


if __name__ == "__main__":
    main()
