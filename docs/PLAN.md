# Recomposer — build plan (execute_v0)

**Status:** awaiting owner approval · **Written:** 2026-10-15 · **Folder:** `D:\py_self\execute_v0`

Recomposer is rebuilt here around one idea: **the app is a set of verbs over a project folder,
and an agent operates those verbs side by side with you.** You and the agent work together
in a local viewer. Sources (movies, podcast links) become transcripts, then chapters, then
meaningful cuts; cuts become journeys; a journey becomes a *recipe*. A recipe renders into
exports in any format and language, and can be shared on a public hub where people explore,
vote, comment, follow and fork each other's recipes. Recomposer's player plays recipes
straight from metadata.

```
 you ──► viewer (web, localhost) ──┐                         ┌──► exports (mp4 · srt · credits · description)
                                   ├─► verbs ─► project folder ┤
 agent ─► recomp CLI / MCP ────────┘   (one      (SQLite +     ├──► recipe.json ──► hub (social: explore · vote ·
                                        registry)  files)      │                     comment · follow · fork · play)
                         workers: local CPU (MVP) │ remote GPU (Kaggle/Colab job folders)
```

---

## 1. Decisions (agreed in conversation, 2026-10-15)

| # | Decision |
|---|---|
| D-01 | **Agent-native.** Every capability is a *verb* in one registry. The CLI (`recomp`), the MCP server, the REST API and the viewer are all generated from or call that registry. Nothing is possible in the UI that an agent cannot do, and the reverse. |
| D-02 | **CLI-first JSON contract.** `recomp <noun> <verb>` prints one JSON envelope. Agents read and write JSON; humans see the same state in the viewer. |
| D-03 | **A project is a folder** (`recomp.db` SQLite + files). Switching projects means pointing at another folder. A studio home holds the project registry, settings and hub login. |
| D-04 | **The recipe is the product; renders are disposable.** A journey is an ordered list of source references and timecodes plus overlays, music and captions. Renders are deterministic and cached per slot, so reordering costs only a re-concatenation. |
| D-05 | **Provenance and precedence are enforced in storage.** Every row records who wrote it (`user` > `agent` > `machine`). The store refuses an agent or machine write over a user-authored field. Every change goes through the operation log and can be undone. |
| D-06 | **Links first, captions first, bytes last.** For links we take metadata and captions, then audio only if ASR is needed, then video only for the ranges a recipe uses. |
| D-07 | **Compute:** local CPU workers for the MVP. Local ASR reuses the faster-whisper environment and cached models in `D:\LangBridgeLocal` (read-only). Remote GPU (Kaggle/Colab) goes through a job-folder protocol, built after the MVP. |
| D-08 | **Export configuration is separate from content.** A journey holds content: slots, overlay text, music bed. *Export profiles* hold format and treatment: aspect, reframe, caption style, music on/off, overlays on/off, language/dub, endcard. You can choose them after chapters and cuts exist, and one run can export a matrix: journey × profiles × languages. |
| D-09 | **Every export carries attribution.** Credits come from source and music metadata. They appear as an end card with a recipe link and QR code, in `description.txt`, in `credits.json` and in the MP4 metadata. |
| D-10 | **You upload, not the app.** The app produces upload-ready packages. After you post, `recomp hub link-post` re-links the posted URL to the recipe. |
| D-11 | **Hub = a social network for recipes, not media.** Work stays private locally until you publish a recipe. The hub plays recipes through official embeds (links) or the viewer's local files. |
| D-12 | **The agent is the language model.** Chapters, cut choices, journey arcs and translations are written by the operating agent through verbs. No API key is needed. Cheap machine fallbacks exist (creator chapters, a TextTiling-style auto-chapterer, Google web translate). |
| D-13 | **This replaces recomposer_v2's constraints where they conflict**: ADR-01 (no network tiers), ADR-03 (no feed, now a hub feed by choice), ADR-07 (no platform download) and ADR-08 (zero ML). Kept from v2: manual-truth precedence (ADR-04), the operation log (ADR-06) and authored journeys (ADR-13). |
| D-14 | **Multilingual from the start.** Any export can be captioned and dubbed into target languages. Acceptance requires **at least three extra dub languages** (edge-tts for easy testing: Amharic, Swahili, French), with Afaan Oromo via MMS-TTS as a stretch goal. |
| D-15 | **Stack:** Python 3.13 venv (FastAPI, pydantic, sqlite3 with FTS5, yt-dlp, edge-tts ≥ 7.3.1, mcp SDK, segno); React 18 + Vite 5 + TypeScript viewer; ffmpeg 8.1 full build. No Docker, no hosted database for the MVP. |
| D-16 | **Names:** product *Recomposer*, Python package `recomp`, CLI `recomp` (`rc` clashes with the Windows resource compiler). |

---

## 2. What exists on this machine (verified 2026-10-15)

