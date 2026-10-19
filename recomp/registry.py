"""The verb registry: the single source of truth for the CLI, MCP tools, REST API and docs.

A verb is a function ``fn(ctx, inp) -> dict | Result`` registered with a pydantic input model.
Mark positional CLI arguments with ``Field(json_schema_extra={"pos": n})``.
"""

from __future__ import annotations

import importlib
import os
import traceback
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator

from pydantic import BaseModel, ValidationError

from .envelope import RecompError, Result, fail, ok

EFFECTS = ("read", "write", "heavy", "network", "publish")
ACTORS = ("user", "agent", "machine")


@dataclass
class Verb:
    name: str
    fn: Callable[..., Any]
    model: type[BaseModel]
    effect: str
    summary: str
    needs_project: bool = True
    examples: list[str] = field(default_factory=list)
    hidden: bool = False

    @property
    def noun(self) -> str:
        return self.name.split(".")[0]

    @property
    def doc(self) -> str:
        return (self.fn.__doc__ or self.summary).strip()

    def positional(self) -> list[str]:
        items = []
        for name, f in self.model.model_fields.items():
            extra = f.json_schema_extra if isinstance(f.json_schema_extra, dict) else {}
            if "pos" in extra:
                items.append((extra["pos"], name))
        return [n for _, n in sorted(items)]

    def schema(self) -> dict:
        s = self.model.model_json_schema()
        s.pop("title", None)
        return s


VERBS: dict[str, Verb] = {}


def verb(name: str, model: type[BaseModel], effect: str = "read", needs_project: bool = True,
         examples: list[str] | None = None, hidden: bool = False, summary: str | None = None):
    if effect not in EFFECTS:
        raise ValueError(effect)

    def deco(fn):
        doc = (fn.__doc__ or "").strip()
        VERBS[name] = Verb(name=name, fn=fn, model=model, effect=effect,
                           summary=summary or (doc.splitlines()[0] if doc else name),
                           needs_project=needs_project, examples=examples or [], hidden=hidden)
        return fn

    return deco


class NoInput(BaseModel):
    pass


class Ctx:
    """What a verb sees: who is acting, which project, and a way to open a write transaction."""

    def __init__(self, actor: str = "agent", project_arg: str | None = None, force: bool = False,
                 project=None, verb_name: str = "", args: dict | None = None):
        self.actor = actor
        self.project_arg = project_arg
        self.force = force
        self._project = project
        self.verb_name = verb_name
        self.args = args or {}
        self.last_op: str | None = None
        self._studio = None

    @property
    def studio(self):
        """The studio store (follows, inbox, library, topics): no project needed."""
        if self._studio is None:
            from .core.studio import open_db
            self._studio = open_db()
        return self._studio

    @contextmanager
    def studio_op(self, summary: str = "") -> Iterator[Any]:
        with self.studio.op(self.verb_name, self.actor, self.args, force=self.force) as tx:
            tx.summary = summary
            yield tx
        if tx.op_id:
            self.last_op = tx.op_id

    def close(self) -> None:
        if self._studio is not None:
            self._studio.close()
            self._studio = None

    @property
    def project(self):
        if self._project is None:
            from .core.project import resolve
            self._project = resolve(self.project_arg)
        return self._project

    @property
    def db(self):
        return self.project.db

    @contextmanager
    def op(self, summary: str = "") -> Iterator[Any]:
        with self.db.op(self.verb_name, self.actor, self.args, force=self.force) as tx:
            tx.summary = summary
            yield tx
        if tx.op_id:
            self.last_op = tx.op_id


_LOADED = False


def load_all() -> dict[str, Verb]:
    """Import every verb module so its decorators run."""
    global _LOADED
    if not _LOADED:
        from . import verbs
        for mod in verbs.MODULES:
            importlib.import_module(f"recomp.verbs.{mod}")
        _LOADED = True
    return VERBS


def run(name: str, args: dict | None = None, actor: str = "agent", project_arg: str | None = None,
        as_user: bool = False, project=None, force: bool = False) -> dict:
    """Run one verb and return its envelope. Never raises for expected failures."""
    load_all()
    args = dict(args or {})
    v = VERBS.get(name)
    if v is None:
        return fail(name, RecompError("E_USAGE", f"unknown verb {name!r}",
                                      hint="`recomp help` lists every verb."))
    if as_user:
        actor = "user"
    if actor not in ACTORS:
        return fail(name, RecompError("E_USAGE", f"actor must be one of {ACTORS}"))
    try:
        inp = v.model.model_validate(args)
    except ValidationError as exc:
        details = [{"field": ".".join(str(p) for p in e["loc"]), "problem": e["msg"]} for e in exc.errors()]
        return fail(name, RecompError("E_INVALID", f"invalid input for {name}", data=details,
                                      hint=f"`recomp help {name}` shows the fields."))
    logged = inp.model_dump(exclude_defaults=True)
    if as_user:
        logged["as_user"] = True
    ctx = Ctx(actor=actor, project_arg=project_arg, force=force, project=project, verb_name=name, args=logged)
    try:
        if v.needs_project:
            ctx.project  # resolve early for a clean E_NO_PROJECT
        out = v.fn(ctx, inp)
        result = out if isinstance(out, Result) else Result(data=out)
        return ok(name, result, ctx.last_op)
    except RecompError as exc:
        return fail(name, exc)
    except Exception as exc:  # noqa: BLE001 — surfaced as E_INTERNAL with the message
        data = traceback.format_exc() if os.environ.get("RECOMP_DEBUG") else None
        return fail(name, RecompError("E_INTERNAL", f"{type(exc).__name__}: {exc}", data=data,
                                      hint="Re-run with RECOMP_DEBUG=1 for a traceback."))
    finally:
        ctx.close()
        if project is None and ctx._project is not None:
            ctx._project.close()
