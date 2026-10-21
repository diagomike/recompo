"""Cross-release matching (compose/release.py) on synthetic transcripts: the same lines at other times."""

import random

from recomp.compose import release

_rng = random.Random(7)
_VOCAB = ("night city hero dawn plan chaos truth people villain mask bridge money fire court judge harbor ferry "
          "rule choice fear coin hospital tower warehouse police mayor lawyer family promise price justice dog car "
          "smile scar letter boat bomb clock door window street signal light shadow name friend enemy trust").split()
LINES = [" ".join(_rng.choice(_VOCAB) for _ in range(_rng.randint(8, 13))).capitalize() + "." for _ in range(36)]
LINES[7] = "You complete me."              # too short to place
LINES[26] = LINES[13]                       # a line said twice, 520 s apart: matching must not jump to it


def film(shift=0.0, rate=1.0, cut_at=None, cut_len=0.0, split=False):
    segs = []
    for k, text in enumerate(LINES):
        t = 30.0 + k * 40.0
        if cut_at is not None and t >= cut_at:
            if t < cut_at + cut_len:
                continue  # the scene is missing from this copy
            t -= cut_len
        t = t * rate + shift
        if split and len(text.split()) > 8:
            words = text.split()
            segs += [{"start": t, "end": t + 2, "text": " ".join(words[:5])},
                     {"start": t + 2, "end": t + 4, "text": " ".join(words[5:])}]
        else:
            segs.append({"start": t, "end": t + 4, "text": text})
    return segs


SPANS = [(28.0, 75.0), (500.0, 560.0), (1300.0, 1340.0)]


def test_anchors_are_lines_with_words_around_slots():
    a = release.anchors(film(), SPANS)
    assert a and all(len(x[1].split()) >= release.MIN_TOKENS for x in a)
    assert all(any(s0 - 20 <= t <= s1 + 5 for s0, s1 in SPANS) for t, _ in a)
    assert "You complete me." not in [x[1] for x in a]  # too short to identify a place


def test_a_shifted_copy_with_lines_split_differently():
    a = release.anchors(film(), SPANS)
    m = release.match(a, film(shift=7.3, split=True))
    assert m["offset_s"] == 7.3 and not m["edit"] and m["matched"] == len(a)
    assert release.offset_near(m, 520.0) == 7.3


def test_a_copy_missing_a_scene_takes_the_offset_near_each_cut():
    a = release.anchors(film(), SPANS)
    m = release.match(a, film(shift=2.0, cut_at=300.0, cut_len=80.0))  # 80 s cut out at 5:00
    assert m["edit"]
    assert release.offset_near(m, 40.0) == 2.0     # before the missing scene
    assert release.offset_near(m, 520.0) == -78.0  # after it
    assert release.offset_near(m, 1320.0) == -78.0


def test_pal_speed_drift_follows_the_film():
    a = release.anchors(film(), SPANS)
    m = release.match(a, film(rate=24 / 25))  # 4 % faster: −1 s every 25 s
    for t in (40.0, 520.0, 1320.0):
        assert abs(release.offset_near(m, t) - (t * 24 / 25 - t)) < 2.5


def test_another_film_matches_nothing():
    a = release.anchors(film(), SPANS)
    other = [{"start": 10.0 * k, "end": 10.0 * k + 4, "text": f"Completely different words number {k} here"} for k in range(100)]
    assert release.match(a, other)["offset_s"] is None
