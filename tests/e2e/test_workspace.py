"""P16: the workspace verbs the viewer is drawn from, and the agent's side of every viewer action."""

import pytest
from fastapi.testclient import TestClient

from recomp.cli import cli_line
from recomp.server import app as server
from tests.media import copy_clip

pytestmark = pytest.mark.e2e


@pytest.fixture
def two(proj, tmp_path, OK, monkeypatch):
    monkeypatch.setenv("RECOMP_JOBS", "inline")
    monkeypatch.setenv("RECOMP_NO_REVEAL", "1")
    media = tmp_path / "media"
    a = copy_clip(media, "clip.mp4")
    b = copy_clip(media, "dialog_a.mp4", srt="dialog_a.srt")
    for f in (a, b):
        OK("source.add", {"target": str(f), "jobs": ["audio"]}, proj)
    return proj, media


def test_checklist_walks_the_project(proj, OK, two):
    p, _ = two
    steps = {s["key"]: s for s in OK("project.checklist", {}, p)["steps"]}
    assert steps["sources"]["state"] == "done" and steps["transcripts"]["state"] == "done"
    assert steps["cuts"]["state"] == "todo"
    data = OK("project.checklist", {}, p)
    assert data["next"] == "cuts" and set(data["folders"]) == {"sources", "recipes", "exports"}
    OK("cut.add", {"ref": "S1", "from": "12", "to": "16.5", "snap": "none", "why": "w"}, p)
    OK("cut.add", {"ref": "S2", "from": "1", "to": "9", "snap": "none", "why": "w"}, p)
    OK("journey.new", {"title": "Two sources", "cuts": ["C2", "C1"]}, p)
    steps = {s["key"]: s for s in OK("project.checklist", {}, p)["steps"]}
    assert steps["cuts"]["detail"] == "2 cut(s) from 2 source(s)" and steps["journeys"]["state"] == "done"
    assert any(a.get("params", {}).get("journey") == "J1" for a in steps["exports"]["actions"])


def test_browse_and_reveal(proj, OK, R, two):
    p, media = two
    b = OK("source.browse", {"path": str(media)})
    assert b["media"] == 2 and {f["kind"] for f in b["files"]} == {"media", "subtitle"} and b["parent"]
    assert OK("project.reveal", {"what": "exports"}, p)["opened"].endswith("exports")
    assert R("project.reveal", {"what": "../.."}, p)["error"]["code"] == "E_INVALID"


def test_cut_list_filters_and_journeys(proj, OK, two):
    p, _ = two
    OK("cut.add", {"ref": "S1", "from": "12", "to": "16.5", "snap": "none", "why": "w"}, p)
    OK("cut.add", {"ref": "S2", "from": "1", "to": "20", "snap": "none", "why": "w"}, p)
    OK("journey.new", {"title": "J", "cuts": ["C2"]}, p)
    assert [c["ref"] for c in OK("cut.list", {"min": 10}, p)] == ["C2"]
    assert [c["ref"] for c in OK("cut.list", {"max": 10}, p)] == ["C1"]
    assert [c["ref"] for c in OK("cut.list", {"journey": "J1"}, p)] == ["C2"]
    c = OK("cut.list", {"by": "agent"}, p)
    assert len(c) == 2 and c[1]["journeys"] == ["J1"] and c[0]["source_title"]


def test_ui_show_views_filters_and_handed_actions(proj, OK, two):
    p, _ = two
    s = OK("ui.show", {"ref": "Cuts", "filter": "source=S2&min=5", "highlight": "journey.add"}, p)
    assert s["ref"] == "cuts" and s["filter"] == {"source": "S2", "min": "5"} and s["highlight"] == "journey.add"
    OK("ui.select", {"refs": ["C1"]}, p)
    n = OK("ui.note", {"text": "please", "verb": "export.run", "args": {"journey": "J1", "profiles": ["shorts"]}}, p,
           actor="user")
    assert n["request"]["cli"] == "recomp export run J1 --profiles shorts" and n["selection"]["refs"] == ["C1"]
    env = __import__("recomp.registry", fromlist=["run"]).run("context", {}, project_arg=str(p))
    assert env["next"][0].startswith("recomp export run J1 --profiles shorts")


