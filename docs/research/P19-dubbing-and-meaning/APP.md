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
| `mt_google.py`, `mt_bergamot.py`, NLLB on the PC | `llmdub.MT` + `recomp/workers/scripts/mt_nllb.py`, `mt_bergamot.py` (worker env) |
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

## How it runs (D-26)

- **No LLM API, ever.** This is your local tool. You and the Claude desktop app work in the same project folder:
  - the agent kit there (`AGENTS.md`, the `recomp-dub` skill, `.mcp.json`) gives Claude the verbs;
  - Claude reads the templates and writes the maps, options and checks itself.
- **Whole films in batches.** `dub understand … --template --limit 40` gives the next 40 lines still without a map;
  `dub write … --template --limit 40` gives the next 40 to write. Repeat until `dub status` says what is next.
- **All work stays on your machine.** Only finished recipes may go to the hub, and only when you publish one.
  - The `google` MT engine is the one network call. Choose `nllb` or `bergamot` (worker env) to stay fully offline.
  - Edge voices are network too; MMS voices are local.

## Not built yet

- **Prosody cues** (`pivot.py prosody`) are not in the app: the question detector over-fired on read speech.
- **Links** added with `source add <url>` don't take the `--dub-*` options yet; use `dub settings --at S…` after
  adding.
