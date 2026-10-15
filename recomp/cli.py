"""``recomp <noun> <verb> [args]`` — argparse built from the verb registry; prints one JSON envelope."""

from __future__ import annotations

import argparse
import json
import os
import sys
import types
import typing
from typing import Any

from pydantic.fields import FieldInfo

from . import registry
from .envelope import EXIT

GLOBAL_HELP = """Recomposer — every command prints one JSON envelope: {"ok": true, "data": ...} or {"ok": false, "error": {...}}.

  recomp context                 one-call briefing on the current project
  recomp help [verb] [--json]    list verbs, or one verb's fields
  recomp <noun> <verb> --help    flags for a verb

Global flags: --project P, --pretty, --as-user (only when the user said so in chat), --input FILE|-
"""


def _unwrap(ann: Any) -> tuple[Any, bool]:
    """Return (inner type, optional?) for ``X | None`` / ``Optional[X]``."""
    origin = typing.get_origin(ann)
    if origin in (typing.Union, types.UnionType):
        args = [a for a in typing.get_args(ann) if a is not type(None)]
        if len(args) == 1:
            return args[0], True
    return ann, False


def _flag(name: str) -> str:
    return "--" + name.replace("_", "-")


def _add_field(parser: argparse.ArgumentParser, name: str, f: FieldInfo, positional: bool) -> None:
    ann, _ = _unwrap(f.annotation)
    origin = typing.get_origin(ann)
    help_text = (f.description or "").replace("%", "%%")
    flag_name = f.alias or name
    if positional:
        # Always optional at the argparse level: --input may supply it, and pydantic reports
        # a missing required field as a JSON E_INVALID envelope rather than a usage dump.
        label = name if not f.is_required() else name.upper()
        parser.add_argument(name, nargs="*" if origin is list else "?", help=help_text,
                            default=argparse.SUPPRESS, metavar=label)
        return
    if ann is bool:
        parser.add_argument(_flag(flag_name), dest=name, action=argparse.BooleanOptionalAction,
                            default=argparse.SUPPRESS, help=help_text)
    elif origin is list:
        parser.add_argument(_flag(flag_name), dest=name, action="append", default=argparse.SUPPRESS,
                            help=(help_text + " (repeat or comma-separate)").strip())
    else:
        parser.add_argument(_flag(flag_name), dest=name, default=argparse.SUPPRESS, help=help_text,
                            required=False)


def _coerce(v: registry.Verb, raw: dict) -> dict:
    out = {}
    for name, value in raw.items():
        f = v.model.model_fields.get(name)
        if f is None:
            continue
        ann, _ = _unwrap(f.annotation)
        origin = typing.get_origin(ann)
        if origin is list and isinstance(value, list):
            flat: list[str] = []
            for item in value:
                if isinstance(item, str) and "," in item and name not in ("quote", "text"):
                    flat.extend(x.strip() for x in item.split(",") if x.strip())
                else:
                    flat.append(item)
            value = flat
        elif origin is dict or ann is dict or (isinstance(ann, type) and ann.__name__ == "Any"):
            if isinstance(value, str):
                try:
                    value = json.loads(value)
                except json.JSONDecodeError:
                    pass
        out[name] = value
    return out


class UsageError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message):  # noqa: D401 — argparse hook
        raise UsageError(f"{message}\n{self.format_usage().strip()}")


def build_parser(v: registry.Verb) -> argparse.ArgumentParser:
    prog = "recomp " + v.name.replace(".", " ")
    epilog = "\n".join(["examples:"] + ["  " + e for e in v.examples]) if v.examples else None
    p = _Parser(prog=prog, description=v.doc, epilog=epilog,
                formatter_class=argparse.RawDescriptionHelpFormatter)
    pos = v.positional()
    for name in pos:
        _add_field(p, name, v.model.model_fields[name], True)
    for name, f in v.model.model_fields.items():
        if name not in pos:
            _add_field(p, name, f, False)
    return p


def _split_globals(argv: list[str]) -> tuple[dict, list[str]]:
    g = {"project": None, "pretty": bool(os.environ.get("RECOMP_PRETTY")), "as_user": False,
         "input": None, "actor": os.environ.get("RECOMP_ACTOR", "agent"), "force": False}
    rest: list[str] = []
    it = iter(range(len(argv)))
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--project" and i + 1 < len(argv):
            g["project"] = argv[i + 1]; i += 2; continue
        if a.startswith("--project="):
            g["project"] = a.split("=", 1)[1]; i += 1; continue
        if a == "--pretty":
            g["pretty"] = True; i += 1; continue
        if a == "--as-user":
            g["as_user"] = True; i += 1; continue
        if a == "--force-undo":
            g["force"] = True; i += 1; continue
        if a == "--actor" and i + 1 < len(argv):
            g["actor"] = argv[i + 1]; i += 2; continue
        if a == "--input" and i + 1 < len(argv):
            g["input"] = argv[i + 1]; i += 2; continue
        rest.append(a)
        i += 1
    del it
    return g, rest


