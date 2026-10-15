"""Editing transcripts in bulk: line selection, text that keeps its word timings, cleaning presets,
line splitting and merging, resegmenting rolling captions.

Text is the truth and words are timing. When a line's text changes, unchanged words keep their times
and new words are spread over the time of the words they replace (`sync_words`). The render path runs the
same function, so a line whose words went stale (after an undo, say) still shows its current text.
"""

from __future__ import annotations

import difflib
import re

from ..core.timecode import parse
from ..envelope import RecompError
from .align import norm, proportional_words, tokens


# ---- word timings follow the text ----

def _spread(toks: list[str], a: float, b: float) -> list[tuple[float, float, str]]:
    if not toks:
        return []
    weights = [max(1, len(norm(t))) + 1 for t in toks]
    total = sum(weights)
    span = max(0.0, b - a)
    out, t = [], a
    for tok, w in zip(toks, weights):
        d = span * w / total
        out.append((round(t, 3), round(t + d, 3), tok))
        t += d
    return out


def sync_words(text: str, words: list[tuple[float, float, str]]) -> list[tuple[float, float, str]]:
    """Word timings for ``text``, reusing ``words`` (start, end, text) where the tokens still match."""
    toks = tokens(text)
    if not words:
        return []
    old = [norm(w[2]) for w in words]
    new = [norm(t) for t in toks]
    if old == new:
        return [(w[0], w[1], t) for w, t in zip(words, toks)]
    out: list[tuple[float, float, str]] = []
    sm = difflib.SequenceMatcher(a=old, b=new, autojunk=False)
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            out += [(words[i][0], words[i][1], toks[j]) for i, j in zip(range(i1, i2), range(j1, j2))]
        elif op == "replace":
            out += _spread(toks[j1:j2], words[i1][0], words[i2 - 1][1])
        elif op == "insert":
            a = out[-1][1] if out else words[0][0]
            b = words[i1][0] if i1 < len(words) else words[-1][1]
            if b - a < 0.08 * (j2 - j1):  # no gap: share the previous word's time
                if out:
                    p = out.pop()
                    mid = (p[0] + p[1]) / 2
                    out.append((p[0], round(mid, 3), p[2]))
                    a = mid
                b = max(b, a + 0.08 * (j2 - j1))
            out += _spread(toks[j1:j2], a, b)
        # "delete": the words are gone
    return out


def rewrite_words(tx, seg: dict, text: str) -> None:
    """Store word rows for a line whose text changed (bulk data, not op-logged)."""
    rows = tx.conn.execute('SELECT start, "end", text FROM word WHERE segment_id=? ORDER BY idx', (seg["id"],)).fetchall()
    old = [(r[0], r[1], r[2]) for r in rows]
    if not old:
        return
    new = sync_words(text, old) or [(w["start"], w["end"], w["text"]) for w in
                                    proportional_words({"start": seg["start"], "end": seg["end"], "text": text})]
    tx.conn.execute("DELETE FROM word WHERE segment_id=?", (seg["id"],))
    tx.conn.executemany('INSERT INTO word(segment_id, idx, start, "end", text, prob) VALUES(?,?,?,?,?,?)',
                        [(seg["id"], j, w[0], w[1], w[2], None) for j, w in enumerate(new)])


def set_text(tx, seg: dict, text: str) -> dict:
    after = tx.update("segment", seg["id"], {"text": text})
    rewrite_words(tx, seg, text)
    return after


# ---- selecting lines ----

def parse_idx(spec: str) -> set[int]:
    """'12', '12-40', '3,7,9-11' → indices."""
    out: set[int] = set()
    for part in str(spec).replace(" ", "").split(","):
        if not part:
            continue
        m = re.fullmatch(r"(\d+)(?:(?:-|\.\.)(\d+))?", part)
        if not m:
            raise RecompError("E_INVALID", f"bad line range {part!r}", hint="Use 12, 12-40 or 3,7,9-11")
        a = int(m.group(1))
        b = int(m.group(2)) if m.group(2) else a
        out.update(range(min(a, b), max(a, b) + 1))
    return out


def compile_pattern(pattern: str, regex: bool = False, case: bool = False, whole: bool = False) -> re.Pattern:
    body = pattern if regex else re.escape(pattern)
    if whole:
        body = rf"(?<!\w)(?:{body})(?!\w)"
    try:
        return re.compile(body, 0 if case else re.IGNORECASE)
    except re.error as e:
        raise RecompError("E_INVALID", f"bad pattern: {e}", hint="Escape special characters or drop --regex")


