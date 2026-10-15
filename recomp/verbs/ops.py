"""Operation log: every change, who made it, and undo/redo."""

from __future__ import annotations

import time

from pydantic import BaseModel, Field

from ..core.timecode import parse
from ..registry import Ctx, verb


class LogIn(BaseModel):
    limit: int = Field(20, description="How many ops to show (newest first)")
    actor: str | None = Field(None, description="Only ops by this actor: user, agent or machine")
    since: str | None = Field(None, description="Only ops newer than this, e.g. 10m, 2h, 90s")
    ref: str | None = Field(None, description="Only ops that touched this ref")


@verb("op.log", LogIn, examples=["recomp op log --actor user --since 1h"])
def op_log(ctx: Ctx, inp: LogIn):
    """The operation log, newest first: verb, actor, refs, summary and undo state."""
    where, params = [], []
    if inp.actor:
        where.append("actor=?")
        params.append(inp.actor)
    if inp.since:
        where.append("time>=?")
        params.append(time.time() - (parse(inp.since) or 0))
    if inp.ref:
        where.append("refs LIKE ?")
        params.append(f'%"{inp.ref}"%')
    sql = ("WHERE " + " AND ".join(where)) if where else ""
    rows = ctx.db.rows("op", f"{sql} ORDER BY seq DESC LIMIT ?", (*params, inp.limit))
    return [{"op": r["id"], "time": round(r["time"], 3), "ago_s": round(time.time() - r["time"]),
             "actor": r["actor"], "verb": r["verb"], "refs": r["refs"], "summary": r["summary"],
             "state": r["state"], "changes": len(r["changes"])} for r in rows]


class UndoIn(BaseModel):
    n: int = Field(1, description="How many ops to undo")


@verb("op.undo", UndoIn, effect="write", examples=["recomp op undo", "recomp op undo --n 3"])
def op_undo(ctx: Ctx, inp: UndoIn):
    """Undo the most recent change(s). Refuses to undo a higher-precedence actor's work."""
    done = []
    for _ in range(max(1, inp.n)):
        done.append(ctx.db.undo(ctx.actor, force=ctx.force))
    return done


@verb("op.redo", UndoIn, effect="write")
def op_redo(ctx: Ctx, inp: UndoIn):
    """Redo the most recently undone change(s)."""
    done = []
    for _ in range(max(1, inp.n)):
        done.append(ctx.db.redo(ctx.actor, force=ctx.force))
    return done