def _resolve_verb(rest: list[str]) -> tuple[str | None, list[str]]:
    verbs = registry.load_all()
    if not rest:
        return None, []
    if len(rest) >= 2 and f"{rest[0]}.{rest[1]}" in verbs:
        return f"{rest[0]}.{rest[1]}", rest[2:]
    if rest[0] in verbs:
        return rest[0], rest[1:]
    if "." in rest[0] and rest[0] in verbs:
        return rest[0], rest[1:]
    return None, rest


def _print(env: dict, pretty: bool) -> None:
    text = json.dumps(env, ensure_ascii=False, indent=2 if pretty else None, default=str)
    try:
        sys.stdout.write(text + "\n")
    except UnicodeEncodeError:
        sys.stdout.buffer.write((text + "\n").encode("utf-8"))
    sys.stdout.flush()


def help_payload(name: str | None = None) -> dict:
    verbs = registry.load_all()
    if name:
        v = verbs.get(name) or verbs.get(name.replace(" ", "."))
        if v is None:
            return {"ok": False, "verb": "help", "error": {"code": "E_NOT_FOUND", "message": f"no verb {name!r}"}}
        return {"ok": True, "verb": "help", "data": {
            "verb": v.name, "cli": "recomp " + v.name.replace(".", " "), "effect": v.effect,
            "summary": v.summary, "doc": v.doc, "positional": v.positional(), "input": v.schema(),
            "examples": v.examples}}
    groups: dict[str, list] = {}
    for v in sorted(verbs.values(), key=lambda x: x.name):
        if v.hidden:
            continue
        groups.setdefault(v.noun, []).append({"verb": v.name, "effect": v.effect, "summary": v.summary})
    return {"ok": True, "verb": "help", "data": groups}


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    argv = list(sys.argv[1:] if argv is None else argv)
    g, rest = _split_globals(argv)
    if not rest or rest[0] in ("-h", "--help"):
        sys.stdout.write(GLOBAL_HELP)
        return 0
    if rest[0] == "mcp":
        from . import mcp_server
        mcp_server.main()
        return 0
    if rest[0] == "serve":
        from .server import app as server_app
        return server_app.main(rest[1:], g["project"])
    if rest[0] == "worker" and len(rest) > 1 and rest[1] == "serve":
        from .core import config as _cfg
        from .workers.scripts import remote_worker
        import argparse as _ap
        ap = _ap.ArgumentParser(prog="recomp worker serve")
        ap.add_argument("--folder", default=_cfg.get("worker.remote_folder"))
        ap.add_argument("--python", default=_cfg.get("worker.python"))
        ap.add_argument("--once", action="store_true")
        ap.add_argument("--idle-exit", type=float, default=0.0)
        a = ap.parse_args(rest[2:])
        if not a.folder:
            print("no folder: pass --folder or set worker.remote_folder")
            return 2
        n = remote_worker.serve(__import__("pathlib").Path(a.folder), a.python, a.once, a.idle_exit)
        print(f"served {n} job(s)")
        return 0
    if rest[0] == "worker" and len(rest) > 1 and rest[1] == "run":
        from .workers import runner
        extra = ["--project", g["project"]] if g["project"] else []
        return runner.main(extra + rest[2:])
    if rest[0] == "help":
        target = None
        tail = [a for a in rest[1:] if a != "--json"]
        if tail:
            target = ".".join(tail) if len(tail) > 1 else tail[0]
        payload = help_payload(target)
        if "--json" in rest or target or not payload["ok"]:
            _print(payload, g["pretty"] or "--json" not in rest)
        else:
            lines = [GLOBAL_HELP]
            for noun, items in payload["data"].items():
                for it in items:
                    lines.append(f"  {it['verb'].replace('.', ' '):<28} {it['effect']:<8} {it['summary']}")
            sys.stdout.write("\n".join(lines) + "\n")
        return 0
    name, tail = _resolve_verb(rest)
    if name is None:
        env = {"ok": False, "verb": " ".join(rest[:2]), "error": {
            "code": "E_USAGE", "message": f"unknown command: recomp {' '.join(rest[:2])}",
            "hint": "`recomp help` lists every verb."}}
        _print(env, g["pretty"])
        return EXIT["E_USAGE"]
    v = registry.VERBS[name]
    parser = build_parser(v)
    try:
        ns = parser.parse_args(tail)
    except SystemExit as exc:  # --help
        return int(exc.code or 0) if exc.code in (0, None) else EXIT["E_USAGE"]
    except UsageError as exc:
        _print({"ok": False, "verb": name, "error": {"code": "E_USAGE", "message": str(exc).splitlines()[0],
                                                       "hint": str(exc).splitlines()[-1]}}, g["pretty"])
        return EXIT["E_USAGE"]
    args: dict = {}
    if g["input"]:
        raw = sys.stdin.read() if g["input"] == "-" else open(g["input"], encoding="utf-8-sig").read()
        loaded = json.loads(raw)
        if isinstance(loaded, list):
            loaded = {"items": loaded}
        args.update(loaded)
    args.update(_coerce(v, vars(ns)))
    env = registry.run(name, args, actor=g["actor"], project_arg=g["project"], as_user=g["as_user"],
                       force=g["force"])
    _print(env, g["pretty"])
    if env["ok"]:
        return 0
    return EXIT.get(env["error"]["code"], 1)


if __name__ == "__main__":
    raise SystemExit(main())
