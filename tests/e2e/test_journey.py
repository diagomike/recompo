import json

import pytest

from recomp.compose import recipe as R
from tests.media import copy_clip

pytestmark = pytest.mark.e2e


@pytest.fixture
def jproj(proj, tmp_path, OK, monkeypatch):
    monkeypatch.setenv("RECOMP_JOBS", "inline")
    clip = copy_clip(tmp_path / "media", "clip.mp4")
    OK("source.add", {"target": str(clip), "jobs": ["audio"]}, proj)
    OK("source.rights", {"ref": "S1", "owner": "Test Studio"}, proj)
    for a, b in [(1.5, 4), (6.5, 9.5), (11.5, 16.5), (18.5, 22), (34.5, 37)]:
        OK("cut.add", {"ref": "S1", "from": str(a), "to": str(b), "snap": "none", "why": "w", "people": ["Narrator"]}, proj)
    return proj


def test_build_reorder_and_recipe(jproj, OK):
    j = OK("journey.new", {"title": "Fall and rise", "intent": "test", "cuts": ["C1", "C2", "C3"]}, jproj)
    assert j["ref"] == "J1" and [s["slot"] for s in j["slots"]] == ["J1#1", "J1#2", "J1#3"]
    OK("journey.add", {"journey": "J1", "cuts": ["C5"], "at": 1, "section": "Opening"}, jproj)
    show = OK("journey.show", {"journey": "J1"}, jproj)
    assert [s["cut"] for s in show["slots"]] == ["C5", "C1", "C2", "C3"]
    assert show["slots"][0]["section"] == "Opening"
    OK("journey.move", {"slot": "J1#1", "to": 4}, jproj)
    OK("journey.reorder", {"journey": "J1", "order": [4, 1, 2, 3]}, jproj)
    show = OK("journey.show", {"journey": "J1"}, jproj)
    assert [s["cut"] for s in show["slots"]] == ["C5", "C1", "C2", "C3"]
    OK("journey.trim-slot", {"slot": "J1#4", "start": "+1", "end": "-1"}, jproj)
    OK("journey.transition", {"slot": "J1#2", "type": "fade", "dur": 0.5}, jproj)
    rec = OK("recipe.show", {"journey": "J1"}, jproj)
    assert R.validate(rec) == []
    assert rec["slots"][3]["in"] == pytest.approx(12.5) and rec["slots"][3]["out"] == pytest.approx(15.5)
    assert rec["credits"][0]["text"].endswith("© Test Studio")
    # duration: 2.5 + 2.5 + 3 + 3 - 0.5 fade overlap
    assert rec["duration"] == pytest.approx(10.5)
    mirror = list((jproj / "recipes").glob("J1-*.recipe.json"))
    assert mirror and json.loads(mirror[0].read_text(encoding="utf-8"))["hash"] == rec["hash"]


def test_overlays_and_lower_thirds(jproj, OK):
    OK("journey.new", {"title": "T", "cuts": ["C1", "C2"]}, jproj)
    OK("overlay.add", {"target": "J1", "kind": "title", "text": "Fall\nand rise"}, jproj)
    OK("overlay.add", {"target": "J1#2", "kind": "quote", "text": "pick ourselves up", "at": "0.5"}, jproj)
    made = OK("overlay.auto-lower-thirds", {"journey": "J1"}, jproj)
    assert len(made) == 2 and made[0]["text"].startswith("Narrator\nclip")
    again = OK("overlay.auto-lower-thirds", {"journey": "J1"}, jproj)
    assert len(OK("overlay.list", {"journey": "J1"}, jproj)) == 4  # replaced, not duplicated
    OK("journey.remove", {"slot": "J1#2"}, jproj)
    assert len(OK("overlay.list", {"journey": "J1"}, jproj)) == 2  # slot overlays went with the slot
    OK("op.undo", {}, jproj)
    assert len(OK("overlay.list", {"journey": "J1"}, jproj)) == 4


def test_cut_in_use_is_protected_and_duplicate(jproj, OK, R):
    OK("journey.new", {"title": "T", "cuts": ["C1"]}, jproj)
    assert R("cut.remove", {"ref": "C1"}, jproj)["error"]["code"] == "E_CONFLICT"
    d = OK("journey.duplicate", {"journey": "J1"}, jproj)
    assert d["ref"] == "J2" and len(d["slots"]) == 1
    v = OK("journey.validate", {"journey": "J1"}, jproj)
    assert v["ok"], v


def test_export_interchange_and_import_roundtrip(jproj, OK, tmp_path):
    OK("journey.new", {"title": "Round trip", "cuts": ["C3", "C1"]}, jproj)
    OK("overlay.add", {"target": "J1", "kind": "title", "text": "Hello"}, jproj)
    for fmt in ("json", "edl", "otio"):
        out = OK("recipe.export", {"journey": "J1", "format": fmt}, jproj)
        assert out["bytes"] > 100
    edl = (jproj / "recipes").glob("J1-*.edl").__next__().read_text()
    assert "001  S1" in edl and "FROM CLIP NAME: clip" in edl
    rec_path = next((jproj / "recipes").glob("J1-*.recipe.json"))
    imp = OK("recipe.import", {"file": str(rec_path)}, jproj)
    assert imp["journey"] == "J2" and imp["sources"] == {"S1": "S1"}  # matched by fingerprint
    a = OK("recipe.show", {"journey": "J1"}, jproj)
    b = OK("recipe.show", {"journey": "J2"}, jproj)
    assert [(s["in"], s["out"]) for s in a["slots"]] == [(s["in"], s["out"]) for s in b["slots"]]


def test_from_search_drafts_cuts(jproj, OK):
    d = OK("journey.from-search", {"query": "world burn villain", "limit": 2, "min_s": 3}, jproj)
    assert d["ref"] == "J1" and 1 <= len(d["slots"]) <= 2
