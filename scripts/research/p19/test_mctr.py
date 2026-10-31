"""Unit tests for the pure parts of MCTR (allocation, fit penalty, exact selection). Run: pytest scripts/research/p19/test_mctr.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import mctr as M  # noqa: E402


def line(units, segs, source):
    ln = M.Line("t", source, "gist", [], [M.Unit(*u) for u in units], [{"dur": d} for d in segs])
    M.allocate(ln)
    return ln


def test_allocate_follows_source_position_and_stays_monotone():
    ln = line([("u1", "a", "Er stand auf", "core"), ("u2", "b", "und als er zurückkehrte", "core"),
               ("u3", "c", "fragten alle", "core")], [1.0, 2.0, 2.0],
              "Er stand auf, [pause] und als er zurückkehrte, [pause] fragten alle")
    assert [u.seg for u in ln.units] == [0, 1, 2]


def test_allocate_unfound_source_keeps_previous_segment():
    ln = line([("u1", "a", "Er stand auf", "core"), ("u2", "b", "nicht im Text", "support")], [1.0, 1.0],
              "Er stand auf und ging")
    assert ln.units[1].seg == ln.units[0].seg


def test_fit_penalty_band_and_asymmetry():
    assert M.fit_penalty(0.9) == 0.0 and M.fit_penalty(1.05) == 0.0
    assert M.fit_penalty(1.05 * 1.1) > M.fit_penalty(0.8 / 1.1)  # 10 % long costs more than 10 % short
    M.SOFT_FLOOR = 0.65
    try:
        assert M.fit_penalty(0.7) < 0.5
    finally:
        M.SOFT_FLOOR = None


def test_select_keeps_core_and_prefers_fit_then_meaning():
    ln = line([("u1", "a", "eins", "core"), ("u2", "b", "zwei", "colour")], [1.0], "eins zwei")
    dur = {"short": 0.9, "long fits": 1.0, "too long with colour": 1.4, "no core": 0.95}.get
    variants = {0: [{"text": "short", "units": ["u1"]}, {"text": "long fits", "units": ["u1", "u2"]},
                    {"text": "too long with colour", "units": ["u1", "u2"]}, {"text": "no core", "units": ["u2"]}]}
    out = M.select(ln, variants, dur)
    assert out["phrases"] == ["long fits"] and out["kept_all_core"]


def test_select_conserve_mode_prefers_silence_over_invention():
    ln = line([("u1", "a", "eins", "core")], [1.0], "eins")
    dur = {"plain": 0.72, "padded": 0.95}.get
    variants = {0: [{"text": "plain", "units": ["u1"]}, {"text": "padded", "units": ["u1"], "added": ["very"]}]}
    assert M.select(ln, variants, dur)["phrases"] == ["padded"]
    M.GAMMA, M.SOFT_FLOOR = 2.0, 0.65
    try:
        assert M.select(ln, variants, dur)["phrases"] == ["plain"]
    finally:
        M.GAMMA, M.SOFT_FLOOR = 0.0, None
