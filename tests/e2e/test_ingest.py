import json

import pytest

from recomp.core.project import Project
from tests.media import copy_clip, fixtures

pytestmark = pytest.mark.e2e


@pytest.fixture(autouse=True)
def inline_jobs(monkeypatch):
    monkeypatch.setenv("RECOMP_JOBS", "inline")


def test_add_local_file_imports_subs_and_processes(proj, tmp_path, OK):
    clip = copy_clip(tmp_path / "media", "clip.mp4")
    data = OK("source.add", {"target": str(clip)}, proj)
    added = data["added"][0]
    assert added["ref"] == "S1" and added["kind"] == "video"
    assert added["transcripts"][0]["segments"] == len(fixtures()["sentences"])
    assert data["runner"] == "inline"
    status = OK("source.status", {}, proj)[0]["status"]
    for stage in ("probe", "audio", "peaks", "shots", "thumbs", "transcript"):
        assert status.get(stage) == "done", (stage, status)
    show = OK("source.show", {"ref": "S1"}, proj)
    assert show["counts"]["shot"] >= 30  # colour changes every second
    assert show["transcripts"][0]["primary"] is True
    peaks = proj / "cache" / "peaks" / "S1.u8"
    meta = json.loads(peaks.with_suffix(".json").read_text())
    assert meta["bins"] == pytest.approx(40 * 20, abs=3)
    assert (proj / "cache" / "thumbs" / "S1" / "index.json").exists()
    # Adding the same file again is a no-op.
    again = OK("source.add", {"target": str(clip)}, proj)
    assert again["added"] == [] and again["skipped"][0]["ref"] == "S1"


def test_surround_source_downmixes_dialogue(proj, tmp_path, OK):
    clip = copy_clip(tmp_path / "media", "clip51.mp4", srt="clip51.srt")
    OK("source.add", {"target": str(clip), "jobs": ["audio"]}, proj)
    wav = proj / "sources" / "S1" / "audio16k.wav"
    from recomp.media.audio import read_wav
    data, sr = read_wav(wav, 12.5, 15.0)
    quiet, _ = read_wav(wav, 0.2, 1.5)
    rms = lambda a: float((a ** 2).mean() ** 0.5)
    assert sr == 16000 and rms(data) > 4 * rms(quiet)  # speech dominates over the bed


def test_rights_relink_remove_undo(proj, tmp_path, OK, R):
    clip = copy_clip(tmp_path / "media", "clip.mp4")
    OK("source.add", {"target": str(clip), "process": False}, proj)
    r = OK("source.rights", {"ref": "S1", "owner": "Test Studio", "notice": "Clip (2026), Test Studio"}, proj)
    assert r["rights"]["owner"] == "Test Studio"
    moved = tmp_path / "elsewhere" / "clip.mp4"
    moved.parent.mkdir()
    clip.rename(moved)
    OK("source.relink", {"ref": "S1", "path": str(moved)}, proj)
    assert OK("source.show", {"ref": "S1"}, proj)["path"] == str(moved.resolve())
    OK("source.remove", {"ref": "S1"}, proj)
    assert OK("source.list", {}, proj) == []
    OK("op.undo", {}, proj)
    assert OK("source.list", {}, proj)[0]["ref"] == "S1"


def test_user_rights_protected_from_agent(proj, tmp_path, OK, R):
    clip = copy_clip(tmp_path / "media", "clip.mp4", with_srt=False)
    OK("source.add", {"target": str(clip), "process": False}, proj)
    OK("source.rights", {"ref": "S1", "notice": "Mine"}, proj, actor="user")
    env = R("source.rights", {"ref": "S1", "notice": "Agent's"}, proj)
    assert env["error"]["code"] == "E_PRECEDENCE"


def test_job_verbs(proj, tmp_path, OK, monkeypatch):
    monkeypatch.setenv("RECOMP_JOBS", "off")
    clip = copy_clip(tmp_path / "media", "clip.mp4", with_srt=False)
    data = OK("source.add", {"target": str(clip), "jobs": ["audio", "peaks"]}, proj)
    assert data["runner"] == "queued"
    jl = OK("job.list", {}, proj)["jobs"]
    assert {j["type"] for j in jl} == {"audio", "peaks"}
    OK("job.cancel", {"ref": jl[0]["ref"]}, proj)  # newest first: peaks
    OK("job.run", {}, proj)
    states = {j["type"]: j["status"] for j in OK("job.list", {}, proj)["jobs"]}
    assert states == {"audio": "done", "peaks": "cancelled"}
    w = OK("job.wait", {"refs": [jl[1]["ref"]], "timeout": 1}, proj)
    assert w["finished"] is True
    tail = OK("job.tail", {"ref": jl[1]["ref"]}, proj)
    assert any("done" in line for line in tail["log"])
