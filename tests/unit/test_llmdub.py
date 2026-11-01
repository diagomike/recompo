"""The LLM dubber's language-free core: routes, frames, exact selection and layered settings."""

import itertools
import random

import pytest

from recomp.envelope import RecompError
from recomp.lang import llmdub as L


def P(src, tgt, **kw):
    return L.plan(src, tgt, {**L.DEFAULTS, **L.normalise(kw)})


def test_auto_routes_follow_llm_strength():
    assert P("de", "es")["route"] == "direct"
    t = P("am", "es")
    assert t["route"] == "target" and t["writes"] == ["es"] and t["views"] == [{"lang": "en", "mt": "google"}]
    s = P("en", "om")
    assert s["route"] == "source" and s["writes"] == ["en"] and s["back_translate"]
    m = P("am", "om")
    assert m["route"] == "middle" and m["reads"] == ["en"] and m["writes"] == ["en"] and m["back_translate"]


def test_named_routes_and_aliases():
    assert P("am", "om", route="src-en")["route"] == "source"
    assert P("am", "es", route="tgt-en")["route"] == "target"
    assert P("am", "om", route="mid-en")["route"] == "middle"
    mm = P("am", "om", route="multi", middle="en,es", views_mt="google,nllb")
    assert mm["reads"] == ["en", "es"] and [v["mt"] for v in mm["views"]] == ["google", "nllb"]
    assert [b["lang"] for b in mm["back_translate"]] == ["en", "es"]
    assert P("am", "om", route="multi")["reads"] == ["en", "es"]  # multi always has two middles


def test_quality_budget_adds_a_second_writing_language():
    assert P("am", "om", route="multi", middle="en,es", budget="quality")["writes"] == ["en", "es"]
    assert P("am", "es", budget="quality")["writes"] == ["es", "en"]
    assert P("en", "om", budget="quality", middle="en,es")["writes"] == ["en", "es"]
    assert P("de", "es", budget="quality")["writes"] == ["es"]  # direct stays direct


def test_strong_list_and_verify_override():
    assert P("am", "om", strong="en,am")["route"] == "source"
    assert not P("en", "om", verify="never")["back_translate"]
    assert P("de", "es")["back_translate"] == []  # nothing crosses MT on a direct route
    assert [b["lang"] for b in P("de", "es", verify="always")["back_translate"]] == ["de"]


def test_normalise_rejects_bad_settings():
    for bad in ({"route": "sideways"}, {"budget": "lavish"}, {"mt": "babelfish"}, {"band": "1.2,0.8"}, {"colour": 1}):
        with pytest.raises(RecompError):
            L.normalise(bad)


def test_frames_split_at_pauses_and_clip_to_the_cut():
    words = [(0.0, 0.4, "a"), (0.45, 0.9, "b"), (1.5, 2.0, "c"), (2.05, 2.5, "d"), (3.2, 3.6, "e")]
    fr = L.frames(words, (0.0, 3.6), "a b c d e", 0.3)
    assert [f["text"] for f in fr] == ["a b", "c d", "e"]
    assert L.frames(words, (1.4, 2.6), "x", 0.3)[0]["text"] == "c d"
    assert len(L.frames([], (1.0, 2.5), "no words", 0.3)) == 1


def test_syllables_any_script():
    assert L.syllables("Hello there friend") == 4
    assert L.syllables("ሰላም ነው") >= 3


def brute(units, frames, variants, dur, band=(0.8, 1.05)):
    wt = {u["id"]: L.TIER_W[u["tier"]] for u in units}
    core = {u["id"] for u in units if u["tier"] == "core"}
    best = None
    for combo in itertools.product(*[variants[k] for k in range(len(frames))]):
        cov, sc = set(), 0.0
        for k, v in enumerate(combo):
            us = set(v["units"])
            r = dur(v["text"]) / frames[k]["dur"] if v["text"] else 0.0
            sc -= L.ALPHA * L.fit_penalty(r, band, None) + L.BETA * len(cov & us) + L.ERR_COST * len(v.get("errors", []))
            cov |= us
        sc += sum(wt[u] for u in cov)
        key = (core <= cov, sc)
        if best is None or key > best[0]:
            best = (key, [v["text"] for v in combo])
    return best


def test_exact_selection_matches_brute_force():
    rnd = random.Random(7)
    dur = lambda t: len(t) / 10  # noqa: E731
    for _ in range(40):
        units = [{"id": f"u{i}", "tier": rnd.choice(["core", "support", "colour"])} for i in range(4)]
        frames = [{"dur": rnd.uniform(0.8, 3.0)} for _ in range(3)]
        variants = {k: [{"text": "x" * rnd.randint(4, 40), "units": rnd.sample([u["id"] for u in units], rnd.randint(0, 2)),
                         "errors": ["e"] if rnd.random() < 0.15 else []} for _ in range(3)] for k in range(3)}
        got = L.select(units, frames, variants, dur)
        (has_core, score), phrases = brute(units, frames, variants, dur)
        assert got["kept_all_core"] == has_core
        assert abs(got["score"] - round(score, 3)) < 1e-6, (got, score, phrases)


def test_selection_routes_around_verified_errors():
    units = [{"id": "u1", "tier": "core"}]
    frames = [{"dur": 1.0}]
    dur = lambda t: 1.0  # noqa: E731
    v = {0: [{"text": "fits but wrong", "units": ["u1"], "errors": ["polarity"]}, {"text": "fits and right", "units": ["u1"]}]}
    assert L.select(units, frames, v, dur)["phrases"] == ["fits and right"]


def test_settings_layers(proj, OK, tmp_path):
    from tests.media import copy_clip
    clip = copy_clip(tmp_path / "media", "clip.mp4")
    OK("source.add", {"target": str(clip), "jobs": [], "process": False, "dub_route": "tgt-en", "dub_to": ["om"]}, proj)
    OK("dub.settings", {"at": "project", "middle": ["en", "es"], "budget": "quality"}, proj)
    s = OK("dub.settings", {"target": "S1", "to": "om"}, proj)
    assert s["settings"]["route"] == "target" and s["from"]["route"] == "source S1"
    assert s["settings"]["middle"] == ["en", "es"] and s["from"]["middle"] == "project"
    OK("dub.settings", {"at": "S1", "clear": ["route"]}, proj)
    s = OK("dub.settings", {"target": "S1", "to": "om"}, proj)
    assert s["from"]["route"] == "studio" and s["plan"]["route"] == "source"  # English source, Oromo target
