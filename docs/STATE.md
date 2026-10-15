# STATE

The build's working memory. If context runs short, resume from here.

**Last updated:** 2026-10-15

| | |
|---|---|
| Phase | **P0 done**: foundations and agent contract |
| Next | P1: ingest and media (local scan, probe, fingerprint, subtitles discovery, audio, shots, peaks, jobs) |
| Suite | 20 passed |
| Plan | [PLAN.md](PLAN.md) approved 2026-10-15 with the defaults for Q1–Q6 |

## Defaults in force (open questions Q1–Q6)
- Projects at `C:\Recomposer\projects` (D: has about 15 GB free). Source movies stay in place on D:.
- Git is local only; commit after each verified phase; nothing is pushed.
- edge-tts network access is approved when it first prompts (pin `edge-tts>=7.3.1`; 7.2.8 gets 403).
- Afaan Oromo dub via MMS-TTS is the stretch goal for M3.
- No `--cookies-from-browser` without asking.
- I choose the Alex O'Connor journey theme from the latest episodes and say which.

## What exists
- `recomp` CLI and envelope, the verb registry, generated `docs/VERBS.md`, the MCP stdio server (`recomp mcp`).
- SQLite store with every table the plan needs (migration 1), FTS5 on segments, the op log with
  undo/redo, the precedence guard, the event table for the viewer.
- Verbs: `context`, `doctor`, `version`, `config get/set`, `setup shim`, `project init/use/list/show/set/agent-kit`,
  `op log/undo/redo`, `ui selection/select/show/ask/answer/note/notes`.
- The agent kit (AGENTS.md, CLAUDE.md, six skills, .mcp.json, read-verb permissions) is installed by
  `project init`.

## Environment (verified 2026-10-15)
- App venv: `.venv` (Python 3.13.2): fastapi, uvicorn, pydantic, httpx, yt-dlp 2026.08.19 + curl_cffi,
  edge-tts 7.3.1, segno, mcp 2.3.0, pytest.
- Worker python: `D:\LangBridgeLocal\.venv` (faster-whisper 1.2.1, pyannote 4.0.7, torch CPU), HF cache
  `D:\LangBridgeLocal\cache\hf` (whisper-turbo, wav2vec2-en, pyannote community-1, wavlm-sv, Ethio-ASR).
- ffmpeg 8.1.2 full; Node 24.

## Lessons
- MCP SDK 2.x: low-level `Server(name, on_list_tools=…, on_call_tool=…)`; types come from `mcp_types`
  with snake_case fields (`input_schema`, `is_error`).
