"""P17c: rights statuses, the posting gate, the queue, your channel's numbers (read-only)."""

from __future__ import annotations

import time

from recomp.core.project import Project


def finished_export(root, tmp_path, creator="Alex O'Connor"):
    """A project with one link source, a cut, a journey and a finished export (rows only; no rendering)."""
    video = tmp_path / "out" / "video.mp4"
    video.parent.mkdir(parents=True)
    video.write_bytes(b"\x00" * 64)
    (video.parent / "description.txt").write_text("Why AI\n\nSources:\n- \"Why AI Will Never Be Conscious\", Alex O'Connor\n",
                                                  encoding="utf-8")
    proj = Project(root)
    db = proj.db
    with db.op("test", "agent") as tx:
        s = tx.insert("source", {"kind": "link", "uri": "https://www.youtube.com/watch?v=lsi8T_WtLnE", "platform": "youtube",
                                 "platform_id": "lsi8T_WtLnE", "title": "Why AI Will Never Be Conscious", "creator": creator,
                                 "rights": {"owner": creator}})
        c = tx.insert("cut", {"source_id": s["id"], "start": 10.0, "end": 40.0})
        j = tx.insert("journey", {"title": "Why AI"})
        tx.insert("slot", {"journey_id": j["id"], "pos": 1, "cut_id": c["id"]})
        x = tx.insert("export", {"journey_id": j["id"], "profile": "shorts", "status": "done", "folder": str(video.parent),
                                 "outputs": {"video": str(video)}})
    proj.close()
    return s["ref"], x["ref"]


def test_posting_gate_queue_and_link(proj, tmp_path, OK, R):
    src, x = finished_export(proj, tmp_path)
    e = R("post.plan", {"ref": x}, proj)
    assert e["error"]["code"] == "E_RIGHTS" and e["error"]["data"]["private"][0]["ref"] == src
    bad = R("source.rights", {"ref": src, "status": "permitted"}, proj)
    assert bad["error"]["code"] == "E_INVALID" and "evidence" in bad["error"]["message"]
    OK("source.rights", {"ref": src, "status": "permitted", "evidence": "https://example.org/permission"}, proj)

    p = OK("post.plan", {"ref": "J1", "profile": "shorts", "at": "2026-10-20 18:00"}, proj)
    assert p["ref"] == "Q1" and p["status"] == "planned" and p["at"] == "2026-10-20 18:00" and p["export"] == x
    assert p["credits"] == [f"{src} Alex O'Connor (permitted)"]
    ch = OK("channel.show", {})
    assert ch["placeholder"] and ch["posts"] == {"planned": 1}
    OK("channel.set", {"name": "Ideas in a minute", "handle": "ideasinaminute"})
    assert OK("channel.show", {})["url"] == "https://www.youtube.com/@ideasinaminute"

    o = OK("post.open", {"ref": "Q1"})
    assert o["status"] == "opened" and "Alex O'Connor" in o["description"] and o["upload_page"].startswith("https://studio.youtube")
    assert [q["ref"] for q in OK("post.queue", {})] == ["Q1"]
    done = OK("post.link", {"ref": "Q1", "url": "https://youtube.com/shorts/abcdefghijk"})
    assert done["status"] == "posted"
    assert OK("journey.show", {"journey": "J1"}, proj)["links"]["posts"][0]["url"].endswith("abcdefghijk")
    assert OK("post.queue", {}) == [] and len(OK("post.queue", {"status": "posted"})) == 1

    csv = tmp_path / "Table data.csv"
    csv.write_text("Content,Video title,Video publish time,Duration,Views,Watch time (hours),Subscribers,Impressions,"
                   "Impressions click-through rate (%)\nTotal,,,,1200,30.5,12,9000,5.1\n"
                   "abcdefghijk,Why AI,\"Oct 20, 2026\",58,1200,30.5,12,9000,5.1\n", encoding="utf-8")
    st = OK("channel.stats", {"csv": str(csv)})
    assert st["totals"]["views"] == 1200 and st["posts"][0]["post"] == "Q1" and st["posts"][0]["views"] == 1200


def test_credits_added_when_the_description_lacks_a_creator(proj, tmp_path, OK):
    src, x = finished_export(proj, tmp_path, creator="Lex Fridman")
    OK("source.rights", {"ref": src, "status": "campaign", "evidence": "https://example.org/program-terms"}, proj)
    p = OK("post.plan", {"ref": x}, proj)
    o = OK("post.open", {"ref": p["ref"]})
    assert "Credits: Why AI Will Never Be Conscious by Lex Fridman" in o["description"]
    OK("post.cancel", {"ref": p["ref"]})
    assert OK("post.queue", {}) == []
    OK("op.undo", {"studio": True})
    assert OK("post.queue", {})[0]["status"] == "opened"
