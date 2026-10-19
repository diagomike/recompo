"""Transcripts by route, without touching the video: segments ``{start, end, text, speaker?}``.

* ``published``: a podcast feed's ``<podcast:transcript>`` (VTT, SRT or Podcasting 2.0 JSON); podcast timing.
* ``lex``: a lexfridman.com transcript page (speaker names, the YouTube id, chapters); video timing.
* ``captions``: YouTube's captions for one video (one per-video request; refused when YouTube is blocking).
* ``asr`` is not here: it needs the audio and the worker (``transcript asr`` on a taken source).
"""

from __future__ import annotations

import html
import json
import re
import tempfile
from pathlib import Path

from ..envelope import RecompError
from ..transcript import parse as tparse
from . import net

_LEX_SEG = re.compile(r'<span class="ts-name">(.*?)</span>.*?\((\d+:\d\d:\d\d|\d+:\d\d)\).*?<span class="ts-text">(.*?)</span>', re.S)
_LEX_CH = re.compile(r'href="#chapter\d+_[^"]*">\s*(\d+:\d\d(?::\d\d)?)\s*&#8211;\s*(.*?)</a>', re.S)
_LEX_VID = re.compile(r"youtube\.com/(?:embed/|watch\?v=)([\w-]{11})")


def _secs(ts: str) -> float:
    parts = [float(x) for x in ts.replace(",", ".").split(":")]
    total = 0.0
    for p in parts:
        total = total * 60 + p
    return total


def parse_lex(page: str) -> dict:
    """A lexfridman.com transcript page → ``{segments, video_id, chapters}``."""
    segs = []
    for m in _LEX_SEG.finditer(page):
        text = html.unescape(re.sub(r"<[^>]+>", "", m.group(3))).strip()
        if text:
            segs.append({"start": _secs(m.group(2)), "speaker": html.unescape(m.group(1)).strip(), "text": text})
    segs.sort(key=lambda s: s["start"])
    for i, s in enumerate(segs):
        nxt = segs[i + 1]["start"] if i + 1 < len(segs) else s["start"] + max(5.0, len(s["text"]) / 15)
        s["end"] = max(s["start"] + 0.5, nxt)
    vid = _LEX_VID.search(page)
    chapters = [{"start": _secs(t), "title": html.unescape(re.sub(r"<[^>]+>", "", title)).strip()}
                for t, title in _LEX_CH.findall(page)]
    for i, c in enumerate(chapters):
        c["end"] = chapters[i + 1]["start"] if i + 1 < len(chapters) else (segs[-1]["end"] if segs else c["start"])
    return {"segments": segs, "video_id": vid.group(1) if vid else None, "chapters": chapters}


def parse_podcast_json(text: str) -> list[dict]:
    """Podcasting 2.0 JSON transcript: ``{"segments": [{"startTime", "endTime", "body", "speaker"}]}``."""
    data = json.loads(text)
    out = []
    for s in data.get("segments") or []:
        body = (s.get("body") or "").strip()
        if body:
            out.append({"start": float(s.get("startTime", 0)), "end": float(s.get("endTime", s.get("startTime", 0))),
                        "text": body, "speaker": s.get("speaker")})
    return out


def fetch(route: dict) -> dict:
    """The words for a route → ``{segments, video_id?, chapters?, timing}``."""
    kind = route.get("kind")
    if kind == "published":
        text = net.get_text(route["url"], timeout=60)
        if route.get("format") == "json":
            segs = parse_podcast_json(text)
        else:
            segs, _ = tparse.parse_cues(text)
        return {"segments": segs, "timing": route.get("timing", "podcast")}
    if kind == "lex":
        out = parse_lex(net.get_text(route["url"], timeout=60))
        if not out["segments"]:
            raise RecompError("E_EXTERNAL", f"no transcript lines on {route['url']}",
                              hint="The page layout may have changed; try the episode's captions instead.")
        return {**out, "timing": "video"}
    if kind == "captions":
        return {"segments": youtube_captions(route["video_id"], route.get("language")), "timing": "video",
                "video_id": route["video_id"]}
    if kind == "asr":
        raise RecompError("E_USAGE", "this episode has no published transcript; its words need local ASR",
                          hint="Take it into a project (`recomp inbox take <I>`), then `recomp transcript asr <S>`.")
    raise RecompError("E_NOT_FOUND", "no transcript route for this item")


def youtube_captions(video_id: str, language: str | None = None) -> list[dict]:
    """One video's captions (manual first, else automatic in its spoken language) as segments."""
    from ..ingest import links
    url = f"https://www.youtube.com/watch?v={video_id}"
    info = links.extract(url)
    meta = {"captions": {"manual": sorted((info.get("subtitles") or {}).keys()),
                         "auto": sorted(k for k in (info.get("automatic_captions") or {}).keys()
                                        if k.endswith("-orig") or len(k) <= 3)}}
    code, is_auto = links.pick_caption_lang(meta, language or info.get("language"))
    if code is None:
        raise RecompError("E_NOT_FOUND", f"{video_id} has no captions")
    with tempfile.TemporaryDirectory(prefix="recomp-cap-") as tmp:
        opts = {"skip_download": True, "writesubtitles": not is_auto, "writeautomaticsub": is_auto,
                "subtitleslangs": [code], "subtitlesformat": "json3/vtt/best", "outtmpl": str(Path(tmp) / "cap.%(ext)s")}
        try:
            with links._ydl(opts) as ydl:
                ydl.download([url])
        except Exception as exc:  # noqa: BLE001
            raise links.classify_error(exc) from exc
        files = sorted(Path(tmp).glob("cap*.json3")) + sorted(Path(tmp).glob("cap*.vtt"))
        if not files:
            raise RecompError("E_EXTERNAL", "no caption file was written")
        text = tparse.read_text(files[0])
        segs, _ = tparse.parse_json3(text) if files[0].suffix == ".json3" else tparse.parse_cues(text)
    return segs
