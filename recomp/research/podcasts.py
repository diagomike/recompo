"""Podcasts: find a show (iTunes Search API, keyless) and read its feed."""

from __future__ import annotations

from urllib.parse import urlencode

from . import feeds, net

PEEK_BYTES = 400_000  # enough of a feed to see its first episodes and whether they carry transcripts


def search(term: str, limit: int = 8) -> list[dict]:
    data = net.get_json("https://itunes.apple.com/search?" + urlencode({"media": "podcast", "term": term, "limit": limit}))
    out = []
    for r in data.get("results") or []:
        if not r.get("feedUrl"):
            continue
        out.append({"kind": "podcast", "name": r.get("collectionName"), "author": r.get("artistName"),
                    "feed": r.get("feedUrl"), "episodes": r.get("trackCount"), "latest": (r.get("releaseDate") or "")[:10],
                    "genre": r.get("primaryGenreName"), "url": r.get("collectionViewUrl")})
    return out


def read(feed_url: str) -> dict:
    return feeds.parse_podcast(net.get_text(feed_url, timeout=60))


def read_head(feed_url: str, max_bytes: int = 600_000) -> dict:
    """The show and its newest episodes from the start of the feed (large feeds run to megabytes)."""
    text = net.get_text(feed_url, timeout=30, max_bytes=max_bytes)
    end = text.rfind("</item>")
    if end != -1 and len(text.encode("utf-8")) >= max_bytes:
        text = text[: end + len("</item>")] + "\n</channel>\n</rss>\n"
    return feeds.parse_podcast(text)


def peek_route(feed_url: str) -> str:
    """What the newest episodes offer: published, lex, asr or none (reads only the start of the feed)."""
    text = net.get_text(feed_url, timeout=20, max_bytes=PEEK_BYTES)
    if "podcast:transcript" in text:
        return "published"
    if feeds.LEX_TRANSCRIPT.search(text):
        return "lex"
    if "<enclosure" in text:
        return "asr"
    return "none"
