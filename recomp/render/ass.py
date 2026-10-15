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


def caption_layout(prof: dict, lang: str | None = None, sample: str = "") -> dict:
    """Caption box for a profile and language: characters per row, rows, font scale, distance from the bottom.

    Profile keys caption_max_chars, caption_max_lines, caption_scale and caption_margin (a fraction of the
    height) override the defaults; caption_lang {lang: {max_chars, max_lines, scale, margin}} overrides per language.
    (Measured on a caption sheet: Ebrima's Ethiopic syllables are about as wide as Latin letters, so the default
    row length is the same for both scripts.)
    """
    w, h = prof.get("width", 1920), prof.get("height", 1080)
    vertical = h > w
    karaoke = prof.get("caption_style") == "karaoke"
    chars = (22 if vertical else 34) if karaoke else (30 if vertical else 44)
    over = (prof.get("caption_lang") or {}).get(lang or "", {}) or {}
    scale = float(over.get("scale") or prof.get("caption_scale") or 1.0)
    explicit = over.get("max_chars") or prof.get("caption_max_chars")
    chars = int(explicit) if explicit else max(8, round(chars / scale))
    lines = int(over.get("max_lines") or prof.get("caption_max_lines") or 2)
    margin = over.get("margin", prof.get("caption_margin"))
    return {"max_chars": chars, "max_lines": max(1, lines), "scale": scale,
            "margin": float(margin) if margin is not None else None}


