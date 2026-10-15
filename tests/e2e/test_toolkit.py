"""P15 editing toolkit on the fixture clip: bulk transcript edits, manual speakers, translation editing, caption sheet."""

import json
from pathlib import Path

import pytest

from tests.media import copy_clip

pytestmark = pytest.mark.e2e

TALK = """1
00:00:01,000 --> 00:00:04,000
>> Do you think a plant could be conscious?

2
00:00:04,500 --> 00:00:08,000
>> I doubt it, it needs a nervous system.

3
00:00:08,500 --> 00:00:12,000
But plants respond in complex ways. >>

4
00:00:12,500 --> 00:00:15,000
Responding is not experiencing.
"""

FILM = """1
00:00:02,000 --> 00:00:04,000
BRUCE: Why do we fall?

2
00:00:07,000 --> 00:00:10,000
ALFRED: So we can learn to pick ourselves up.

3
00:00:12,000 --> 00:00:16,000
[thunder]
"""


@pytest.fixture
def tp(proj, tmp_path, OK, monkeypatch):
    monkeypatch.setenv("RECOMP_JOBS", "inline")
    clip = copy_clip(tmp_path / "media", "clip.mp4")
    OK("source.add", {"target": str(clip), "jobs": ["audio"]}, proj)
    OK("transcript.align", {"ref": "S1", "method": "proportional"}, proj)
    return proj


def _import(proj, tmp_path, OK, body, name):
    f = tmp_path / name
    f.write_text(body, encoding="utf-8")
    return OK("transcript.import", {"ref": "S1", "file": str(f), "primary": True}, proj)


def _lines(OK, proj, ref="S1"):
    return OK("transcript.export", {"ref": ref, "format": "json", "out": str(proj / "t.json")}, proj) and \
        json.loads((proj / "t.json").read_text(encoding="utf-8"))["segments"]


def test_replace_dry_run_apply_and_undo(tp, OK):
    d = OK("transcript.replace", {"ref": "S1", "find": "villain", "replace": "bad guy", "dry_run": True}, tp)
    assert d["replaced"] == 1 and d["changes"][0]["after"].endswith("become the bad guy.")
    assert "villain" in _lines(OK, tp)[2]["text"]
    OK("transcript.replace", {"ref": "S1", "find": "villain", "replace": "bad guy"}, tp)
    seg = _lines(OK, tp)[2]
    assert seg["text"].endswith("bad guy.") and [w["text"] for w in seg["words"]][-2:] == ["bad", "guy."]
    assert OK("search", {"query": "bad guy"}, tp)["hits"]
    OK("op.undo", {}, tp)
    assert "villain" in _lines(OK, tp)[2]["text"]


def test_regex_whole_and_all(tp, OK):
    r = OK("transcript.replace", {"ref": "all", "find": r"\bwhy\b", "replace": "How", "regex": True}, tp)
    assert r["replaced"] == 2


def test_edit_many_merge_split_delete(tp, OK):
    OK("transcript.edit", {"ref": "S1", "edits": [{"idx": 0, "text": "Why do we fall, Master Bruce?"},
                                                   {"idx": 6, "end": "36.2"}]}, tp)
    segs = _lines(OK, tp)
    assert segs[0]["text"] == "Why do we fall, Master Bruce?" and segs[6]["end"] == 36.2
    m = OK("transcript.merge", {"ref": "S1", "lines": "0-1"}, tp)
    assert m["merged"] == 2 and m["end"] == 10.125
    s = OK("transcript.split", {"ref": "S1", "idx": 0, "after": "Why do we fall, Master Bruce?"}, tp)
    assert s["second"]["text"] == "So we can learn to pick ourselves up." and 4.0 < s["first"]["end"] < 7.5
    segs = _lines(OK, tp)
    assert [x["text"][:6] for x in segs[:2]] == ["Why do", "So we "]
    d = OK("transcript.delete", {"ref": "S1", "match": "serious"}, tp)
    assert d["deleted"] == 1 and len(_lines(OK, tp)) == 6


