import subprocess

import numpy as np
import pytest

from tests.media import copy_clip

pytestmark = pytest.mark.e2e


def rms_at(video, a, b):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(a), "-t", str(b - a), "-i", str(video), "-map", "0:a:0",
                          "-ac", "1", "-ar", "16000", "-f", "s16le", "-"], capture_output=True).stdout
    x = np.frombuffer(raw, dtype="<i2").astype("float32") / 32768
    return float(np.sqrt((x ** 2).mean() + 1e-12))


@pytest.fixture
def mproj(proj, tmp_path, OK, monkeypatch):
    monkeypatch.setenv("RECOMP_JOBS", "inline")
    clip = copy_clip(tmp_path / "media", "clip.mp4")
    OK("source.add", {"target": str(clip), "jobs": ["audio"]}, proj)
    OK("cut.add", {"ref": "S1", "from": "1.5", "to": "6.0", "snap": "none", "why": "w"}, proj)   # speech then silence
    OK("cut.add", {"ref": "S1", "from": "11.8", "to": "17.0", "snap": "none", "why": "w"}, proj)
    OK("journey.new", {"title": "With music", "cuts": ["C1", "C2"]}, proj)
    tune = tmp_path / "tune.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=f=330:d=30", "-f", "lavfi", "-i",
                    "sine=f=495:d=30", "-filter_complex", "amix=inputs=2", str(tune)], check=True)
    return proj, tune


def test_bed_mixes_ducks_and_credits(mproj, OK, R):
    proj, tune = mproj
    m = OK("music.library-add", {"file": str(tune), "title": "Fixture Tune", "artist": "Tester", "licence": "CC0 1.0"}, proj)
    OK("music.bed-add", {"journey": "J1", "track": m["ref"], "gain": -14}, proj)
    res = OK("export.run", {"journey": "J1", "profiles": ["landscape"]}, proj)
    x = OK("export.show", {"ref": res["exports"][0]["export"]}, proj)
    assert x["status"] == "done", x["problems"]
    assert 'Music: "Fixture Tune" by Tester (CC0 1.0)' in x["description"]
    gap = rms_at(x["video"], 3.0, 4.2)        # no speech in the source here: the bed is up
    speech = rms_at(x["video"], 0.6, 1.8)     # "Why do we fall, Bruce?"
    assert gap > 0.01
    # A second render without music: the gap is near-silent.
    OK("profile.new", {"name": "nomusic", "from": "landscape", "music": False}, proj)
    res2 = OK("export.run", {"journey": "J1", "profiles": ["nomusic"]}, proj)
    y = OK("export.show", {"ref": res2["exports"][0]["export"]}, proj)
    assert rms_at(y["video"], 3.0, 4.2) < gap / 4
    assert speech > gap


def test_nd_licence_refused(mproj, OK, R):
    proj, tune = mproj
    m = OK("music.library-add", {"file": str(tune), "title": "T", "licence": "CC BY-ND 4.0"}, proj)
    env = R("music.bed-add", {"journey": "J1", "track": m["ref"]}, proj)
    assert env["error"]["code"] == "E_INVALID" and "no-derivatives" in env["error"]["message"]
