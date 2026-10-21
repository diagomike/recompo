# STATE

The build's working memory. If context runs short, resume from here.

**Last updated:** 2026-10-21 (M5 complete: the worktree branch merged into master, the full suite green, J3 public on
the local hub after your yes, the endcard's recipe URL wraps on Shorts)

| | |
|---|---|
| Phases | **P0–P16b built** (P16b awaits your review) · **P17 research wing** approved 2026-10-19 with defaults P17-Q1–Q6: **P17a–d built** (find, follow, inbox, library; topics, briefs, journeys from topics; rights, posting queue, hub permission; Follows and Topics pages) |
| Milestones | **M1** ([report](runs/M1-dark-knight.md)) · **M2** ([report](runs/M2-alex-oconnor.md)) · **M3** am/sw/fr + om · **M4** local hub ([report](runs/M3-M4-languages-and-hub.md)) · **M5** follows and topics ([report](runs/M5-follows-and-topics.md)): all done |
| Suite | 100+ fast tests (`pytest -q`), slow speaker test (`pytest -m slow`), live P17 sources (`pytest -m real tests/unit/test_follow_real.py`); the reorder-cache timing assert can flake under heavy load |
| Projects | `C:\Recomposer\projects\dark-knight` (M1, M3), `alex-oconnor` (M2: 5 episodes, 12 cuts, 3 journeys), `ai-and-ideas` (M5: 7 sources, J1–J3, J3 public on the local hub); `_uitest` scratch folder (forgotten from the list; safe to delete) |
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
- YouTube refused per-video requests again on 2026-10-19 (bot check). Taking an inbox item still works: the source
  is added from the listing's metadata (`source refresh` completes it later) and Lex transcripts come from his site.

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

## Viewer (P16, reworked in P16b)
- Shell: nav rail (Make · Material · Deliver; icons only below 1180 px, bottom bar on phones), top bar with
  **New journey** (`n`) and the **Agent** drawer (`.`; docked ≥ 1440 px, a slide-over below, closed by default).
- Dense, flat design system in `web/src/styles.css` (13 px, 26 px controls, 3 px radius, tables and flat lists, no
  cards); shared parts in `web/src/ui.tsx`: tooltip layer (`data-tip`, `data-tip-cmd`), `Menu`, `Dialog`,
  `Disclosure` (remembers being opened), `Empty`, `SrcBadge`. The user wants industry-grade density; clarity comes from
  structure and progressive disclosure (Word-like), not padding.
- **Journey studio** (`#/p/<name>/journeys/J1?step=gather`): six step tabs from `journey guide` (the agent reads the
  same), one-line step header with the step's commands, a preview pane that hides, a status bar with the next action.
  Gather takes cuts from suggestions (`cut suggest` on the intent), the cut bin, or a source room opened with `?j=J1`
  (new cuts go straight in via `cut add --journey`). `journey review J1 order|look|check` confirms judgement steps.
  `recomp ui show J1 --filter step=look` and `ui show home --filter new=1` (the New journey dialog) work.
- Journeys carry destinations (`--formats shorts,landscape,square,hub`): length goal, validate notes, export profiles
  and the hub hand-off follow from them.
- Project home (`#/p/<name>/home`): journeys table with step progress first, then the open setup steps (`project
  checklist`; finished ones folded); Cut bin (`#/p/<name>/cuts`) mixes sources.
- `scripts/shots.py` takes headless screenshots for run reports (waits for data; `--dark`, any size).
- Filters live in the URL; `recomp ui show <view> --filter "k=v&k=v" --highlight <verb>` opens the same view.
- Every button runs one verb (hover shows the command; the robot hands it to the agent via `ui notes`).
- Studio keys: `1`–`6` go to a step, `Enter` runs the status bar's primary action (not while typing, in a dialog or a
  menu, or with a button focused). Tooltips on the step tabs and the primary buttons show the key.
