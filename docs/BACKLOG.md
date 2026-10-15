# BACKLOG

Every open task, by phase. Ticked when it lands. Phases follow [PLAN.md §6](PLAN.md#6-build-phases).

## P0 — Foundations and agent contract
- [x] venv, pyproject, `recomp` entry point
- [x] registry, envelope, CLI (JSON errors for usage too)
- [x] studio home config, project registry, project init/use/list/show/set
- [x] SQLite migrations, ULIDs and short refs, op log with undo/redo, precedence guard, events
- [x] `context`, `doctor`, `config`, `setup shim`, `ui` bridge verbs
- [x] generated VERBS.md and drift test; MCP server and test
- [x] agent kit (AGENTS.md, CLAUDE.md, 6 skills, .mcp.json, permissions)

## P1 — Ingest and media
- [ ] job table runner (local subprocess, progress, heartbeat, wait/tail/cancel/retry)
- [ ] source add: file, folder, glob; fingerprint; probe; rights defaults; title/year from filename
- [ ] sidecar and embedded subtitle discovery → transcript import
- [ ] audio extraction (16 kHz mono, 5.1 aware), shots (scdet), peaks, thumbnail sprites
- [ ] source list/show/status/relink/rights/remove

## P2 — Transcripts, search, ASR
- [ ] parsers srt/vtt/ass/json3 (+ malformed numbering)
- [ ] transcript import/read/outline/list/set-primary/edit-segment
- [ ] FTS5 search with filters and context
- [ ] ASR job (faster-whisper turbo, VAD, words) under worker python
- [ ] align (wav2vec2) for subtitle word timing; sync-check and --fix
- [ ] optional model2vec semantic layer

## P3 — Chapters and cuts
- [ ] chapter seed/auto/set/add/edit/merge/split/remove/list
- [ ] cut add by time/segments/quote; snapping words/shots/silence; pad
- [ ] cut suggest; edit/trim/split/merge/remove/tag/list/show

## P4 — Studio server and viewer v1
- [ ] FastAPI verb API, SSE events, media range streaming, static viewer
- [ ] web: Start, Sources, Source room (video, transcript, lanes), Search, Activity/undo, Jobs
- [ ] ui selection bridge verified in the browser pane

## P5 — Journeys and recipes
- [ ] journey/slot/section/transition verbs; overlays; music beds
- [ ] recipe spec, JSON Schema, hash, recipes/*.recipe.json mirror
- [ ] Journey builder + recipe player (local files); EDL and OTIO export

## P6 — Render and export · P7 — Music
- [ ] render plan, slot cache, reframe, ASS captions (clean, karaoke, quote), overlays, audio mix, endcard + QR
- [ ] profiles, export matrix, packaging, checks, preview, single-cut exports
- [ ] Openverse search/get with licences; local library; credits integration

## M1 — Dark Knight acceptance run
## P8 Links · P9 Speakers · M2 Alex O'Connor
## P10 Multilingual and dubbing · M3 (am, sw, fr + om stretch)
## P11 Hub · M4
## P12 Remote workers · P13 Trends · P14 Hardening