def styles(w: int, h: int, sample_text: str = "", layout: dict | None = None) -> str:
    short = min(w, h)
    vertical = h > w
    base = round(short * 0.048)
    layout = layout or {}
    cap_scale = layout.get("scale") or 1.0
    mv = round(h * (layout["margin"] if layout.get("margin") is not None else (0.20 if vertical else 0.075)))
    mk = round(h * (layout["margin"] if layout.get("margin") is not None else (0.30 if vertical else 0.12)))
    font = font_for(sample_text)
    white, yellow, black = _colour("ffffff"), _colour("ffd84a"), _colour("000000")
    box = _colour("101010", 0x50)
    rows = [
        # Name, Font, Size, Primary, Secondary, Outline, Back, Bold, Italic, BorderStyle, Outline, Shadow, Align, ML, MR, MV
        ("Caption", font, round(base * cap_scale), white, white, black, _colour("000000", 0x80), 0, 0, 1, max(2, base // 14), 1, 2, 60, 60, mv),
        ("Karaoke", font, round(base * 1.25 * cap_scale), white, yellow, black, _colour("000000", 0x80), 1, 0, 1, max(3, base // 10), 2, 2, 50, 50, mk),
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


def header(w: int, h: int, sample: str = "", layout: dict | None = None) -> str:
    return "\n".join(["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {w}", f"PlayResY: {h}", "WrapStyle: 0",
                      "ScaledBorderAndShadow: yes", "YCbCr Matrix: TV.709", "", styles(w, h, sample, layout), "",
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


def _rows(text: str, max_chars: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > max_chars:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    return lines


def wrap(text: str, max_chars: int, max_lines: int = 2) -> str:
    lines = _rows(text, max_chars)
    if len(lines) > max_lines:  # rebalance into max_lines rows of similar length
        target = len(text) / max_lines
        lines, cur = [], ""
        for w in text.split():
            if cur and len(cur) + 1 + len(w) > target + 6 and len(lines) < max_lines - 1:
                lines.append(cur)
                cur = w
            else:
                cur = (cur + " " + w).strip()
        lines.append(cur)
    return "\\N".join(esc(x) for x in lines)


def split_timed(text: str, a: float, b: float, limit: int) -> list[tuple[float, float, str]]:
    """A long untimed line (a translation) as caption screens of at most ``limit`` characters, each shown for
    a share of the line's time in proportion to its length. Breaks prefer sentence and clause ends."""
    toks = text.split()
    if len(text) <= limit or len(toks) < 2:
        return [(a, b, text)]
    pieces, cur = [], []
    for t in toks:
        n = len(" ".join(cur + [t]))
        if cur and n > limit:
            pieces.append(cur)
            cur = []
        cur.append(t)
        if t.endswith((".", "?", "!", "።", "؟", "፧")) and len(" ".join(cur)) > limit * 0.45:
            pieces.append(cur)
            cur = []
        elif t.endswith((",", ";", ":", "፣", "፤", "،")) and len(" ".join(cur)) > limit * 0.7:
            pieces.append(cur)
            cur = []
    if cur:
        if pieces and len(" ".join(cur)) < limit * 0.25 and len(" ".join(pieces[-1] + cur)) <= limit * 1.15:
            pieces[-1] += cur  # no orphan word on a screen of its own
        else:
            pieces.append(cur)
    texts = [" ".join(p) for p in pieces]
    total = sum(len(t) for t in texts) or 1
    out, t0 = [], a
    for tx in texts:
        t1 = t0 + (b - a) * len(tx) / total
        out.append((round(t0, 3), round(t1, 3), tx))
        t0 = t1
    return out


def caption_events(captions: list[dict], style: str, w: int, h: int, layout: dict | None = None) -> list[str]:
    """captions: [{start, end, text, words: [(s, e, text)]}] on the output timeline."""
    vertical = h > w
    layout = layout or caption_layout({"width": w, "height": h, "caption_style": style})
    max_chars, max_lines = layout["max_chars"], layout["max_lines"]
    out = []
    if style == "karaoke":
        chunks: list[list[tuple[float, float, str]]] = []
        plain: list[tuple[float, float, str]] = []  # untimed text (translations): screens without a word highlight
        for cap in captions:
            words = cap.get("words") or []
            if words:
                chunks += chunk_words(words, max_chars)
            else:
                plain += split_timed(cap["text"], cap["start"], cap["end"], max_chars * max_lines)
        starts = sorted([c[0][0] for c in chunks] + [p[0] for p in plain])
        for a, b, text in plain:
            later = [s for s in starts if s > a + 1e-6]
            b = min(b, later[0] - 0.02) if later else b
            if b - a > 0.15:
                out.append(dialogue(a, b, "Karaoke", wrap(text, max_chars, max_lines)))
        chunks.sort(key=lambda c: c[0][0])
        for ci, chunk in enumerate(chunks):
            later = [s for s in starts if s > chunk[0][0] + 1e-6]
            limit = later[0] if later else chunk[-1][1] + 0.3
            c_end = min(chunk[-1][1] + 0.15, limit)
            for k, (ws, we, _) in enumerate(chunk):
                nxt = chunk[k + 1][0] if k + 1 < len(chunk) else c_end
                parts = []
                for kk, (_, _, tx) in enumerate(chunk):
                    t = esc(tx)
                    parts.append(r"{\c&H4AD8FF&}" + t + r"{\c&HFFFFFF&}" if kk == k else t)
                s0 = chunk[0][0] if k == 0 else ws
                # a word's highlight ends where the next word's begins (no minimum that could overlap it)
                e0 = min(nxt if k + 1 < len(chunk) else max(nxt, ws + 0.05), limit)
                if e0 > s0:
                    out.append(dialogue(s0, e0, "Karaoke", " ".join(parts)))
        return out
    del vertical
    box = max_chars * max_lines
    events: list[tuple[float, float, str]] = []
    for cap in captions:
        words = cap.get("words") or []
        if words and (cap["end"] - cap["start"] > 6 or len(cap["text"]) > box):
            for chunk in chunk_words(words, box, max_dur=5.5):
                events.append((chunk[0][0], chunk[-1][1] + 0.2, " ".join(x[2] for x in chunk)))
        else:
            events += split_timed(cap["text"], cap["start"], cap["end"], box)
    events.sort(key=lambda e: e[0])
    for k, (a, b, text) in enumerate(events):
        if k + 1 < len(events):
            b = min(b, events[k + 1][0] - 0.02)  # one caption at a time: never stack overlapping lines
        if b - a > 0.15:
            out.append(dialogue(a, b, "Caption", wrap(text, max_chars, max_lines)))
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


def document(w: int, h: int, captions: list[dict], caption_style: str, overlays: list[dict],
             layout: dict | None = None) -> str:
    sample = " ".join([c["text"] for c in captions[:20]] + [o["text"] for o in overlays[:10]])
    lines = [header(w, h, sample, layout)]
    if caption_style != "off":
        lines += caption_events(captions, caption_style, w, h, layout)
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
