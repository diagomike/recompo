import pytest

from tests.media import copy_clip

pytestmark = pytest.mark.e2e


@pytest.fixture
def clip_proj(proj, tmp_path, OK, monkeypatch):
    monkeypatch.setenv("RECOMP_JOBS", "inline")
    clip = copy_clip(tmp_path / "media", "clip.mp4")
    OK("source.add", {"target": str(clip), "jobs": ["audio", "shots"]}, proj)
    OK("transcript.align", {"ref": "S1", "method": "proportional"}, proj)
    return proj


def test_transcript_read_and_outline(clip_proj, OK):
    r = OK("transcript.read", {"ref": "S1", "from": "10", "to": "20"}, clip_proj)
    assert "#2 [00:00:12.0] You either die a hero" in r["text"]
    o = OK("transcript.outline", {"ref": "S1"}, clip_proj)
    assert o["segments"] == 7 and o["buckets"]


def test_search_and_suggest(clip_proj, OK):
    s = OK("search", {"query": "world burn"}, clip_proj)
    assert s["hits"][0]["idx"] == 3 and "--segments" in s["hits"][0]["cut"]
    sug = OK("cut.suggest", {"query": "villain", "min_s": 5}, clip_proj)
    assert sug["candidates"] and "hero" in sug["candidates"][0]["text"]


def test_cut_by_quote_snaps_to_words(clip_proj, OK):
    c = OK("cut.add", {"ref": "S1", "quote_start": "You either die a hero", "quote_end": "become the villain",
                       "title": "Live long enough", "why": "thesis", "tags": ["fate"]}, clip_proj)
    assert c["ref"] == "C1"
    assert 11.7 <= c["start"] <= 12.0 and 15.8 <= c["end"] <= 17.0
    assert c["quote"].startswith("You either die a hero")


def test_cut_by_segments_and_time(clip_proj, OK):
    c = OK("cut.add", {"ref": "S1", "segments": "3..4", "why": "x"}, clip_proj)
    assert c["start"] < 19.1 and c["quote"].startswith("Some men")
    t = OK("cut.add", {"ref": "S1", "from": "29.5", "to": "33", "snap": "none", "why": "x"}, clip_proj)
    assert (t["start"], t["end"]) == (29.5, 33.0)


def test_trim_split_merge_tag_list(clip_proj, OK, R):
    OK("cut.add", {"ref": "S1", "from": "1", "to": "10", "snap": "none", "why": "x"}, clip_proj)
    c = OK("cut.trim", {"ref": "C1", "start": "+1", "end": "-1"}, clip_proj)
    assert (c["start"], c["end"]) == (2.0, 9.0)
    parts = OK("cut.split", {"ref": "C1", "at": "5"}, clip_proj)
    assert [p["ref"] for p in parts] == ["C1", "C2"]
    OK("cut.tag", {"refs": ["C1", "C2"], "add": ["opening"]}, clip_proj)
    assert len(OK("cut.list", {"tag": "opening"}, clip_proj)) == 2
    m = OK("cut.merge", {"ref": "C1", "other": "C2"}, clip_proj)
    assert (m["start"], m["end"]) == (2.0, 9.0)
    assert R("cut.show", {"ref": "C2"}, clip_proj)["error"]["code"] == "E_NOT_FOUND"


def test_chapters_set_snap_and_precedence(clip_proj, OK):
    items = [{"start": "0", "title": "Falling"}, {"start": "11", "title": "Heroes"}, {"start": "23.5", "title": "Who I am"}]
    made = OK("chapter.set", {"ref": "S1", "items": items}, clip_proj)
    assert [c["ref"] for c in made] == ["S1.c1", "S1.c2", "S1.c3"]
    assert made[1]["start"] == pytest.approx(12.0)  # snapped to the segment start
    assert made[2]["end"] == pytest.approx(40.0, abs=0.1)
    OK("chapter.edit", {"ref": "S1.c2", "title": "Heroes and villains"}, clip_proj, actor="user")
    again = OK("chapter.set", {"ref": "S1", "items": items[:1]}, clip_proj)
    left = OK("chapter.list", {"ref": "S1"}, clip_proj)
    assert {c["title"] for c in left} == {"Falling", "Heroes and villains"}  # the user's chapter survives
    c = OK("cut.add", {"ref": "S1", "quote_start": "Some men just want", "why": "x"}, clip_proj)
    assert c["chapter"] is not None
