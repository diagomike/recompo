"""P17b: topics from the news, scans across followed creators, the brief, and a journey from a topic."""

from __future__ import annotations

import pytest

from recomp.envelope import RecompError
from recomp.ingest import links
from recomp.research import net, topics, youtube
from tests.unit.test_follow import LEX_FEED, WR_FEED, Net, text


class NewsNet(Net):
    def get_text(self, url, timeout=30, max_bytes=None, user_agent=None):
        if "news.google.com/rss" in url:
            self.calls.append(url)
            return text("news-search-ai-models.xml") if "/search?" in url else text("news-tech.xml")
        if "trends.google.com" in url:
            self.calls.append(url)
            return text("gtrends-us.xml")
        if "wikimedia.org" in url:
            assert user_agent and "me@example.org" in user_agent  # Wikimedia's policy: contact details
            self.calls.append(url)
            return text("wiki-top.json")
        if "hn.algolia.com" in url:
            self.calls.append(url)
            return text("hn-front.json")
        return super().get_text(url, timeout, max_bytes)


@pytest.fixture
def fake(monkeypatch):
    n = NewsNet()
    monkeypatch.setattr(net, "get_text", n.get_text)
    monkeypatch.setattr(youtube, "flat", n.flat)

    def blocked(url, flat=False, limit=None):
        raise RecompError("E_EXTERNAL", "the site asks to confirm this is not a bot")
    monkeypatch.setattr(links, "extract", blocked)
    monkeypatch.setenv("RECOMP_JOBS", "off")
    return n


def test_news_parsers():
    items = topics.parse_news(text("news-search-ai-models.xml"))
    assert items[0]["title"].startswith("Anthropic warns AI models could soon copy themselves")
    assert items[0]["source"] == "CNBC" and not items[0]["title"].endswith("CNBC") and items[0]["date"]
    assert "copy" in [t.lower() for t in topics.key_terms(items[0]["title"], 6)]
    ps = topics.passages([{"start": i * 10.0, "end": i * 10.0 + 9, "text": t, "speaker": "A"} for i, t in enumerate(
        ["hello there", "AI models keep getting better", "and the models could copy themselves", "lunch", "weather",
         "sports", "more sports", "AGI talk: models", "end", "end", "end"])], ["AI", "models", "copy itself", "AGI"], k=2)
    assert ps and ps[0]["start"] <= 10 and "models" in ps[0]["terms"]


def test_guest_from_title():
    g = topics.guest_from_title
    assert g("#452 – Dario Amodei: Anthropic CEO on Claude, AGI & the Future of AI & Humanity") == "Dario Amodei"
    assert g("Dario Amodei: Anthropic CEO on Claude, AGI & the Future of AI & Humanity | Lex Fridman Podcast #452") == "Dario Amodei"
    assert g('AI Whistleblower: "They Are Hiding What Is Really Happening" | Jeffrey Ladish') == "Jeffrey Ladish"
    assert g("Are Plants Conscious? - Michael Pollan") == "Michael Pollan"
    assert g("Psychiatry, Insane Asylums, ECT, Lobotomies, Freud & Jung | Lex Fridman Podcast #502") is None
    assert g("AI Experts Debate: The AI Labs Are Lying To Everyone, Is There A 99% Chance Of Human Extinction?") is None
    assert g("Why AI Will Never Be Conscious - Anil Seth") == "Anil Seth"


def test_passage_speakers_carry_over_unnamed_lines():
    segs = [{"start": 0, "end": 30, "speaker": "Dario Amodei", "text": "scaling laws"},
            {"start": 30, "end": 60, "speaker": None, "text": "and more scaling"},
            {"start": 60, "end": 61, "speaker": None, "text": "ok"}]
    p = topics.passages(segs[1:], ["scaling"], k=1, min_s=10)[0]
    assert p["speakers"] == []  # nobody named before it in what it was given
    p = topics.passages(segs, ["scaling"], k=1, min_s=10)
    assert all(q["speakers"] == ["Dario Amodei"] for q in p)


