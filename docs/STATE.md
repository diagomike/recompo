# STATE

The build's working memory. If context runs short, resume from here.

**Last updated:** 2026-10-15 (evening)

| | |
|---|---|
| Phases | **P0–P14 built** |
| Milestones | **M1** ([report](runs/M1-dark-knight.md)) · **M2** ([report](runs/M2-alex-oconnor.md)) · **M3** am/sw/fr + om · **M4** local hub ([report](runs/M3-M4-languages-and-hub.md)): all done |
| Suite | 70+ fast tests (`pytest -q`), slow speaker test (`pytest -m slow`) |
| Projects | `C:\Recomposer\projects\dark-knight` (M1, M3), `alex-oconnor` (M2: 5 episodes, 12 cuts, 3 journeys); `_uitest` scratch folder (forgotten from the list; safe to delete) |
| Hub | `python -m hub` on 8790, data in `%USERPROFILE%\.recomp\hub`, seeded test users in `seed_users.json` there |

## Notes for the user
- YouTube blocked per-video requests from this machine from ~06:30 until the evening of 2026-10-15; it lifted on its
  own. If it returns: wait, or decide on browser cookies (`recomp config set network.cookies_from_browser chrome`),
  or run ingest through the remote notebook.
- Link videos are fetched whole at ≤720p once per source (`network.link_video full`); `sections` is the alternative.

## Defaults in force (open questions Q1–Q6)
- Projects at `C:\Recomposer\projects` (D: has ~15 GB free); source movies stay on D:.
- Git local only; commit after each verified phase; nothing pushed.
- edge-tts allowed (needs `speech.platform.bing.com`; runs outside the sandbox); pin `edge-tts>=7.3.1`.
- Afaan Oromo via MMS-TTS (`facebook/mms-tts-orm`, non-commercial weights) as the stretch goal.
- No browser cookies unless the user sets them.
- Alex O'Connor theme: **consciousness** (Pollan, Frankish, Anil Seth, Galen Strawson).

## Environment (verified 2026-10-15)
- App venv `.venv` (Python 3.13.2): fastapi, uvicorn, pydantic, httpx, yt-dlp 2026.08.19 + curl_cffi, edge-tts 7.3.1,
  segno, mcp 2.3.0, numpy, pytest. Viewer: React 18 / Vite 5 (node_modules copied from recomposer_v2 + lucide-react).
- Worker python `D:\LangBridgeLocal\.venv` (faster-whisper 1.2.1, pyannote 4.0.7, transformers, audio-separator);
  HF cache `D:\LangBridgeLocal\cache\hf`; `facebook/mms-tts-orm` downloaded there on first Oromo dub.
- Measured: whisper-turbo int8 ASR at RTF 0.33 on this CPU; shots 79 s and audio 7 s for an 89-min film;
  pyannote ~70 s on 40 s of audio including load.

## Lessons
- Whisper word starts run ~0.4 s early: refine against energy onsets (`transcript/refine.py`).
- Aligning subtitles to ASR: keep matches inside the line's own window (repeated phrases borrow timings).
- Frame-exact slots + sample-exact audio assembly, or captions drift ~34 ms per slot.
- Limit true peak at 4× oversampling; AAC overshoots a sample-peak limiter.
- CC BY-ND music cannot be laid under video (sync = adaptation); default music search is CC0/BY.
- Dub fit: voice-over placement with a 1 s delay budget, edge `rate` before time-stretch, short interjections may keep
  the original voice; the agent shortens lines the check lists.
- The runner process keeps old code loaded: after changing worker code, let it go idle (30 s) or stop it before re-queuing.
- Shell heredoc edits mangle backslashes: use the Edit tool for code with `\b`, `\c`, `\n`.
- MCP SDK 2.x: low-level `Server(on_list_tools=…, on_call_tool=…)`, types in `mcp_types` with snake_case fields.
