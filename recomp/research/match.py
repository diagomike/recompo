"""A podcast episode's YouTube upload, and the shift from the podcast's clock to the video's.

Podcast and YouTube titles of the same conversation often differ (The Diary of a CEO), and feed audio carries
intros and inserted ads. So: search YouTube for the episode, keep uploads from the creator's own channel with a
similar length, and confirm by **words**: a stretch of the podcast transcript must match the video's captions.
The match also gives the offset; offsets are measured again near each passage, because inserted ads move them.
"""

from __future__ import annotations

from ..envelope import RecompError
from ..transcript import align
from . import feeds, youtube

PROBE = (600.0, 1200.0)   # podcast minutes 10–20: past intros, before most mid-roll ads
MIN_MATCHED = 40          # words that must line up to call it the same conversation


def _words(segments: list[dict]) -> list[dict]:
    out = []
    for s in segments:
        out += s.get("words") or align.proportional_words(s)
    return out


def _window(segs: list[dict], a: float, b: float) -> list[dict]:
    return [s for s in segs if s["end"] >= a and s["start"] <= b]


def offset_near(pod_segs: list[dict], video_words: list[dict], at: float, guess: float, span: float = 90.0) -> dict:
    """Podcast time − video time around ``at`` (podcast clock), searching video words near ``at − guess``."""
    sub = _window(pod_segs, at - span, at + span)
    ref = [w for w in video_words if at - guess - 4 * span <= w["start"] <= at - guess + 4 * span]
    return align.estimate_offset(sub, ref)


def channel_ok(channel: str, names: list[str]) -> bool:
    ch = (channel or "").lower()
    if not ch or "clips" in ch:
        return False
    for n in names:
        key = (n or "").lower().split(" with ")[0].strip()
        if key and (ch.startswith(key) or key in ch):
            return True
    return False


def find_upload(title: str, pod_segs: list[dict], names: list[str], tries: int = 3) -> dict | None:
    """``{video_id, title, offset_s, matched, captions}`` for the podcast episode's YouTube upload, or None."""
    length = pod_segs[-1]["end"] if pod_segs else None
    query = f"{title} {names[-1] if names else ''}".strip()
    info = youtube.flat(f"ytsearch10:{query}", limit=10)
    cands = []
    for e in info.get("entries") or []:
        if not e or not e.get("id") or not channel_ok(e.get("channel") or e.get("uploader") or "", names):
            continue
        d = e.get("duration")
        if d and length and not (0.75 * length <= d <= 1.3 * length):
            continue
        cands.append(e)
    cands.sort(key=lambda e: -feeds.title_match(title, e.get("title") or ""))
    from .transcripts import youtube_captions
    probe = _window(pod_segs, *PROBE) or pod_segs[:200]
    for e in cands[:tries]:
        try:
            cap = youtube_captions(e["id"])
        except RecompError as exc:
            if exc.code == "E_EXTERNAL":
                raise
            continue
        words = _words(cap["segments"])
        lo = PROBE[0] - 900  # the video may start up to 15 min earlier or later than the podcast
        est = align.estimate_offset(probe, [w for w in words if lo <= w["start"] <= PROBE[1] + 900])
        if est.get("offset_s") is not None and est.get("matched", 0) >= MIN_MATCHED:
            return {"video_id": e["id"], "title": e.get("title"), "offset_s": est["offset_s"], "matched": est["matched"],
                    "captions": cap}
    return None
