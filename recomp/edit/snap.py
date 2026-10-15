"""Where a cut should really start and end: word edges, shot changes, silences; and quote lookup.

Words come from the primary transcript (or are spread proportionally inside segments when it
has no word timing). A cut snapped to words starts a little before its first word and ends a
little after its last, without catching the tail of the previous word or the head of the next.
"""

from __future__ import annotations

import bisect
import difflib
import json
from pathlib import Path

from ..envelope import RecompError
from ..transcript.align import norm, proportional_words, tokens

PAD_IN = 0.15
PAD_OUT = 0.35
SHOT_REACH = 0.6


def load_words(db, transcript: dict) -> list[dict]:
    if transcript["has_words"]:
        rows = db.all('SELECT w.start, w."end", w.text, s.idx AS seg FROM word w JOIN segment s ON s.id=w.segment_id '
                      "WHERE s.transcript_id=? ORDER BY w.start, w.idx", (transcript["id"],))
        return [dict(r) for r in rows]
    out = []
    for r in db.all('SELECT idx, start, "end", text FROM segment WHERE transcript_id=? ORDER BY idx', (transcript["id"],)):
        for w in proportional_words(dict(r)):
            w["seg"] = r["idx"]
            out.append(w)
    return out


def load_shots(db, source_id: str) -> list[float]:
    return [r[0] for r in db.all("SELECT t FROM shot WHERE source_id=? ORDER BY t", (source_id,))]


def snap_range(a: float, b: float, words: list[dict], shots: list[float], mode: str = "words",
               pad: tuple[float, float] = (PAD_IN, PAD_OUT), duration: float | None = None) -> tuple[float, float, dict]:
    info: dict = {"mode": mode, "requested": [round(a, 3), round(b, 3)]}
    if mode == "none" or not words:
        return a, b, info
    starts = [w["start"] for w in words]
    # first word that ends after a; last word that starts before b
    i = next((k for k, w in enumerate(words) if w["end"] > a + 0.02), None)
    j = None
    for k in range(len(words) - 1, -1, -1):
        if words[k]["start"] < b - 0.02:
            j = k
            break
    if i is None or j is None or j < i:
        info["note"] = "no words inside the range; kept as requested"
        return a, b, info
    prev_end = words[i - 1]["end"] if i > 0 else 0.0
    next_start = words[j + 1]["start"] if j + 1 < len(words) else (duration or words[j]["end"] + 5)
    na = max(words[i]["start"] - pad[0], min(prev_end + 0.05, words[i]["start"]))
    nb = min(words[j]["end"] + pad[1], max(next_start - 0.05, words[j]["end"]))
    info.update({"first_word": words[i]["text"], "last_word": words[j]["text"]})
    if mode in ("shots", "words+shots") and shots:
        k = bisect.bisect_left(shots, na)
        near = [s for s in shots[max(0, k - 2):k + 2] if abs(s - na) <= SHOT_REACH and prev_end - 0.05 <= s <= words[i]["start"]]
        if near:
            na = min(near, key=lambda s: abs(s - na))
            info["start_on_shot"] = True
        k = bisect.bisect_left(shots, nb)
        near = [s for s in shots[max(0, k - 2):k + 2] if abs(s - nb) <= SHOT_REACH and words[j]["end"] <= s <= next_start + 0.05]
        if near:
            nb = min(near, key=lambda s: abs(s - nb))
            info["end_on_shot"] = True
    na = max(0.0, na)
    if duration:
        nb = min(duration, nb)
    return round(na, 3), round(nb, 3), info


def find_quote(words: list[dict], quote: str, after: float = -1.0, before: float | None = None,
               min_ratio: float = 0.6) -> tuple[int, int, float]:
    """Best match of a quote in the word list: (first word index, last word index, score)."""
    q = [norm(t) for t in tokens(quote) if norm(t)]
    if not q:
        raise RecompError("E_INVALID", "empty quote")
    idx = [k for k, w in enumerate(words) if w["start"] >= after and (before is None or w["start"] <= before)]
    if not idx:
        raise RecompError("E_NOT_FOUND", "no transcript words in that range")
    normed = [norm(words[k]["text"]) for k in idx]
    n = len(q)
    best = (-1.0, 0, 0)
    first = q[0]
    # Candidate anchors: positions where any of the first three quote words occur.
    anchors = set()
    for p, t in enumerate(normed):
        if t and (t == first or t in q[:3]):
            anchors.add(max(0, p - q.index(t) if t in q else p))
    if not anchors:
        anchors = set(range(0, len(normed), max(1, n // 2)))
    for p in anchors:
        window = normed[p:p + n + 2]
        sm = difflib.SequenceMatcher(a=q, b=window, autojunk=False)
        score = sm.ratio()
        if score > best[0]:
            blocks = [blk for blk in sm.get_matching_blocks() if blk.size]
            if not blocks:
                continue
            s = p + blocks[0].b
            e = p + blocks[-1].b + blocks[-1].size - 1
            best = (score, s, e)
    if best[0] < min_ratio:
        raise RecompError("E_NOT_FOUND", f"quote not found: {quote[:60]!r} (best match {best[0]:.0%})",
                          hint="Copy the words exactly from `transcript read`, or cut by --from/--to.")
    return idx[best[1]], idx[best[2]], round(best[0], 3)


def silences_for(project, src: dict) -> list[tuple[float, float]]:
    cache = project.dir("cache", "silences") / f"{src['ref']}.json"
    if cache.exists():
        return [tuple(x) for x in json.loads(cache.read_text())]
    wav = project.root / "sources" / src["ref"] / "audio16k.wav"
    if not wav.exists():
        return []
    from ..media.audio import silences
    sil = silences(Path(wav))
    cache.write_text(json.dumps(sil))
    return sil