def test_topic_suggest_scan_brief_and_journey(fake, proj, OK, R):
    from recomp.core import config
    no_contact = R("topic.suggest", {"sources": ["wikipedia"]})
    assert no_contact["error"]["code"] == "E_EXTERNAL" and "research.contact" in no_contact["error"]["message"]
    config.set_value("research.contact", "me@example.org")
    sug = OK("topic.suggest", {"sources": ["news", "trends", "wikipedia", "hn"]})["suggestions"]
    assert {s["from"] for s in sug} == {"news", "trends", "wikipedia", "hn"}
    assert all(s["terms"] for s in sug) and sug[0]["n"] == 1

    OK("follow.add", {"target": "@CosmicSkeptic", "project": [str(proj)], "person": "Alex O'Connor", "podcast": WR_FEED})
    OK("follow.add", {"target": LEX_FEED, "project": [str(proj)], "name": "Lex Fridman", "person": "Lex Fridman"})
    t = OK("topic.add", {"title": "How psychiatry treated madness", "terms": ["psychiatry", "lobotomy", "asylum", "insulin coma"],
                         "since": "2000-01-01"})
    assert t["ref"] == "T1" and t["projects"] == ["p1"]
    scan = OK("topic.scan", {"ref": "T1"})
    assert scan["summary"]["creators"] == 1 and scan["summary"]["passages"] >= 1
    lex = next(c for c in scan["creators"] if c["name"] == "Lex Fridman")
    assert lex["fetched"] == 1 and lex["episodes"] == 1
    brief = OK("topic.brief", {"ref": "T1"})
    lexb = next(c for c in brief["creators"] if c["follow"] == "F2")
    ep = lexb["episodes"][0]
    assert ep["where"] == "L1" and ep["timing"] == "video" and ep["passages"][0]["id"] == "p1"
    assert ep["passages"][0]["speakers"] and ep["passages"][0]["link"].startswith("https://youtu.be/s7d2d8FhevU?t=")
    assert brief["news"]  # this week's headlines kept as context
    md = OK("topic.brief", {"ref": "T1", "format": "md"})["markdown"]
    assert "## Lex Fridman (F2)" in md and "**p1**" in md

    # The library now knows who talked about psychiatry: suggestions show it.
    from recomp.core import studio
    from recomp.verbs.topic import _voices
    db = studio.open_db()
    try:
        assert _voices(db, ["psychiatry", "lobotomy"]) == {"Lex Fridman": 1}
    finally:
        db.close()

    j = OK("journey.from-topic", {"topic": "T1"}, proj)
    assert j["journey"] == "J1" and list(j["sections"]) == ["Lex Fridman"] and len(j["cuts"]) >= 1
    shown = OK("journey.show", {"journey": "J1"}, proj)
    assert shown["slots"][0]["section"] == "Lex Fridman"
    src = OK("source.show", {"ref": j["sources"]["L1"]}, proj)
    assert "s7d2d8FhevU" in src["uri"]
    trs = OK("transcript.list", {"ref": src["ref"]}, proj)
    assert any("library L1" in (tr.get("label") or "") for tr in (trs if isinstance(trs, list) else trs.get("transcripts", [])))
    assert OK("topic.list", {})[0]["journeys"][0]["journey"] == "J1"
    bad = R("journey.from-topic", {"topic": "T1", "passages": ["p99"]}, proj)
    assert bad["error"]["code"] == "E_NOT_FOUND"


def test_scan_fetches_the_most_on_topic_episode_first(fake, OK):
    OK("follow.add", {"target": LEX_FEED, "name": "Lex Fridman"})
    OK("topic.add", {"title": "AI and programming", "terms": ["AI", "programming"], "since": "2000-01-01"})
    OK("topic.scan", {"ref": "T1", "fetch": 1, "news": False})
    lib = OK("library.list", {})
    assert [d["title"][:4] for d in lib] == ["#501"]  # "AI" and "Programming" in its title, not the newest (#502)


def test_podcast_passage_is_cut_from_its_youtube_upload(fake, proj, OK, monkeypatch):
    """A feed-only episode is matched to its upload by words; the cut moves onto the video's clock."""
    from recomp.research import transcripts as tr
    from recomp.transcript import align, parse
    DOAC = "https://rss2.flightcast.com/xmsftuzjjykcmqwolaqn6mdn.xml"
    cues, _ = parse.parse_cues(text("doac.vtt"))
    late = [{"start": c["start"] + 5, "end": c["end"] + 5, "text": c["text"]} for c in cues]  # the video runs 5 s later
    for c in late:
        c["words"] = align.proportional_words(c)
    flat = youtube.flat

    def fake_flat(url, limit=30):
        if url.startswith("ytsearch10:"):
            return {"entries": [{"id": "Up1oadVid01", "title": "Phone Addiction Scientist", "channel": "The Diary Of A CEO Clips"},
                                {"id": "Up1oadVid02", "title": "Phone Addiction Scientist | Dr Sahar Yousef", "channel": "The Diary Of A CEO"}]}
        return flat(url, limit)
    monkeypatch.setattr(youtube, "flat", fake_flat)
    monkeypatch.setattr(tr, "youtube_captions", lambda vid, language=None: {"segments": late, "published": None, "title": "x"})

    OK("follow.add", {"target": DOAC, "project": [str(proj)]})
    OK("topic.add", {"title": "Attention", "terms": ["attention", "multitasking"], "since": "2000-01-01"})
    brief = OK("topic.scan", {"ref": "T1", "fetch": 1, "news": False})
    assert brief["summary"]["passages"] >= 1
    b = OK("topic.brief", {"ref": "T1"})
    ep = b["creators"][0]["episodes"][0]
    p = ep["passages"][0]
    assert ep["timing"] == "podcast" and not ep["video_id"]
    j = OK("journey.from-topic", {"topic": "T1", "passages": [p["id"]]}, proj)
    src = OK("source.show", {"ref": list(j["sources"].values())[0]}, proj)
    assert "Up1oadVid02" in src["uri"]  # the channel's own upload, not the clips channel
    cut = OK("cut.show", {"ref": j["cuts"][0]}, proj)
    assert abs(cut["start"] - (p["start"] + 5)) < 1.0  # snapped to words, within a second
    assert OK("library.list", {})[0]["ref"] == ep["where"]
