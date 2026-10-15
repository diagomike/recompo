"""The JSON envelope every verb returns, and the error codes agents can branch on."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

EXIT = {
    "E_USAGE": 2,
    "E_INVALID": 2,
    "E_NOT_FOUND": 3,
    "E_NO_PROJECT": 3,
    "E_PRECEDENCE": 4,
    "E_LOCKED": 4,
    "E_CONFLICT": 5,
    "E_EXISTS": 5,
    "E_EXTERNAL": 6,
    "E_NETWORK": 6,
    "E_JOB_FAILED": 7,
    "E_TOOL": 8,
    "E_INTERNAL": 9,
}


class RecompError(Exception):
    """An expected failure. ``code`` is stable; ``hint`` tells the caller what to do next."""

    def __init__(self, code: str, message: str, hint: str | None = None, data: Any = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint
        self.data = data

    @property
    def exit_code(self) -> int:
        return EXIT.get(self.code, 1)

    def to_dict(self) -> dict:
        err = {"code": self.code, "message": self.message}
        if self.hint:
            err["hint"] = self.hint
        if self.data is not None:
            err["data"] = self.data
        return err


def not_found(what: str, ref: str, hint: str | None = None) -> RecompError:
    return RecompError("E_NOT_FOUND", f"{what} {ref!r} not found", hint)


def invalid(message: str, hint: str | None = None) -> RecompError:
    return RecompError("E_INVALID", message, hint)


@dataclass
class Result:
    """What a verb function returns. Plain dicts are wrapped into ``Result(data=...)``."""

    data: Any = None
    refs: list[str] = field(default_factory=list)
    next: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    job: str | None = None


def ok(verb: str, result: Result, op: str | None) -> dict:
    env: dict[str, Any] = {"ok": True, "verb": verb, "data": result.data}
    if result.refs:
        env["refs"] = result.refs
    if op:
        env["op"] = op
    if result.job:
        env["job"] = result.job
    if result.warnings:
        env["warnings"] = result.warnings
    if result.next:
        env["next"] = result.next
    return env


def fail(verb: str, error: RecompError) -> dict:
    return {"ok": False, "verb": verb, "error": error.to_dict()}
