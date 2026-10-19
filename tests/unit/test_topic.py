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
