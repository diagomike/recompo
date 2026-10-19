"""YouTube for the research wing: find channels and people, list a channel's uploads, search within a channel.

All listings are yt-dlp *flat* extractions (one page request, no per-video requests), through :func:`flat`.
The keyless RSS feed is tried first for new uploads because it carries dates; it often answers 404/500, and
then the listing is used.
"""

from __future__ import annotations

import re
from urllib.parse import quote_plus

from ..envelope import RecompError
from . import feeds, net

CHANNEL_FILTER = "EgIQAg%253D%253D"  # search results: channels only


def flat(url: str, limit: int = 30) -> dict:
    from ..ingest import links
    return links.extract(url, flat=True, limit=limit)


def base_url(target: str) -> str:
    """A channel's base URL from a handle, a channel URL, or a link to one of its tabs."""
    t = target.strip()
    if t.startswith("@"):
        return f"https://www.youtube.com/{t}"
    if re.fullmatch(r"UC[\w-]{22}", t):
        return f"https://www.youtube.com/channel/{t}"
    m = re.match(r"(https?://(?:www\.|m\.)?youtube\.com/(?:@[^/?#]+|channel/[\w-]+|c/[^/?#]+|user/[^/?#]+))", t)
    if not m:
        raise RecompError("E_INVALID", f"{target!r} is not a YouTube channel",
                          hint="Give @handle, a channel link, or find one: `recomp find creators \"<name>\"`.")
    return m.group(1).replace("://m.", "://www.")


def resolve_channel(target: str) -> dict:
    """``{channel, channel_id, handle, url}`` for a channel (one flat request)."""
    base = base_url(target)
    info = flat(base + "/videos", limit=1)
    handle = info.get("uploader_id") if str(info.get("uploader_id") or "").startswith("@") else None
    return {"channel": info.get("channel") or info.get("uploader") or info.get("title") or base,
            "channel_id": info.get("channel_id"), "handle": handle,
            "url": f"https://www.youtube.com/{handle}" if handle else base}


def _video(e: dict, kind: str = "video") -> dict:
    vid = e.get("id")
    url = e.get("url") if str(e.get("url") or "").startswith("http") else f"https://www.youtube.com/watch?v={vid}"
    if "/shorts/" in url:
        kind = "short"
    return {"video_id": vid, "title": e.get("title") or "", "url": url, "duration": e.get("duration"),
            "views": e.get("view_count"), "published": _date(e), "channel": e.get("channel") or e.get("uploader"),
            "channel_id": e.get("channel_id"), "kind": kind, "description": e.get("description") or ""}


def _date(e: dict) -> str | None:
    d = e.get("upload_date")
    if d and len(d) == 8:
        return f"{d[:4]}-{d[4:6]}-{d[6:]}"
    return None


def uploads(feed: dict, only: str = "videos", limit: int = 30) -> list[dict]:
    """A followed channel's newest uploads. ``only``: videos, shorts or all."""
    out: list[dict] = []
    cid = feed.get("channel_id")
    if cid and only in ("videos", "all"):
        try:
            atom = feeds.parse_youtube_atom(net.get_text(
                f"https://www.youtube.com/feeds/videos.xml?playlist_id=UULF{cid[2:]}", timeout=15))
            out = [i for i in atom["items"] if i["video_id"]]
        except Exception:  # noqa: BLE001 — the feed is unreliable; the listing below is the fallback
            out = []
    tabs = {"videos": ["videos"], "shorts": ["shorts"], "all": ["videos", "shorts"]}[only]
    have = {i["video_id"] for i in out}
    for tab in tabs:
        if tab == "videos" and out:
            continue
        info = flat(f"{feed['url']}/{tab}", limit=limit)
        for e in info.get("entries") or []:
            if e and e.get("id") and e["id"] not in have:
                out.append(_video(e, "short" if tab == "shorts" else "video"))
                have.add(e["id"])
    return out[:limit * len(tabs)]


def search_channels(query: str, limit: int = 10) -> list[dict]:
    info = flat(f"https://www.youtube.com/results?search_query={quote_plus(query)}&sp={CHANNEL_FILTER}", limit=limit)
    out = []
    for e in (info.get("entries") or [])[:limit]:
        if not e:
            continue
        handle = e.get("uploader_id") if str(e.get("uploader_id") or "").startswith("@") else None
        out.append({"kind": "channel", "name": e.get("channel") or e.get("title"), "handle": handle,
                    "url": f"https://www.youtube.com/{handle}" if handle else (e.get("channel_url") or e.get("url")),
                    "channel_id": e.get("channel_id") or e.get("id"), "subscribers": e.get("channel_follower_count"),
                    "description": (e.get("description") or "")[:240], "route": "captions"})
    return out


def search_person(name: str, limit: int = 40) -> dict:
    """Videos about or with a person, grouped by channel: their own channel and where they appear as a guest."""
    info = flat(f"ytsearch{limit}:{name}", limit=limit)
    first = name.split()[0].lower() if name.split() else name.lower()
    groups: dict[str, dict] = {}
    for e in info.get("entries") or []:
        if not e or not e.get("id"):
            continue
        v = _video(e)
        if first not in (v["title"] + " " + v["description"]).lower():
            continue
        key = v["channel_id"] or v["channel"] or "?"
        g = groups.setdefault(key, {"channel": v["channel"], "channel_id": v["channel_id"],
                                    "url": e.get("uploader_url") or e.get("channel_url"), "videos": []})
        g["videos"].append({"video_id": v["video_id"], "title": v["title"], "duration": v["duration"],
                            "views": v["views"], "url": v["url"]})
    ranked = sorted(groups.values(), key=lambda g: -len(g["videos"]))
    return {"person": name, "channels": ranked}


def search_in_channel(feed: dict, query: str, limit: int = 30) -> list[dict]:
    """A followed channel's own search: past videos about a topic (titles, length, views)."""
    info = flat(f"{feed['url']}/search?query={quote_plus(query)}", limit=limit)
    return [_video(e) for e in (info.get("entries") or []) if e and e.get("id")][:limit]
