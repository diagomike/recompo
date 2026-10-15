"""ASS subtitle documents for captions (clean, karaoke, quote) and overlays (title, lower third,
quote, section, text). One file per render, burned in by libass.

Sizes scale with the frame's short side, so 1080×1920 and 1920×1080 get the same visual weight.
Fonts follow the script: Ebrima for Ethiopic (Amharic, Tigrinya), Arial otherwise.
"""

from __future__ import annotations

import re

from ..core.timecode import ass_clock

ETHIOPIC = re.compile(r"[ሀ-፿]")
ARABIC = re.compile(r"[؀-ۿ]")


def font_for(text: str, default: str = "Arial") -> str:
    if ETHIOPIC.search(text or ""):
        return "Ebrima"
    if ARABIC.search(text or ""):
        return "Segoe UI"
    return default


def esc(text: str) -> str:
    return (text or "").replace("\\", "\\\\").replace("{", "(").replace("}", ")").replace("\r", "").replace("\n", "\\N")


def _colour(rgb: str, alpha: int = 0) -> str:
    rgb = rgb.lstrip("#")
    r, g, b = rgb[0:2], rgb[2:4], rgb[4:6]
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def styles(w: int, h: int, sample_text: str = "") -> str:
    short = min(w, h)
    vertical = h > w
    base = round(short * 0.048)
    mv = round(h * (0.20 if vertical else 0.075))
    font = font_for(sample_text)
    white, yellow, black = _colour("ffffff"), _colour("ffd84a"), _colour("000000")
    box = _colour("101010", 0x50)
    rows = [
        # Name, Font, Size, Primary, Secondary, Outline, Back, Bold, Italic, BorderStyle, Outline, Shadow, Align, ML, MR, MV
        ("Caption", font, base, white, white, black, _colour("000000", 0x80), 0, 0, 1, max(2, base // 14), 1, 2, 60, 60, mv),
        ("Karaoke", font, round(base * 1.25), white, yellow, black, _colour("000000", 0x80), 1, 0, 1, max(3, base // 10), 2, 2, 50, 50, round(h * (0.30 if vertical else 0.12))),
        ("Title", font, round(base * 1.7), white, white, black, black, 1, 0, 1, max(3, base // 9), 2, 5, 80, 80, 0),
        ("Section", font, round(base * 1.05), white, white, black, black, 1, 0, 1, max(2, base // 12), 1, 5, 80, 80, 0),
        ("Quote", "Georgia" if font == "Arial" else font, round(base * 1.25), white, white, black, black, 0, 1, 1, max(2, base // 12), 2, 5, 100, 100, 0),
        # Name tags sit top-left in every format: clear of captions and of channel watermarks (bottom-right).
        ("Lower", font, round(base * 0.82), white, white, box, box, 1, 0, 3, round(base * 0.35), 0, 7,
         round(w * 0.05), 60, round(h * 0.09) if vertical else round(h * 0.06)),
        ("Text", font, base, white, white, black, black, 0, 0, 1, max(2, base // 14), 1, 8, 60, 60, round(h * 0.08)),
        ("End", font, round(base * 1.1), white, white, black, black, 0, 0, 1, 0, 0, 7, round(w * 0.08), 60, round(h * 0.12)),
        ("EndTitle", font, round(base * 1.5), white, white, black, black, 1, 0, 1, 0, 0, 7, round(w * 0.08), 60, round(h * 0.12)),
    ]
    out = ["[V4+ Styles]",
           "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
           "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding"]
    for (name, fnt, size, p, s, o, bk, bold, ital, bs, ol, sh, al, ml, mr, mvv) in rows:
        out.append(f"Style: {name},{fnt},{size},{p},{s},{o},{bk},{-1 if bold else 0},{-1 if ital else 0},0,0,100,100,0,0,"
                   f"{bs},{ol},{sh},{al},{ml},{mr},{mvv},1")
    return "\n".join(out)


def header(w: int, h: int, sample: str = "") -> str:
    return "\n".join(["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {w}", f"PlayResY: {h}", "WrapStyle: 0",
                      "ScaledBorderAndShadow: yes", "YCbCr Matrix: TV.709", "", styles(w, h, sample), "",
                      "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"])


def dialogue(start: float, end: float, style: str, text: str, layer: int = 0, prefix: str = "") -> str:
    return f"Dialogue: {layer},{ass_clock(start)},{ass_clock(end)},{style},,0,0,0,,{prefix}{text}"


def chunk_words(words: list[tuple[float, float, str]], max_chars: int, max_dur: float = 3.2) -> list[list[tuple[float, float, str]]]:
    out, cur, n = [], [], 0
    for w in words:
        if cur and (n + len(w[2]) + 1 > max_chars or w[1] - cur[0][0] > max_dur or w[0] - cur[-1][1] > 0.7):
            out.append(cur)
            cur, n = [], 0
        cur.append(w)
        n += len(w[2]) + 1
        if w[2].endswith((".", "?", "!")) and n > max_chars * 0.5:
            out.append(cur)
            cur, n = [], 0
    if cur:
        out.append(cur)
    return out


def wrap(text: str, max_chars: int) -> str:
    words, lines, cur = text.split(), [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > max_chars:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    if len(lines) > 2:  # rebalance into two lines
        half = len(text) // 2
        cut = text.rfind(" ", 0, half + 8)
        lines = [text[:cut].strip(), text[cut:].strip()] if cut > 0 else lines[:2]
    return "\\N".join(esc(x) for x in lines)


def caption_events(captions: list[dict], style: str, w: int, h: int) -> list[str]:
    """captions: [{start, end, text, words: [(s, e, text)]}] on the output timeline."""
    vertical = h > w
    out = []
    if style == "karaoke":
        max_chars = 22 if vertical else 34
        chunks: list[list[tuple[float, float, str]]] = []
        for cap in captions:
            words = cap.get("words") or []
            if not words:
                words = [(cap["start"], cap["end"], cap["text"])]
            chunks += chunk_words(words, max_chars)
        chunks.sort(key=lambda c: c[0][0])
        for ci, chunk in enumerate(chunks):
            limit = chunks[ci + 1][0][0] if ci + 1 < len(chunks) else chunk[-1][1] + 0.3
            c_end = min(chunk[-1][1] + 0.15, limit)
            for k, (ws, we, _) in enumerate(chunk):
                nxt = chunk[k + 1][0] if k + 1 < len(chunk) else c_end
                parts = []
                for kk, (_, _, tx) in enumerate(chunk):
                    t = esc(tx)
                    parts.append(r"{\c&H4AD8FF&}" + t + r"{\c&HFFFFFF&}" if kk == k else t)
                s0 = chunk[0][0] if k == 0 else ws
                e0 = min(max(nxt, ws + 0.05), limit)
                if e0 > s0:
                    out.append(dialogue(s0, e0, "Karaoke", " ".join(parts)))
        return out
    max_chars = 30 if vertical else 44
    events: list[tuple[float, float, str]] = []
    for cap in captions:
        words = cap.get("words") or []
        if words and cap["end"] - cap["start"] > 6:
            for chunk in chunk_words(words, max_chars * 2, max_dur=5.5):
                events.append((chunk[0][0], chunk[-1][1] + 0.2, " ".join(x[2] for x in chunk)))
        else:
            events.append((cap["start"], cap["end"], cap["text"]))
    events.sort(key=lambda e: e[0])
    for k, (a, b, text) in enumerate(events):
        if k + 1 < len(events):
            b = min(b, events[k + 1][0] - 0.02)  # one caption at a time: never stack overlapping lines
        if b - a > 0.15:
            out.append(dialogue(a, b, "Caption", wrap(text, max_chars)))
    return out


def overlay_events(overlays: list[dict], w: int, h: int) -> list[str]:
    """overlays: [{kind, text, start, end, style}] on the output timeline."""
    out = []
    vertical = h > w
    for o in overlays:
        kind, text = o["kind"], o["text"] or ""
        a, b = o["start"], o["end"]
        fade = "{\\fad(250,250)}"
        if kind == "title":
            out.append(dialogue(a, b, "Title", fade + wrap(text, 18 if vertical else 30), layer=5))
        elif kind == "section":
            out.append(dialogue(a, b, "Section", fade + wrap(text.upper(), 24 if vertical else 40), layer=5))
        elif kind == "quote":
            out.append(dialogue(a, b, "Quote", fade + "“" + wrap(text, 24 if vertical else 40) + "”", layer=5))
        elif kind == "lower_third":
            lines = text.split("\n")
            first = esc(lines[0])
            rest = esc(" · ".join(lines[1:])) if len(lines) > 1 else ""
            body = first + ("\\N{\\b0\\fscx82\\fscy82}" + rest if rest else "")
            out.append(dialogue(a, b, "Lower", "{\\fad(200,300)}" + body, layer=4))
        elif kind in ("text", "endcard"):
            pos = (o.get("style") or {}).get("position")
            al = {"top": 8, "middle": 5, "bottom": 2}.get(pos or "top", 8)
            out.append(dialogue(a, b, "Text", f"{{\\an{al}}}" + fade + wrap(text, 26 if vertical else 48), layer=4))
    return out


def document(w: int, h: int, captions: list[dict], caption_style: str, overlays: list[dict]) -> str:
    sample = " ".join([c["text"] for c in captions[:20]] + [o["text"] for o in overlays[:10]])
    lines = [header(w, h, sample)]
    if caption_style != "off":
        lines += caption_events(captions, caption_style, w, h)
    lines += overlay_events(overlays, w, h)
    return "\n".join(lines) + "\n"


def endcard_document(w: int, h: int, title: str, lines: list[str], dur: float, link_text: str = "") -> str:
    sample = title + " ".join(lines)
    out = [header(w, h, sample)]
    vertical = h > w
    y0 = round(h * (0.18 if vertical else 0.14))
    out.append(dialogue(0, dur, "EndTitle", f"{{\\pos({round(w * 0.08)},{y0})\\fad(300,0)}}" + wrap(title, 22 if vertical else 40)))
    step = round(min(w, h) * 0.055)
    y = y0 + round(step * (3.2 if vertical else 2.4))
    for line in lines[:9]:
        out.append(dialogue(0, dur, "End", f"{{\\pos({round(w * 0.08)},{y})\\fad(400,0)\\fscx72\\fscy72}}" + esc(line)))
        y += round(step * 0.85)
    if link_text:
        out.append(dialogue(0, dur, "End", f"{{\\pos({round(w * 0.08)},{y + step})\\fad(400,0)\\fscx80\\fscy80\\c&H9BE0C8&}}" + esc(link_text)))
    return "\n".join(out) + "\n"
