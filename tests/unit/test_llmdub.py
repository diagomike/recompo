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
    assert t["route"] == "target" and t["writes"] == ["es"] and t["views"] == [{"lang": "en", "mt": "nllb"}]
    s = P("en", "om")
    assert s["route"] == "source" and s["writes"] == ["en"] and s["back_translate"]
    m = P("am", "om")
    assert m["route"] == "middle" and m["reads"] == ["en"] and m["writes"] == ["en"] and m["back_translate"]


def test_named_routes_and_aliases():
    assert P("am", "om", route="src-en")["route"] == "source"
    assert P("am", "es", route="tgt-en")["route"] == "target"
    assert P("am", "om", route="mid-en")["route"] == "middle"
    mm = P("am", "om", route="multi", middle="en,es", views_mt="google,nllb", online=True)
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


def test_offline_by_default_two_independent_systems():
    m = P("am", "om", route="multi", middle="en,es")
    assert not m["online"] and [v["mt"] for v in m["views"]] == ["nllb", "m2m100"]  # two different offline systems
    assert m["mt_into"] == {"en": "nllb"}  # M2M-100 has no Oromo
    assert [b["mt"] for b in m["back_translate"]] == ["nllb", "nllb"] and m["notes"]


def test_engines_fall_back_to_what_can_do_the_pair():
    assert L.engine_for("bergamot", "am", "en", False)[0] == "nllb"  # Mozilla has no Amharic
    assert L.engine_for("bergamot", "de", "en", False) == ("bergamot", "")
    eng, note = L.engine_for("google", "am", "en", False)
    assert eng == "nllb" and "offline" in note  # google is refused offline
    assert L.engine_for("google", "am", "en", True) == ("google", "")
    assert L.engine_for("nllb", "am", "es", False, avoid=("nllb",))[0] == "m2m100"
    with pytest.raises(RecompError):
        L.engine_for("nllb", "xx", "yy", False)


def test_voices_offline_by_default(monkeypatch):
    from recomp.lang import tts
    monkeypatch.delenv("RECOMP_TTS", raising=False)
    assert tts.voice_for("om") == ("mms", "facebook/mms-tts-orm")
    assert tts.voice_for("am") == ("mms", "facebook/mms-tts-amh")
    assert tts.voice_for("am", online=True)[0] == "edge"
    with pytest.raises(RecompError) as e:
        tts.voice_for("am", voice="am-ET-MekdesNeural")
    assert e.value.code == "E_OFFLINE"


def test_mms_voices_are_offline_options(proj, OK, monkeypatch):
    from recomp.lang import tts
    monkeypatch.delenv("RECOMP_TTS", raising=False)
    assert tts.voice_for("kin") == ("mms", "facebook/mms-tts-kin")  # any MMS language by its ISO 639-3 code
    assert tts.voice_for("om", voice="mms:facebook/mms-tts-orm") == ("mms", "facebook/mms-tts-orm")
    v = OK("lang.voices", {"lang": "om"}, proj)  # offline: no network call, edge voices not listed
    assert v["online"] is False and v["online_voices"] == []
    mms = next(x for x in v["offline"] if x["backend"] == "mms")
    assert mms["voice"] == "mms:facebook/mms-tts-orm" and mms["default"] and mms["installed"] is False
    assert any(x["voice"] == "clone" for x in v["offline"])
    OK("dub.settings", {"at": "project", "voice": "mms:facebook/mms-tts-orm"}, proj)
    assert OK("dub.settings", {"to": "om"}, proj)["settings"]["voice"] == "mms:facebook/mms-tts-orm"


# ---- nuance (P20): marks and bounded selection effects ---------------------------------------------------------

def test_nuance_setting_and_items_are_validated():
    assert L.normalise({"nuance": "MARK"})["nuance"] == "mark" and L.DEFAULTS["nuance"] == "on"
    with pytest.raises(RecompError):
        L.normalise({"nuance": "sometimes"})
    items = L.check_nuance("k", [{"id": "n1", "trigger": "lose her", "kind": "pun:mishearing", "bound": "l", "laugh": True,
                                  "units": ["u1"]}, {"id": "n2", "kind": "banter"}], {"u1", "u2"})
    assert items[0]["kind"] == "pun" and items[0]["bound"] == "L" and items[0]["payoff_last"] and items[1]["kind"] == "other"
    for bad in ([{"id": "n1", "units": ["u9"]}], [{"id": "n1"}, {"id": "n1"}], [{"trigger": "x"}]):
        with pytest.raises(RecompError):
            L.check_nuance("k", bad, {"u1"})


def test_laugh_units_are_never_droppable_colour():
    units = [{"id": "u1", "tier": "core"}, {"id": "u2", "tier": "colour"}, {"id": "u3", "tier": "colour"}]
    got = {u["id"]: u["tier"] for u in L.promote(units, [{"id": "n1", "laugh": True, "units": ["u2"]},
                                                         {"id": "n2", "laugh": False, "units": ["u3"]}])}
    assert got == {"u1": "core", "u2": "support", "u3": "colour"}


def _one(units, options, dur=lambda t: 1.0, **kw):  # noqa: E731
    return L.select(units, [{"dur": 1.0}], {0: options}, dur, **kw)["phrases"][0]


