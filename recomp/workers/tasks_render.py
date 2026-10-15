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
    try:
        return _export(ctx)
    except Exception as exc:
        msg = exc.message if isinstance(exc, RecompError) else f"{type(exc).__name__}: {exc}"
        exp = ctx.db.get("export", ctx.params["export"])
        if exp is not None:
            with ctx.db.op("export.failed", "machine") as tx:
                tx.update("export", exp["id"], {"status": "failed", "checks": {"ok": False, "error": msg[:500], "checks": []}},
                          log=False)
                tx.event("export", {"export": exp["ref"], "status": "failed"})
        raise


def _export(ctx: JobCtx):
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
    if plan.get("dub"):
        d = plan["dub"]
        over = d.get("overflow") or []
        chk["checks"].append({"check": "dub fit", "ok": not over,
                              "detail": f"{d['lines']} lines, {d['sped_up']} sped up, {len(over)} overflowing ({d['backend']} {d['voice']}, {d['mode']})"})
        import os
        if not ctx.params.get("preview") and not ctx.params.get("skip_roundtrip") and os.environ.get("RECOMP_DUB_ROUNDTRIP") != "0":
            from ..lang import dubcheck
            try:
                rt = dubcheck.check(folder, plan, log=ctx.log)
            except Exception as exc:  # noqa: BLE001
                rt = {"check": "dub intelligibility", "ok": False, "detail": f"round trip failed: {exc}"[:200]}
            if rt:
                chk["checks"].append(rt)
        (folder / "dub.json").write_text(__import__("json").dumps(d, indent=1, ensure_ascii=False), encoding="utf-8")
        chk["ok"] = all(c["ok"] for c in chk["checks"])
    status = "done" if chk["ok"] else "done-with-problems"
    with db.op("export.done", "machine") as tx:
        tx.update("export", exp["id"], {"status": status, "outputs": result, "checks": chk}, log=False)
        tx.event("export", {"export": exp["ref"], "status": status})
    return {"export": exp["ref"], "status": status, "video": result["video"], "seconds": result["seconds"],
            "cache_hits": result["slot_cache_hits"], "problems": [c for c in chk["checks"] if not c["ok"]]}
