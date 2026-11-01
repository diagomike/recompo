# From research to the app: the LLM dubber (2026-11-01)

The app now carries what P19 found as `recomp dub …` verbs (CLI, MCP, REST and the studio, all from the registry).
Every option is a setting that follows the media.

## Settings: one set of options, four layers

| Layer | Where it is stored | Set with |
|---|---|---|
| studio (every project) | `config.json` → `dub` | `recomp dub settings --at studio …` |
| project | project manifest → `dub` | `recomp dub settings --at project …` |
| **source** (the media you load) | `source.meta.dub` | `recomp source add <file> --dub-route … --dub-middle … --dub-to om`, or `recomp dub settings --at S1 …` |
| journey | `journey.settings.dub` | `recomp dub settings --at J1 …` |

A higher layer wins value by value. `recomp dub settings J1 --to om` shows each source's effective settings, the
layer each value came from, and the route they give.

In the studio, the same controls appear in three places:

- Sources → *Add sources* → **Dubbing**: set while loading media.
- Sources → a source's menu → **Dub settings…**
- Translations → **LLM dub**: per journey and language, with the route steps shown.

| Setting | Values | Research |
|---|---|---|
| `route` | `auto`, `direct`, `source` (src-en), `target` (tgt-en), `middle` (mid-en), `multi` | `wt-routes`, `wt-pivot`, `wt-bipivot` |
| `middle` | middle languages in order, e.g. `en` or `en,es` | `wt-bipivot` |
| `views_mt` | MT systems for the understanding views, one per middle language: `google`, `nllb`, `bergamot` | `wt-bipivot` (an independent second system is what consolidates the meaning) |
| `mt` | MT into the target and for back-translation | `wt-twosided` |
| `budget` | `economy` (one writing language) or `quality` (two, pooled) | `wt-routes` |
| `verify` | `auto` (when MT crosses into a weak language), `always`, `never` | `wt-twosided` |
| `conserve` | meaning-conserving mode (costs added content, allows short silences) | `wt-mctr` |
| `band`, `rounds`, `mt_prior`, `min_pause` | fit band 0.8–1.05; 2 rounds; pooled prior 0.5; frame pause 0.3 s | `wt-llm-multiround`, `wt-routes`, `wt-placement` |
| `strong` | the languages the LLM is strong in (decides `auto`) | `wt-routes` |
| `voice` | target voice (default: the language's configured voice) | — |

## How `auto` picks the route

| Source | Target | Route | The LLM reads | The LLM writes |
|---|---|---|---|---|
| strong | strong | `direct` | the source | the target |
| strong | weak | `source` | the source | the source (+ a middle language in quality mode) |
| weak | strong | `target` | MT views of the source in the middle language(s) | the target (+ the middle language in quality mode) |
| weak | weak | `middle`, or `multi` with two middle languages | MT views in the middle language(s) | the first middle (+ the second in quality mode) |

## The verbs (the agent writes, the machine measures)

| Stage | Verb | Machine | Agent |
|---|---|---|---|
| 1 | `dub understand J1 --to om --template` / `--input maps.json` | Speech frames from word timings; MT views (whole line + per frame) for every middle language and system | The meaning map: units (core/support/colour) pinned to frames, confidence, notes |
| 2 | `dub write … --template` / `--input options.json` | Per frame: seconds, syllable target for the target voice, units, writing language(s) | 2–4 options per frame, each labelled with its units |
| 3 | `dub fit …` (a job) | MT of crossing options, the target voice speaks every candidate, exact selection (DP over units covered), writes the lines as translations (`llmdub`) and the per-frame choice | — |
| 4 | `dub verify … --template` / `--input checks.json` | Back-translations of the chosen options that crossed MT | Units kept and errors per option, then fit again |
| 5 | `dub write … --template` again | Only the frames still out of band, with syllable targets | Rewrites (`steer`) |
| — | `dub status J1 --to om` | Where it stands and the next command | — |

Then `export run --langs om` voices **each frame at the speaker's own pause**. The caption carries the chosen
phrases; the dub builder places one clip per frame. If you edit the line afterwards, it falls back to the whole
line.

## Code map

| Research | App |
|---|---|
| `scripts/research/p19/timing.py` (syllables, runs) | `recomp/lang/llmdub.py`: `syllables`, `frames` |
| `mctr.py` `select` (exhaustive product) | `llmdub.select`: exact DP over the set of units covered (same optimum; tested against brute force) |
| `routes.py` `plan` | `llmdub.plan` (adds `multi`, back-translation targets, aliases) |
| `mt_google.py`, `mt_bergamot.py`, NLLB on the PC | `llmdub.MT`, `engine_for` + `recomp/workers/scripts/mt_nllb.py`, `mt_m2m100.py`, `mt_bergamot.py`, `fetch_models.py` (worker env) |
| `wt_multiround.Voice` | `llmdub.Ruler` (any configured backend: edge, MMS, stub; cached) |
| `twosided.py select` with lazy verification | `recomp/workers/tasks_lang.py` `fit` (job `dubfit`) |
| `pivot.py views/sheet` | `dub understand --template` |

Storage: table `dub_work` (migration 2), one row per journey, language, kind (`map`, `options`, `verified`,
`choice`) and key. It goes through the op log, so undo works and the user's edits outrank the agent's.

Tests:

- `tests/unit/test_llmdub.py`: routes, aliases, budgets, frames, selection against brute force, error avoidance,
  settings layers.
- `tests/e2e/test_llmdub.py`: settings → understand → write → fit → verify → fit → export, with per-frame voicing.
  Also multi-middle views and the target-direct override.

## Offline by default, online when you want it (D-27)

| | Offline (default, `online: false`) | Online (`--online true`) |
|---|---|---|
| MT for the views | NLLB-200, plus **M2M-100** as the independent second system; Mozilla **bergamot** where it covers the pair (European languages, not Amharic or Oromo) | the same, plus Google |
| MT into the target, back-translation | NLLB (or the system you pick, if it can do the pair) | the same, plus Google |
| Voices | **MMS-TTS** for the language (`facebook/mms-tts-orm`, `-amh`, …) or your configured `tts.mms` voice | Edge neural voices first (`tts.voices`) |

- **Which engine.** Each MT crossing gets the engine you asked for if it can do the pair and is allowed. Otherwise
  it gets the first offline system that can, and the two understanding views take different systems where possible.
  The route says when it substituted (`notes`).
- **Getting the models once.** `recomp dub models` lists what the project's routes need (Hugging Face repos in the
  worker cache, bergamot pairs) and what is already here. `recomp dub models --download` fetches the missing ones;
  after that, nothing goes online.
