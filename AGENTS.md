# Working on the Recomposer codebase

This file is for agents changing the **code**. To *operate* a project (cut, compose, export), read
`recomp/agent_kit/AGENTS.project.md`; it is installed as `AGENTS.md` in every project folder.

## Start here
1. `docs/STATE.md`: where the build is, what's next. `docs/BACKLOG.md`: every open task by priority.
2. `docs/PLAN.md`: the approved plan (phases P0–P14, milestones M1–M5). `docs/DECISIONS.md`: decisions.
3. `docs/VERBS.md`: every verb, generated from the registry.

## Shape
- `recomp/registry.py`: `@verb(name, InputModel, effect=…)`. The CLI (`recomp/cli.py`), the MCP server
  (`recomp/mcp_server.py`), the REST API (`recomp/server/`) and the docs are all generated from it.
  **Add capabilities as verbs**, never as UI-only or API-only endpoints.
- `recomp/core/store.py`: all writes go through `with ctx.op("summary") as tx:` and `tx.insert/update/delete`.
  That gives undo/redo, events for the viewer, and the precedence guard (user > agent > machine).
  Bulk machine data (segments, words, shots) uses `log=False`.
- `recomp/core/schema.py`: append-only migrations; JSON columns are declared in `JSON_COLS`.
- Heavy work runs as jobs (`recomp/workers/`); worker scripts run under the *worker python*
  (`config worker.python`, default `D:\LangBridgeLocal\.venv`) and must only import what that env has.

## Rules
- Python 3.13 venv in `.venv` (`.venv\Scripts\python.exe -m pip install -e .[dev]`).
- Tests: `.venv\Scripts\python.exe -m pytest -q` (fast; e2e on generated media with `-m e2e`;
  `-m real` needs real media and network). After changing verbs: `python scripts/gen_docs.py`.
- Never modify `D:\LangBridgeLocal`, other repositories or source media. Tests use temp folders
  (`RECOMP_HOME` is set per test).
- Every verb: a docstring (its first line is the summary), field descriptions, examples for non-obvious ones.
- Errors: raise `RecompError(code, message, hint)` with a hint that says what to do next.
- Do not spawn subagents unless the user names one.
- Commit after each verified step, with the trailer the session asks for. Nothing is pushed.