def test_a_kept_joke_never_outweighs_meaning_or_fit():
    items = [{"id": "n1", "laugh": True, "units": ["u1"]}]
    units = [{"id": "u1", "tier": "core"}, {"id": "u2", "tier": "colour"}] + L.nuance_units(items)
    meaning = {"text": "more meaning", "units": ["u1", "u2"]}
    joke = {"text": "the joke", "units": ["u1", "n:n1"]}
    assert _one(units, [joke, meaning]) == "more meaning"  # even a colour unit (1.0) outweighs a laugh point (0.5)
    dur = lambda t: 1.0 if t == "fits" else 1.3  # noqa: E731
    assert _one(units, [{"text": "fits", "units": ["u1"]}, {"text": "long joke", "units": ["u1", "n:n1"]}], dur) == "fits"
    plain = {"text": "plain", "units": ["u1"]}
    assert _one(units, [plain, joke]) == "the joke"  # same meaning, same fit: the joke wins the tie
    # core is still core: a joke option without the core unit loses to one with it
    assert _one(units, [{"text": "joke only", "units": ["n:n1", "u2"]}, plain]) == "plain"


def test_declared_substitution_is_not_charged_as_added_in_conserve_mode():
    units = [{"id": "u1", "tier": "core"}] + L.nuance_units([{"id": "n1", "laugh": True}])
    sub = {"text": "substitute joke", "units": ["u1", "n:n1"], "strategy": "substitute", "added": ["new joke material"]}
    inv = {"text": "invention", "units": ["u1"], "added": ["invented detail"]}
    plain = {"text": "plain", "units": ["u1"]}
    assert _one(units, [inv, plain], conserve=True) == "plain"
    assert _one(units, [plain, sub], conserve=True) == "substitute joke"


def test_exact_selection_with_nuance_matches_brute_force():
    rnd = random.Random(11)
    dur = lambda t: len(t) / 10  # noqa: E731
    for _ in range(40):
        units = [{"id": f"u{i}", "tier": rnd.choice(["core", "support", "colour"])} for i in range(3)]
        units += L.nuance_units([{"id": "n1", "laugh": True}, {"id": "n2"}])
        ids = [u["id"] for u in units]
        frames = [{"dur": rnd.uniform(0.8, 3.0)} for _ in range(3)]
        variants = {k: [{"text": "x" * rnd.randint(4, 40), "units": rnd.sample(ids, rnd.randint(0, 3))} for _ in range(3)]
                    for k in range(3)}
        got = L.select(units, frames, variants, dur)
        best = None
        wt = {u["id"]: u.get("w", L.TIER_W.get(u["tier"], 0)) for u in units}
        core = {u["id"] for u in units if u["tier"] == "core"}
        for combo in itertools.product(*[variants[k] for k in range(3)]):
            cov, sc = set(), 0.0
            for k, v in enumerate(combo):
                us = set(v["units"])
                r = dur(v["text"]) / frames[k]["dur"]
                sc -= L.ALPHA * L.fit_penalty(r, (0.8, 1.05), None) + L.BETA * len({x for x in cov & us if not x.startswith("n:")})
                cov |= us
            key = (core <= cov, sc + sum(wt[u] for u in cov))
            best = key if best is None or key > best else best
        assert got["kept_all_core"] == best[0] and abs(got["score"] - round(best[1], 3)) < 1e-6
        assert not any(u.startswith("n:") for u in got["units"]) and set(got["nuance"]) <= {"n1", "n2"}


def test_guides_follow_the_writing_language():
    strong = L.strong_set(L.DEFAULTS)
    assert L.guide("es", "es", strong).startswith("naturalize")
    assert L.guide("en", "en", strong).startswith("naturalize")
    assert L.guide("en", "om", strong).startswith("function-preserving")  # written in English, carried by MT
    assert L.guide("am", "am", strong).startswith("function-preserving")  # the LLM is not strong in Amharic


def test_literal_flags_spot_word_for_word_idioms():
    items = [{"id": "n1", "kind": "idiom", "trigger": "played the Gunther card too soon"},
             {"id": "n2", "kind": "joke", "trigger": "take my grandmother to the vet"}]
    assert L.literal_flags(items, "I think you played Gunther's card too early.") == ["n1"]
    assert L.literal_flags(items, "I think you asked Gunther for help too early.") == []


def test_writer_sees_chain_lines_and_earlier_renderings_of_a_running_joke():
    from recomp.verbs.dub import _nuance_for_writer
    settings = {**L.DEFAULTS}
    ln = {"key": "seg:2", "settings": settings, "route": {"writes": ["es"]}}
    mp = {"nuance": [{"id": "n1", "laugh": True, "deps": ["seg:1"], "canon": "break"}]}
    by_key = {"seg:1": {"text": "We were on a break!"}, "seg:2": {"text": "A BREAK!"}}
    maps = {"seg:9": {"data": {"nuance": [{"id": "n7", "canon": "break"}]}}}
    choice = {"seg:9": {"data": {"picks": [{"text": "¡Nos estábamos dando un tiempo!", "nuance": ["n7"]}]}}}
    got = _nuance_for_writer(ln, mp, by_key, maps, choice, "es")
    assert got["guide"]["es"].startswith("naturalize") and got["deps_text"] == {"seg:1": "We were on a break!"}
    assert got["glossary"]["break"]["rendered"] == "¡Nos estábamos dando un tiempo!"
    assert _nuance_for_writer({**ln, "settings": {**settings, "nuance": "off"}}, mp, by_key, maps, choice, "es") == {}
