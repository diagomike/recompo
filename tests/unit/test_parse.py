import json

import pytest

from recomp.media.identity import title_from_filename
from recomp.transcript import parse


def test_srt_glued_numbers_and_markup():
    text = ("1\n00:01:10,592 --> 00:01:12,811\n<i>What about</i> chocolate?\n8\n"
            "00:01:14,117 --> 00:01:16,250\n- Hello.\n- Hello.\n\n"
            "3\n00:01:20,000 --> 00:01:19,000\nbackwards\n\n"
            "4\n00:75:00,000 --> 00:75:01,000\nbad minutes\n")
    cues, problems = parse.parse_cues(text)
    assert [c["text"] for c in cues] == ["What about chocolate?", "- Hello. - Hello."]
    assert cues[0]["start"] == pytest.approx(70.592)
    assert len(problems) == 2


def test_vtt():
    text = "WEBVTT\n\n00:00.500 --> 00:02.000 align:start\nHi <c.yellow>there</c>\n\n00:03.000 --> 00:04.250\nBye\n"
    cues, _ = parse.parse_cues(text)
    assert [(c["start"], c["end"], c["text"]) for c in cues] == [(0.5, 2.0, "Hi there"), (3.0, 4.25, "Bye")]


def test_ass():
    text = ("[Script Info]\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
            "Dialogue: 0,0:00:01.50,0:00:03.00,Default,JOKER,0,0,0,,{\\i1}Why so{\\i0}\\Nserious?\n")
    cues, _ = parse.parse_ass(text)
    assert cues == [{"start": 1.5, "end": 3.0, "text": "Why so serious?", "speaker": "JOKER"}]


def test_json3_words_become_segments():
    data = {"events": [
        {"tStartMs": 0, "dDurationMs": 3000, "segs": [{"utf8": "hello"}, {"utf8": " world", "tOffsetMs": 400},
                                                       {"utf8": " this", "tOffsetMs": 900}, {"utf8": " is.", "tOffsetMs": 1200}]},
        {"tStartMs": 3000, "aAppend": 1, "segs": [{"utf8": "\n"}]},
        {"tStartMs": 5000, "dDurationMs": 2000, "segs": [{"utf8": "after"}, {"utf8": " pause", "tOffsetMs": 300}]},
    ]}
    segs, _ = parse.parse_json3(json.dumps(data))
    assert [s["text"] for s in segs] == ["hello world this is.", "after pause"]
    assert segs[0]["words"][1]["start"] == pytest.approx(0.4)
    assert segs[1]["start"] == pytest.approx(5.0)


def test_title_from_filename():
    assert title_from_filename("The.Dark.Knight.2026.1080p.WEBRip.x264.AAC5.1-[YTS.GG - YTS.BZ].mp4") == ("The Dark Knight", 2026)
    assert title_from_filename("Obsession.2026.1920x924.WEBRip.x264.AAC-pudszTTIOT.mp4") == ("Obsession", 2026)
    assert title_from_filename("April Fasting And Prayer Day 3 Video 1.mp4") == ("April Fasting And Prayer Day 3 Video 1", None)
    assert title_from_filename("2001.A.Space.Odyssey.1968.mkv") == ("2001 A Space Odyssey", 1968)


def test_guess_language():
    assert parse.guess_language("film.am.srt", []) == "am"
    assert parse.guess_language("film.srt", [{"text": "ሰላም ለዓለም"}]) == "am"
    assert parse.guess_language("film.srt", [{"text": "hello"}], "en") == "en"
