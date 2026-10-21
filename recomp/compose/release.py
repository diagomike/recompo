"""Cross-release matching: the same film in another copy (another release, a cut scene, PAL speed-up).

A recipe's file sources carry **anchors**: a few transcript lines (time, text) around each slot of the copy it
was made from. On a copy with a different fingerprint, each anchor is looked up in that copy's own transcript;
the time differences give the offset. One offset for the whole film is the usual case; offsets that change
along the film mean the copies differ by an edit (a scene cut or added) or run at another speed, and each cut
then takes the offset measured near it.
"""

from __future__ import annotations

import difflib
import statistics

from ..transcript import align, store

PER_SLOT = 4          # anchors kept around each slot
MAX_ANCHORS = 60      # per source
MIN_TOKENS = 4        # shorter lines ("Yeah.") match anywhere
SEARCH_S = 600.0      # first pass: how far a copy may be off (PAL speed-up drifts ~5 min over two hours)
NEAR_S = 120.0        # a cut uses the anchors this close to it
AGREE_S = 1.0         # offsets closer than this are the same offset


def _toks(text: str) -> list[str]:
    return [n for n in (align.norm(t) for t in align.tokens(text)) if n]


def segments(db, source_id: str) -> list[dict]:
    tr = store.primary(db, source_id)
    if not tr:
        return []
    return [dict(r) for r in db.all('SELECT start, "end", text FROM segment WHERE transcript_id=? ORDER BY start', (tr["id"],))]


def anchors(segs: list[dict], spans: list[tuple[float, float]]) -> list[list]:
    """[[time, text], …]: for each span, up to PER_SLOT lines with enough words, from just before it to its end."""
    out: dict[float, str] = {}
    for a, b in spans:
        near = [s for s in segs if a - 20 <= s["start"] <= b + 5 and len(_toks(s["text"])) >= MIN_TOKENS]
        if len(near) > PER_SLOT:  # spread them over the span
            step = (len(near) - 1) / (PER_SLOT - 1)
            near = [near[round(k * step)] for k in range(PER_SLOT)]
        for s in near:
            out[round(s["start"], 2)] = s["text"].strip()[:160]
    return [[t, out[t]] for t in sorted(out)][:MAX_ANCHORS]


def _candidates(anchor_toks: list[str], segs: list[dict], lo: float, hi: float, top: int = 6) -> list[tuple[float, float]]:
    """(score, local start) of the lines (or two joined lines: releases split subtitles differently) that read
    like the anchor, best first."""
    best: dict[float, float] = {}
    for i, s in enumerate(segs):
        if s["start"] < lo or s["start"] > hi:
            continue
        for k in (1, 2):
            if i + k > len(segs):
                break
            cand = _toks(" ".join(x["text"] for x in segs[i:i + k]))
            if not cand:
                continue
            r = difflib.SequenceMatcher(a=anchor_toks, b=cand, autojunk=False).ratio()
            if r >= MIN_SCORE and r > best.get(s["start"], 0.0):
                best[s["start"]] = r
    return sorted(((r, st) for st, r in best.items()), reverse=True)[:top]


MIN_SCORE = 0.6   # how alike an anchor and a line must read
SKIP = 0.7        # cost of leaving an anchor unmatched (its line may be missing from this copy)
JUMP = 1.5        # cost of the offset changing (an edit): worth it only when several anchors after it agree
DRIFT = 0.05      # offset change per second that is speed, not an edit (PAL: 4 %)


