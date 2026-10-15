"""Aligning texts to timings.

* :func:`estimate_offset`: how far a subtitle track is from what was actually said (ASR words).
* :func:`words_from_reference`: give each word of a subtitle segment a time, by matching the
  subtitle's words to ASR words (difflib over normalised tokens); unmatched words are
  interpolated inside their segment.
* :func:`proportional_words`: no reference? Spread words across the segment by character length.
"""

from __future__ import annotations

import difflib
import re
import statistics

_NORM = re.compile(r"[^\w']+", re.UNICODE)


def norm(token: str) -> str:
    return _NORM.sub("", token.lower().replace("’", "'"))


def tokens(text: str) -> list[str]:
    return [t for t in re.split(r"\s+", text.strip()) if t]


def proportional_words(seg: dict) -> list[dict]:
    toks = tokens(seg["text"])
    if not toks:
        return []
    weights = [max(1, len(norm(t))) + 1 for t in toks]
    total = sum(weights)
    span = max(0.01, seg["end"] - seg["start"])
    out, t = [], seg["start"]
    for tok, w in zip(toks, weights):
        d = span * w / total
        out.append({"start": round(t, 3), "end": round(t + d, 3), "text": tok, "prob": None})
        t += d
    return out


def _flatten(segments: list[dict]) -> list[tuple[int, str, str]]:
    out = []
    for i, s in enumerate(segments):
        for tok in tokens(s["text"]):
            n = norm(tok)
            if n:
                out.append((i, tok, n))
    return out


def match_words(sub_segments: list[dict], ref_words: list[dict]) -> list[tuple[int, int, dict]]:
    """Pairs (segment index, token index within the flattened subtitle, matched ref word)."""
    flat = _flatten(sub_segments)
    a = [n for _, _, n in flat]
    b = [norm(w["text"]) for w in ref_words]
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    pairs = []
    for block in sm.get_matching_blocks():
        for k in range(block.size):
            ia, ib = block.a + k, block.b + k
            pairs.append((flat[ia][0], ia, ref_words[ib]))
    return pairs


def estimate_offset(sub_segments: list[dict], ref_words: list[dict], window: tuple[float, float] | None = None) -> dict:
    """Median of (subtitle word time − spoken word time) over matched words in runs of ≥3."""
    if window:
        sub_segments = [s for s in sub_segments if s["end"] >= window[0] - 15 and s["start"] <= window[1] + 15]
        ref_words = [w for w in ref_words if window[0] <= w["start"] <= window[1]]
    if not sub_segments or not ref_words:
        return {"offset_s": None, "matched": 0, "confidence": 0.0}
    flat_words: list[tuple[int, dict]] = []
    for i, s in enumerate(sub_segments):
        for w in proportional_words(s):
            if norm(w["text"]):
                flat_words.append((i, w))
    pairs = match_words(sub_segments, ref_words)
    # Subtitles are authored by cue start, so compare each cue's start with the spoken time of
    # its first word (when that word matched); fall back to proportional word positions.
    first_flat: dict[int, int] = {}
    for k, (seg_i, _) in enumerate(flat_words):
        first_flat.setdefault(seg_i, k)
    deltas = [sub_segments[seg_i]["start"] - ref["start"] for seg_i, ia, ref in pairs
              if first_flat.get(seg_i) == ia]
    if len(deltas) < 5:
        deltas = [flat_words[ia][1]["start"] - ref["start"] for _, ia, ref in pairs]
    if len(deltas) < 5:
        return {"offset_s": None, "matched": len(deltas), "confidence": 0.0}
    med = statistics.median(deltas)
    close = [d for d in deltas if abs(d - med) < 1.0]
    spread = statistics.pstdev(close) if len(close) > 1 else 0.0
    coverage = len(pairs) / max(1, len(ref_words))
    return {"offset_s": round(statistics.median(close), 3), "matched": len(pairs), "spread_s": round(spread, 3),
            "ref_words": len(ref_words), "coverage": round(coverage, 3),
            "confidence": round(min(1.0, coverage * 1.5) * (1.0 if spread < 0.6 else 0.5), 3)}


def words_from_reference(sub_segments: list[dict], ref_words: list[dict]) -> tuple[list[list[dict]], dict]:
    """Per subtitle segment, a list of timed words (matched to ASR where possible)."""
    pairs = match_words(sub_segments, ref_words)
    matched_by_flat = {ia: ref for _, ia, ref in pairs}
    out: list[list[dict]] = []
    flat_i = 0
    matched = 0
    total = 0
    for seg in sub_segments:
        toks = tokens(seg["text"])
        words = []
        for tok in toks:
            if not norm(tok):
                words.append({"text": tok, "start": None, "end": None})
                continue
            ref = matched_by_flat.get(flat_i)
            flat_i += 1
            total += 1
            if ref and seg["start"] - 2.0 <= ref["start"] <= seg["end"] + 2.0:
                matched += 1
                words.append({"text": tok, "start": ref["start"], "end": ref["end"], "prob": ref.get("prob")})
            else:
                words.append({"text": tok, "start": None, "end": None})
        out.append(_fill(words, seg["start"], seg["end"]))
    return out, {"matched": matched, "words": total, "ratio": round(matched / max(1, total), 3)}


def _fill(words: list[dict], start: float, end: float) -> list[dict]:
    """Interpolate missing word times between known neighbours (or the segment edges)."""
    n = len(words)
    i = 0
    while i < n:
        if words[i]["start"] is not None:
            i += 1
            continue
        j = i
        while j < n and words[j]["start"] is None:
            j += 1
        left = words[i - 1]["end"] if i > 0 else start
        right = words[j]["start"] if j < n else end
        if right < left:
            right = left
        step = (right - left) / (j - i)
        for k in range(i, j):
            words[k]["start"] = round(left + step * (k - i), 3)
            words[k]["end"] = round(left + step * (k - i + 1), 3)
        i = j
    for w in words:
        if w["end"] < w["start"]:
            w["end"] = w["start"]
    return words