def test_clean_warns_about_marks_then_speakers_by_marks(tp, tmp_path, OK, R):
    _import(tp, tmp_path, OK, TALK, "talk.srt")
    env = R("transcript.clean", {"ref": "S1", "dry_run": True}, tp)
    assert env["ok"] and env["warnings"] and "speaker assign" in env["warnings"][0]
    a = OK("speaker.assign", {"ref": "S1", "by": "marks", "names": "Alex,Michael"}, tp)
    assert a["by_person"] == {"Alex": 2, "Michael": 2}
    segs = _lines(OK, tp)
    assert [s["speaker"] for s in segs] == ["Alex", "Michael", "Michael", "Alex"]
    c = OK("transcript.clean", {"ref": "S1"}, tp)
    assert c["cleaned"] == 3 and ">>" not in " ".join(s["text"] for s in _lines(OK, tp))
    people = OK("speaker.people", {}, tp)["people"]
    assert {p["name"]: p["lines"] for p in people} == {"Alex": 2, "Michael": 2}
    voices = OK("speaker.list", {"ref": "S1"}, tp)["voices"]
    assert {v["voice"] for v in voices} == {"S1:Alex", "S1:Michael"} and all(v["seconds"] > 0 for v in voices)
    OK("speaker.people", {"person": "Michael", "rename": "Michael Pollan"}, tp)
    assert OK("speaker.people", {}, tp)["people"][1]["aliases"] == ["Michael"]


def test_speakers_by_prefix_and_range(tp, tmp_path, OK):
    _import(tp, tmp_path, OK, FILM, "film.srt")
    d = OK("speaker.assign", {"ref": "S1", "by": "prefix", "dry_run": True}, tp)
    assert d["by_person"] == {"Bruce": 1, "Alfred": 1}
    OK("speaker.assign", {"ref": "S1", "by": "prefix"}, tp)
    segs = _lines(OK, tp)
    assert segs[0]["text"] == "Why do we fall?" and segs[0]["speaker"] == "Bruce"
    OK("speaker.assign", {"ref": "S1", "name": "Narrator", "lines": "2"}, tp)
    assert _lines(OK, tp)[2]["speaker"] == "Narrator"
    OK("op.undo", {}, tp)
    assert _lines(OK, tp)[2].get("speaker") is None


def test_shift_scale_and_range_resegment_export_import(tp, OK):
    OK("transcript.shift", {"ref": "S1", "by": "1", "from": "20"}, tp)
    segs = _lines(OK, tp)
    assert segs[2]["start"] == 12.0 and segs[4]["start"] == 25.0
    OK("transcript.shift", {"ref": "S1", "by": "0", "scale": 0.5}, tp)
    assert _lines(OK, tp)[2]["start"] == 6.0
    r = OK("transcript.resegment", {"ref": "S1", "max_chars": 40}, tp)
    assert r["lines_after"] > r["lines_before"] and r["transcript"] == "S1.t2"
    f = OK("transcript.export", {"ref": "S1", "format": "srt"}, tp)["file"]
    assert Path(f).read_text(encoding="utf-8").startswith("1\n")
    j = OK("transcript.export", {"ref": "S1", "format": "json", "out": str(tp / "back.json")}, tp)
    back = OK("transcript.import", {"ref": "S1", "file": j["file"]}, tp)
    assert back["segments"] == r["lines_after"]


@pytest.fixture
def jp(tp, OK, monkeypatch):
    monkeypatch.setenv("RECOMP_TTS", "stub")
    OK("cut.add", {"ref": "S1", "from": "11.8", "to": "17.0", "snap": "none", "why": "w"}, tp)
    OK("journey.new", {"title": "Heroes", "cuts": ["C1"]}, tp)
    return tp


def test_translation_lines_edit_replace_clear(jp, OK):
    t = OK("lang.translate", {"journey": "J1", "to": "fr", "template": True}, jp)
    seg_key = [l["key"] for l in t["lines"] if l["key"].startswith("seg:")][0]
    long = ("Soit tu meurs en héros, soit tu vis assez longtemps pour te voir devenir le méchant de cette histoire "
            "qui ne finit jamais vraiment.")
    OK("lang.edit", {"journey": "J1", "lang": "fr", "key": seg_key, "text": long}, jp)
    lines = OK("lang.lines", {"journey": "J1", "lang": "fr", "over": True, "profile": "shorts"}, jp)
    assert lines["lines"][0]["key"] == seg_key and lines["lines"][0]["screens"] >= 2
    rep = OK("lang.replace", {"lang": "fr", "find": "méchant", "replace": "vilain"}, jp)
    assert rep["replaced"] == 1
    assert "vilain" in OK("lang.lines", {"journey": "J1", "lang": "fr", "find": "vilain"}, jp)["lines"][0]["text"]
    sheet = OK("export.caption-sheet", {"journey": "J1", "profile": "shorts", "lang": "fr"}, jp)
    assert Path(sheet["file"]).stat().st_size > 10_000 and sheet["screens"] >= 2
    OK("profile.edit", {"name": "shorts", "caption_lang": "fr:max_chars=18,max_lines=3"}, jp)
    assert OK("profile.show", {"name": "shorts"}, jp)["caption_lang"] == {"fr": {"max_chars": 18, "max_lines": 3}}
    c = OK("lang.clear", {"journey": "J1", "lang": "fr"}, jp)
    assert c["removed"] == 1
