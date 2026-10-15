"""Speakers with the real worker models (pyannote). Slow: run with `pytest -m slow`."""

from pathlib import Path

import pytest

from recomp.core import config
from tests.media import copy_clip

pytestmark = [pytest.mark.e2e, pytest.mark.slow]


@pytest.fixture
def sproj(proj, tmp_path, OK, monkeypatch):
    monkeypatch.setenv("RECOMP_JOBS", "inline")
    if not Path(config.DEFAULTS["worker"]["python"]).exists():
        pytest.skip("no worker python")
    config.set_value("worker.python", config.DEFAULTS["worker"]["python"])
    for name in ("dialog_a", "dialog_b"):
        clip = copy_clip(tmp_path / "media", f"{name}.mp4", srt=f"{name}.srt")
        OK("source.add", {"target": str(clip), "jobs": ["audio"]}, proj)
    return proj


def test_diarize_name_and_recognise(sproj, OK):
    for ref in ("S1", "S2"):
        r = OK("speaker.diarize", {"ref": ref, "speakers": 2}, sproj)
        j = OK("job.show", {"ref": r["job"]}, sproj)
        assert j["status"] == "done", j
    voices = OK("speaker.list", {"ref": "S1"}, sproj)["voices"]
    assert voices and all(v["sample"] for v in voices)
    lines = OK("transcript.read", {"ref": "S1"}, sproj)["text"]
    assert "SPEAKER_0" in lines  # transcript lines carry speakers
    top = max(voices, key=lambda v: v["seconds"])
    named = OK("speaker.name", {"voice": top["voice"], "name": "Zira"}, sproj)
    assert named["person"]["ref"] == "P1" and named["segments"] >= 1
    assert any(m["source"] == "S2" and m["score"] >= 0.7 for m in named["recognised_elsewhere"])
    hits = OK("search", {"query": "illusion", "speaker": "Zira"}, sproj)
    assert hits["hits"] is not None