- **Switching.** `--online true` works at any layer: `dub settings --at studio|project|S1|J1`, or
  `source add --dub-online`.
- **Drafts.** `lang translate --engine nllb|m2m100|bergamot` drafts offline too.

### Offline voices

| Voice | Choose it with | Notes |
|---|---|---|
| **MMS-TTS** for the language (default offline) | `--voice mms:facebook/mms-tts-orm`; any MMS language by ISO 639-3 code (`kin`, `tir`, …); `config set tts.mms.<lang> <model>` | One speaker per language. Long lines speed up naturally: the VITS speaking rate goes up to 1.35×, before any time-stretch |
| Original speakers (OmniVoice clone) | `--voice clone` (export only) | Each line in its speaker's voice; credited as AI voices |
| Windows SAPI | `--voice sapi:<name>` | Built-in voices on Windows |
| Edge neural voices (online) | an edge voice name, with `online: true` | Best quality; needs the network |

`recomp lang voices om` lists the offline voices first, with whether each is downloaded. It lists edge voices only
when online is allowed (or with `--online`). `recomp lang say "…" --lang om --voice mms:…` auditions a voice.

In the studio, the LLM dub dialog has a **Voice** picker (offline group, online group when allowed) with an
**Audition** button. The voice can be set at any layer (`dub settings --voice`), when adding media
(`source add --dub-voice`), or for one export (`export run --voice`).

## Several movies at once

- `recomp dub next --limit 40` looks at every journey whose media has dub languages (`--dub-to`). For each journey
  and language it gives the next stage (map, write, check, rewrite) with that stage's template, up to 40 lines in
  all. Journeys whose next step is the machine's get a `dub fit` job queued.
- `recomp dub submit --input batch.json` takes all the answers at once (`{"J1:om": {"maps"|"options"|"checks": …}}`)
  and queues the fits. Those run while Claude reads the next batch.
- Repeat until `dub next` returns nothing. `--journeys J1,J4 --to om` narrows it.

## How it runs (D-26)

- **No LLM API, ever.** This is your local tool. You and the Claude desktop app work in the same project folder:
  - the agent kit there (`AGENTS.md`, the `recomp-dub` skill, `.mcp.json`) gives Claude the verbs;
  - Claude reads the templates and writes the maps, options and checks itself.
- **Whole films in batches.** `dub understand … --template --limit 40` gives the next 40 lines still without a map;
  `dub write … --template --limit 40` gives the next 40 to write. Repeat until `dub status` says what is next.
- **All work stays on your machine.** Only finished recipes may go to the hub, and only when you publish one.
  - Offline by default (D-27): no network at all once `dub models --download` has run.

## Not built yet

- **Prosody cues** (`pivot.py prosody`) are not in the app: the question detector over-fired on read speech.
- **Links** added with `source add <url>` don't take the `--dub-*` options yet; use `dub settings --at S…` after
  adding.