| Item | Finding | Consequence |
|---|---|---|
| Python | 3.13.2 has fastapi 0.138, pydantic 2.13, uvicorn, yt-dlp 2026.08.19; 3.14 is the `py` default | App venv on **3.13** |
| ffmpeg | 8.1.2 full: `ass`, `subtitles`, `drawtext`, `xfade`, `acrossfade`, `loudnorm`, `sidechaincompress`, `scdet`, `zoompan` | Whole render engine on ffmpeg |
| SQLite | 3.45.3 with FTS5 | Full-text search with no extra dependencies |
| ASR env | `D:\LangBridgeLocal\.venv` (3.13): faster-whisper 1.2.1, ctranslate2 4.8.2, pyannote 4.0.7, torch 2.14 CPU, transformers 5.17, audio-separator. `.venv-xpu` = same on Intel Arc | Worker python, used read-only |
| Cached models | faster-whisper-large-v3-turbo, wav2vec2-base-960h (EN align), pyannote community-1, wavlm-base-plus-sv, Ethio-ASR-amharic, OmniVoice (+amharic), Gemma-4-E4B OV | ASR, alignment, diarisation, speaker ID and Amharic round-trip check need **no downloads** |
| GPU | none (CPU PyTorch; Arc via XPU env) | ASR on long media runs as background jobs |
| Network | about 0.6 MB/s. yt-dlp lists channels and metadata fine (Alex O'Connor: 5 latest, creator chapters present). **Captions answered HTTP 429** on 2026-10-15 | Caption ladder with backoff and audio+ASR fallback (§3.12) |
| Music | Openverse audio API answers without a key (CC0 / CC BY results from Freesound, Jamendo, …) | Default music source |
| edge-tts | 7.2.8 → **403**; **7.3.1 works** (Amharic synthesised). The sandbox blocks `speech.platform.bing.com` | Pin `edge-tts>=7.3.1`; dub runs need that domain allowed. (Also fixes lang_bridge's 403.) |
| Media | `D:\Recomp\Video\The.Dark.Knight.2026…mp4`: 89 min, 1920×800, H.264, **AAC 5.1**, with a matching `.srt` (1,053 cues, ends 01:25:49). `Obsession.2026…mp4`: 105 min, no subtitles | M1 test media; 5.1 needs a dialogue-preserving downmix |
| Fonts | Arial / Arial Nova, Segoe, **Ebrima and Nyala (Ethiopic)** | Captions in Amharic script work |
| Disk | **D: 15 GB free**, C: 150 GB free | Project folders and caches default to **C:** (open question Q1); source movies stay in place on D: |
| HF token | `~/.cache/huggingface/token` exists | Gated pyannote already usable |

---

## 3. Architecture

### 3.1 Components

| Component | What it is | Port |
|---|---|---|
| `recomp` CLI | Verb runner, JSON envelope | — |
| `recomp serve` | **Studio server**: REST mirror of the verbs, SSE event stream, media range streaming, serves the viewer build | 127.0.0.1:8770 |
| `recomp mcp` | MCP stdio server; tools generated from the registry | stdio |
| `recomp worker` | Job executor; runs worker scripts under the configured worker python | — |
| `hub` | Separate FastAPI service: users, recipes, votes, comments, follows, feeds | 127.0.0.1:8790 |
| `web/` | Vite + React + TS: **studio** entry (local) and **hub** entry (public) | dev 5180 |

### 3.2 Repository layout

```
execute_v0/
  AGENTS.md  CLAUDE.md  README.md  pyproject.toml  requirements*.txt  Recomposer.cmd
  .mcp.json  .claude/{launch.json, settings.json, skills/…}
  recomp/
    registry.py        # @verb decorator: name, pydantic In/Out models, side-effect class, docs, examples
    envelope.py        # JSON envelope, error codes, exit codes
    cli.py             # argparse built from registry; --json/--pretty; stdin JSON input (--input -)
    core/              # ids (ULID + short refs), db (migrations), oplog (undo/redo), precedence guard,
                       # events (SSE bus), config (studio home), paths, timecode parsing, locking
    media/             # probe, fingerprint, ffmpeg runner (progress), shots, peaks, thumbs/sprites, audio extract
    ingest/            # local scan, sidecar/embedded subs, links (yt-dlp ladder), sections fetch
    transcript/        # parsers (srt/vtt/ass/json3), read windows, sync-check, ASR orchestration, align
    index/             # FTS5, optional model2vec embeddings, hybrid search (RRF)
    edit/              # chapters, cuts (snapping, quote-resolve), tags, collections
    compose/           # journeys, slots, overlays, music beds, recipe spec + JSON schema, EDL/OTIO export
    render/            # plan → filtergraphs; slot cache; reframe; ASS caption/overlay generator; audio mix; endcard; QR
    export/            # profiles, export matrix runner, packaging (description/credits/metadata), checks
    music/             # openverse, freesound (optional key), local library, licences
    lang/              # translation (agent-supplied / google web), TTS backends (edge, mms, sapi), dub planner
    speakers/          # diarisation jobs, person registry, embedding match
    workers/           # backends: local subprocess, folder (remote); job protocol; worker scripts (run in worker env)
    server/            # FastAPI app: /api/verb/{noun}/{verb}, /api/events (SSE), /media/{ref}, /ui state
    mcp_server.py
    hubclient/         # login, publish, pull, fork, vote, link-post
  hub/                 # hub service (own package, own SQLite), seed script
  web/                 # studio + hub UI
  notebooks/recomp_worker.ipynb   # remote GPU worker (generated by scripts/build_notebook.py)
  docs/  PLAN.md STATE.md BACKLOG.md DECISIONS.md VERBS.md(generated) RECIPE_SPEC.md AGENT_GUIDE.md
         LESSONS.md gates.md runs/
  tests/ unit/ golden/ e2e/ fixtures/ (synthetic media generated, never committed)
  scripts/ make_fixtures.py gen_docs.py check.ps1 build_notebook.py
```

### 3.3 Studio home and project folder

```
%USERPROFILE%\.recomp\            # studio home (small)
  config.json        # projects root, worker python, HF cache, hub url, default profiles, tts voices
  projects.json      # registry: name → path, last opened, current
  hub_token.json     # hub session (local dev)
  .env               # user-supplied keys (YouTube Data API, Freesound); never printed by any verb

<projects root>\<project>\        # default projects root C:\Recomposer\projects (Q1)
  recomp.project.json   # id, name, kind (movies|channel|speaker|topic|mixed), languages, defaults
  recomp.db             # system of record
  sources\<ref>\        # downloaded media (links), extracted audio (16 kHz wav), captions, info.json
  cache\                # peaks, thumbs/sprites, shots, render slot cache (size-capped, prunable)
  music\                # licensed tracks + <track>.licence.json
  recipes\<journey>.recipe.json     # human-readable, git-friendly copy written on every journey change
  exports\<journey>\<profile>-<lang>\  video.mp4 · captions.srt · description.txt · credits.json · recipe.json · thumb.jpg
  jobs\<job-id>\        # job folders (same protocol local and remote)
  AGENTS.md CLAUDE.md .claude\skills .mcp.json   # agent kit, written by `recomp project init`
```

Local source files are **referenced in place** (absolute path, size and a partial hash of the
first and last 4 MB plus size), never copied. `recomp source relink` repairs moved files by
fingerprint.

### 3.4 Data model (SQLite, migrations in `core/db.py`)

| Table | Key fields |
|---|---|
| `source` | id (ULID), ref (`S1`), kind file\|link, uri/path, platform, platform_id, title, creator, year, duration, fingerprint, rights{licence, owner, attribution, url}, status per stage, meta json |
| `asset` | source_id, role original\|audio16k\|section\|proxy, path, range, codec info |
| `transcript` | source_id, origin sidecar\|embedded\|platform\|asr\|translation, language, model, primary flag, offset_s, quality metrics |
| `segment` / `word` | transcript_id, idx, start, end, text, speaker_turn / word timing + probability (FTS5 virtual table over segment text) |
| `person` / `speaker_turn` | project-level people (name, voice embedding centroid) / turn → person, origin |
| `shot` | source_id, t, score |
| `chapter` | source_id, ref (`S1.c4`), start, end, title, summary, tags, origin, locked |
| `cut` | ref (`C17`), source_id, start, end, title, quote (text inside), why, tags, emotions, people, chapter_id, snap info, rating, origin, locked |
| `journey` / `slot` | ref (`J2`), title, intent, description, language, status / order, cut_id, trim overrides, section heading, transition, per-slot overlay ids |
| `overlay` | journey/slot scope, kind title\|lower_third\|quote\|caption_note\|endcard, text, style, timing |
| `music_track` / `music_bed` | source api, url, title, artist, licence, attribution, file / journey_id, track_id, in/out, gain, duck, fades |
| `profile` | name, aspect, resolution, fps, reframe, captions mode+style, overlays on/off, music on/off, loudness target, endcard, languages, dub mode |
| `export` | journey ref + recipe hash, profile, lang, status, outputs, check results |
| `translation` | target lang, segment/overlay id, text, origin |
| `op` | ULID, time, actor user\|agent\|machine, verb, args, inverse, affected refs (undo/redo, activity feed) |
| `job` | type, backend, status, progress, log path, depends_on, result |
| `ui_state` | viewer selection, focused ref, pending "agent asks" notes (the co-work bridge) |

**Short refs** (`S3`, `S3.c4`, `C17`, `J2`, `J2#3`, `M5` for music, `P1` for profile) are what
you and the agent say in chat ("move C17 before C9"). ULIDs stay internal and are used for the
hub.

### 3.5 Provenance and precedence

- Every write passes `actor`. The CLI defaults to `agent` (`RECOMP_ACTOR`); the viewer writes as `user`; jobs write as `machine`.
- A field last written by `user` is **locked** against `agent` and `machine` writes. The store raises `E_PRECEDENCE` with a hint to ask the user. `--as-user` exists for when you tell the agent in chat to override; it is logged.
- Each op stores its inverse. `recomp op undo [--n N]`, `recomp op redo` and `recomp op log --actor agent --since 10m` exist, and the viewer Activity panel shows the same log with actor badges.

### 3.6 Verb contract

```json
{ "ok": true, "verb": "cut.add", "data": { … }, "warnings": [], "op": "01K…", "refs": ["C17"],
  "next": ["recomp journey add J2 C17", "recomp preview C17"] }
{ "ok": false, "verb": "cut.add", "error": { "code": "E_PRECEDENCE", "message": "…", "hint": "…" } }
```

- Exit codes: 0 ok, 2 usage, 3 not found, 4 precedence/locked, 5 conflict, 6 external (network/429), 7 job failed.
- Input as flags, or `--input file.json` / `--input -` for bulk (chapters, cuts, translations).
- Times accept `01:12:03.4`, `4323.4`, `72m3.4s`; output is always seconds plus a clock string.
- Long work returns `{"job": "…"}`. `recomp job wait <id> --timeout 100` returns early with progress, so agents never block long. `recomp job tail <id>` shows the log.
- Reads are paged and compact so agents save context: `--limit/--cursor`, `--format compact|full`.
- Side-effect classes in the registry: `read`, `write`, `heavy` (job), `network`, `external-publish` (hub). MCP annotations and the agent guide use them.
- `docs/VERBS.md`, `recomp help --json`, MCP tool schemas and `web/src/api.gen.ts` are all generated from the registry; a test fails if any of them drift.

### 3.7 Verb catalogue (target; phases in §6)

| Noun | Verbs |
|---|---|
| `context` | (no verb) one-call briefing: project, counts, per-source pipeline status, open jobs, viewer selection, pending asks, suggested next steps |
| `doctor` | checks ffmpeg/fonts/worker python/models/disk/hub/network endpoints |
| `project` | `init <path> [--kind]`, `use`, `list`, `show`, `set`, `archive`, `agent-kit` (re)install |
| `source` | `add <path\|glob\|url> [--limit --since --match]`, `list`, `show`, `status`, `relink`, `rights set`, `remove`, `fetch-audio`, `fetch-sections` |
| `transcript` | `import <file>`, `fetch-captions`, `asr [--model --lang --on local\|remote]`, `align`, `sync-check [--fix]`, `read <S> [--from --to --chapter --format]`, `outline <S>`, `set-primary`, `edit-segment` |
| `search` | `<query> [--sources --person --chapter --mode bm25\|semantic\|hybrid --limit]`, `index rebuild` |
| `shots` / `peaks` | `detect`, `show` / `build` |
| `chapter` | `seed` (creator/platform chapters), `auto` (machine), `set <S> --input` (bulk, snaps to segment boundaries), `add/edit/merge/split/remove`, `list` |
| `cut` | `add <S> --from --to \| --segments 412..430 \| --quote-start "…" --quote-end "…"` (`--snap words\|shots\|silence\|none`, `--pad`), `suggest <query>`, `edit/trim/split/merge/remove`, `tag`, `list [--tag --person --source]`, `show` |
| `journey` | `new`, `add <J> <C…> [--at]`, `move`, `remove`, `section <J> "Heading" [--at]`, `trim-slot`, `transition`, `show` (timeline with totals), `duplicate`, `from-search` (draft), `validate` |
| `overlay` | `add <J\|J#n> --kind --text [--style --at --dur]`, `auto-lower-thirds <J>`, `edit/remove/list` |
| `music` | `search <query> [--licence commercial\|any --max-dur]`, `get <result>`, `library add <file> --licence`, `bed add <J> <M> [--gain --duck --fade]`, `bed edit/remove` |
| `profile` | `list`, `new <name> --aspect 9:16 --res 1080x1920 --reframe fit-blur --captions burn:karaoke --music on --endcard recipe --langs en,am`, `edit`, `show` |
| `preview` | `<C\|J> [--profile]` → fast 480p render, then the viewer opens it |
| `export` | `run <J> --profiles a,b --langs en,am,sw,fr`, `cuts <C…> --profile`, `status`, `check <export>`, `package <export>`, `recipe <J>` (json), `edl <J>`, `otio <J>` |
| `lang` | `translate <J> --to am [--input file]` (agent-supplied) or `--engine google`, `voices <lang>`, `dub <J> --lang am --mode voiceover\|replace [--voice]` |
| `speaker` | `diarize <S>`, `list`, `name <S:SPK_n> "Name"`, `match` (cross-source), `merge` |
| `job` | `list`, `show`, `wait`, `tail`, `cancel`, `retry` |
| `worker` | `serve [--folder]`, `status`, `config` |
| `op` | `log`, `undo`, `redo` |
| `ui` | `selection`, `show <ref> [--at t]`, `ask "question"` (pinned note in the viewer), `notes` |
| `hub` | `login`, `logout`, `whoami`, `publish <J> --visibility`, `pull <recipe-id>`, `fork`, `vote`, `comment`, `follow`, `feed`, `link-post <J> <url>` |
| `trends` | `youtube [--region --category]` (API key), `search <topic> --since 7d`, `channel <url> --since 30d` |
| `cache` | `size`, `prune [--max-gb]` |

### 3.8 Recipe spec v1 (`docs/RECIPE_SPEC.md`, JSON Schema in `compose/recipe.schema.json`)

```json
{
  "recipe": "recomposer/1",
  "id": "01K…", "title": "What the hero costs", "intent": "…", "language": "en",
  "author": {"handle": "local"}, "created": "2026-10-16T…Z", "hash": "sha256:…",
  "sources": {
    "S1": {"kind": "file", "title": "The Dark Knight", "year": 2026, "duration": 5341.66,
           "fingerprint": "pf1:…", "subtitle_fingerprint": "…", "rights": {"owner": "…", "notice": "…"}},
    "S2": {"kind": "link", "platform": "youtube", "id": "T_7Fm1VujEs", "url": "https://youtu.be/T_7Fm1VujEs",
           "title": "Are Plants Conscious? - Michael Pollan", "creator": "Alex O'Connor"}
  },
  "slots": [
    {"source": "S2", "in": 1203.40, "out": 1261.05, "title": "…", "quote": "…", "people": ["Alex O'Connor"],
     "section": "1 · The question", "transition": {"type": "cut"}, "overlays": ["o1"]}
  ],
  "overlays": {"o1": {"kind": "lower_third", "text": "Alex O'Connor · Are Plants Conscious?", "at": 0.5, "dur": 4}},
  "music": [{"track": "M1", "title": "…", "artist": "…", "licence": "CC-BY-4.0", "url": "…",
             "in": 0, "out": null, "gain_db": -18, "duck_db": -10}],
  "translations": {"am": {"overlays": {"o1": "…"}, "captions": "embedded"}},
  "credits": [ … generated … ],
  "links": {"hub": "http://127.0.0.1:8790/r/01K…", "posts": []}
}
```

Rules: times are source seconds; a slot carries its own quote text so it stays readable without
the source; credits are always derived and never hand-typed; `hash` covers content and
excludes `links`. A file source can be matched on another machine by fingerprint, or by
subtitle/audio alignment when the release differs (offset estimate, M5).

### 3.9 Render engine

1. **Plan:** recipe + profile + language → a render plan (pure function, golden-tested).
2. **Slot render** (cached at `cache/render/<hash(source-fp,in,out,profile-video-params)>.mp4`): accurate seek, trim, fps and timebase normalisation, reframe, and audio as 48 kHz stereo. 5.1 is downmixed with a dialogue-preserving pan (`FL=FC+0.3*FL+0.3*BL`, `FR=FC+0.3*FR+0.3*BR`).
3. **Assemble:** concat demuxer for hard cuts; `xfade`/`acrossfade` where slots ask for transitions.
4. **Overlay pass:** one generated `.ass` file holds captions remapped to the output timeline from word timings, karaoke highlighting, titles, lower thirds and quote cards. Fonts are chosen by script (Ebrima for Ethiopic).
5. **Audio:** dialogue (or dub) + music bed with `sidechaincompress` ducking and fades, then two-pass `loudnorm` to the profile target (default −14 LUFS, −1 dBTP).
6. **Endcard:** a 3–4 s slate with the title, recipe link and QR code (segno), plus short credits.
7. **Package:** MP4 metadata (`comment=recipe:<url>`, `title`, audio `language` tags), `.srt` per language, `description.txt` (title, credits, recipe link, ready to paste), `credits.json`, `recipe.json`, `thumb.jpg`.

Reframe modes: `fit-blur` (default for 2.4:1 films going to 9:16), `crop-center`, `crop-x` (per-slot
offset), `fit-pad`. Face-aware crop is backlogged. Preview profile: 854×480 or 480×854,
`ultrafast`, CRF 30.

### 3.10 Export profiles (seeded)

| Profile | Format | Treatment |
|---|---|---|
| `shorts` | 1080×1920, 30 fps | fit-blur, karaoke captions burned, lower thirds, music on, endcard, −14 LUFS |
| `landscape` | 1920×1080 | clean captions as sidecar + burned option, lower thirds, music on, endcard |
| `square` | 1080×1080 | fit-blur, clean captions burned |
| `clip` | source aspect, 1080p | single-cut export, captions burned, short endcard |
| `preview` | 480p | everything on, fastest settings |

Languages are a profile dimension: `--langs en,am,sw,fr`. Each language adds translated
captions and overlays, and with `dub` on, a dubbed audio track. With `--multitrack`, one MP4
carries all audio tracks plus the original.

### 3.11 Workers and jobs

- **Local backend:** a subprocess under `config.worker.python` (default `D:\LangBridgeLocal\.venv\Scripts\python.exe`, `HF_HOME=D:\LangBridgeLocal\cache\hf`) runs `recomp/workers/scripts/*.py`, which use only the worker env's packages. Progress goes through `status.json`; the studio server relays it over SSE.
- **Job folder protocol** (from lang_bridge, one writer per file): the app writes `job.json` and `in/`; the worker writes `status.json`, `out/` and `log.txt`. Supports `depends_on`, resumable stages and takeover by heartbeat.
- **Remote backend:** the same folders inside a synced folder (Google Drive / HF bucket), processed by `notebooks/recomp_worker.ipynb` on Kaggle or Colab. Tested locally with `recomp worker serve --folder` acting as a fake remote.
- Job types: `asr`, `align`, `diarize`, `embed-speakers`, `separate`, `tts`, `shots`, `render`, `export`, `fetch` (links), `index`.
- One CPU-heavy job at a time by default (16 GB RAM); network jobs run in parallel with it.

### 3.12 Link ingest ladder

1. `yt-dlp --flat-playlist` for channels and playlists → candidate list (title, duration, date, views). The user or agent picks with `--limit`, `--match` or `--since`.
2. `info.json`: metadata, **creator chapters → seed chapters**, available caption tracks.
3. Captions: manual subs, then auto (`en-orig`), as `json3` (word timing), with `--sleep-subtitles` and exponential backoff on 429. Impersonation via `curl_cffi` (`yt-dlp[default,curl-cffi]`) in the app venv.
4. If captions stay blocked: audio-only download (format 251/140, about 50–90 MB per 90 min, 2–3 min at 0.6 MB/s) → local ASR job. The ASR transcript is primary.
5. Video: `--download-sections` for the slot ranges only (± 2 s), at 720p or 1080p per profile. If section download stalls (seen 2026-10-10), the fallback is a whole-file download at 480p for preview and the profile's resolution only for export.
6. The last resort, only if you allow it: `--cookies-from-browser` (Q5). On bot checks I stop and ask.
7. Everything is cached under `sources/<ref>/`; refetching is idempotent.

### 3.13 Search and index

- FTS5 BM25 over segments, with source, chapter, person and time filters. Hits come back with ± N segments of context and a ready-to-run `cut add` command.
- Optional semantic layer: `model2vec` static embeddings (`minishlab/potion-base-8M`, about 30 MB, numpy-only, fast on CPU) per segment window, stored as `.npy` per project. Hybrid ranking uses Reciprocal Rank Fusion. A multilingual model (Amharic/Oromo) is backlogged.
- `cut suggest <query>` expands hits to complete thoughts: sentence boundaries, speaker turns, 15–90 s.

### 3.14 Multilingual and dubbing

- **Translation:** the agent translates through `lang translate --input` (best quality, agent origin). `--engine google` (lang_bridge's clients5 endpoint) is the bulk fallback. Translations are stored per segment and overlay and stay editable and lockable.
- **TTS backends:** `edge` (edge-tts ≥ 7.3.1: am-ET, sw-KE, fr-FR, so-SO, es-ES, …), `mms` (facebook/mms-tts-orm for Afaan Oromo, in the worker env, about 150 MB, CC-BY-NC weights) and `sapi` (Windows offline voices, a fallback).
- **Dub planner:** each slot's segments → target text → TTS clip → fit into the segment window. Speed-up goes to 1.25× with `atempo`; if it still overflows, the line is flagged and the agent shortens the translation and re-voices. Leftover space is padded.
- **Mix modes:** `voiceover` (original ducked to −18 dB under the dub; the MVP default and robust) and `replace` (background from audio-separator in the worker env, plus the dub).
- **Automated dub checks:** language tags; no TTS overflow > 150 ms; loudness on target; **round-trip intelligibility**: faster-whisper re-transcribes the fr/sw dub (WER), and the cached Ethio-ASR re-transcribes the am dub (CER). Thresholds are measured first, then fixed in `gates.md`.
- Voice cloning (OmniVoice / Seed-VC via lang_bridge) is a later, opt-in backend with an AI-dub label in credits.

### 3.15 Hub (social for recipes)

- **Entities:** user (handle, display name, bio, password hash with stdlib `scrypt`), session token, recipe (owner, visibility private\|unlisted\|public, current version, tags, languages, forked_from, thumbnail), recipe_version (json, hash), source_page (canonical key: `youtube:<id>`, or `work:<title>:<year>:<fp>`), vote (+1/−1, one per user), comment (threaded, one level, edit/delete own), follow, post_link (posted video URL ↔ recipe), report.
- **Feeds:** following, new, trending (score = votes with time decay), by tag, by source, by person.
- **Pages (hub UI):** Explore, Recipe page (player, slot list with source links and timecodes, credits, votes, comments, fork, *open in studio*), Source page (all recipes that cut this source, plus a heatmap of its most-cut moments), Profile (recipes, followers/following, follow button), Tag page.
- **Hub recipe player:** link sources play through the YouTube IFrame API with start/end per slot. File sources show what is needed and offer *open in local studio* (deep link to `127.0.0.1:8770`).
- **Privacy:** everything is private by default. `hub publish` sends only the recipe JSON and a thumbnail; local paths are stripped. Publishing to a non-local hub always needs your go-ahead in chat.
- **Local first:** the hub runs at `127.0.0.1:8790` with SQLite and seeded test users. Public deployment (host, Postgres, OAuth) is a later decision of yours.

### 3.16 Viewer (studio) and the co-work bridge

- **Screens:** Start (projects, create, switch) · Sources (pipeline status per source, add files/links) · **Source room** (video, word-highlighted transcript, lanes for chapters, cuts, shots, waveform and speakers; select a range → cut) · Search (cross-source hits, play in place, add to journey) · **Journey builder** (slot list with drag-reorder and trims, sections, overlay and music lanes, *play recipe* without rendering, *render preview*) · Exports (profile editor, matrix runner, outputs and check results, description/credits copy buttons) · Jobs · Activity (op log with actor badges, undo) · Hub (explore, recipe, profile).
- **Live:** the viewer subscribes to `/api/events`, so you watch the agent's cuts appear as it works.
- **Bridge:** your selection (range, refs) is stored in `ui_state` → `recomp ui selection`, so you can say "cut this". `recomp ui show C17 --at 3` moves your view. `recomp ui ask "…"` pins a question for you in the viewer.
- **Self-guiding:** each screen has a short guide panel and empty states that explain the next step. Compact, transcript-first, light/dark themes, IBM Plex and CSS-variable tokens, matching your other tools.

---

## 4. Agent toolkit (so any agent can operate the app)

| Piece | Content |
|---|---|
| `AGENTS.md` (repo and every project) | Mental model; golden rules (only verbs, never touch `recomp.db`; run `recomp context` first; read before you cut; respect `E_PRECEDENCE`; long work → jobs; ask before `external-publish`; keep context small with `outline` and windows); the standard pipeline; refs and time syntax; how to show the user things (`ui show`, `preview`); error codes |
| `CLAUDE.md` | `@AGENTS.md`, plus the skills list, MCP, launch configs, the no-subagents rule |
| `.claude/skills/recomp-operate` | Verb cheatsheet, the envelope, jobs, undo, common failures |
| `.claude/skills/recomp-chapters` | How to chapter by media type (film scenes and beats vs podcast topics), granularity, title and summary style, the bulk JSON format |
| `.claude/skills/recomp-cuts` | What makes a meaningful cut: a complete thought or beat, standalone context, a hook at the start, 15–90 s for shorts; quote-based cutting; snapping |
| `.claude/skills/recomp-journeys` | Arc patterns (hook, build, turn, resolve), cross-source compilations ("every time X on Y"), pacing, overlay copywriting, music matching |
| `.claude/skills/recomp-export` | Profiles, the language matrix, dub modes, checks, credits, packaging for upload, re-linking posts |
| `.claude/skills/recomp-ingest` | Local scans, the link ladder, captions vs ASR, handling 429 and bot checks (stop and ask) |
| `.mcp.json` | `recomp mcp` (stdio), the same verbs for Claude Desktop and other MCP clients |
| `.claude/launch.json` | `studio` (8770), `web-dev` (5180), `hub` (8790) |
| `.claude/settings.json` | Allow-list for `recomp *` read verbs, so co-work isn't interrupted by prompts |
| `recomp project init` | Writes AGENTS.md, CLAUDE.md, skills and `.mcp.json` into the project folder, so opening Claude Code (or Codex) in a project folder works directly |
| `docs/AGENT_GUIDE.md` | Worked transcripts: a movie journey and a podcast compilation, verb by verb |

---

## 5. Testing strategy

- **Unit:** timecode parsing, subtitle parsers (srt, vtt, ass, json3; malformed numbering like the Dark Knight `.srt`), snapping, quote resolution, precedence guard, oplog undo/redo, registry/schema/doc drift, recipe validation and hashing, caption remap to the output timeline, dub fitting, hub API.
- **Golden:** render plans and filtergraph strings, ASS output, description and credits text.
- **Synthetic media** (`scripts/make_fixtures.py`, generated at test time): a 90 s lavfi video whose colour changes every second plus a burned frame counter; a sine tone with known silences; a 5.1 variant; a matching `.srt` and word-timed `json3`. Render tests check **source-time mapping by sampling pixel colour** at output timestamps, durations by ffprobe, loudness by `ebur128`, and caption timing.
- **E2E (pytest -m e2e):** the fixture project goes ingest → transcript → chapters → cuts → journey → export (2 profiles × 2 languages with a stub TTS) → hub publish → pull. It runs offline.
- **Real-media acceptance runs** M1 to M3 (§7), driven by me as the agent through the CLI, with reports in `docs/runs/`.
- **UI:** viewer and hub flows checked in the built-in browser pane (screenshots in run reports); `tsc --noEmit` and component tests.
- **Gates** (`docs/gates.md`, measured and dated): render determinism (same hash → same frames); caption sync error < 80 ms on fixtures; reorder re-export with a warm slot cache < 25 % of the cold time; `recomp context` < 300 ms; SSE agent-to-viewer latency < 1 s; full test suite green; MCP tool list = registry = VERBS.md.

---

## 6. Build phases

Each phase ends with its tests green, docs/STATE.md updated and a local git commit. `[auto]` = I can verify
without you; `[you]` = needs you.

**P0 — Foundations and agent contract**
venv (3.13) and pyproject with the `recomp` entry point · registry, envelope, CLI · studio home config
· project init/use/list/show · SQLite migrations · ULIDs and short refs · oplog with undo/redo ·
precedence guard · SSE event bus · `context`, `doctor` · generated VERBS.md and `help --json` · MCP
server skeleton (registry → tools) · AGENTS.md, CLAUDE.md, skill skeletons, launch.json, `.mcp.json` ·
git init. *Done when:* `recomp project init` on a temp folder and `recomp context` work; undo works;
drift tests pass; Claude Code can list the MCP tools. `[auto]`

**P1 — Ingest and media**
local scan (globs, extensions) · probe (port from recomposer_v2 `media/probe.py`) · fingerprint ·
sidecar and embedded subtitle discovery (port `subtitles.py`) · audio extraction (16 kHz mono wav, 5.1
aware) · shots (port `shots.py`, ffmpeg `scdet`) · peaks (port `peaks.py`) · thumbnail sprites ·
source status. *Done when:* the fixture project and `D:\Recomp\Video\The.Dark.Knight*` ingest with
status shown. `[auto]`

**P2 — Transcripts, search, ASR**
parsers · `transcript import/read/outline` · FTS5 index and `search` · local ASR job
(faster-whisper turbo int8, VAD, word timestamps; lang_bridge's `segments_from_words`) · `align` (wav2vec2 EN,
BSD-2 `align_core` vendored with attribution) · `sync-check` (ASR on 3 × 60 s windows vs subtitles →
offset estimate; `--fix`) · optional model2vec semantic layer. *Done when:* Dark Knight subtitles are
searchable; sync-check reports the offset; ASR on the fixture is word-timed. `[auto]`

**P3 — Chapters and cuts**
`chapter seed/auto/set/edit/merge/split` · `cut add` by time, segments or quote · snapping (port
`cuts/boundaries.py`: words, shots, silence) with padding · `cut suggest` · tags, emotions, people,
rating · lists and filters. *Done when:* quote-based cuts resolve to times within 50 ms of word
boundaries on fixtures; snapping golden tests pass. `[auto]`

**P4 — Studio server and viewer v1**
FastAPI REST mirror · media range streaming · SSE · `ui selection/show/ask` · web scaffold
(Vite + React 18 + TS) · Start, Sources, Source room (video, transcript, lanes), Search, Activity
with undo, Jobs · launch.json. *Done when:* in the browser pane I can see the agent's `cut add` appear
live and select a range in the viewer that `recomp ui selection` returns. `[auto]`

**P5 — Journeys and recipes**
journey, slot, section, transition, overlay and music-bed verbs · recipe spec, JSON Schema, hashing,
`recipes/*.recipe.json` mirror · Journey builder UI with drag-reorder and **play recipe** from local
files (no render) · EDL and OTIO export. *Done when:* a fixture journey round-trips through recipe
JSON, plays in the viewer and validates against the schema. `[auto]`

**P6 — Render and export**
render plan · slot cache · reframe modes · ASS generator (clean, karaoke, quote; script-aware fonts)
· overlays · audio mix with ducking and loudnorm · transitions · endcard with QR · packaging · export
checks · profiles and the matrix runner · `preview` · single-cut exports. *Done when:* fixture
pixel-mapping, loudness and caption-timing tests pass; the reorder gate is measured. `[auto]`

**P7 — Music**
Openverse search, download and licence capture · local music library · Freesound (only with your
key) · credits integration · music lane in the builder. *Done when:* a CC BY track ends up correctly
credited on the endcard, in `description.txt` and in `credits.json`. `[auto]`

**▶ M1 — Dark Knight acceptance run** (§7.1). Report: `docs/runs/M1-dark-knight.md`.

**P8 — Links**
yt-dlp ladder (§3.12) · channel and playlist pick lists · creator chapters as seeds · caption fetch
with backoff and impersonation · audio-only fetch → ASR · section fetch for slots · YouTube IFrame
player in the viewer's recipe player. *Done when:* the fixture link tests (mocked) pass and one real
short video goes link → captions or ASR → cut → section download → export. `[auto]`, pausing for you
only on bot checks.

**P9 — Speakers**
diarisation job (pyannote community-1, cached) · person registry · `speaker name` · cross-source
matching (wavlm-sv embeddings, cosine threshold, machine origin) · search and cut filters by person ·
speaker lane in the Source room. *Done when:* on two podcast episodes, naming Alex in one labels him
in the other above the threshold, and errors are listed. `[auto]`

**▶ M2 — Alex O'Connor acceptance run** (§7.2). Report: `docs/runs/M2-alex-oconnor.md`.

**P10 — Multilingual and dubbing**
translation store and `lang translate` (agent / google) · TTS backends (edge ≥ 7.3.1, mms, sapi) ·
dub planner, fitting and re-voicing · voiceover and replace mixes · translated captions and overlays ·
multitrack MP4 · automated dub checks including round-trip ASR. *Done when:* the fixture journey
exports with a stub TTS in 3 languages offline, and real edge-tts works for am, sw and fr.
`[auto]` (network approval for edge-tts once `[you]`)

**▶ M3 — Multilingual acceptance** (§7.3). Report: `docs/runs/M3-multilingual.md`.

**P11 — Hub (social)**
hub service, schema and migrations · auth (local) · publish, pull and fork · votes, comments,
follows · feeds · source pages and moment heatmap · post links · hub UI (Explore, Recipe, Source,
Profile, Tag) · hub recipe player (embeds) · `hub` verbs · seed users. *Done when:* the multi-user
flows pass in API tests and in the browser pane with three seeded test users. `[auto]`

**▶ M4 — Hub acceptance:** M1 and M2 recipes published, voted, commented, followed, forked, and
played back on the hub; the posted-URL link flow works (with a placeholder URL you choose).

**P12 — Remote workers**
folder backend · heartbeat and takeover · notebook generator and `recomp_worker.ipynb` (Kaggle 2×T4,
Colab T4, local Jupyter) · `--on remote`. *Done when:* the fake-remote e2e test passes locally. The
real Kaggle/Colab run is `[you]`: you start the notebook and I watch the folder.

**P13 — Trends**
`trends search/channel` (yt-dlp, keyless) · `trends youtube` (Data API, your key in `.env`) → pick list
→ `source add`. *Done when:* keyless trends return ranked candidates and ingest one. `[auto]` / key
`[you]`

**P14 — Hardening and handover**
`Recomposer.cmd` launcher · project backup/export (zip without media) · cache pruning · source
relinking and cross-release offset matching · performance pass · full docs (README, AGENT_GUIDE
transcripts) · final regression of M1 to M4 · BACKLOG of what's next (face-aware reframe, voice cloning
via lang_bridge, public hub deployment, multilingual embeddings). `[auto]`

---

## 7. Acceptance runs (scripted)

### 7.1 M1 — The Dark Knight (local movie + `.srt`)

1. `recomp project init C:\Recomposer\projects\dark-knight --kind movies`
2. `recomp source add "D:\Recomp\Video\The.Dark.Knight*.mp4"`: the file is referenced in place and the `.srt` is picked up.
3. probe, shots, peaks, audio extraction (5.1 → mono 16 kHz) as jobs.
4. `transcript sync-check S1` (local ASR on 3 windows) → offset under 0.3 s or fixed automatically.
5. **Full local ASR of the film as a second transcript** (background, about 30–60 min on CPU): validates the no-subtitles path; agreement with the `.srt` is measured (WER on aligned lines).
6. I read the transcript (`outline` and windows) and write **≥ 12 scene chapters** with summaries, then **≥ 20 cuts** with titles, why, tags and emotions, snapped to words and shots.
7. Two journeys: **J1** a single-theme short (45–75 s) and **J2** a 3–5 min landscape arc with sections. You can redirect themes in the viewer at any time.
8. Music: `music search` → a CC0 or CC BY bed on each journey; overlays: title card, quote cards, auto lower thirds.
9. Exports: `shorts` and `landscape` for J1 and J2, plus `clip` for 3 single cuts; previews first.
10. Checks: durations, loudness −14 ± 1 LUFS, caption sync on 5 known lines, endcard present, credits complete, the files play in the browser pane.
11. Reorder J2 (move 2 slots) → re-export → measure the cache gain.
12. Viewer walkthrough with screenshots. You review; your notes become BACKLOG items.

### 7.2 M2 — Alex O'Connor (links)

1. `recomp project init C:\Recomposer\projects\alex-oconnor --kind channel`
2. `recomp source add https://www.youtube.com/@CosmicSkeptic/videos --limit 30` → pick list → choose **5 episodes** on one theme (for example consciousness, suffering or God), plus 1 short video for a quick full run.
3. Metadata and creator chapters → seed chapters; the caption ladder outcome is recorded per episode; **at least one episode goes through audio + local ASR** even if captions work, so the fallback is proven.
4. Diarisation on 2–3 episodes → name Alex and the guests → cross-episode matching.
5. `search` across episodes → `cut suggest` → **≥ 8 cuts from ≥ 3 episodes** → **J1 "<theme> — across N conversations"** (60–90 s short) and **J2** (4–6 min landscape), with person lower thirds.
6. Section downloads for the slot ranges only; the downloaded size is reported.
7. Exports as in M1; recipe published to the **local hub**; the hub recipe player plays J1 through YouTube embeds.

### 7.3 M3 — Multilingual exports (≥ 3 additional dub languages)

1. For M1 J1 and M2 J1, plus M2 J2 in landscape: translations to **Amharic (am), Swahili (sw) and French (fr)**. I write them as the agent; Google is the comparison and fallback.
2. Dubs with edge-tts: `am-ET-MekdesNeural/AmehaNeural`, `sw-KE-ZuriNeural/RafikiNeural`, `fr-FR-DeniseNeural`, in voiceover mode. Replace mode is tested on one export.
3. **Stretch:** Afaan Oromo via `facebook/mms-tts-orm` (about 150 MB download, non-commercial weights).
4. Per export: target-language burned captions (Ethiopic font for am), translated overlays and endcard, an audio language tag, a multitrack MP4 variant.
5. Automated checks: overflow, loudness, tags, round-trip intelligibility (faster-whisper for fr/sw, Ethio-ASR for am), with the numbers in the report.
6. `[you]` listen to a sample per language; your verdicts are recorded in the report.

---

## 8. Working method for the long run

- I work through the phases in order. After each phase I commit locally (no remote, nothing pushed) and update `docs/STATE.md` (where we are) and `docs/BACKLOG.md` (every open task by priority).
- I write a run report at each milestone, and send you a short note there and keep going unless something needs you.
- Heavy and long commands (ASR, downloads, full renders) run in the background; I don't sit polling.
- No subagents (your global rule). I keep the plan on the session task list.
- **I stop and ask when:** YouTube bot checks or persistent 429s happen (cookies are your call); a download over 500 MB is needed; disk space for a project would pass 20 GB; anything would leave this machine besides fetching sources, music, models or TTS (the hub stays local); a creative direction is ambiguous enough that guessing would waste a long render.
- **I never:** upload or post anywhere; enter API keys, passwords or cookies (you place keys in `.env`; I may create hub test accounts only on localhost); modify `D:\LangBridgeLocal` or other repos; delete source media.

---

## 9. Risks and mitigations

| Risk | Mitigation |
|---|---|
| YouTube 429 / bot checks on captions or downloads | Backoff, impersonation, audio-only ASR fallback, section downloads, ask before cookies |
| CPU ASR is slow on long media | Background jobs, VAD, turbo int8, subtitles/captions first, remote GPU in P12 |
| D: has 15 GB free | Projects and caches on C:, size-capped render cache, sources referenced in place |
| Section download stalls | Low-res whole-file fallback for preview, profile resolution for the final export only |
| edge-tts endpoint changes (403) | Pin ≥ 7.3.1, MMS and SAPI fallbacks, stub TTS for tests |
| Copyright / platform strikes on posted exports | Credits on every export, rights fields per source, a description template; posting stays with you |
| Agent overwriting your edits | Storage-level precedence, the op log and undo |
| Verb surface drifting from the docs | Everything generated from one registry; drift tests |
| Scope size | Phase gates; M1 delivers a usable studio before links, speakers, dubs or the hub |

---

## 10. Open questions (each has a default I'll use unless you say otherwise)

| # | Question | Default |
|---|---|---|
| Q1 | Where do projects and caches live? D: has only 15 GB free | `C:\Recomposer\projects` (source movies stay on D:) |
| Q2 | Git: init this folder and commit locally after each verified phase? | Yes, local only, nothing pushed |
| Q3 | Allow edge-tts network access (sandbox prompt) for dubs | Yes, approved when it first prompts |
| Q4 | Afaan Oromo via MMS-TTS (non-commercial weights) for testing | Yes, as the stretch goal |
| Q5 | `--cookies-from-browser` as the last step of the YouTube ladder | No; ask you when it's needed |
| Q6 | Theme of the Alex O'Connor test journey | I choose from what the 30 latest episodes cover and tell you; change it any time |
