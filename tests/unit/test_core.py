import time

import pytest

from recomp.core import ids, timecode
from recomp.core.project import Project
from recomp.envelope import RecompError


def test_timecode_parse_forms():
    assert timecode.parse("4323.4") == pytest.approx(4323.4)
    assert timecode.parse("01:12:03.4") == pytest.approx(4323.4)
    assert timecode.parse("12:03") == pytest.approx(723)
    assert timecode.parse("72m3.4s") == pytest.approx(4323.4)
    assert timecode.parse("1h2m") == pytest.approx(3720)
    assert timecode.parse("00:01:10,592") == pytest.approx(70.592)
    assert timecode.parse(None) is None
    with pytest.raises(timecode.TimecodeError):
        timecode.parse("soon")


def test_timecode_format():
    assert timecode.clock(3723.45) == "01:02:03.5"
    assert timecode.srt_clock(70.592) == "00:01:10,592"
    assert timecode.ass_clock(70.592) == "0:01:10.59"


def test_ulid_sortable_and_unique():
    a = [ids.ulid() for _ in range(2000)]
    assert len(set(a)) == 2000
    assert a == sorted(a)
    assert abs(ids.ulid_time_ms(a[0]) - time.time() * 1000) < 5000


def _db(proj):
    return Project(proj).db


def test_insert_assigns_refs_and_logs(proj):
    db = _db(proj)
    with db.op("t.add", "agent") as tx:
        s = tx.insert("source", {"kind": "file", "uri": "x.mp4", "title": "X"})
        c = tx.insert("cut", {"source_id": s["id"], "start": 1, "end": 2, "title": "one"})
        ch = tx.insert("chapter", {"source_id": s["id"], "start": 0, "end": 5}, ref_kind=s["ref"] + ".c")
    assert s["ref"] == "S1" and c["ref"] == "C1" and ch["ref"] == "S1.c1"
    assert c["prov"]["title"] == "agent"
    op = db.rows("op")[-1]
    assert op["verb"] == "t.add" and len(op["changes"]) == 3


def test_precedence_blocks_lower_actor(proj):
    db = _db(proj)
    with db.op("t.add", "agent") as tx:
        s = tx.insert("source", {"kind": "file", "uri": "x", "title": "X"})
        c = tx.insert("cut", {"source_id": s["id"], "start": 1, "end": 2, "title": "agent title"})
    with db.op("t.edit", "user") as tx:
        tx.update("cut", c["id"], {"title": "user title"})
    with pytest.raises(RecompError) as e:
        with db.op("t.edit", "agent") as tx:
            tx.update("cut", c["id"], {"title": "agent again"})
    assert e.value.code == "E_PRECEDENCE"
    # Other fields stay writable by the agent.
    with db.op("t.edit", "agent") as tx:
        tx.update("cut", c["id"], {"why": "because"})
    with pytest.raises(RecompError):
        with db.op("t.del", "agent") as tx:
            tx.delete("cut", c["id"])
    with pytest.raises(RecompError):
        with db.op("t.edit", "machine") as tx:
            tx.update("cut", c["id"], {"why": "machine"})
    assert db.get("cut", c["id"])["title"] == "user title"


def test_undo_redo_roundtrip(proj):
    db = _db(proj)
    with db.op("t.add", "agent") as tx:
        s = tx.insert("source", {"kind": "file", "uri": "x", "title": "X"})
    with db.op("t.add", "agent") as tx:
        c = tx.insert("cut", {"source_id": s["id"], "start": 1, "end": 2, "title": "a"})
    with db.op("t.edit", "agent") as tx:
        tx.update("cut", c["id"], {"title": "b"})
    db.undo("agent")
    assert db.get("cut", c["id"])["title"] == "a"
    db.undo("agent")
    assert db.get("cut", c["id"]) is None
    db.redo("agent")
    assert db.get("cut", c["id"])["title"] == "a"
    db.redo("agent")
    assert db.get("cut", c["id"])["title"] == "b"
    with pytest.raises(RecompError):
        db.redo("agent")


def test_undo_restores_cascaded_children(proj):
    db = _db(proj)
    with db.op("t", "agent") as tx:
        s = tx.insert("source", {"kind": "file", "uri": "x", "title": "X"})
        c = tx.insert("cut", {"source_id": s["id"], "start": 1, "end": 2})
        j = tx.insert("journey", {"title": "J"})
        tx.insert("slot", {"journey_id": j["id"], "pos": 1, "cut_id": c["id"]})
        tx.insert("overlay", {"journey_id": j["id"], "kind": "title", "text": "hi"})
    with db.op("t.del", "agent") as tx:
        tx.delete("journey", j["id"])
    assert db.scalar("SELECT COUNT(*) FROM slot") == 0
    db.undo("agent")
    assert db.scalar("SELECT COUNT(*) FROM slot") == 1
    assert db.scalar("SELECT COUNT(*) FROM overlay") == 1


def test_undo_refuses_when_row_changed_since(proj):
    db = _db(proj)
    with db.op("t", "agent") as tx:
        s = tx.insert("source", {"kind": "file", "uri": "x", "title": "X"})
    with db.op("t", "agent") as tx:
        c = tx.insert("cut", {"source_id": s["id"], "start": 1, "end": 2, "title": "a"})
    # A change outside the op log (e.g. a direct write) makes undo unsafe.
    db.conn.execute("UPDATE cut SET title='zzz' WHERE id=?", (c["id"],))
    with pytest.raises(RecompError) as e:
        db.undo("agent")
    assert e.value.code == "E_CONFLICT"


def test_agent_cannot_undo_user_op(proj):
    db = _db(proj)
    with db.op("t", "user") as tx:
        tx.insert("source", {"kind": "file", "uri": "x", "title": "X"})
    with pytest.raises(RecompError) as e:
        db.undo("agent")
    assert e.value.code == "E_PRECEDENCE"


def test_events_written_per_op(proj):
    db = _db(proj)
    before = db.scalar("SELECT COUNT(*) FROM event")
    with db.op("t", "agent") as tx:
        tx.insert("source", {"kind": "file", "uri": "x", "title": "X"})
    assert db.scalar("SELECT COUNT(*) FROM event") == before + 1


def test_fts_follows_segment_writes(proj):
    db = _db(proj)
    with db.op("t", "agent") as tx:
        s = tx.insert("source", {"kind": "file", "uri": "x", "title": "X"})
        t = tx.insert("transcript", {"source_id": s["id"], "origin": "sidecar"}, ref_kind="S1.t")
        seg = tx.insert("segment", {"transcript_id": t["id"], "idx": 0, "start": 0, "end": 1,
                                    "text": "Why so serious?"}, log=False)
    hits = db.all("SELECT rowid FROM segment_fts WHERE segment_fts MATCH 'serious'")
    assert [h[0] for h in hits] == [seg["id"]]
    db.conn.execute("UPDATE segment SET text='Let us smile' WHERE id=?", (seg["id"],))
    assert db.all("SELECT rowid FROM segment_fts WHERE segment_fts MATCH 'serious'") == []
