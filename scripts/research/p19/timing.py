"""Speech timing for dubbing: speech runs, syllable budgets and isochrony scores.

A dub sounds right when the new voice speaks while the original speaker's mouth moves and is silent in their
pauses, at a pace natural for that speaker (Brannon et al. 2023: professional dubbers keep the source's
speech/pause structure and its speaking rate; they do not speed up to fit). So the budget for a translated phrase
is **time and syllables**, not characters:

- A **run** is speech between pauses (a gap of ``min_pause`` or more between word timings, 0.25 s by default, the
  usual threshold for a prosodic phrase break). Long pauses are kept in professional dubs (Öktem et al. 2019:
  70 % of pauses over 0.1 s, 91 % over 0.4 s).
- A **unit** is a whole thought: runs up to a sentence end, a speaker change or a long pause. Translation reads a
  unit as a whole and then shares its words among the unit's runs.
- The **budget** of a run is its duration × the target language's typical syllable rate × the speaker's own tempo
  (their measured syllable rate against their language's typical rate), so a fast talker gets a fast dub.

Syllable counts are estimates from the script (Ethiopic: one per fidel; Latin: vowel groups; Han: one per
character). Typical rates are Pellegrino et al. (2011) for the languages they measured; the rest use the
cross-language mean (Coupé et al. 2019: 6.63 syl/s) until a dubbed corpus calibrates them (``RATES_SOURCE``).
"""

from __future__ import annotations

import re
import unicodedata

# Typical syllables per second (read speech). Pellegrino, Coupé & Marsico 2011, Language 87(3).
RATES = {"en": 6.19, "fr": 7.18, "de": 5.97, "it": 6.99, "ja": 7.84, "zh": 5.18, "es": 7.82, "vi": 5.22}
MEAN_RATE = 6.63  # Coupé et al. 2019, 17 languages
RATES_SOURCE = {k: "Pellegrino 2011" for k in RATES}

MIN_PAUSE = 0.25   # a gap this long between words is a phrase break
UNIT_PAUSE = 1.2   # a gap this long ends a thought unit even without punctuation
TEMPO_RANGE = (0.75, 1.35)  # how far a speaker's own tempo may move the budget

_VOWELS = "aeiouyàáâãäåæèéêëìíîïòóôõöøùúûüýÿœɛɔəɨ"
_VOWEL_RX = re.compile(f"[{_VOWELS}]+")
_END_RX = re.compile(r"[.!?…።፧]['\"”’)\]]*$")


def rate(lang: str, rates: dict | None = None) -> float:
    """Typical syllables per second for a language (calibrated rates first, then the table, then the mean)."""
    lang = (lang or "").lower()[:2]
    return (rates or {}).get(lang) or RATES.get(lang) or MEAN_RATE


def _ethiopic(ch: str) -> bool:
    cp = ord(ch)
    return 0x1200 <= cp <= 0x139F or 0x2D80 <= cp <= 0x2DDF or 0xAB00 <= cp <= 0xAB2F


def _cjk(ch: str) -> bool:
    cp = ord(ch)
    return 0x4E00 <= cp <= 0x9FFF or 0x3400 <= cp <= 0x4DBF or 0x3040 <= cp <= 0x30FF or 0xAC00 <= cp <= 0xD7AF


def _word_syllables(word: str) -> float:
    if not word:
        return 0.0
    eth = [c for c in word if _ethiopic(c) and unicodedata.category(c).startswith("L")]
    if eth:
        # Sixth-order fidel (ə or a bare consonant) is often not a syllable of its own: inside a word it counts 0.4
        # (sometimes an epenthetic ə is voiced), at the end of a word 0.2. Other orders are one CV syllable each.
        n = 0.0
        for k, c in enumerate(eth):
            sixth = 0x1200 <= ord(c) <= 0x137F and (ord(c) - 0x1200) % 8 == 5
            n += (0.2 if k == len(eth) - 1 and k > 0 else 0.4) if sixth else 1.0
        return max(1.0, n)
    cjk = [c for c in word if _cjk(c)]
    if cjk:
        return float(len([c for c in cjk if c not in "ゃゅょャュョっッー"]))
    w = word.lower()
    if w.isdigit():
        return 1.5 * len(w)
    groups = len(_VOWEL_RX.findall(w))
    if groups > 1 and w.endswith("e") and not w.endswith(("le", "ee", "ie")):
        groups -= 1  # silent final e (English); harmless elsewhere at this precision
    if groups == 0:
        letters = sum(ch.isalpha() for ch in w)
        return max(1.0, letters / 3) if letters else 0.0
    return float(groups)


