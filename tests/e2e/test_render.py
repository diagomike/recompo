import json
import subprocess
import time

import pytest

from recomp.core.project import Project
from tests.media import colour_for_second, copy_clip

pytestmark = pytest.mark.e2e


def pixel(video, t, x, y):
    out = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1",
                          "-vf", f"crop=2:2:{x}:{y}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    return tuple(out[:3])


def close(a, b, tol=22):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


@pytest.fixture
def rproj(proj, tmp_path, OK, monkeypatch):
    monkeypatch.setenv("RECOMP_JOBS", "inline")
    clip = copy_clip(tmp_path / "media", "clip.mp4")
    OK("source.add", {"target": str(clip), "jobs": ["audio"]}, proj)
    OK("transcript.align", {"ref": "S1", "method": "proportional"}, proj)
    OK("source.rights", {"ref": "S1", "owner": "Fixture Films"}, proj)
    # cuts at known source seconds (snap none so the mapping is exact)
    for a, b in [(12.0, 17.0), (2.0, 6.0), (19.0, 23.0)]:
        OK("cut.add", {"ref": "S1", "from": str(a), "to": str(b), "snap": "none", "why": "w", "people": ["Narrator"]}, proj)
    OK("journey.new", {"title": "Render test", "cuts": ["C1", "C2", "C3"]}, proj)
    return proj


def test_landscape_export_maps_source_time(rproj, OK):
    res = OK("export.run", {"journey": "J1", "profiles": ["landscape"]}, rproj)
    x = OK("export.show", {"ref": res["exports"][0]["export"]}, rproj)
    assert x["status"] == "done", x["checks"]
    video = x["video"]
    # output 1.5 s → slot 1 (source 12.0 + 1.5 = 13.5 → second 13); output 6.5 s → slot 2 (2.0 + 1.5 → 3)
    assert close(pixel(video, 1.5, 1900, 20), colour_for_second(13))
    assert close(pixel(video, 6.5, 1900, 20), colour_for_second(3))
    assert close(pixel(video, 11.5, 1900, 20), colour_for_second(21))
    # endcard is dark
    assert sum(pixel(video, 14.5, 1900, 20)) < 80
    files = set(x["files"])
    assert {"video.mp4", "captions.srt", "description.txt", "credits.json", "recipe.json", "thumb.jpg"} <= files
    assert "© Fixture Films" in x["description"]
    loud = x["loudness"]["integrated"]
    assert -15.0 <= loud <= -13.0


def test_shorts_blur_karaoke_and_reorder_cache(rproj, OK):
    t0 = time.time()
    res = OK("export.run", {"journey": "J1", "profiles": ["shorts"]}, rproj)
    cold = time.time() - t0
    x = OK("export.show", {"ref": res["exports"][0]["export"]}, rproj)
    assert x["status"] == "done", x["checks"]
    assert any(c["check"] == "frame size" and c["detail"] == "1080x1920" for c in x["checks"])
    ass = (rproj / "exports").rglob("overlay.ass").__next__().read_text(encoding="utf-8")
    assert "Karaoke" in ass and r"\c&H4AD8FF&" in ass
    OK("journey.move", {"slot": "J1#3", "to": 1}, rproj)
    t1 = time.time()
    res2 = OK("export.run", {"journey": "J1", "profiles": ["shorts"]}, rproj)
    warm = time.time() - t1
    j = OK("job.show", {"ref": res2["exports"][0]["job"]}, rproj)
    assert j["result"]["cache_hits"] == 3
    assert warm < cold
    # --speed fast: same slots from cache, only the final pass is encoded faster; every check still passes
    OK("journey.move", {"slot": "J1#3", "to": 1}, rproj)
    res3 = OK("export.run", {"journey": "J1", "profiles": ["shorts"], "speed": "fast"}, rproj)
    x3 = OK("export.show", {"ref": res3["exports"][0]["export"]}, rproj)
    assert x3["status"] == "done", x3["checks"]
    assert OK("job.show", {"ref": res3["exports"][0]["job"]}, rproj)["result"]["cache_hits"] == 3
    plan = json.loads(next((rproj / "exports").rglob("plan.json")).read_text(encoding="utf-8"))
    assert plan["profile"]["final_speed"] == "fast"


def test_face_crop_profile_needs_the_model_and_falls_back_without_faces(rproj, OK, R, recomp_home):
    import shutil
    from pathlib import Path
    from recomp.render import faces
    assert "shorts-face" in [p["name"] for p in OK("profile.list", {}, rproj)]  # seeded into an existing project
    env = R("export.run", {"journey": "J1", "profiles": ["shorts-face"]}, rproj)
    assert not env["ok"] and env["error"]["code"] == "E_NOT_FOUND" and "face" in env["error"]["message"]
    real = Path.home() / ".recomp" / "models" / "yunet" / faces.MODEL_NAME
    if not real.exists():
        pytest.skip("face model not installed on this machine")
    dest = recomp_home / "models" / "yunet"
    dest.mkdir(parents=True)
    shutil.copy(real, dest / faces.MODEL_NAME)
    res = OK("export.run", {"journey": "J1", "profiles": ["shorts-face"]}, rproj)
    x = OK("export.show", {"ref": res["exports"][0]["export"]}, rproj)
    assert x["status"] == "done", x["checks"]  # the fixture has no faces: every slot used the blurred fill
    assert any(c["check"] == "frame size" and c["detail"] == "1080x1920" for c in x["checks"])


def test_transitions_and_single_cut_export(rproj, OK):
    OK("journey.transition", {"slot": "J1#2", "type": "fade", "dur": 0.5}, rproj)
    OK("journey.transition", {"slot": "J1#3", "type": "dip", "dur": 0.4}, rproj)
    res = OK("export.run", {"journey": "J1", "profiles": ["square"]}, rproj)
    x = OK("export.show", {"ref": res["exports"][0]["export"]}, rproj)
    assert x["status"] == "done", x["problems"]
    c = OK("export.cuts", {"cuts": ["C2"], "profile": "clip"}, rproj)
    y = OK("export.show", {"ref": c["exports"][0]["export"]}, rproj)
    assert y["status"] == "done", y["problems"]


def test_preview_is_small(rproj, OK):
    p = OK("preview", {"target": "J1", "profile": "shorts"}, rproj)
    x = OK("export.show", {"ref": p["export"]}, rproj)
    assert any(c["check"] == "frame size" and c["detail"] == "480x852" for c in x["checks"]), x["checks"]
