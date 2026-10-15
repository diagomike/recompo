import pytest
from fastapi.testclient import TestClient

from recomp.server import app as server
from tests.media import copy_clip

pytestmark = pytest.mark.e2e


@pytest.fixture
def client(proj, tmp_path, OK, monkeypatch):
    monkeypatch.setenv("RECOMP_JOBS", "inline")
    server._projects.clear()
    clip = copy_clip(tmp_path / "media", "clip.mp4")
    OK("source.add", {"target": str(clip), "jobs": ["audio", "peaks", "shots"]}, proj)
    return TestClient(server.app), str(proj)


def test_verb_as_user_and_room(client, OK):
    c, p = client
    env = c.post("/api/verb/cut.add", json={"project": p, "args": {"ref": "S1", "from": "2", "to": "5", "why": "x"}}).json()
    assert env["ok"] and env["data"]["by"] == "user"
    room = c.get(f"/api/room/S1?project={p}").json()
    assert room["source"]["has_media"] and len(room["segments"]) == 7 and room["cuts"][0]["ref"] == "C1"
    assert room["peaks"]["per_second"] == 20


def test_media_range(client):
    c, p = client
    r = c.get(f"/media/source/S1?project={p}", headers={"Range": "bytes=100-199"})
    assert r.status_code == 206 and len(r.content) == 100
    assert r.headers["content-range"].startswith("bytes 100-199/")
    assert c.get(f"/media/file?project={p}&path=..%2F..%2Fsecret").status_code in (403, 404)


def test_verbs_listing(client):
    c, _ = client
    data = c.get("/api/verbs").json()["data"]
    assert "cut" in data and any(v["verb"] == "cut.add" for v in data["cut"])
