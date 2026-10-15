"""Render jobs: exports and previews."""

from __future__ import annotations

import time
from pathlib import Path

from ..envelope import RecompError
from ..render import checks, engine, plan as P, profiles
from .jobs import JobCtx, task


def build_plan(db, project, exp: dict, overrides: dict | None = None) -> dict:
    prof_row = db.one("SELECT settings FROM profile WHERE name=?", (exp["profile"],))
    if prof_row is None:
        raise RecompError("E_NOT_FOUND", f"profile {exp['profile']!r} not found")
    import json
    settings = json.loads(prof_row[0])
    settings.update(overrides or {})
    if exp.get("journey_id"):
        j = db.get("journey", exp["journey_id"])
        return P.build(db, project, journey=j, profile=settings, lang=exp["lang"])
    cut = db.get("cut", exp["cut_id"])
    return P.build(db, project, cuts=[cut], profile=settings, lang=exp["lang"])


@task("export", lane="cpu")
def job_export(ctx: JobCtx):
    db = ctx.db
    exp = db.get("export", ctx.params["export"])
    if exp is None:
        raise RecompError("E_NOT_FOUND", "export row vanished")
    overrides = ctx.params.get("overrides") or {}
    plan = build_plan(db, ctx.project, exp, overrides)
    if ctx.params.get("dub"):
        from ..lang import dub
        plan = dub.apply_to_plan(ctx.project, db, plan, exp, ctx)
    folder = Path(exp["folder"])
    with db.op("export.start", "machine") as tx:
        tx.update("export", exp["id"], {"status": "rendering", "recipe_hash": plan["recipe_hash"]}, log=False)
    rc = engine.Ctx(progress=ctx.progress, cancelled=ctx.cancelled, log=ctx.log)
    result = engine.render(ctx.project, plan, folder, rc)
    ctx.log(f"rendered in {result['seconds']}s, cache hits {result['slot_cache_hits']}/{result['slots']}")
    chk = checks.run(folder, plan)
    status = "done" if chk["ok"] else "done-with-problems"
    with db.op("export.done", "machine") as tx:
        tx.update("export", exp["id"], {"status": status, "outputs": result, "checks": chk}, log=False)
        tx.event("export", {"export": exp["ref"], "status": status})
    return {"export": exp["ref"], "status": status, "video": result["video"], "seconds": result["seconds"],
            "cache_hits": result["slot_cache_hits"], "problems": [c for c in chk["checks"] if not c["ok"]]}