def match(anchor_list: list[list], segs: list[dict]) -> dict:
    """Find the anchors in this copy's transcript. Returns the offset (local − recipe), the matched pairs and
    whether the offset changes along the film.

    Each anchor has a few candidate places; one pass over the anchors in time order picks a place (or none) for
    each so that the offset stays the same, or drifts slowly, from one to the next, paying JUMP where it changes.
    A line said again elsewhere would need two jumps and loses; a scene missing from one copy costs one jump that
    the anchors after it pay back."""
    items = []
    for t, text in sorted(anchor_list):
        toks = _toks(text)
        if len(toks) >= MIN_TOKENS:
            c = _candidates(toks, segs, t - SEARCH_S, t + SEARCH_S)
            if c:
                items.append((t, c))
    n_usable = len([a for a in anchor_list if len(_toks(a[1])) >= MIN_TOKENS])
    if not items:
        return {"offset_s": None, "matched": 0, "anchors": len(anchor_list), "pairs": [], "edit": False, "confidence": 0.0}
    # states per anchor: (cost, current offset or None, back pointer, chosen (score, local) or None)
    layers: list[list[tuple[float, float | None, int, tuple | None]]] = []
    prev = [(0.0, None, -1, None)]
    prev_t = items[0][0]
    for t, cands in items:
        tol = AGREE_S + DRIFT * abs(t - prev_t)
        layer = []
        for choice in [*cands, None]:
            best = None
            for k, (pc, pd, _, _) in enumerate(prev):
                if choice is None:
                    cost, d = pc + SKIP, pd
                else:
                    d = choice[1] - t
                    cost = pc + (1.0 - choice[0]) + (0.0 if pd is None or abs(d - pd) <= tol else JUMP)
                if best is None or cost < best[0]:
                    best = (cost, d, k, choice)
            layer.append(best)
        layers.append(layer)
        prev, prev_t = layer, t
    k = min(range(len(prev)), key=lambda i: prev[i][0])
    chosen = []
    for i in range(len(layers) - 1, -1, -1):
        cost, d, back, choice = layers[i][k]
        if choice is not None:
            chosen.append((items[i][0], choice[1], choice[0]))
        k = back
    chosen.reverse()
    pairs = [(t, lt) for t, lt, _ in chosen]
    if not pairs:
        return {"offset_s": None, "matched": 0, "anchors": len(anchor_list), "pairs": [], "edit": False, "confidence": 0.0}
    deltas = [lt - t for t, lt in pairs]
    med = statistics.median(deltas)
    close = [d for d in deltas if abs(d - med) < AGREE_S]
    edit = max(deltas) - min(deltas) > AGREE_S
    spread = statistics.pstdev(close) if len(close) > 1 else 0.0
    coverage = len(pairs) / max(1, n_usable)
    return {"offset_s": round(statistics.median(close) if close else med, 3), "matched": len(pairs),
            "anchors": len(anchor_list), "coverage": round(coverage, 3), "spread_s": round(spread, 3), "edit": edit,
            "pairs": [[round(t, 2), round(lt, 2)] for t, lt in pairs],
            "confidence": round(min(1.0, coverage * 1.4) * (1.0 if spread < 0.5 else 0.5) * (1.0 if len(pairs) >= 2 else 0.5), 3)}


def offset_near(m: dict, t: float) -> float | None:
    """The offset at recipe time t: the median of the anchors within NEAR_S that agree with each other, else the
    film's offset (or the nearest anchor's, when the copies differ by an edit)."""
    pairs = m.get("pairs") or []
    if not pairs:
        return m.get("offset_s")
    near = sorted((abs(a - t), lt - a) for a, lt in pairs if abs(a - t) <= NEAR_S)
    if near:
        d0 = near[0][1]
        same = [d for _, d in near if abs(d - d0) < AGREE_S]
        return round(statistics.median(same), 3)
    if m.get("edit"):
        return round(min(((abs(a - t), lt - a) for a, lt in pairs))[1], 3)
    return m.get("offset_s")


def apply(tx, db, source: dict, m: dict, cut_ids: list[str]) -> list[dict]:
    """Shift these cuts (made from the recipe's times) by the offset measured near each. Re-running shifts by the
    difference to what was applied before (kept on the source as release_match.applied)."""
    meta = dict(source.get("meta") or {})
    rm = dict(meta.get("release_match") or {})
    applied = dict(rm.get("applied") or {})
    moved = []
    for cid in cut_ids:
        cut = db.get("cut", cid)
        if cut is None:
            continue
        before = float(applied.get(cid, 0.0))
        orig = cut["start"] - before
        off = offset_near(m, orig)
        if off is None:
            continue
        d = off - before
        if abs(d) >= 0.01:
            tx.update("cut", cid, {"start": round(max(0.0, cut["start"] + d), 3), "end": round(max(0.0, cut["end"] + d), 3)})
        applied[cid] = off
        moved.append({"cut": cut["ref"], "offset_s": off})
    rm.update({k: v for k, v in m.items() if k != "pairs"})
    rm["pairs"] = m.get("pairs", [])[:MAX_ANCHORS]
    rm["applied"] = applied
    meta["release_match"] = rm
    meta["release_offset_s"] = m.get("offset_s")
    tx.update("source", source["id"], {"meta": meta})
    return moved