def select(db, tr: dict, lines: str | None = None, frm: str | None = None, to: str | None = None,
           match: re.Pattern | None = None, speaker: str | None = None) -> list[dict]:
    sql = 'SELECT id, idx, start, "end", text, speaker, person_id FROM segment WHERE transcript_id=?'
    params: list = [tr["id"]]
    if frm:
        sql += ' AND "end" > ?'
        params.append(parse(frm))
    if to:
        sql += " AND start < ?"
        params.append(parse(to))
    rows = [dict(r) for r in db.all(sql + " ORDER BY idx", params)]
    if lines:
        want = parse_idx(lines)
        rows = [r for r in rows if r["idx"] in want]
    if match is not None:
        rows = [r for r in rows if match.search(r["text"])]
    if speaker:
        rows = [r for r in rows if (r["speaker"] or "") == speaker or (r["person_id"] or "") == speaker]
    return rows


# ---- cleaning presets ----

FILLERS = r"(?:um+|uh+|erm+|hmm+|mm+|ah+)"
CLEAN_RULES: dict[str, tuple[str, callable]] = {}


def _rule(name: str, doc: str):
    def deco(fn):
        CLEAN_RULES[name] = (doc, fn)
        return fn
    return deco


@_rule("marks", "remove YouTube '>>' speaker-turn marks (assign speakers from them first: `speaker assign --by marks`)")
def _marks(t: str) -> str:
    return t.replace(">>", " ")


@_rule("tags", "remove [bracketed] and (parenthesised) sound tags such as [Music], [Applause], (laughs)")
def _tags(t: str) -> str:
    t = re.sub(r"\[[^\]]{1,40}\]", " ", t)
    return re.sub(r"\((?:laughs?|laughter|applause|music|sighs?|inaudible|crosstalk|coughs?)\)", " ", t, flags=re.I)


@_rule("notes", "remove ♪ music notes (and lines that are only music)")
def _notes(t: str) -> str:
    return t.replace("♪", " ").replace("♫", " ")


@_rule("doubles", "collapse accidental doubled words: 'the the' → 'the'")
def _doubles(t: str) -> str:
    return re.sub(r"\b(\w+)(\s+\1\b)+", r"\1", t, flags=re.I)


@_rule("fillers", "remove fillers: um, uh, erm, hmm")
def _fillers(t: str) -> str:
    t = re.sub(rf"(?<!\w){FILLERS}[,.]?(?!\w)", " ", t, flags=re.I)
    return re.sub(r"\s+([,.?!])", r"\1", t)


@_rule("spacing", "normalise spaces and punctuation spacing")
def _spacing(t: str) -> str:
    t = re.sub(r"\s+([,.?!;:])", r"\1", t)
    return " ".join(t.split())


@_rule("case", "sentence case for all-lowercase auto captions: capitalise the first word, 'i' → 'I'")
def _case(t: str) -> str:
    t = re.sub(r"(?<!\w)i(?=$|\s|')", "I", t)
    return t[:1].upper() + t[1:] if t else t


DEFAULT_CLEAN = ["marks", "tags", "notes", "doubles", "spacing"]


def clean_text(text: str, rules: list[str]) -> str:
    for r in rules:
        text = CLEAN_RULES[r][1](text)
    return " ".join(text.split())


# ---- resegmenting ----

def resegment(words: list[dict], max_chars: int = 84, max_dur: float = 7.0, gap: float = 0.8) -> list[dict]:
    """Readable lines from a stream of words: break at sentence ends, long pauses, or the size limits."""
    out: list[dict] = []
    cur: list[dict] = []

    def flush():
        if cur:
            out.append({"start": cur[0]["start"], "end": cur[-1]["end"], "text": " ".join(w["text"] for w in cur),
                        "words": list(cur), "speaker": cur[0].get("speaker")})
            cur.clear()

    for w in words:
        if cur:
            n = sum(len(x["text"]) + 1 for x in cur)
            if (w["start"] - cur[-1]["end"] > gap or n + len(w["text"]) > max_chars
                    or w["end"] - cur[0]["start"] > max_dur or (w.get("speaker") != cur[-1].get("speaker"))):
                flush()
        cur.append(w)
        n = sum(len(x["text"]) + 1 for x in cur)
        if w["text"].endswith((".", "?", "!")) and n > max_chars * 0.35:
            flush()
    flush()
    return out
