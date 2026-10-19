"""Feeds: podcast RSS (episodes, audio, published transcripts) and YouTube's Atom feeds.

Each episode gets a **transcript route**, cheapest first:
``published`` (``<podcast:transcript>``: VTT, SRT or JSON), ``lex`` (a lexfridman.com transcript page linked from
the episode), then ``asr`` (the feed's audio, transcribed locally; slow: ~0.8× real time on this CPU).
"""

from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

NS = {"itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd",
      "podcast": "https://podcastindex.org/namespace/1.0",
      "content": "http://purl.org/rss/1.0/modules/content/",
      "atom": "http://www.w3.org/2005/Atom",
      "yt": "http://www.youtube.com/xml/schemas/2015",
      "media": "http://search.yahoo.com/mrss/"}

LEX_TRANSCRIPT = re.compile(r"https://lexfridman\.com/[\w-]+-transcript")
YT_ID = re.compile(r"(?:youtube\.com/watch\?v=|youtu\.be/)([A-Za-z0-9_-]{11})")
_TAG = re.compile(r"<[^>]+>")
# Preference among published transcript formats: timed text first.
_FORMATS = {"text/vtt": 0, "application/x-subrip": 1, "application/srt": 1, "text/srt": 1,
            "application/json": 2, "text/html": 3, "text/plain": 4}


def _text(el, path: str) -> str:
    node = el.find(path, NS)
    return (node.text or "").strip() if node is not None and node.text else ""


def _date(value: str) -> str | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value).strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        m = re.match(r"(\d{4}-\d{2}-\d{2})", value)
        return m.group(1) if m else None


def duration_s(value: str) -> float | None:
    """``itunes:duration``: seconds, MM:SS or HH:MM:SS."""
    value = (value or "").strip()
    if not value:
        return None
    try:
        parts = [float(p) for p in value.split(":")]
    except ValueError:
        return None
    total = 0.0
    for p in parts:
        total = total * 60 + p
    return total


def plain(html_text: str, limit: int = 2000) -> str:
    text = _TAG.sub(" ", html.unescape(html_text or ""))
    return re.sub(r"\s+", " ", text).strip()[:limit]


def parse_podcast(xml_text: str) -> dict:
    """A podcast feed → ``{title, author, link, image, items: [...]}``, newest first as the feed lists them."""
    try:
        root = ET.fromstring(xml_text.encode("utf-8") if isinstance(xml_text, str) else xml_text)
    except ET.ParseError as exc:
        from ..envelope import RecompError
        raise RecompError("E_EXTERNAL", f"the feed is not valid RSS: {exc}") from exc
    ch = root.find("channel")
    if ch is None:
        from ..envelope import RecompError
        raise RecompError("E_EXTERNAL", "the feed has no <channel>")
    img = ch.find("itunes:image", NS)
    out = {"title": _text(ch, "title"), "author": _text(ch, "itunes:author"), "link": _text(ch, "link"),
           "image": img.get("href") if img is not None else None, "items": []}
    for it in ch.findall("item"):
        raw_desc = _text(it, "content:encoded") or _text(it, "description")
        enc = it.find("enclosure")
        transcripts = []
        for t in it.findall("podcast:transcript", NS):
            transcripts.append({"url": t.get("url"), "type": (t.get("type") or "").lower(),
                                "language": t.get("language"), "rel": t.get("rel")})
        transcripts.sort(key=lambda t: _FORMATS.get(t["type"], 9))
        lex = LEX_TRANSCRIPT.search(raw_desc or "")
        yt = YT_ID.search(raw_desc or "")
        guid = _text(it, "guid") or (enc.get("url") if enc is not None else "") or _text(it, "title")
        item = {"guid": guid, "title": html.unescape(_text(it, "title")), "link": _text(it, "link"),
                "published": _date(_text(it, "pubDate")), "duration": duration_s(_text(it, "itunes:duration")),
                "audio_url": enc.get("url") if enc is not None else None,
                "episode": _text(it, "itunes:episode") or None,
                "transcripts": [t for t in transcripts if t["url"]],
                "lex_transcript": lex.group(0) if lex else None,
                "video_id": yt.group(1) if yt else None,
                "description": plain(raw_desc)}
        item["route"] = route_for(item)
        out["items"].append(item)
    return out


def route_for(item: dict) -> dict:
    """The cheapest way to this episode's words, and whose clock its times follow."""
    for t in item.get("transcripts") or []:
        kind = {"text/vtt": "vtt", "application/x-subrip": "srt", "application/srt": "srt", "text/srt": "srt",
                "application/json": "json"}.get(t["type"])
        if kind:
            return {"kind": "published", "format": kind, "url": t["url"], "timing": "podcast"}
    if item.get("lex_transcript"):
        # lexfridman.com transcripts carry speaker names and the YouTube video's timestamps.
        return {"kind": "lex", "url": item["lex_transcript"], "timing": "video"}
    if item.get("audio_url"):
        return {"kind": "asr", "url": item["audio_url"], "timing": "podcast"}
    return {"kind": "none"}


def parse_youtube_atom(xml_text: str) -> dict:
    """YouTube's ``feeds/videos.xml`` (latest 15) → ``{title, channel_id, items: [{video_id, title, published, url}]}``."""
    root = ET.fromstring(xml_text.encode("utf-8") if isinstance(xml_text, str) else xml_text)
    out = {"title": _text(root, "atom:title"), "channel_id": _text(root, "yt:channelId"), "items": []}
    for e in root.findall("atom:entry", NS):
        vid = _text(e, "yt:videoId")
        link = e.find("atom:link", NS)
        url = link.get("href") if link is not None else f"https://www.youtube.com/watch?v={vid}"
        out["items"].append({"video_id": vid, "title": _text(e, "atom:title"), "url": url,
                             "published": (_text(e, "atom:published") or "")[:10] or None,
                             "kind": "short" if "/shorts/" in url else "video"})
    return out


def norm_title(title: str) -> set[str]:
    """Title words for matching a podcast episode to its YouTube upload (episode numbers and filler dropped)."""
    t = html.unescape(title or "").lower()
    t = re.sub(r"#\d+|\bep(isode)?\.?\s*\d+", " ", t)
    words = set(re.findall(r"[a-z0-9']+", t))
    return {w for w in words if len(w) > 2 and w not in {"the", "and", "with", "for", "you", "are", "this", "that",
                                                         "what", "why", "how", "podcast", "full", "episode"}}


def title_match(a: str, b: str) -> float:
    """Overlap of two titles' words (0–1, Jaccard)."""
    x, y = norm_title(a), norm_title(b)
    if not x or not y:
        return 0.0
    return len(x & y) / len(x | y)
