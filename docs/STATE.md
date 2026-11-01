# STATE

The build's working memory. If context runs short, resume from here.

**Last updated:** 2026-11-01 (P19: the LLM dubber is in the app — `recomp dub …`, route settings per media, merged to main with all research; before that 2026-10-31 P19 research; 2026-10-21: M5 complete; P18 backlog run built: fast re-exports, viewer polish, cross-release
matching, gapless recipe player, dub fixes, face-cropped Shorts, semantic search, cloned-voice dubs)

| | |
|---|---|
| Phases | **P0–P16b built** (P16b awaits your review) · **P17 research wing** approved 2026-10-19 with defaults P17-Q1–Q6: **P17a–d built** (find, follow, inbox, library; topics, briefs, journeys from topics; rights, posting queue, hub permission; Follows and Topics pages) · **P18 backlog run built** 2026-10-21 (a–h) |
| Milestones | **M1** ([report](runs/M1-dark-knight.md)) · **M2** ([report](runs/M2-alex-oconnor.md)) · **M3** am/sw/fr + om · **M4** local hub ([report](runs/M3-M4-languages-and-hub.md)) · **M5** follows and topics ([report](runs/M5-follows-and-topics.md)): all done |
| Suite | 100+ fast tests (`pytest -q`), slow speaker test (`pytest -m slow`), live P17 sources (`pytest -m real tests/unit/test_follow_real.py`); the reorder-cache timing assert can flake under heavy load |
| Projects | `C:\Recomposer\projects\dark-knight` (M1, M3), `alex-oconnor` (M2: 5 episodes, 12 cuts, 3 journeys), `ai-and-ideas` (M5: 7 sources, J1–J3, J3 public on the local hub); `_uitest` scratch folder (forgotten from the list; safe to delete) |
| Hub | `python -m hub` on 8790, data in `%USERPROFILE%\.recomp\hub`, seeded test users in `seed_users.json` there. Since 2026-10-22 this PC is the **central hub for the LAN**: `Recomposer.cmd hub-lan` / launch `hub-lan` (0.0.0.0:8790, http://192.168.1.100:8790); other PCs run their own studio with `hub.url` pointing here (README "Two PCs") |
| Remote | `origin` = https://github.com/diagomike/recompo.git, branch `main` (local `master` renamed 2026-10-22) |

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

## P18 backlog run (2026-10-21; plan §6 P18)
- P18a: `export run --speed fast` (or `config render.final_speed fast`) sets the profile's `final_speed`; only the
  final pass reads it (`profiles.final_encoding`: `superfast`, CRF −2), so slot cache keys are unchanged. J2
  landscape, all 11 slots cached: 249 s normal → 100 s fast, same loudness, all checks pass. The studio's Export
  step has a "Fast re-export" box once a journey has exports.
- P18c: `compose/release.py`. Recipes carry `anchors` on file sources (out of the hash). The importer keeps them on
  the source (`meta.release_anchors`, `release_cuts`) when it finds the source by title rather than fingerprint, and
  shifts the imported cuts at once if the copy has a transcript; `source match-release S…` (re)does it, moving cuts
  by the difference to what was applied (`meta.release_match.applied`). `relink --force` points at it.
- Title matching allows 6 % length difference now (PAL runs 4 % short); year and title must still agree.
- P18b (viewer): `personColors()` in `ui.tsx` (a hash of the name into 8 hues; a clash within one source takes the
  next free one, in name order) colours the room's speech/speaker lanes and the transcript's names (`--who`, lifted
  toward white in dark mode by `--who-lift`). Export step: `ExportMatrix` (formats × languages, newest export per
  cell, a bar while rendering; shown from two languages) and the "Fast re-export" box. Look step: `LowerPreview`
  draws each lower third over a frame of its slot at the "Lower" style's place and size, with the blurred fill on
  vertical. Export rows show done-with-problems as a problem (was the blue running chip).
- P18d: `RecipePlayer.tsx` holds two players (a `<video>` and/or a YouTube embed each). While one plays slot n,
  the other has slot n+1 loaded at its in point, paused (`YTHandle.cue`: loads muted, pauses at the time once it
  plays, unmutes); at the out point they swap and the freed one loads n+2. Measured in the pane: local S2→S4 swap
  with no frame of gap (7467.97 → 3006.61, ready state 4); YouTube swap shows the next slot's first frame at once
  and moves ~0.3 s later (the embed's play start). The advance runs on a 20 ms interval (animation frames stop in a
  hidden tab and the old player ran past its out point there).
- P18e: Dark Knight J1, the lines the dub check flagged, shortened with `lang edit` (by the agent): am 456/457,
  sw 456/457, fr 455–458, om 15 lines of the bar scene and the closing question (also fixed the draft's "'em" and
  "'Sababni"). Re-dub: 0 overflow in am/sw/fr/om, all checks pass (X36–X39; am round trip CER 0.12). French keeps
  "Sérieux ?" and "Bonne soirée." in the original voice. The Oromo lines need an Oromo speaker's reading.
- P18f (the user's request, 2026-10-21): profile **`shorts-face`** (reframe `crop-face`) is an extra option next to
  `shorts` (blurred fill), shown beside it in the Export step as "Shorts, Reels, TikTok · cropped to the speaker".
  Default profiles added later are seeded into a project when profiles are listed or exported. `render/faces.py`:
  YuNet (`~/.recomp/models/yunet/`, 230 KB, MIT, sha256 8f2383e4…) runs under the worker python over each slot's
  range at 4 fps (`workers/scripts/faces.py`, frames from ffmpeg, no OpenCV), cached in `cache/faces/`; the main
  face (big, sure, central, near where it was) gives one steady crop per shot from the shot table, slow pans in a
  shot where it moves; ffmpeg `crop` takes a keyframed x expression. No face in a slot → blurred fill. ai-and-ideas
  J3 → X7: crops on Dario, Lex, Ladish, the DOAC host and Alex O'Connor; 258 s for 2:42 including detection.
- P18g: `transcript/semantic.py` + `workers/scripts/embed.py` (multilingual-e5-small, transformers, mean pooling,
  "passage:"/"query:" prefixes; in the worker HF cache, downloaded 2026-10-21 over plain HTTPS: Xet stalled here,
  `HF_HUB_DISABLE_XET=1`). `transcript embed [S…]` queues one job per source (windows of ~40 words / 30 s, half
  overlapping; `cache/semantic/<transcript>.npz` with a text hash); `search --semantic` ranks windows by cosine
  (overlaps merged) and warns about missing or edited indexes. Search page: "By meaning" (`?m=1`) and an "Index every
  transcript" button when nothing is indexed. ai-and-ideas: 7 sources indexed in ~8 min (while a clone dub ran);
  "will machines take away people's work" → Ed Zitron on jobs (S5) first; an Amharic query finds related English
  passages, less sharply. Queries (2026-10-21) go to a resident embedder: `embed.py --serve`, one detached
  worker-python process per studio home (HF_HOME from `worker.hf_home`, offline), started by the first query from
  any caller (CLI, MCP, studio), JSON lines on 127.0.0.1 with a token from `<home>/run/embed.json`, exits after
  `search.embed_idle_s` (600) without a query (`search.resident false` turns it off); a failed start falls back to the one-shot script (index building
  stays a job on the one-shot script). ai-and-ideas from the CLI: first query 9 s (start), then 0.6 s each.
- P18h: `--voice clone` on `export run` (Export step › Languages › Voices: "Original voices (AI)"). `dub.clone_lines`
  takes each translated line's original segment (widened with the same speaker's neighbours to 4–10 s) as the
  voice reference and its text as the prompt, and `workers/scripts/tts_clone.py` (OmniVoice `k2-fsa/OmniVoice`,
  CPU, 16 steps) speaks the line at its natural length, again to fit (≤ 1.4× squeeze) when it is too long; normal
  placement and atempo follow. Lines without a reference use the language's voice. The export goes to
  `<profile>-<lang>-clone` (beside the usual dub) and carries a "voice" credit ("AI voices cloned from the original
  speakers (OmniVoice); not their recordings") in credits.json, the description and the endcard. Dark Knight J1 fr:
  23 lines cloned in ~25 min; after shortening seg:126/183, 1 line over (0.99 s), round-trip WER 0.26 vs 0.04 for
  the studio voice (X41 vs X42). The viewer marks these exports "original voices (AI)" with their own matrix row.

## P19 LLM dubber in the app (2026-11-01, D-25)
- `recomp dub settings | understand | write | fit | verify | status` (docs/VERBS.md; agent skill `recomp-dub`).
  Routes by language strength: `direct`, `source` (src-en), `target` (tgt-en), `middle` (mid-en), `multi` (two or
  more middle languages from different MT systems); `economy` or `quality` budget; MT `google` / `nllb` / `bergamot`
  (worker scripts `mt_nllb.py`, `mt_bergamot.py`); back-translation checks; conserve mode.
- Settings layer studio → project → **source** (`source add --dub-route/--dub-middle/--dub-budget/--dub-views-mt/--dub-mt/--dub-to`)
  → journey; the studio shows them in Add sources → Dubbing, a source's *Dub settings…*, and Translations → *LLM dub*.
- Storage: table `dub_work` (migration 2). `dub fit` is a job (`dubfit`); it writes translations with method `llmdub`
  and per-frame choices. Exports voice each frame at the speaker's pause (`captions[].parts`).
- Tests: `tests/unit/test_llmdub.py`, `tests/e2e/test_llmdub.py`. Write-up: `docs/research/P19-dubbing-and-meaning/APP.md`.
- Offline by default (D-27): NLLB + M2M-100 + bergamot MT and MMS voices; `--online true` (any layer) allows
  Google and edge. `dub models [--download]` checks and fetches the models once. Export dubs follow the same switch.
- Several movies at once: `dub next --limit N` (next stage per journey and language, fits queued as jobs) and
  `dub submit --input batch.json`.
- How it runs (D-26): you and the Claude desktop app in the shared project folder; no LLM API, ever. Whole films in
  batches (`dub understand/write --template --limit N`). All work local; only recipes go to the hub when you publish.
- Not yet: prosody cues, `--dub-*` on links.
- All research branches were merged (history kept) into the session branch and main; the folder
  `docs/research/P19-dubbing-and-meaning/` holds README (index), JOURNEY, RESULTS, BRANCHES, APP and every worktree.

## P19 research (2026-10-31, research only — no app changes)
- Your direction: explore (1) Claude-written timed dubbing scripts, (2) a model / no-training path learned from your
  dual-audio movies (own branch `ccr-327cc642-xnfs3i-track2-models`), (3) LLM cut creation. Mid-run you asked for
  feasibility research instead of app building: the `lang frame`/`lang fit` verb prototype was removed again.
- Report: `docs/research/P19-dubbing-and-meaning/feasibility-report.md` (verdicts, literature, pilot, go/no-go experiments).
- Pilot on two real dual-audio excerpts (movie2parallelDB samples, en→es): `scripts/research/p19/pilot_dub_pairs.py`
  (sherpa-onnx Parakeet TDT v3 + Silero VAD, CPU, ~0.25 RTF). Human-dub speech overlap 0.72/0.81; dialogue rates
  far below read-speech tables; dub says up to 28 % more words than the subtitle; subtracting tracks does not isolate
  the dub voice; token times too coarse for pauses (needs forced alignment + diarisation).
- **Mechanisms round (2026-10-31, worktrees):** one branch per timed-rephrasal mechanism, all on a shared bench
  (IWSLT 2023 de→en test lines, German speakers' real speech frames; 30 k forced-aligned English utterances):
  `…-p19-duration` (text→duration floor ~15 % MAPE), `…-p19-placement` (rate DP: 94–97 % of breaks within a word),
  `…-p19-llm-loop` (Claude timed lines: 0.92 overlap with a real TTS voice, 5 % needing >1.1× speed-up, −7 chrF),
  `…-p19-trained-mt` (IWSLT duration-aware Sockeye baseline, run after your OK: 0.80 voice overlap, normalised chrF
  53.5 — fits like placement alone and loses the most meaning; train pretrained models, not from scratch),
  `…-p19-algorithmic` (rules + WordNet + trigram LM, no neural model: safe edits +0.02 overlap; aggressive ones
  0.90 but 27 % of segments ungrammatical in a blind check; next: an XLM-R masked LM as the judge, on your PC),
  `…-p19-llm-multiround` (**best**: multi-round LLM refinement measured with the voice — 98 % of segments in band,
  0 % needing >1.1× speed-up, 98 % fluent, converges in 3 rounds),
  `…-p19-mctr` (**implementable form**: meaning-conserving top-down rephrasing — meaning units → allocation →
  variants → voice-measured exact selection; same fit in 2 rounds, fewer additions, optional conserve mode),
  `…-p19-twosided` (**MT-only targets**: LLM rephrases the source, MT translates, target voice times, exact
  selection with target-side verification; de→en real MT: ±20 % fit 57→87 %, meaning 73→93 %; en→es: speed-up 55→0 %;
  transfer guide for am/om in its README),
  `…-p19-pivot` (**end to end between two MT-only languages via English**: multi-view MT understanding + prosody →
  pivot meaning map pinned to source segments → two-sided timing; 24 unseen de→es lines: blind adequacy 1.17 → 2.71/3,
  ±20 % fit 52 → 88 %; low-confidence lines flagged for a human; am→om steps in its README),
  `…-p19-routes` (**working-language routing**: the LLM works only in languages it is strong in — direct /
  target-direct / source-side / pivot, economy or quality budget; target-direct beats the pivot route on fit 91 vs
  86 % and fluency 88 vs 50 % natural; pooled two languages 95 % fit with a route prior),
  `…-p19-bipivot` (**two middle languages**: English + Spanish views from two MT systems; understanding 2.54 → 2.88/3,
  French dub with real Mozilla MT + back-translation checks 2.83 vs 2.42 for the best cascade; Mozilla models run
  offline via `mt_bergamot.py`). Summary: `docs/research/P19-dubbing-and-meaning/mechanisms-compared.md`.
  Worktrees live at `/home/user/recompo-wt-*` in the cloud session only.
- Sandbox notes: HuggingFace, arXiv, ACL Anthology are blocked here; GitHub (git and release assets) and PyPI work.
- Open questions for you: language pairs in the library; lip-synced vs narrated dubs. (Agent vs API: agent only, D-26.)
- `tests/unit/test_contract.py::test_verbs_doc_is_current` fails on Linux only (VERBS.md holds the Windows default
  `C:\Users\pc\bin`); unrelated to P19.

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
