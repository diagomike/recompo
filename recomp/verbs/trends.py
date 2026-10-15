"""Trends: find what is being watched, then pick entries into the project (`source add --pick`)."""

from __future__ import annotations

import time

import httpx
from pydantic import BaseModel, Field

from ..core import config
from ..core.timecode import clock
from ..envelope import RecompError, Result
from ..registry import Ctx, verb
from .ui import set_state


def _days(since: str | None) -> float | None:
    if not since:
        return None
    s = since.strip().lower()
    try:
        return float(s[:-1]) if s.endswith("d") else float(s) / 86400
    except ValueError:
        raise RecompError("E_INVALID", "since looks like 7d or 30d") from None


def _age_days(date: str | None) -> float | None:
    if not date or len(date) != 8:
        return None
    t = time.mktime(time.strptime(date, "%Y%m%d"))
    return max(0.5, (time.time() - t) / 86400)


def _rank(entries: list[dict], since: float | None) -> list[dict]:
    out = []
    for e in entries:
        age = _age_days(e.get("date"))
        if since and age and age > since:
            continue
        e["views_per_day"] = round(e["views"] / age) if e.get("views") and age else None
        out.append(e)
    out.sort(key=lambda e: (e["views_per_day"] or 0, e.get("views") or 0), reverse=True)
    for k, e in enumerate(out, start=1):
        e["n"] = k
    return out


def _pick_list(ctx: Ctx, title: str, entries: list[dict]) -> Result:
    set_state(ctx.db, "pick_list", {"url": title, "title": title, "entries": entries})
    return Result(data={"list": title, "entries": entries},
                  next=["recomp source add --pick 1,2,3   # add the ones worth working on"])


def _flat(url: str, limit: int) -> list[dict]:
    from ..ingest import links
    info = links.extract(url, flat=True, limit=limit)
    out = []
    for e in info.get("entries") or []:
        if not e:
            continue
        vid = e.get("id")
        out.append({"id": vid, "title": e.get("title"), "channel": e.get("channel") or e.get("uploader"),
                    "duration": clock(e.get("duration"), 0) if e.get("duration") else None, "duration_s": e.get("duration"),
                    "views": e.get("view_count"), "date": e.get("upload_date"),
                    "url": e.get("url") if (e.get("url") or "").startswith("http") else f"https://www.youtube.com/watch?v={vid}"})
    return out


class SearchIn(BaseModel):
    topic: str = Field(..., json_schema_extra={"pos": 0})
    since: str | None = Field("30d", description="Only videos newer than this (7d, 30d)")
    limit: int = 25


@verb("trends.search", SearchIn, effect="network", examples=['recomp trends search "free will" --since 7d'])
def trends_search(ctx: Ctx, inp: SearchIn):
    """Recent videos on a topic, ranked by views per day (no key needed). Pick them with `source add --pick`."""
    from urllib.parse import quote_plus
    # Search results sorted by upload date (sp=CAI%3D), read through yt-dlp's search-URL extractor.
    entries = _flat(f"https://www.youtube.com/results?search_query={quote_plus(inp.topic)}&sp=CAI%253D", inp.limit * 2)
    return _pick_list(ctx, f"search: {inp.topic}", _rank(entries, _days(inp.since))[:inp.limit])


class ChannelIn(BaseModel):
    url: str = Field(..., description="Channel or playlist link", json_schema_extra={"pos": 0})
    since: str | None = None
    limit: int = 30


@verb("trends.channel", ChannelIn, effect="network", examples=["recomp trends channel https://www.youtube.com/@CosmicSkeptic/videos"])
def trends_channel(ctx: Ctx, inp: ChannelIn):
    """A channel's recent videos ranked by views (per day when dates are known)."""
    entries = _flat(inp.url, inp.limit)
    return _pick_list(ctx, f"channel: {inp.url}", _rank(entries, _days(inp.since))[:inp.limit])


class YoutubeIn(BaseModel):
    region: str = Field("US", description="Region code, e.g. US, ET, KE, FR")
    category: str | None = Field(None, description="YouTube category id (22 People & Blogs, 27 Education, 25 News…)")
    limit: int = 25


@verb("trends.youtube", YoutubeIn, effect="network", examples=["recomp trends youtube --region ET --category 27"])
def trends_youtube(ctx: Ctx, inp: YoutubeIn):
    """YouTube's 'most popular' chart for a region (needs your YOUTUBE_API_KEY in the studio home's .env)."""
    key = config.env_value("YOUTUBE_API_KEY")
    if not key:
        raise RecompError("E_INVALID", "no YouTube Data API key",
                          hint=f"Put YOUTUBE_API_KEY=… in {config.home() / '.env'} (keys are yours to create and add).")
    params = {"part": "snippet,statistics,contentDetails", "chart": "mostPopular", "regionCode": inp.region,
              "maxResults": min(50, inp.limit), "key": key}
    if inp.category:
        params["videoCategoryId"] = inp.category
    try:
        r = httpx.get("https://www.googleapis.com/youtube/v3/videos", params=params, timeout=20)
    except httpx.HTTPError as exc:
        raise RecompError("E_NETWORK", f"YouTube API unreachable: {exc}") from exc
    if r.status_code != 200:
        raise RecompError("E_EXTERNAL", f"YouTube API: {r.json().get('error', {}).get('message', r.status_code)}")
    entries = []
    for it in r.json().get("items", []):
        sn, st = it["snippet"], it.get("statistics", {})
        entries.append({"id": it["id"], "title": sn["title"], "channel": sn.get("channelTitle"),
                        "views": int(st.get("viewCount", 0)), "date": sn.get("publishedAt", "")[:10].replace("-", ""),
                        "duration": it.get("contentDetails", {}).get("duration"), "url": f"https://www.youtube.com/watch?v={it['id']}"})
    return _pick_list(ctx, f"youtube most popular {inp.region} {inp.category or ''}".strip(), _rank(entries, None))