def test_cli_line_and_op_log(proj, OK, two):
    p, _ = two
    assert cli_line("cut.add", {"ref": "S1", "from": "12", "to": "16", "title": "Why so serious", "tags": ["a", "b"]}) == \
        'recomp cut add S1 --from 12 --to 16 --title "Why so serious" --tags a,b'
    assert cli_line("journey.add", {"journey": "J1", "cuts": ["C3", "C9"], "at": 2}) == "recomp journey add J1 C3 C9 --at 2"
    assert cli_line("lang.edit", {"journey": "J1", "lang": "am", "lines": {"seg:1": "x"}}).endswith("--input <file.json>")
    assert cli_line("speaker.assign", {"ref": "S1", "dry_run": True, "by": "prefix"}) == "recomp speaker assign S1 --by prefix --dry-run"
    OK("cut.add", {"ref": "S1", "from": "1", "to": "3", "snap": "none", "why": "w"}, p)
    log = OK("op.log", {"limit": 1}, p)
    assert log[0]["cli"] == "recomp cut add S1 --from 1 --to 3 --snap none --why w"


def test_server_envelope_carries_cli_and_room_names_voices(proj, OK, two):
    p, _ = two
    server._projects.clear()
    c = TestClient(server.app)
    env = c.post("/api/verb/speaker.assign", json={"project": str(p), "args": {"ref": "S2", "name": "Host", "lines": "0-1"}}).json()
    assert env["ok"] and env["cli"] == "recomp speaker assign S2 Host --lines 0-1"
    assert c.post("/api/cli", json={"verb": "cut.remove", "args": {"ref": "C1"}}).json()["cli"] == "recomp cut remove C1"
    room = c.get(f"/api/room/S2?project={p}").json()
    assert room["voices"]["Host"]["name"] == "Host" and room["people"][0]["name"] == "Host"
    assert room["transcripts"][0]["primary"] is True


def test_google_drafts_belong_to_the_machine(proj, OK, two, monkeypatch):
    p, _ = two
    OK("cut.add", {"ref": "S1", "from": "12", "to": "16.5", "snap": "none", "why": "w"}, p)
    OK("journey.new", {"title": "Heroes", "cuts": ["C1"]}, p)
    from recomp.lang import google

    monkeypatch.setattr(google.Translator, "translate", lambda self, items: {i["id"]: "brouillon " + i["text"] for i in items})
    OK("lang.translate", {"journey": "J1", "to": "fr", "engine": "google"}, p, actor="user")
    lines = OK("lang.lines", {"journey": "J1", "lang": "fr"}, p)["lines"]
    assert {line["by"] for line in lines} == {"google"}
    key = [line["key"] for line in lines if line["kind"] == "segment"][0]
    r = OK("lang.edit", {"journey": "J1", "lang": "fr", "key": key, "text": "Mieux."}, p)  # the agent may refine it
    assert r["written"] == 1 and not r["kept_users"]


def test_link_source_filmstrip_from_fetched_video(proj, OK, two):
    """A link source with its video fetched gets frames and a waveform like a local file (P16 room lanes)."""
    import json as _json
    import time as _time

    from recomp.core import project as P
    from recomp.core.ids import ulid
    p, media = two
    db = P.resolve(str(p)).db
    with db.op("test", "machine") as tx:
        tx.conn.execute("UPDATE source SET kind='link', path=NULL, meta=? WHERE ref='S1'", (_json.dumps({}),))
        sid = tx.conn.execute("SELECT id FROM source WHERE ref='S1'").fetchone()[0]
        tx.conn.execute("INSERT INTO asset(id, source_id, role, path, info, created_at) VALUES(?,?,?,?,?,?)",
                        (ulid(), sid, "video", str(media / "clip.mp4"), "{}", _time.time()))
    OK("source.process", {"ref": "S1", "jobs": ["thumbs"], "force": True}, p)
    st = OK("source.status", {}, p)
    assert {s["ref"]: s["status"].get("thumbs") for s in st}["S1"] == "done"
    assert any((p / "cache" / "thumbs" / "S1").glob("sheet_*.jpg"))
