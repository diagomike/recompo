"""Semantic search (transcript/semantic.py): windows, the index job, and finding a line by meaning in another language."""

from pathlib import Path

import pytest

from recomp.core import config
from recomp.transcript import semantic
from tests.media import copy_clip

pytestmark = pytest.mark.e2e


def test_windows_overlap_and_cover_every_line():
    segs = [{"idx": k, "start": 3.0 * k, "end": 3.0 * k + 2.5, "text": "one two three four five six seven"} for k in range(20)]
    wins = semantic.windows(segs)
    assert wins[0]["i0"] == 0 and wins[-1]["i1"] == 19
    assert all(b["i0"] <= a["i1"] for a, b in zip(wins, wins[1:]))          # each starts inside the one before
    assert all(len(w["text"].split()) <= semantic.WORDS + 7 for w in wins)


def _model_cached() -> bool:
    hub = Path(config.get("worker.hf_home") or "") / "hub" / ("models--" + semantic.model_name().replace("/", "--"))
    return hub.exists() and Path(config.get("worker.python") or "").exists()


def test_search_by_meaning_across_languages(proj, OK, R, tmp_path, monkeypatch, recomp_home):
    import json
    # the worker's model cache is the real one (read only): the test home's config points at it
    cfg = json.loads((recomp_home / "config.json").read_text(encoding="utf-8"))
    cfg["worker"] = {"hf_home": config.DEFAULTS["worker"]["hf_home"], "python": config.DEFAULTS["worker"]["python"]}
    (recomp_home / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
    if not _model_cached():
        pytest.skip("multilingual-e5-small is not in the worker's model cache")
    monkeypatch.setenv("RECOMP_JOBS", "inline")
    clip = copy_clip(tmp_path / "media", "clip.mp4")
    OK("source.add", {"target": str(clip), "jobs": []}, proj)
    env = R("search", {"query": "falling down and getting back up", "semantic": True}, proj)
    assert not env["ok"] and env["error"]["code"] == "E_NOT_FOUND"            # nothing indexed yet
    OK("transcript.embed", {}, proj)
    assert OK("transcript.embed", {}, proj)["current"] == ["S1"]              # a current index is skipped
    for q in ("falling down and getting back up", "pourquoi tombons-nous ? pour apprendre à nous relever"):
        hits = OK("search", {"query": q, "semantic": True, "limit": 3}, proj)["hits"]
        assert hits and "fall" in hits[0]["context"].lower(), (q, hits)
        assert hits[0]["cut"].startswith("recomp cut add S1 --segments ")
