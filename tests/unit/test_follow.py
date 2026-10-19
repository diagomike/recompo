"""P17a: find and follow creators, the inbox, taking items into a project, the transcript library.

The network is replaced by responses saved during the P17 research (tests/fixtures/p17, cut by
scripts/research/make_p17_fixtures.py): podcast feeds, a Lex Fridman transcript page, a DOAC VTT, iTunes search,
yt-dlp listings, and YouTube's RSS answering 500 as it did.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from recomp.envelope import RecompError
from recomp.ingest import links
from recomp.research import feeds, net, transcripts, youtube

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "p17"

WR_FEED = "https://anchor.fm/s/10a220e88/podcast/rss"
LEX_FEED = "https://lexfridman.com/feed/podcast/"
DOAC_FEED = "https://rss2.flightcast.com/xmsftuzjjykcmqwolaqn6mdn.xml"


def text(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


class Net:
    """Routes URLs to fixtures and counts requests."""

    def __init__(self):
        self.calls: list[str] = []
        self.listing = json.loads(text("yt-listing-alex.json"))

    def get_text(self, url, timeout=30, max_bytes=None, user_agent=None):
        self.calls.append(url)
        if "itunes.apple.com" in url:
            return text("itunes-within-reason.json")
        if url.startswith(WR_FEED):
            return text("feed-within-reason.xml")
        if url.startswith(LEX_FEED.rstrip("/")):
            return text("feed-lex.xml")
        if url.startswith(DOAC_FEED):
            return text("feed-doac.xml")
        if "-transcript" in url and "lexfridman.com" in url:
            return text("lex-transcript.html")
        if url.endswith(".vtt"):
            return text("doac.vtt")
        if "feeds/videos.xml" in url:
            raise RecompError("E_EXTERNAL", "www.youtube.com answered HTTP 500")
        raise RecompError("E_NOT_FOUND", f"HTTP 404 for {url}")  # other shows' feeds in the search results

    def flat(self, url, limit=30):
        self.calls.append(url)
        if "sp=EgIQAg" in url:
            return json.loads(text("yt-search-channels.json"))
        if url.startswith("ytsearch"):
            return json.loads(text("yt-search-person-alex.json"))
        if "/search?query=" in url:
            return json.loads(text("yt-channelsearch-alex-ai.json"))
        if url.endswith("/videos") or url.endswith("/shorts"):
            d = dict(self.listing)
            d["entries"] = d["entries"][:limit]
            return d
        raise AssertionError(f"unexpected listing {url}")


@pytest.fixture
def fake(monkeypatch):
    n = Net()
    monkeypatch.setattr(net, "get_text", n.get_text)
    monkeypatch.setattr(youtube, "flat", n.flat)

    def blocked(url, flat=False, limit=None):  # per-video YouTube requests refused, as during the research
        raise RecompError("E_EXTERNAL", "the site asks to confirm this is not a bot")
    monkeypatch.setattr(links, "extract", blocked)
    monkeypatch.setenv("RECOMP_JOBS", "off")
    return n


# ---- parsers --------------------------------------------------------------------------------------

def test_podcast_feeds_and_routes():
    wr = feeds.parse_podcast(text("feed-within-reason.xml"))
    assert wr["title"] == "Within Reason" and len(wr["items"]) == 4
    ep = wr["items"][0]
    assert ep["title"].startswith("#166 Are Plants Conscious") and ep["published"] and ep["duration"] > 3000
    assert ep["route"]["kind"] == "asr" and ep["audio_url"].startswith("http")
    lex = feeds.parse_podcast(text("feed-lex.xml"))
    assert lex["items"][0]["route"] == {"kind": "lex", "url": "https://lexfridman.com/andrew-scull-transcript", "timing": "video"}
    doac = feeds.parse_podcast(text("feed-doac.xml"))
    r = doac["items"][0]["route"]
    assert r["kind"] == "published" and r["format"] == "vtt" and r["timing"] == "podcast"


def test_title_pairing_between_feed_and_upload():
    assert feeds.title_match("Are Plants Conscious? - Michael Pollan", "#166 Are Plants Conscious? - Michael Pollan") == 1.0
    assert feeds.title_match("Religion is an Obligation - NYT Columnist Ross Douthat",
                             "#163 Religion is an Obligation - Ross Douthat") > 0.45
    assert feeds.title_match("A Priest Challenges Me About Jesus", "#165 Buddhist Emptiness Explained - Jan Westerhoff") < 0.2


def test_lex_page_has_speakers_video_and_chapters():
    got = transcripts.parse_lex(text("lex-transcript.html"))
    assert got["video_id"] == "s7d2d8FhevU"
    assert len(got["segments"]) >= 30 and {"Lex Fridman", "Andrew Scull"} <= {s["speaker"] for s in got["segments"]}
    assert all(s["end"] > s["start"] for s in got["segments"])
    assert got["chapters"][1]["title"] == "Crisis in Psychiatry" and got["chapters"][1]["start"] == 80


def test_channel_urls():
    assert youtube.base_url("@CosmicSkeptic") == "https://www.youtube.com/@CosmicSkeptic"
    assert youtube.base_url("https://m.youtube.com/@CosmicSkeptic/videos?x=1") == "https://www.youtube.com/@CosmicSkeptic"
    with pytest.raises(RecompError):
        youtube.base_url("https://example.com/feed")


# ---- verbs --------------------------------------------------------------------------------------

def test_find_creators(fake, OK):
    d = OK("find.creators", {"query": "philosophy podcast"})
    kinds = {r["kind"] for r in d["results"]}
    assert {"channel", "podcast", "appearances"} <= kinds
    ch = next(r for r in d["results"] if r["kind"] == "channel")
    assert ch["subscribers"] and ch["url"].startswith("https://www.youtube.com/@")
    pod = next(r for r in d["results"] if r["kind"] == "podcast")
    assert pod["feed"] == WR_FEED and pod["route"] == "asr"
    assert [r["n"] for r in d["results"]] == list(range(1, len(d["results"]) + 1))


def test_follow_check_take_and_library(fake, proj, OK, R):
    OK("project.set", {"themes": ["conscious", "plants"]}, proj)
    f = OK("follow.add", {"target": "@CosmicSkeptic", "project": [str(proj)], "person": "Alex O'Connor",
                          "podcast": WR_FEED})
    assert f["ref"] == "F1" and f["youtube"] == "https://www.youtube.com/@CosmicSkeptic" and f["podcast"] == WR_FEED
    assert R("follow.add", {"target": "@CosmicSkeptic"})["error"]["code"] == "E_EXISTS"
    lex = OK("follow.add", {"target": LEX_FEED, "project": [str(proj)], "name": "Lex Fridman", "person": "Lex Fridman"})
    assert lex["route"] == "lex"

    first = OK("follow.check", {})
    by = {o["follow"]: o for o in first["follows"]}
    assert len(by["F1"]["new"]) == 3 and by["F1"]["first_check"] and by["F1"]["held_back"] == 5
    assert by["F1"]["new"][0]["title"] == "Are Plants Conscious? - Michael Pollan"
    assert len(by["F2"]["new"]) == 3 and by["F2"]["new"][0]["route"] == "lex"
    again = OK("follow.check", {})
    assert again["new"] == 0  # a second check finds nothing new

    inbox = OK("inbox.list", {})
    assert len(inbox) == 6 and all(i["status"] == "new" for i in inbox)
    plants = next(i for i in inbox if i["title"].startswith("Are Plants"))
    lex_item = next(i for i in inbox if i["title"].startswith("#502"))

    # A YouTube upload while YouTube refuses per-video requests: added from the listing's metadata.
    t = OK("inbox.take", {"refs": [plants["ref"]]})["taken"][0]
    assert t["source"] == "S1" and t["project"] == "p1"
    # A podcast episode whose transcript page is published: the transcript, chapters and cut candidates now.
    t2 = OK("inbox.take", {"refs": [lex_item["ref"]]})["taken"][0]
    steps = {k: v for s in t2["steps"] for k, v in s.items()}
    assert steps["transcript"] and steps["route"] == "lex" and steps["primary"] is True
    assert steps["chapter.seed"]
    src = OK("source.show", {"ref": t2["source"]}, proj)
    assert src["rights"]["status"] == "private"
    assert "s7d2d8FhevU" in src["uri"]  # the Lex page named the YouTube video: the source is the video, on its clock
    hits = OK("search", {"query": "psychiatry"}, proj)
    assert hits["hits"] and hits["hits"][0]["speaker"] in ("Lex Fridman", "Andrew Scull")
    assert OK("inbox.list", {"status": "taken"})[0]["taken"]["project"] == "p1"
    rest = [i["ref"] for i in OK("inbox.list", {})]
    OK("inbox.dismiss", {"refs": rest[:1]})
    assert len(OK("inbox.list", {})) == len(rest) - 1

    # Backfill: the back catalogue's published transcripts into the library, then search across it.
    b = OK("follow.backfill", {"ref": "Lex Fridman", "since": "2000-01-01", "limit": 2})
    assert len(b["added"]) == 2 and b["remaining"] == 1
    b2 = OK("follow.backfill", {"ref": "F2", "since": "2000-01-01"})
    assert len(b2["added"]) == 1 and b2["remaining"] == 0
    s = OK("library.search", {"query": "psychiatry"})
    assert s["hits"] and s["hits"][0]["creator"] == "Lex Fridman"
    assert s["hits"][0]["link"].startswith("https://youtu.be/s7d2d8FhevU?t=")
    assert OK("search", {"query": "psychiatry", "scope": "library"})["hits"]
    lib = OK("library.list", {"follow": "F2"})
    assert len(lib) == 3 and lib[0]["route"] == "lex"
    shown = OK("library.show", {"ref": lib[0]["ref"], "to": "2:00"})
    assert shown["lines"] and shown["lines"][0]["speaker"]


def test_follow_rules_and_undo(fake, proj, OK, R):
    e = R("follow.add", {"target": "@CosmicSkeptic", "rights": "permitted"})
    assert e["error"]["code"] == "E_INVALID" and "evidence" in e["error"]["message"]
    f = OK("follow.add", {"target": "@CosmicSkeptic", "project": [str(proj)], "match": "Conscious|Chosen"})
    OK("follow.edit", {"ref": f["ref"], "rights": "permitted", "evidence": "https://example.org/permission"})
    assert OK("follow.list", {})[0]["rights"] == "permitted"
    d = OK("follow.check", {"first": 10})
    assert [i["title"] for i in d["follows"][0]["new"]] and \
        all(("Conscious" in i["title"] or "Chosen" in i["title"]) for i in d["follows"][0]["new"])
    OK("follow.remove", {"ref": f["ref"]})
    assert OK("follow.list", {}) == [] and OK("inbox.list", {}) == []
    OK("op.undo", {"studio": True}, actor="user")
    assert OK("follow.list", {})[0]["ref"] == f["ref"] and OK("inbox.list", {})
    assert R("follow.check", {"follow": ["F9"]})["error"]["code"] == "E_NOT_FOUND"


def test_follow_needs_no_project(fake, OK):
    f = OK("follow.add", {"target": LEX_FEED})
    assert f["projects"] == []
    d = OK("follow.check", {})
    item = d["follows"][0]["new"][0]
    assert item["project"] is None
    from tests.conftest import run
    e = run("inbox.take", {"refs": [item["ref"]]})
    assert e["error"]["code"] == "E_INVALID" and "--project" in e["error"]["hint"]


def test_background_checks_are_due_every_few_hours(fake, OK):
    import time

    from recomp.core import config
    from recomp.research import schedule
    assert not schedule.due()  # nothing followed
    OK("follow.add", {"target": LEX_FEED})
    assert schedule.due()
    env = schedule.run_once()
    assert env["ok"] and env["data"]["new"] == 3
    assert not schedule.due() and schedule.due(time.time() + 2 * 3600 + 1)
    config.set_value("research.check_every_h", 0)
    assert not schedule.due(time.time() + 10 * 3600)