def syllables(text: str, lang: str | None = None) -> float:
    """Estimated syllables in a line (any script)."""
    return sum(_word_syllables(w) for w in re.findall(r"\w+", unicodedata.normalize("NFC", text or "")))


def duration(text: str, lang: str, tempo: float = 1.0, rates: dict | None = None) -> float:
    """Estimated speaking time of a line at a speaker's tempo (1.0 = the language's typical rate)."""
    return syllables(text, lang) / (rate(lang, rates) * tempo)


# ---- runs and units --------------------------------------------------------------------------------------------

def runs(words: list[dict], min_pause: float = MIN_PAUSE) -> list[dict]:
    """Group timed words ({start, end, text, speaker?}, in order) into speech runs split at pauses ≥ ``min_pause``
    and at speaker changes."""
    out: list[dict] = []
    for w in words:
        if not str(w.get("text", "")).strip():
            continue
        if out and w["start"] - out[-1]["end"] < min_pause and w.get("speaker") == out[-1].get("speaker"):
            r = out[-1]
            r["end"] = max(r["end"], w["end"])
            r["words"].append(w)
        else:
            out.append({"start": w["start"], "end": w["end"], "words": [w], "speaker": w.get("speaker")})
    for k, r in enumerate(out):
        r["text"] = " ".join(str(w["text"]).strip() for w in r["words"])
        r["dur"] = round(r["end"] - r["start"], 3)
        r["pause_after"] = round(out[k + 1]["start"] - r["end"], 3) if k + 1 < len(out) else None
    return out


def units(rs: list[dict], unit_pause: float = UNIT_PAUSE) -> list[list[dict]]:
    """Group runs into thought units: a unit ends at a sentence end, a speaker change or a long pause."""
    out: list[list[dict]] = []
    cur: list[dict] = []
    for k, r in enumerate(rs):
        cur.append(r)
        nxt = rs[k + 1] if k + 1 < len(rs) else None
        ends = _END_RX.search(r["text"].strip()) is not None
        if nxt is None or ends or (r.get("pause_after") or 0) >= unit_pause or \
                (nxt.get("speaker") or None) != (r.get("speaker") or None):
            out.append(cur)
            cur = []
    return out


def tempo(rs: list[dict], lang: str, rates: dict | None = None) -> float:
    """A speaker's tempo over some runs: their syllable rate against their language's typical rate (clamped)."""
    syl = sum(syllables(r["text"], lang) for r in rs)
    dur = sum(r["dur"] for r in rs)
    if dur < 1.0 or syl < 3:
        return 1.0
    lo, hi = TEMPO_RANGE
    return round(min(hi, max(lo, syl / dur / rate(lang, rates))), 3)


def budget(run: dict, src_lang: str, tgt_lang: str, speaker_tempo: float = 1.0, rates: dict | None = None) -> dict:
    """Target syllables for a run, plus the slack it may borrow from the pause after it (≤ 0.3 s, ≤ half the pause)."""
    pause = run.get("pause_after")
    slack = 0.3 if pause is None else max(0.0, min(0.3, pause / 2))
    target = run["dur"] * rate(tgt_lang, rates) * speaker_tempo
    return {"syllables": round(target, 1), "max_syllables": round((run["dur"] + slack) * rate(tgt_lang, rates) * speaker_tempo, 1),
            "slack_s": round(slack, 2), "source_syllables": round(syllables(run["text"], src_lang), 1)}