- Source room (P16b structure, 2026-10-16): a one-line source header (badge, title, length, transcript; ⋯ for build
  lanes, the original, its cuts, reset panels, keys), then under the player one **command row** in groups —
  play · In/Out · selection (Esc clears) │ Cut · Chapter │ zoom in/out/to selection/whole │ find. New cut, new chapter
  and editing one are a **dialog** (title and why; tags and snapping folded), so the lanes never jump. Cuts and
  chapters below are a flat list (click selects; ⋯ plays, edits, adds to the gathering journey, deletes with a
  confirm). Phones get one scrolling column. Escape in a dialog or menu closes only that layer (`ui.tsx`).
  A container query on the left column (≤ 640 px) shortens the selection chip to its length (range in the tooltip),
  so the command row stays on one line at 1024 px.
- `.claude/launch.json` uses the main checkout's venv by absolute path, so `studio` and `hub` also start in worktrees.
- Transcript pane: transcript picker + find box + ⋯ (find and replace, speakers, clean every line, re-fetch/ASR) in
  one row; a contextual line bar for selected lines (speaker, merge/split, ⋯ clean, replace in lines, delete with a
  confirm). Find and replace (`Ctrl+H`) and Speakers are dialogs. Ctrl+F searches that source (words or "a phrase",
  across caption line breaks), Enter/↑↓/F3 jump and seek, hits tick the lanes; `ui show S3 --filter "tq=free will"`
  opens it searched. Lanes adapt to what a source has; player and transcript widths drag and are remembered.
- Translation editor (Exports › Translations, `?tj=J1&tl=am&tp=shorts`, or `?journey=J1` from the studio): one
  command row (journey, language, **+ Language** dialog — Google draft or ask the agent — caption box format, Draft
  missing, Replace dialog, ⋯ caption sheet, export, redo Google drafts), the caption box folded to one line, filters,
  the lines (stacked on phones) and the save bar.
- Link sources with fetched video build frames and waveform from it (`source process S3 --jobs audio,peaks,thumbs`).
- `p16-check` project: the acceptance run (two fixture clips from `C:\Recomposer\p16-media`, J1, X1/X2).

## Research wing (P17a, 2026-10-19)
- **Studio store** `studio.db` in the studio home (`recomp/core/studio.py`, `schema.STUDIO_MIGRATIONS`): follows (F),
  `follow_seen`, inbox (I), library docs (L) with `lib_seg` + FTS. Same store code as projects: op log, precedence,
  events; `recomp op log|undo|redo --studio`. Verbs reach it through `ctx.studio` / `ctx.studio_op()` (no project).
- `recomp/research/`: `net` (HTTP), `feeds` (podcast RSS → episodes with a transcript **route**: published VTT/SRT/JSON
  → lex page → asr; YouTube Atom), `youtube` (flat listings: channel search, person search, uploads, in-channel
  search), `podcasts` (iTunes search, feed read and peek), `transcripts` (fetch by route; Lex pages give speakers,
  chapters and the YouTube id), `library` (add docs, search), `schedule` (checks every `research.check_every_h`).
- Verbs (`recomp/verbs/follow.py`): `find creators`, `follow add|list|edit|remove|check|backfill`,
  `inbox list|take|dismiss`, `library search|list|show|remove`; `search --scope library`; `project set --themes`.
- A follow with a channel and a podcast pairs each upload with its feed episode by title words (≥ 0.45 Jaccard), so a
  YouTube item gets the podcast's published transcript route. Lex's feed items become YouTube sources (the page
  names the video and follows its clock); a feed-timed transcript on a video source is kept non-primary, labelled
  "podcast timing".
- First check of a follow: the newest `research.first_check_items` (3) go to the inbox, the rest are marked seen.
  Feed reads are op-logged as the **machine** (the choices — take, dismiss — are the person's or agent's).
- Taking a YouTube item uses the project's pick list, so a refused metadata request falls back to the listing.
- Rights status (D-23) is stored on the follow and copied to `source.rights.status` on take; P17c adds the gate.
- Tests: `tests/unit/test_follow.py` over fixtures cut from the research's saved responses
  (`scripts/research/make_p17_fixtures.py` → `tests/fixtures/p17/`); live checks in `test_follow_real.py`.
