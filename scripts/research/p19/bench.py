"""P19 timed-rephrasal benchmark on real speech timing (IWSLT 2023 dubbing task data, CoVoST2 de→en).

Each test item has a German sentence (the line to dub), its English reference, and the **real English speech** of
that sentence (Montreal Forced Aligner phones and words, from Common Voice): speech segments separated by pauses
≥ 0.3 s (the IWSLT convention). A mechanism gets the German text and the segment durations and must produce English
phrases, one per segment, that mean the German and fit the segments.

Scoring uses one shared duration model (so mechanisms are compared on the same ruler) and reports how far that
ruler is from the truth by running the reference text through it ("reference through model").

    from bench import load_items, score
    items = load_items(MFA_DIR, IWSLT_DIR, "subset2")
"""

from __future__ import annotations

import json
import re
from pathlib import Path

SIL = {"sil", "sp", "spn", ""}
PAUSE = 0.3


def read_mfa(path: Path) -> dict:
    d = json.loads(path.read_text(encoding="utf-8"))
    words = [(float(s), float(e), w) for s, e, w in d["tiers"]["words"]["entries"]]
    phones = [(float(s), float(e), p) for s, e, p in d["tiers"]["phones"]["entries"]]
    return {"words": words, "phones": phones}


def segments(mfa: dict, pause: float = PAUSE) -> dict:
    """Speech segments of an utterance: words grouped between silences ≥ ``pause`` (leading/trailing silence cut)."""
    words = [w for w in mfa["words"] if w[2] and w[2] not in SIL]
    if not words:
        return {"segments": [], "words": []}
    segs, cur = [], [0]
    for i in range(1, len(words)):
        if words[i][0] - words[i - 1][1] >= pause:
            segs.append(cur)
            cur = []
        cur.append(i)
    segs.append(cur)
    out = []
    for k, idx in enumerate(segs):
        a, b = words[idx[0]][0], words[idx[-1]][1]
        nxt = words[segs[k + 1][0]][0] if k + 1 < len(segs) else None
        out.append({"start": round(a, 3), "end": round(b, 3), "dur": round(b - a, 3), "words": idx,
                    "pause_after": round(nxt - b, 3) if nxt is not None else None,
                    "text": " ".join(words[i][2] for i in idx)})
    return {"segments": out, "words": [{"start": s, "end": e, "text": w} for s, e, w in words]}


def phones_by_word(mfa: dict) -> list[list[tuple[str, float]]]:
    """Each spoken word's phones with their durations (seconds)."""
    words = [w for w in mfa["words"] if w[2] and w[2] not in SIL]
    out = []
    for s, e, _ in words:
        out.append([(p, pe - ps) for ps, pe, p in mfa["phones"] if p not in SIL and ps >= s - 1e-4 and pe <= e + 1e-4])
    return out


def load_items(mfa_dir: Path, iwslt_dir: Path, subset: str) -> list[dict]:
    base = iwslt_dir / "data" / "test"
    de = (base / f"{subset}.de").read_text(encoding="utf-8").splitlines()
    en = (base / f"{subset}.en").read_text(encoding="utf-8").splitlines()
    names = (base / f"{subset}.filenames.txt").read_text(encoding="utf-8").splitlines()
    items = []
    for k, (d, e, n) in enumerate(zip(de, en, names)):
        p = mfa_dir / (n.split(".")[0] + ".json")
        if not p.exists():
            continue
        seg = segments(read_mfa(p))
        if not seg["segments"]:
            continue
        items.append({"id": f"{subset}-{k}", "name": n.split(".")[0], "de": d, "en": e,
                      "de_pauses": d.count("[pause]"), **seg})
    return items


# ---- scoring -------------------------------------------------------------------------------------------------

def _merge(iv):
    out = []
    for a, b in sorted(iv):
        if out and a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return out


def _inter(x, y):
    x, y = _merge(x), _merge(y)
    i = j = 0
    t = 0.0
    while i < len(x) and j < len(y):
        a, b = max(x[i][0], y[j][0]), min(x[i][1], y[j][1])
        t += max(0.0, b - a)
        if x[i][1] < y[j][1]:
            i += 1
        else:
            j += 1
    return t


def score_item(item: dict, phrases: list[str], dur_fn) -> dict:
    """Score one candidate: ``phrases`` (one per segment; extra/missing phrases are merged/empty) placed at each
    segment's start with their model durations, against the real speech segments."""
    segs = item["segments"]
    k = len(segs)
    ph = list(phrases)
    if len(ph) > k:
        ph = ph[: k - 1] + [" ".join(ph[k - 1:])]
    ph += [""] * (k - len(ph))
    ref_iv = [(s["start"], s["end"]) for s in segs]
    hyp_iv, per = [], []
    for s, t in zip(segs, ph):
        d = dur_fn(t) if t.strip() else 0.0
        if d > 0:
            hyp_iv.append((s["start"], s["start"] + d))
        per.append((s["dur"], d))
    union = sum(b - a for a, b in _merge(ref_iv + hyp_iv))
    ref_total = sum(s["dur"] for s in segs)
    hyp_total = sum(d for _, d in per)
    return {"speech_overlap": round(_inter(ref_iv, hyp_iv) / union, 4) if union else 0.0,
            "duration_overlap": round(1 - abs(ref_total - hyp_total) / ref_total, 4),
            "slc_0.2": round(sum(1 for r, d in per if r > 0 and abs(d - r) / r <= 0.2) / k, 4),
            "seg_ratio": [round(d / r, 3) if r else None for r, d in per]}


def chrf(hyps: list[str], refs: list[str]) -> float:
    """Corpus chrF (character n-gram F-score, β=2), no dependencies; close to sacrebleu's chrF."""
    from collections import Counter
    tot = {n: [0, 0, 0] for n in range(1, 7)}
    for h, r in zip(hyps, refs):
        h, r = re.sub(r"\s+", " ", h.strip()), re.sub(r"\s+", " ", r.strip())
        for n in range(1, 7):
            hc = Counter(h.replace(" ", "")[i:i + n] for i in range(max(0, len(h.replace(" ", "")) - n + 1)))
            rc = Counter(r.replace(" ", "")[i:i + n] for i in range(max(0, len(r.replace(" ", "")) - n + 1)))
            tot[n][0] += sum((hc & rc).values())
            tot[n][1] += sum(hc.values())
            tot[n][2] += sum(rc.values())
    ps = [m / h if h else 0 for m, h, _ in tot.values()]
    rs = [m / r if r else 0 for m, _, r in tot.values()]
    p, r = sum(ps) / 6, sum(rs) / 6
    return round(100 * (5 * p * r / (4 * p + r)) if p + r else 0.0, 2)


def summary(items: list[dict], outputs: dict[str, list[str]], dur_fn) -> dict:
    """Mean scores over items for {item id: phrases}; plus corpus chrF of the joined text vs the reference."""
    rows = [score_item(it, outputs[it["id"]], dur_fn) for it in items if it["id"] in outputs]
    hyps = [" ".join(outputs[it["id"]]) for it in items if it["id"] in outputs]
    refs = [it["en"] for it in items if it["id"] in outputs]
    n = len(rows)
    return {"n": n, **{k: round(sum(r[k] for r in rows) / n, 4) for k in ("speech_overlap", "duration_overlap", "slc_0.2")},
            "chrF": chrf(hyps, refs)}