def fit(text: str, run: dict, tgt_lang: str, speaker_tempo: float = 1.0, rates: dict | None = None) -> dict:
    """How a proposed line fits its run: estimated duration, ratio to the run, and a verdict."""
    est = duration(text, tgt_lang, speaker_tempo, rates)
    ratio = est / max(0.05, run["dur"])
    pause = run.get("pause_after")
    slack = 0.3 if pause is None else max(0.0, min(0.3, pause / 2))
    if not text.strip():
        verdict = "empty"
    elif est > run["dur"] + slack + 0.05:
        verdict = "long"
    elif ratio < 0.7:
        verdict = "short"
    else:
        verdict = "ok"
    return {"est_s": round(est, 2), "ratio": round(ratio, 2), "verdict": verdict,
            "syllables": round(syllables(text, tgt_lang), 1)}


# ---- isochrony scores ------------------------------------------------------------------------------------------

def _total(iv: list[tuple[float, float]]) -> float:
    return sum(max(0.0, b - a) for a, b in _merge(iv))


def _merge(iv: list[tuple[float, float]]) -> list[tuple[float, float]]:
    out: list[list[float]] = []
    for a, b in sorted(iv):
        if out and a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return [(a, b) for a, b in out]


def _intersect(x: list[tuple[float, float]], y: list[tuple[float, float]]) -> float:
    x, y = _merge(x), _merge(y)
    i = j = 0
    tot = 0.0
    while i < len(x) and j < len(y):
        a, b = max(x[i][0], y[j][0]), min(x[i][1], y[j][1])
        if b > a:
            tot += b - a
        if x[i][1] < y[j][1]:
            i += 1
        else:
            j += 1
    return tot


def speech_overlap(src: list[tuple[float, float]], dub: list[tuple[float, float]]) -> float:
    """Time both voices speak over the time either speaks (1.0: the dub speaks exactly when the source does)."""
    union = _total(src + dub)
    return round(_intersect(src, dub) / union, 3) if union > 0 else 1.0


def duration_overlap(src_dur: float, dub_dur: float) -> float:
    """IWSLT 2023 'speech overlap' for one segment: 1 − |source − dub| / source."""
    return round(1 - abs(src_dur - dub_dur) / src_dur, 3) if src_dur > 0 else 0.0


def length_compliance(pairs: list[tuple[float, float]], p: float = 0.2) -> float:
    """Share of segments whose dub lasts within ±p of the source (SLC_p, as in TransVIP)."""
    if not pairs:
        return 0.0
    return round(sum(1 for s, d in pairs if s > 0 and abs(d - s) / s <= p) / len(pairs), 3)


def pause_compliance(src: list[tuple[float, float]], dub: list[tuple[float, float]], min_pause: float = 0.4,
                     need: float = 0.5) -> float | None:
    """Share of the source's pauses (≥ ``min_pause``, inside its speech) during which the dub is mostly silent too."""
    s = _merge(src)
    gaps = [(s[k][1], s[k + 1][0]) for k in range(len(s) - 1) if s[k + 1][0] - s[k][1] >= min_pause]
    if not gaps:
        return None
    kept = sum(1 for a, b in gaps if _intersect([(a, b)], dub) <= (1 - need) * (b - a))
    return round(kept / len(gaps), 3)


def report(src: list[tuple[float, float]], dub: list[tuple[float, float]],
           pairs: list[tuple[float, float]] | None = None) -> dict:
    """Every isochrony score for one stretch: interval overlap, pause compliance, and SLC/duration overlap per pair."""
    out = {"speech_overlap": speech_overlap(src, dub), "pause_compliance": pause_compliance(src, dub),
           "source_speech_s": round(_total(src), 2), "dub_speech_s": round(_total(dub), 2)}
    if pairs:
        out["slc_0.2"] = length_compliance(pairs, 0.2)
        out["slc_0.4"] = length_compliance(pairs, 0.4)
        out["duration_overlap"] = round(sum(duration_overlap(s, d) for s, d in pairs) / len(pairs), 3)
    return out
