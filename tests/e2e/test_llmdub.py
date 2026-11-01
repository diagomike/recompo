"""The LLM dubber end to end, offline: stub MT and a stub voice (tones whose length follows the text)."""

import json

import pytest

from recomp.core.project import Project
from tests.media import copy_clip

pytestmark = pytest.mark.e2e


@pytest.fixture
def lproj(proj, tmp_path, OK, monkeypatch):
    monkeypatch.setenv("RECOMP_JOBS", "inline")
    monkeypatch.setenv("RECOMP_TTS", "stub")
    monkeypatch.setenv("RECOMP_MT", "stub")
    monkeypatch.setenv("RECOMP_DUB_ROUNDTRIP", "0")
    clip = copy_clip(tmp_path / "media", "clip.mp4")
    OK("source.add", {"target": str(clip), "jobs": ["audio"], "dub_to": ["om"]}, proj)
    OK("cut.add", {"ref": "S1", "from": "1.8", "to": "6.5", "snap": "none", "why": "w"}, proj)
    OK("journey.new", {"title": "Heroes", "cuts": ["C1"]}, proj)
    # word timings with a pause in the middle of every line: two speech frames each
    db = Project(proj).db
    with db.op("test words", "machine") as tx:
        for s in db.all('SELECT id, start, "end", text FROM segment'):
            ws, mid = s["text"].split(), (s["start"] + s["end"]) / 2
            half = max(1, len(ws) // 2)
            for i, (w, a, b) in enumerate([(" ".join(ws[:half]), s["start"], mid - 0.25),
                                           (" ".join(ws[half:]) or "…", mid + 0.25, s["end"])]):
                tx.insert("word", {"segment_id": s["id"], "idx": i, "start": a, "end": b, "text": w}, log=False)
        tx.conn.execute("UPDATE transcript SET has_words=1")
    return proj


def test_source_side_route_through_fit_verify_and_export(lproj, OK):
    s = OK("dub.settings", {"target": "J1", "to": "om"}, lproj)
    plan = s["sources"][0]["plan"]
    assert plan["route"] == "source" and plan["writes"] == ["en"] and plan["back_translate"]
    assert s["sources"][0]["settings"]["targets"] == ["om"]

    one = OK("dub.understand", {"journey": "J1", "to": "om", "template": True, "limit": 1}, lproj)
    assert len(one["lines"]) == 1 and one["still_unmapped"] == one["of"]  # a whole film goes in batches
    t = OK("dub.understand", {"journey": "J1", "to": "om", "template": True}, lproj)
    assert t["lines"] and all("text" in l and len(l["frames"]) == 2 for l in t["lines"])  # English source: read directly
    maps = {l["key"]: {"best": l["text"], "confidence": "high",
                       "units": [{"id": "u1", "text": "first half", "tier": "core", "frame": 1},
                                 {"id": "u2", "text": "second half", "tier": "support", "frame": 2}]} for l in t["lines"]}
    OK("dub.understand", {"journey": "J1", "to": "om", "maps": maps}, lproj)

    w = OK("dub.write", {"journey": "J1", "to": "om", "template": True}, lproj)
    assert all(f["target_syllables"] > 0 for l in w["lines"] for f in l["frames"])
    opts = {}
    for l in w["lines"]:  # the stub voice speaks 15 characters a second; "[om] " is the stub MT's prefix
        per = {}
        for f in l["frames"]:
            n, us = max(2, int(f["dur"] * 15 * 0.95) - 5), [u["id"] for u in f["units"]]
            per[str(f["n"])] = [{"text": ("ok" + " ok" * 60)[:n], "lang": "en", "units": us},
                                {"text": ("no" + " no" * 60)[:n], "lang": "en", "units": us},
                                {"text": "a much longer option " * 6, "lang": "en", "units": us}]
        opts[l["key"]] = per
    OK("dub.write", {"journey": "J1", "to": "om", "options": opts}, lproj)

    fit = OK("dub.fit", {"journey": "J1", "to": "om"}, lproj)["result"]
    assert fit["written"] == len(w["lines"]) and fit["needs_check"] > 0  # Oromo is MT-only: checks are asked for

    v = OK("dub.verify", {"journey": "J1", "to": "om", "template": True}, lproj)
    assert v["checks"] and all(c["back_translations"] for c in v["checks"])
    first = v["checks"][0]
    checks = {c["id"]: {"covered": [u["id"] for u in c["units"]], "errors": []} for c in v["checks"]}
    checks[first["id"]] = {"covered": [], "errors": ["reversed polarity"]}
    OK("dub.verify", {"journey": "J1", "to": "om", "checks": checks}, lproj)
    fit2 = OK("dub.fit", {"journey": "J1", "to": "om"}, lproj)["result"]
    st = OK("dub.status", {"journey": "J1", "to": "om"}, lproj)
    line = next(r for r in st["per_line"] if r["key"] == first["key"])
    assert first["target"] not in line["text"].split(" | ")  # the erroneous option was routed around
    assert st["fitted"] == st["lines"]

    lines = OK("lang.lines", {"journey": "J1", "lang": "om"}, lproj)["lines"]
    seg = [l for l in lines if l["key"].startswith("seg:")]
    assert all(l["text"].startswith("[om]") and l["by"] for l in seg)

    # the export voices each frame at the speaker's own pause
    title = OK("lang.translate", {"journey": "J1", "to": "om", "template": True}, lproj)
    OK("lang.translate", {"journey": "J1", "to": "om", "translations": {l["key"]: "om " + l["text"] for l in title["lines"]
                                                                           if not l["key"].startswith("seg:")}}, lproj)
    res = OK("export.run", {"journey": "J1", "profiles": ["landscape"], "langs": ["om"]}, lproj)
    x = OK("export.show", {"ref": res["exports"][0]["export"]}, lproj)
    assert x["status"] == "done", [c for c in x["checks"] if not c["ok"]]
    from pathlib import Path
    dub = json.loads(next(Path(lproj).rglob("dub.json")).read_text(encoding="utf-8"))
    assert dub["lines"] == 2 * len(seg)  # two speech frames per line, voiced separately


def test_target_direct_and_multi_middle_views(lproj, OK):
    OK("dub.settings", {"at": "S1", "route": "multi", "middle": ["en", "es"], "views_mt": ["stub", "stub"]}, lproj)
    t = OK("dub.understand", {"journey": "J1", "to": "fr", "template": True}, lproj)
    v = t["lines"][0]["views"]
    assert [x["lang"] for x in v] == ["en", "es"] and v[1]["whole"].startswith("[es]") and len(v[1]["frames"]) == 2
    OK("dub.settings", {"at": "J1", "route": "tgt-en"}, lproj)
    s = OK("dub.settings", {"target": "J1", "to": "fr"}, lproj)
    assert s["sources"][0]["plan"]["writes"] == ["fr"] and s["sources"][0]["from"]["route"] == "journey J1"