- YouTube's RSS answered 404 on 2026-10-19 (500 on 2026-10-16): the listing is the working path.

## Topics (P17b, 2026-10-19)
- Studio migration 2: `topic` (T): title, terms, follows (empty = all), since, news query, projects, `brief` (JSON).
- `recomp/research/topics.py`: Google News RSS (top, sections, 7-day search), Google Trends daily RSS, Wikipedia
  most-viewed (only with `research.contact`: Wikimedia's robot policy 403s any agent without contact details), Hacker
  News front page (Algolia); `key_terms` (acronyms and names first, a stop list), `passages` (45–90 s windows scored
  by terms, a bonus for several different terms; best k non-overlapping).
- `topic suggest` marks each prompt with the followed creators whose library episodes use two of its terms within
  ~8 lines (single words need 3 mentions; words in most episodes are ignored). A hint for choosing, not a ranking.
- `topic scan`: per follow, feed episodes and the channel's own search whose titles/descriptions mention a term;
  missing transcripts fetched by route into the library (`--fetch` per creator; captions stop at the first YouTube
  refusal; audio-only episodes listed as needs ASR); plus the follow's project sources (creator name match).
  Writes the brief to `topic.brief` and `<studio home>/topics/T1-brief.md`. Passage ids `p1…` in reading order.
- `journey from-topic` (project verb): adds missing episodes as their YouTube video (library transcript along when
  it is on the video's clock), shifts podcast-timed passages by `align.estimate_offset` against a word-timed video
  transcript (warns when there is none), cuts with why/people/tags `topic:T1`, sections per creator or stance,
  auto lower thirds; records the journey on the topic.
- Live 2026-10-19: "AI models are getting good" → 6 passages from 4 Lex Fridman episodes (2 fetched); Alex O'Connor's
  AI episodes are audio-only in the feed (needs ASR) and YouTube refused captions, so the brief listed them as unread.

## Rights and posting (P17c, 2026-10-19)
- `recomp/core/rights.py`: `source.rights.status` campaign | permitted | private (missing = private); campaign and
  permitted need `evidence`. `source rights S3 --status … --evidence …` (the plan's `source rights set` became flags
  on the existing verb).
- Studio migration 3: `channel` (CH; one channel, a placeholder until named — P17-Q3) and `post` (Q: project, export,
  journey, file, title, description, at, status planned → opened → posted | cancelled, URL, sources' rights).
- `post plan` (project verb) refuses private sources with **E_RIGHTS**; adds a credit line for any creator the
  export's description lacks. `post open` returns file, text and upload page (`--reveal` shows the file);
  `post link` records the URL on the post, the journey and its hub recipe (`hub.link-post`). `channel stats`: a
  YouTube Studio CSV, or public totals with your API key; posted videos get their row. Read-only.
- `hub publish` is **private by default**. Public/unlisted with private sources → **E_CONFIRM** with the question,
  each source and its consequences; only the user can answer (`--confirm` from the user, or the agent's
  `--confirm --as-user` after a yes in chat). The answer and time go on the hub's `recipe_version.permission`
  (owner-only in the API) and on `journey.links.permissions`.
- Store: journey `links` is bookkeeping (unguarded), so the agent can record a post after the user published;
  inbox and post `status` are decisions (guarded and undoable: `schema.unguarded(table)`).

## Research pages (P17d, 2026-10-19)
- Studio-level routes `#/follows` and `#/topics` (also `#/p/<name>/follows|topics`; a **Research** group in the nav rail
  with the inbox count; top-bar links on the start page). `ui show follows|topics|T1` opens them.
- Follows (`web/src/views/Follows.tsx`): Inbox (Take into the follow's project, or the open one; Dismiss), Following
  (Check, Backfill, Unfollow), Find creators (search → Follow result n), Library (search with links at the moment).
  Studio changes don't stream: every action bumps a revision that reloads the tabs.
- Topics (`Topics.tsx`): your topics (add with terms, Scan), In the air (`topic suggest` with who has talked about each
  prompt; "Make it a topic"), the brief (passages to tick, play at the moment, "Draft journey in <project>", or pick a
  project from the start page).
- `PublishButton.tsx`: visibility (private default) and the permission dialog on E_CONFIRM (consequences, "Publish it
  private instead", "Yes, I have permission"). `PostQueue.tsx`: Exports › Posting (channel form, queue, Open with
  copyable text and upload page, "Posted…" link, Cancel); "Plan a post" on a finished export.
- Toasts: studio verbs undo with `op undo --studio`; multi-store verbs (inbox take, topic scan, backfill, journey
  from-topic) offer no one-click undo. The main area is keyed by project (a project change remounts every view).
- CLI: the global `--project P` also fills a studio verb's own `project` field (follow add, topic add, inbox take).
- Live 2026-10-19 (real studio): followed Lex Fridman (F1) and The Diary of a CEO (F2) from the Find tab into the new
  `ai-and-ideas` project, Alex O'Connor (F3, channel + Within Reason) into `Alex O'Connor` by CLI; checks filled the
  inbox; I1 (Lex #502) taken → ai-and-ideas S1 with the Lex transcript, 14 chapters, a cut candidate; topic T1 "AI
  models are getting good" scanned from the page → 34 passages from 12 episodes, 3 creators, 2024-11-11 → 2026-10-08.
- F2's person is "DOAC" (set by your Follow click, so the agent may not change it): `recomp follow edit F2 --person
  "Steven Bartlett" --as-user` if you agree. New shows now default to the host named in the title.

## M5 run (2026-10-20, [report](runs/M5-follows-and-topics.md))
- `recomp/research/match.py`: a podcast-only brief episode is matched to its YouTube upload (search, the creator's
  own channel, similar length, confirmed by ≥ 40 words lining up in podcast minutes 10–20). The captions come along
  as the video's transcript; `journey from-topic` shifts each passage by an offset measured near it (inserted ads
  move it: −20 s → −37.5 s within one DOAC episode). The match is stored on the library doc (`video_id`,
  `route.video_offset_s`).
- Credits: passages without speaker names credit the guest from the title plus the creator
  (`topics.guest_from_title`); unnamed Lex transcript lines continue the previous speaker. Endcard credits wrap to
  the width and never overlap (`ass.endcard_document`).
- Follows: F4 Dwarkesh Patel (channel; his podcast feed answered 502). Journeys in ai-and-ideas: J1 topic (7 cuts,
  landscape X4), J2 lobotomy (from the taken I1), J3 topic shorts (3 cuts). J4, the page test of "Draft journey",
  you deleted on 2026-10-21.
- Hub step, live 2026-10-21: you answered the permission question for J3 (three private sources) with a yes in chat;
  `hub publish J3 --visibility public --confirm --as-user` → local hub `/r/01M5DZ9J8SQZ5HE99XAHTD9XG9` v1. The
  Shorts re-export carries the link and QR code; `ass.endcard_document` breaks a URL longer than the row after a "/".
- Agent sessions here are refused by the permission classifier for: deleting files or journeys (even with a yes),
  `git restore` of uncommitted work (stash instead), and `hub publish --visibility public` until you have said yes.
- Runner note: `export run` spawns `recomp.exe` from the main venv, i.e. the **main checkout's** code. From a worktree,
  run `RECOMP_JOBS=inline python -m recomp.cli export run …` (in the background) to render with the worktree's code.

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
- Podcast and video copies of one conversation: match by words, not titles, and measure the offset per passage.
- Check rendered frames, not only the checks: the endcard overlap passed every automatic check.
- MCP SDK 2.x: low-level `Server(on_list_tools=…, on_call_tool=…)`, types in `mcp_types` with snake_case fields.
