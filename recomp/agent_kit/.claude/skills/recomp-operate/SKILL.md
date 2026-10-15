---
name: recomp-operate
description: Operate a Recomposer project through the `recomp` CLI or MCP tools — the envelope, refs, jobs, undo, the viewer bridge and common failures. Load before doing anything in a Recomposer project.
---

# Operating Recomposer

## First moves
1. `recomp context`: the project, what exists per source (pipeline status), journeys, open jobs, the
   user's selection and notes, and suggested next commands.
2. `recomp ui notes`: questions you pinned and anything the user left for you in the viewer.
3. `recomp help` lists verbs grouped by noun; `recomp help cut.add` shows one verb's fields and examples.

## The envelope
```json
{"ok": true, "verb": "cut.add", "data": {...}, "refs": ["C17"], "op": "01K…", "next": ["…"]}
{"ok": false, "verb": "cut.add", "error": {"code": "E_PRECEDENCE", "message": "…", "hint": "…"}}
```
Exit codes: 0 ok · 2 usage/invalid · 3 not found · 4 precedence · 5 conflict · 6 external · 7 job failed.
`--pretty` indents. `--input file.json` (or `--input -` with stdin) passes bulk input: a JSON
object of fields, or a list (it becomes `items`).

## Jobs
Heavy verbs (ASR, downloads, renders, exports) return `"job": "job7"`.
- `recomp job wait job7 --timeout 90` returns when done *or* at the timeout with progress, so call it
  again or do something else meanwhile.
- `recomp job tail job7` shows the log; `recomp job list` shows what's running; `recomp job retry job7`.
- One CPU-heavy job runs at a time; downloads run alongside it.

## Undo and precedence
- Every write is an op: `recomp op log --since 30m`, `recomp op undo`, `recomp op redo`.
- The user outranks you, and you outrank machine jobs. `E_PRECEDENCE` means the user wrote it. Ask, and use
  `--as-user` only with their explicit go-ahead in chat (it is logged).

## The viewer bridge
- `recomp ui selection`: what the user has selected (source range or refs). "Cut this" means this.
- `recomp ui show C17 [--at 12.5] [--play]` moves their view.
- `recomp ui ask "Trim the laugh?" --refs C17 --options keep,trim` pins a question; answers appear in `ui notes`.

## Failures you will meet
| Code | Meaning | Do |
|---|---|---|
| `E_NO_PROJECT` | no project selected | `recomp project list` → `recomp project use <name>` |
| `E_NOT_FOUND` | bad ref | `recomp context` / `… list` |
| `E_INVALID` | bad field | `recomp help <verb>`; `error.data` lists the fields |
| `E_EXTERNAL` | site refused (429, bot check) | wait and retry once; then tell the user and suggest the fallback the hint names |
| `E_TOOL` | ffmpeg/worker failed | `recomp job tail`, `recomp doctor` |
