"""Subtitle and caption parsers → segments ``{start, end, text, words?}``.

SRT/VTT parsing follows recomposer_v2: one cue reader for both, markup stripped, and every
dropped cue reported rather than silently lost. Additions: a cue number glued to the previous
cue (no blank line) is not taken as text, ASS dialogue lines, and YouTube ``json3`` captions
with per-word timing.
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

_ARROW = "-->"
_TC = re.compile(r"(?:(\d+):)?(\d{1,2}):(\d{2})[.,](\d{1,3})\s*-->\s*(?:(\d+):)?(\d{1,2}):(\d{2})[.,](\d{1,3})")
_TAG = re.compile(r"<[^>]+>|\{\\[^}]*\}")
_ASS_TAG = re.compile(r"\{[^}]*\}")


def read_text(path: Path) -> str:
    raw = Path(path).read_bytes()
    for enc in ("utf-8-sig", "utf-16", "cp1252", "latin-1"):
        try:
            text = raw.decode(enc)
            if enc == "utf-16" and not raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
                continue
            return text
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def _secs(h, m, s, frac) -> float | None:
    if int(m) > 59 or int(s) > 59:
        return None
    return int(h or 0) * 3600 + int(m) * 60 + int(s) + int(frac.ljust(3, "0")[:3]) / 1000.0


def clean(text: str) -> str:
    text = html.unescape(_TAG.sub("", text))
    text = text.replace("\\N", " ").replace("\\n", " ")
    return re.sub(r"\s+", " ", text).strip()


def parse_cues(text: str) -> tuple[list[dict], list[str]]:
    """SRT or WebVTT."""
    cues: list[dict] = []
    problems: list[str] = []
    pending: dict | None = None
    lines: list[str] = []
    pending_line = 0

    def flush():
        nonlocal pending, lines
        if pending is not None:
            body = clean(" ".join(x.strip() for x in lines if x.strip()))
            if not body:
                problems.append(f"line {pending_line}: timing with no text")
            elif pending["end"] <= pending["start"]:
                problems.append(f"line {pending_line}: ends before it starts")
            else:
                pending["text"] = body
                cues.append(pending)
        pending, lines = None, []

    for no, raw in enumerate(text.replace("\r\n", "\n").replace("\r", "\n").split("\n"), start=1):
        if _ARROW in raw:
            if lines and lines[-1].strip().isdigit():
                lines.pop()  # the next cue's number, glued on without a blank line
            flush()
            m = _TC.search(raw)
            a = _secs(*m.groups()[:4]) if m else None
            b = _secs(*m.groups()[4:]) if m else None
            if a is None or b is None:
                problems.append(f"line {no}: unreadable timing {raw.strip()[:60]!r}")
                continue
            pending_line = no
            pending = {"start": round(a, 3), "end": round(b, 3)}
        elif pending is not None:
            if raw.strip():
                lines.append(raw)
            else:
                flush()
    flush()
    return cues, problems


def parse_ass(text: str) -> tuple[list[dict], list[str]]:
    cues, problems = [], []
    fmt = None
    for no, line in enumerate(text.splitlines(), start=1):
        if line.startswith("Format:") and fmt is None and "Start" in line:
            fmt = [f.strip().lower() for f in line[7:].split(",")]
        if not line.startswith("Dialogue:"):
            continue
        fields = (fmt or ["layer", "start", "end", "style", "name", "marginl", "marginr", "marginv", "effect", "text"])
        parts = line[9:].split(",", len(fields) - 1)
        if len(parts) < len(fields):
            problems.append(f"line {no}: short dialogue line")
            continue
        row = dict(zip(fields, parts))
        a, b = _ass_time(row.get("start", "")), _ass_time(row.get("end", ""))
        body = clean(_ASS_TAG.sub("", row.get("text", "")))
        if a is None or b is None or b <= a or not body:
            problems.append(f"line {no}: unusable dialogue line")
            continue
        cues.append({"start": round(a, 3), "end": round(b, 3), "text": body,
                     "speaker": row.get("name") or None})
    cues.sort(key=lambda c: c["start"])
    return cues, problems


def _ass_time(value: str) -> float | None:
    m = re.match(r"\s*(\d+):(\d{2}):(\d{2})[.](\d{1,2})", value)
    if not m:
        return None
    h, mi, s, cs = m.groups()
    return int(h) * 3600 + int(mi) * 60 + int(s) + int(cs.ljust(2, "0")) / 100.0


def parse_json3(text: str) -> tuple[list[dict], list[str]]:
    """YouTube timed text. Auto captions carry per-word offsets; manual ones carry lines."""
    data = json.loads(text)
    words: list[dict] = []
    lines: list[dict] = []
    for ev in data.get("events", []):
        segs = ev.get("segs")
        if not segs or ev.get("aAppend"):
            continue
        t0 = ev.get("tStartMs", 0) / 1000.0
        dur = ev.get("dDurationMs", 0) / 1000.0
        if any("tOffsetMs" in s for s in segs) or len(segs) > 1:
            for s in segs:
                w = s.get("utf8", "").strip()
                if not w or w == "\n":
                    continue
                words.append({"start": round(t0 + s.get("tOffsetMs", 0) / 1000.0, 3), "text": w,
                              "event_end": round(t0 + dur, 3)})
        else:
            body = clean(segs[0].get("utf8", ""))
            if body:
                lines.append({"start": round(t0, 3), "end": round(t0 + dur, 3), "text": body})
    if words:
        words.sort(key=lambda w: w["start"])
        for i, w in enumerate(words):
            nxt = words[i + 1]["start"] if i + 1 < len(words) else w["event_end"]
            w["end"] = round(min(max(nxt, w["start"] + 0.05), w["start"] + 1.5, w["event_end"] + 0.5), 3)
            w.pop("event_end", None)
        return segments_from_words(words), []
    return lines, []


def segments_from_words(words: list[dict], gap: float = 0.7, max_len: float = 12.0,
                        max_words: int = 40) -> list[dict]:
    """Group timed words into sentence-like segments (after lang_bridge ``segments_from_words``)."""
    segs: list[dict] = []
    cur: list[dict] = []

    def close():
        if cur:
            segs.append({"start": cur[0]["start"], "end": cur[-1]["end"],
                         "text": clean(" ".join(w["text"] for w in cur)),
                         "words": [dict(w) for w in cur]})

    for w in words:
        if cur:
            long = w["end"] - cur[0]["start"] > max_len or len(cur) >= max_words
            paused = w["start"] - cur[-1]["end"] > gap
            sentence_end = cur[-1]["text"].endswith((".", "?", "!")) and len(cur) >= 4
            if long or paused or sentence_end:
                close()
                cur = []
        cur.append(w)
    close()
    return segs


def parse_recomp_json(text: str) -> tuple[list[dict], list[str]]:
    """`transcript export --format json`: {segments: [{start, end, text, speaker?, words?: [{start, end, text}]}]}."""
    import json
    data = json.loads(text)
    rows = data.get("segments", data) if isinstance(data, dict) else data
    segs, problems = [], []
    for k, r in enumerate(rows):
        try:
            seg = {"start": float(r["start"]), "end": float(r["end"]), "text": str(r["text"]).strip()}
        except (KeyError, TypeError, ValueError):
            problems.append(f"line {k}: needs start, end and text")
            continue
        if r.get("speaker"):
            seg["speaker"] = r["speaker"]
        if r.get("words"):
            seg["words"] = [{"start": float(w["start"]), "end": float(w["end"]), "text": w["text"]} for w in r["words"]]
        if seg["text"]:
            segs.append(seg)
    return segs, problems


def parse_file(path: Path) -> tuple[list[dict], list[str]]:
    path = Path(path)
    text = read_text(path)
    ext = path.suffix.lower()
    if ext == ".json3" or (ext == ".json" and '"events"' in text[:2000]):
        return parse_json3(text)
    if ext == ".json":
        return parse_recomp_json(text)
    if ext in (".ass", ".ssa") or "[Script Info]" in text[:500]:
        return parse_ass(text)
    return parse_cues(text)


ETHIOPIC = re.compile(r"[ሀ-፿]")
ARABIC = re.compile(r"[؀-ۿ]")
LANG_TOKENS = {"en": "en", "eng": "en", "english": "en", "am": "am", "amh": "am", "amharic": "am",
               "om": "om", "orm": "om", "oromo": "om", "fr": "fr", "fre": "fr", "fra": "fr", "french": "fr",
               "es": "es", "spa": "es", "spanish": "es", "sw": "sw", "swa": "sw", "ar": "ar", "ara": "ar",
               "so": "so", "som": "so", "ti": "ti", "tir": "ti", "de": "de", "ger": "de", "it": "it"}


def guess_language(path: Path, segments: list[dict], default: str = "en") -> str:
    for tok in re.split(r"[.\-_\s\[\]()]+", Path(path).stem.lower())[::-1]:
        if tok in LANG_TOKENS:
            return LANG_TOKENS[tok]
    sample = " ".join(s["text"] for s in segments[:200])
    if ETHIOPIC.search(sample):
        return "am"
    if ARABIC.search(sample):
        return "ar"
    return default
