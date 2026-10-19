"""The hub service and the studio's hub verbs, end to end (hub served in-process)."""

import httpx
import pytest
from fastapi.testclient import TestClient

from hub import app as hubapp
from recomp.verbs import hub as hubverbs
from tests.media import copy_clip

pytestmark = pytest.mark.e2e


@pytest.fixture
def hub(tmp_path, monkeypatch):
    hubapp._state.update({"conn": None, "data": tmp_path / "hubdata"})
    client = TestClient(hubapp.app)

    def request(method, url, json=None, headers=None, timeout=None):
        path = url.split("8790", 1)[1]
        return client.request(method, path, json=json, headers=headers)

    monkeypatch.setattr(hubverbs.httpx, "request", request)
    yield client
    hubapp._state.update({"conn": None, "data": None})


@pytest.fixture
def hproj(proj, tmp_path, OK, monkeypatch):
    monkeypatch.setenv("RECOMP_JOBS", "inline")
    clip = copy_clip(tmp_path / "media", "clip.mp4")
    OK("source.add", {"target": str(clip), "jobs": ["audio"]}, proj)
    OK("cut.add", {"ref": "S1", "from": "11.8", "to": "17.0", "snap": "none", "why": "thesis", "tags": ["heroes"]}, proj)
    OK("cut.add", {"ref": "S1", "from": "1.8", "to": "6.5", "snap": "none", "why": "fall", "tags": ["rising"]}, proj)
    OK("journey.new", {"title": "Heroes and falls", "cuts": ["C1", "C2"]}, proj)
    return proj


def login(OK, handle, register=True):
    return OK("hub.login", {"handle": handle, "password": f"{handle}-test-pass", "register": register})


PUBLIC = {"journey": "J1", "visibility": "public", "confirm": True}  # the user answered yes (D-23)


def test_publish_vote_comment_follow_fork(hub, hproj, OK, R):
    login(OK, "ada")
    pub = OK("hub.publish", PUBLIC, hproj, actor="user")
    assert pub["url"].startswith("http://127.0.0.1:8790/r/") and pub["version"] == 1
    again = OK("hub.publish", PUBLIC, hproj, actor="user")
    assert again["version"] == 2 and again["url"] == pub["url"]
    rid = pub["url"].rsplit("/", 1)[1]
    login(OK, "ben")
    v = OK("hub.vote", {"recipe": pub["url"], "value": "up"})
    assert v["score"] == 1
    OK("hub.comment", {"recipe": rid, "text": "Great pairing of lines"})
    c = OK("hub.comments", {"recipe": rid})
    OK("hub.comment", {"recipe": rid, "text": "agreed", "reply_to": c[0]["id"]})
    assert len(OK("hub.comments", {"recipe": rid})) == 2
    OK("hub.follow", {"handle": "ada"})
    feed = OK("hub.feed", {"kind": "following"})
    assert feed[0]["id"] == rid and feed[0]["by"] == "ada"
    trending = OK("hub.feed", {"kind": "trending", "tag": "heroes"})
    assert trending[0]["id"] == rid
    # Ben forks it into his own project copy: same slots, linked back.
    forked = OK("hub.fork", {"recipe": rid}, hproj)
    show_a = OK("recipe.show", {"journey": "J1"}, hproj)
    show_b = OK("recipe.show", {"journey": forked["journey"]}, hproj)
    assert [(s["in"], s["out"]) for s in show_a["slots"]] == [(s["in"], s["out"]) for s in show_b["slots"]]
    profile = hub.get("/api/hub/users/ada").json()
    assert profile["followers"] == 1 and len(profile["recipes"]) == 1


def test_source_page_heatmap_and_post_links(hub, hproj, OK):
    login(OK, "cleo")
    pub = OK("hub.publish", PUBLIC, hproj, actor="user")
    rid = pub["url"].rsplit("/", 1)[1]
    r = hub.get(f"/api/hub/recipes/{rid}").json()
    key = r["sources"][0]["key"]
    page = hub.get(f"/api/hub/sources/{key}").json()
    assert page["recipes"][0]["id"] == rid and sum(page["heat"]) > 0
    lp = OK("hub.link-post", {"journey": "J1", "url": "https://example.com/watch/123"}, hproj)
    assert lp["on_hub"] is True
    assert hub.get(f"/api/hub/recipes/{rid}").json()["links"][0]["platform"] == "example.com"


def test_privacy_and_guards(hub, hproj, OK, R):
    login(OK, "dan")
    pub = OK("hub.publish", {"journey": "J1", "visibility": "private"}, hproj)
    rid = pub["url"].rsplit("/", 1)[1]
    assert hub.get(f"/api/hub/recipes/{rid}").status_code == 404  # anonymous can't see it
    assert hub.post("/api/hub/recipes", json={"recipe": {}}).status_code == 401
    bad = {"recipe": "recomposer/1", "title": "x", "sources": {"S1": {"kind": "file", "title": "x", "path": "C:\\secret\\a.mp4"}},
           "slots": [{"source": "S1", "in": 0, "out": 1}]}
    tok = hub.post("/api/hub/auth/login", json={"handle": "dan", "password": "dan-test-pass"}).json()["token"]
    r = hub.post("/api/hub/recipes", json={"recipe": bad}, headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 400 and "local file paths" in r.json()["detail"]
    env = R("hub.login", {"handle": "eve", "password": "eve-test-pass", "register": True, "url": "https://hub.example.org"})
    assert env["error"]["code"] in ("E_PRECEDENCE", "E_NETWORK")


def test_public_needs_the_users_permission_for_private_sources(hub, hproj, OK, R):
    login(OK, "fay")
    # Private by default, and private needs no question.
    pub = OK("hub.publish", {"journey": "J1"}, hproj)
    assert pub["visibility"] == "private" and pub["permission"] is None
    # Public with a private source: the agent gets the consequences and the question, and cannot answer it.
    e = R("hub.publish", {"journey": "J1", "visibility": "public"}, hproj)
    assert e["error"]["code"] == "E_CONFIRM" and e["error"]["data"]["question"] == "Do you have permission to share this?"
    assert e["error"]["data"]["sources"][0]["ref"] == "S1" and "public page" in e["error"]["data"]["consequences"][0]
    assert R("hub.publish", {"journey": "J1", "visibility": "public", "confirm": True}, hproj)["error"]["code"] == "E_CONFIRM"
    # The user answers yes: published, the answer and time saved on the version.
    pub = OK("hub.publish", {"journey": "J1", "visibility": "public", "confirm": True}, hproj, actor="user")
    assert pub["permission"]["answer"] == "yes" and pub["permission"]["by"] == "user"
    rid = pub["url"].rsplit("/", 1)[1]
    tok = hub.post("/api/hub/auth/login", json={"handle": "fay", "password": "fay-test-pass"}).json()["token"]
    seen = hub.get(f"/api/hub/recipes/{rid}", headers={"Authorization": f"Bearer {tok}"}).json()
    assert seen["permission"]["private_sources"][0]["ref"] == "S1" and seen["version"] == 2
    assert "permission" not in hub.get(f"/api/hub/recipes/{rid}").json()  # only the owner sees their answer
    # A source with verified permission asks nothing.
    OK("source.rights", {"ref": "S1", "status": "permitted", "evidence": "https://example.org/ok"}, hproj)
    assert OK("hub.publish", {"journey": "J1", "visibility": "public"}, hproj)["permission"] is None
