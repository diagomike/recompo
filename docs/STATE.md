# STATE

The build's working memory. If context runs short, resume from here.

**Last updated:** 2026-10-16 (early morning)

| | |
|---|---|
| Phases | **P0–P16 built** (P16 awaits your review) · **P17 research wing** re-planned 2026-10-16: follow creators, compile what they say (D-22), rights model (D-23) |
| Milestones | **M1** ([report](runs/M1-dark-knight.md)) · **M2** ([report](runs/M2-alex-oconnor.md)) · **M3** am/sw/fr + om · **M4** local hub ([report](runs/M3-M4-languages-and-hub.md)): all done |
| Suite | 85+ fast tests (`pytest -q`), slow speaker test (`pytest -m slow`); the reorder-cache timing assert can flake under heavy load |
| Projects | `C:\Recomposer\projects\dark-knight` (M1, M3), `alex-oconnor` (M2: 5 episodes, 12 cuts, 3 journeys); `_uitest` scratch folder (forgotten from the list; safe to delete) |
| Hub | `python -m hub` on 8790, data in `%USERPROFILE%\.recomp\hub`, seeded test users in `seed_users.json` there |

## Notes for the user
- YouTube blocked per-video requests from this machine from ~06:30 until the evening of 2026-10-15, and again from
  ~04:10 on 2026-10-16 (429, then the bot check). Listings, searches, feeds and published transcripts kept working.
  Browser cookies are allowed since 2026-10-16 (D-24), but Chrome keeps background processes that lock its cookie
  database: export a cookies.txt (P17 adds `network.cookies_file`) or fully quit Chrome.
- P17 direction (2026-10-16, D-22): we are an active creation team. Follow creators, make journeys from their new
  posts and from topics in the air they have opinions on; no market-watching. Prototype and evidence:
  `docs/research/P17-follow/` (topic brief on "AI models are getting good" across Lex, DOAC and Alex).
- Link videos are fetched whole at ≤720p once per source (`network.link_video full`); `sections` is the alternative.

## Defaults in force (open questions Q1–Q6)
- Projects at `C:\Recomposer\projects` (D: has ~15 GB free); source movies stay on D:.
- Git local only; commit after each verified phase; nothing pushed.
- edge-tts allowed (needs `speech.platform.bing.com`; runs outside the sandbox); pin `edge-tts>=7.3.1`.
- Afaan Oromo via MMS-TTS (`facebook/mms-tts-orm`, non-commercial weights) as the stretch goal.
- Browser cookies allowed for the research wing (D-24); published transcripts and feeds first.
- Alex O'Connor theme: **consciousness** (Pollan, Frankish, Anil Seth, Galen Strawson).

## Environment (verified 2026-10-15)
- App venv `.venv` (Python 3.13.2): fastapi, uvicorn, pydantic, httpx, yt-dlp 2026.08.19 + curl_cffi, edge-tts 7.3.1,
  segno, mcp 2.3.0, numpy, pytest. Viewer: React 18 / Vite 5 (node_modules copied from recomposer_v2 + lucide-react).
- Worker python `D:\LangBridgeLocal\.venv` (faster-whisper 1.2.1, pyannote 4.0.7, transformers, audio-separator);
  HF cache `D:\LangBridgeLocal\cache\hf`; `facebook/mms-tts-orm` downloaded there on first Oromo dub.
- Measured: whisper-turbo int8 ASR at RTF 0.33 on this CPU; shots 79 s and audio 7 s for an 89-min film;
  pyannote ~70 s on 40 s of audio including load.

## Viewer (P16)
- Project home (`#/p/<name>/home`) is the checklist (`project checklist`); Cut bin (`#/p/<name>/cuts`) mixes sources.
- Filters live in the URL; `recomp ui show <view> --filter "k=v&k=v" --highlight <verb>` opens the same view.
- Every button runs one verb (hover shows the command; the robot hands it to the agent via `ui notes`).
- Source room: Ctrl+F searches that source (words or "a phrase", across caption line breaks), Enter/↑↓ jump and seek,
  hits tick the lanes; `ui show S3 --filter "tq=free will"` opens it searched. Lanes adapt to what a source has
  (speech lane without audio, overview strip, hover labels); player and transcript widths drag and are remembered.
- Link sources with fetched video build frames and waveform from it (`source process S3 --jobs audio,peaks,thumbs`).
- `p16-check` project: the acceptance run (two fixture clips from `C:\Recomposer\p16-media`, J1, X1/X2).

## Lessons
- `>>` marks name speakers for free only when dense (≥ 1/min); sparse marks swap every later line (M2: 86 % vs 50 %).
- Ebrima's Ethiopic syllables are about Latin width: caption rows need no script-specific shortening (caption sheet).
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
