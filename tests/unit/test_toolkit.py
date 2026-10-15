"""P15 helpers: word timings that follow edited text, cleaning, resegmenting, caption boxes."""

from recomp.render import ass
from recomp.transcript import edit as E

WORDS = [(1.0, 1.4, "the"), (1.4, 2.0, "conscious"), (2.0, 2.5, "ness"), (2.6, 3.0, "problem")]


def test_sync_words_keeps_matching_timings():
    out = E.sync_words("the consciousness problem", WORDS)
    assert [w[2] for w in out] == ["the", "consciousness", "problem"]
    assert out[0][:2] == (1.0, 1.4) and out[-1][:2] == (2.6, 3.0)
    assert out[1][0] == 1.4 and out[1][1] == 2.5  # the replaced pair's span


def test_sync_words_unchanged_and_inserted():
    assert E.sync_words("the conscious ness problem", WORDS) == WORDS
    out = E.sync_words("the hard conscious ness problem", WORDS)
    assert [w[2] for w in out] == ["the", "hard", "conscious", "ness", "problem"]
    assert all(b >= a for a, b, _ in out) and out[1][0] >= 1.0


def test_clean_rules():
    assert E.clean_text(">> so the the [Music] point is ♪", E.DEFAULT_CLEAN) == "so the point is"
    assert E.clean_text("um, i think, uh, yes", ["fillers", "case", "spacing"]) == "I think, yes"


def test_parse_idx():
    assert E.parse_idx("3,7,9-11") == {3, 7, 9, 10, 11}
    assert E.parse_idx("12..14") == {12, 13, 14}


def test_resegment_breaks_at_sentences_and_speakers():
    ws = [{"start": i * 0.4, "end": i * 0.4 + 0.35, "text": t, "speaker": "A" if i < 6 else "B"}
          for i, t in enumerate("so what is it like? to be a bat then".split())]
    segs = E.resegment(ws, max_chars=40)
    assert segs[0]["text"] == "so what is it like?"
    assert segs[-1]["speaker"] == "B" and segs[-1]["text"] == "be a bat then" and segs[1]["text"] == "to"


def test_caption_layout_overrides():
    prof = {"width": 1080, "height": 1920, "caption_style": "clean"}
    assert ass.caption_layout(prof)["max_chars"] == 30
    assert ass.caption_layout(prof, "am", "ሰላም ነው")["max_chars"] == 24  # Ethiopic rows hold fewer characters
    assert ass.caption_layout(dict(prof, caption_scale=1.5))["max_chars"] == 20
    lay = ass.caption_layout(dict(prof, caption_max_chars=26, caption_lang={"am": {"max_chars": 18, "max_lines": 3}}), "am")
    assert (lay["max_chars"], lay["max_lines"]) == (18, 3)


def test_long_untimed_caption_becomes_screens():
    text = ("This is a long translated line that would never fit in two rows of a vertical frame, "
            "so it must be shown as several screens in time.")
    pieces = ass.split_timed(text, 10.0, 16.0, 60)
    assert len(pieces) >= 3 and all(len(p[2]) <= 66 for p in pieces)
    assert pieces[0][0] == 10.0 and abs(pieces[-1][1] - 16.0) < 1e-6
    ev = ass.caption_events([{"start": 10.0, "end": 16.0, "text": text, "words": []}], "clean", 1080, 1920,
                            {"max_chars": 30, "max_lines": 2, "scale": 1.0, "margin": None})
    assert len(ev) == len(ass.split_timed(text, 10, 16, 60))
    assert all(e.count("\\N") <= 1 for e in ev)


def test_karaoke_untimed_text_has_no_giant_chunk():
    text = "Une phrase traduite assez longue pour plusieurs écrans dans un format vertical, vraiment."
    ev = ass.caption_events([{"start": 0.0, "end": 5.0, "text": text, "words": []}], "karaoke", 1080, 1920)
    assert len(ev) >= 2 and all(len(e.split(",", 9)[9]) <= 22 * 2 + 4 for e in ev)
