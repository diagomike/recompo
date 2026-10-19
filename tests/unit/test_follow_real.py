"""P17 network sources, live (one test each): `pytest -m real tests/unit/test_follow_real.py`.

They check that each source still answers in the shape the parsers expect. A YouTube refusal (429, bot check)
skips rather than fails: that is the site's state, not a code fault.
"""

from __future__ import annotations

import pytest

from recomp.envelope import RecompError
from recomp.research import feeds, net, podcasts, transcripts, youtube

pytestmark = pytest.mark.real


def test_itunes_finds_a_show_and_its_feed():
    hits = podcasts.search("Within Reason Alex O'Connor", 3)
    assert any(h["feed"] and "Within Reason" in (h["name"] or "") for h in hits)


def test_podcast_feed_with_published_transcripts():
    show = podcasts.read("https://lexfridman.com/feed/podcast/")
    assert show["items"] and show["items"][0]["route"]["kind"] == "lex"


def test_lex_transcript_page():
    show = podcasts.read("https://lexfridman.com/feed/podcast/")
    got = transcripts.fetch(show["items"][0]["route"])
    assert len(got["segments"]) > 100 and got["video_id"] and got["chapters"]


def test_youtube_channel_listing_and_search():
    try:
        ch = youtube.resolve_channel("@CosmicSkeptic")
        ups = youtube.uploads(ch, "videos", limit=5)
        found = youtube.search_channels("philosophy podcast", 3)
    except RecompError as exc:
        if exc.code == "E_EXTERNAL":
            pytest.skip(f"YouTube refused: {exc.message}")
        raise
    assert ch["channel_id"] and len(ups) == 5 and found


def test_youtube_rss_still_parses_when_it_answers():
    try:
        atom = feeds.parse_youtube_atom(net.get_text(
            "https://www.youtube.com/feeds/videos.xml?channel_id=UC7kIy8fZavEni8Gzl8NLjOQ", timeout=15))
    except RecompError as exc:
        pytest.skip(f"YouTube RSS unavailable (known to fail often): {exc.message}")
    assert atom["items"] and atom["items"][0]["video_id"]
