# Context: story understanding, recaps and nuance-aware dubbing (2026-10 → 2026-11)

**Who this is for:** anyone picking up this work, whether a person or an agent.

**What it covers:** one long working session across two repositories, in five parts:
1. research on LLM recaps from subtitles;
2. the app built from that research (`storylens`);
3. the decision to run it with the Claude desktop app instead of an API;
4. research on whether jokes and idioms survive dubbing;
5. the nuance layer built into recompo's dubber, and a Google-vs-NLLB comparison.

The same file is in both repositories:

| Repository | Branch | This file |
|---|---|---|
| `LetPastorSpeakInYourLanguage/linger` | `claude/llm-movie-recap-research-eo9g7v` | `CONTEXT.md` |
| `diagomike/recompo` | `claude/p20-nuance-transfer` | `docs/research/CONTEXT-recaps-and-nuance.md` |

---

## 1. The ground rules that shaped everything

- **No LLM API.** Every "thinking" step is done by Claude in the Claude desktop app (or Claude Code). It works by
  answering task files in a shared folder, or by running the project's verbs. The machine does the measurable
  work: parsing, aligning, indexing, selection, timing, rendering. recompo records this as D-26.
- **Offline first.** MT runs on local models (NLLB-200, M2M-100, bergamot) under the worker Python; voices are local
  (Kokoro, MMS). Online engines (Google, edge-tts) are only used behind an explicit `online` switch.
- **Meaning first, then timing.** A dub keeps what is said, and the target voice decides what fits (P19's "voice as
  ruler"). Nothing added later may weaken those two foundations.
- **Measure, and say how.** Every claim below comes from an experiment with its data and scripts in the repo. Most
  judging was done by one model, blind to condition; the caveats are listed with each result.

---

## 2. linger: LLM recaps from subtitles (research)

**Where:** `linger/research/recap/`. The report is `README.md`. Also there:
- `01_literature.md`: literature review;
- `02_agentic_folder_protocol.md`: the folder protocol;
- `03_understanding_architecture.md`: the understanding layer;
- `experiments/exp01…exp16`.

**Question:** from English subtitles (soft or burned in) and media in *any* spoken language, can we produce recaps in
any style and at any length, on top of a persisted understanding that linger can query?

| Finding | Number |
|---|---|
| The plot spine is recoverable from subtitles alone | full causal spine of *Tears of Steel* and *Panic Room*; turning points 3/5 within ±2 scenes |
| …but not what is only on screen | 34 % of *Panic Room*'s salient scenes have no dialogue → a cheap keyframe vision pass fixes the gaps |
| Who said what | heuristics 17–20 %, LLM 62 %, voice clusters × LLM names 80 % |
| Duration slider | nested multiple-choice knapsack over "elastic" beats: at 60 s it keeps 91 % of top-tier beats and all turning points (greedy: 46 %). Every shorter recap is a subset of every longer one |
| Series scale | Friends S1–S3 (73 episodes) in 15 min: all P0/P1 beats, every arc |
| Rendering | four styles end to end; closed-loop fit lands within 1.3 % of the target length |
| Burned-in subtitles | tesseract fails on real double-hardsubbed frames; a vision LLM reads 12/12 lines |
| Language-agnostic sync | Silero VAD recovers subtitle offsets and 25↔23.976 fps stretch exactly |
| An understanding DB helps search | FriendsQA R@5 0.61 vs 0.48 for raw subtitles; speaker names +19 % R@1 |
| Recap-channel quality | 0.66 synopsis coverage, 0 contradictions with a zoom-in pass; what is missing is dialogue-free action |
| Hidden stories (side characters, villains) | name search finds 3 % of a character's lines; a character lens finds 100 % and surfaces "hidden gems" |
| Trait compilations ("Joey being a good friend") | embedding search is at chance; you need a ledger of *acts* per character |
| Talks / podcasts / sermons | topic search is precise (P@10 0.8–1.0); speakers and duplicate recordings are the problems |

**Architecture that came out of it:**
1. evidence;
2. **facts:** a per-scene ledger of who does, says, feels and reveals what, with causes;
3. **structure:** beats, tiers P0–P3, threads, turning points and edges;
4. **lenses:** main story, character, trait, topic;
5. selection, script from the exact lines, checks, render.

Every LLM output cites subtitle line ids, so everything maps back to timestamps.

## 3. storylens: the app built from that research

**Where:** `linger/storylens/`. Start with `README.md`, then `docs/QUICKSTART.md`, `docs/AGENTIC.md` and
`docs/METHODOLOGY.md`.

**What it does:**
- Films, series, podcasts, talk shows, sermons, lectures.
- Main-story recaps from 60 s to unlimited.
- Character stories, trait compilations, and "what X said about Y" no-narrator supercuts.
- A speaker's recurring argument pattern.
- Cross-source search and collections.
- A FastAPI web UI with review gates.

**How the thinking runs (final decision):** there is no API.
- storylens writes task files (`TASK.md`) into `~/storylens-workspace`.
- Claude, in the desktop app, answers them (`answer.json`). You start it by saying "do the storylens queue"; Claude
  reads `CLAUDE.md` in that folder.
- The passes were merged so there are fewer, larger tasks: causes are recorded in P1, the zoom-in pass is folded into
  the script task, and checks are deterministic.

**Commits:** the research is merged from `recap/expNN-*`. Then:
- `e6ad052…7dd8e17`: the app;
- `942afff`: discourse, cross-source;
- `c0e8f1a`: desktop-only, no API.

## 4. recompo P20: do jokes, idioms and nuance survive the dub? (research)

**Where:** `recompo/docs/research/P20-nuance-transfer/`:

| File | Contents |
|---|---|
| `README.md` | the answers |
| `RESULTS.md` | every number |
| `DESIGN.md` | the nuance card and the strategy policy |
| `LITERATURE.md` | earlier work |
| `GOOGLE.md` | Google vs NLLB |
| `data/` | all the data |

Scripts are in `scripts/research/p20/`.

**Benchmark:** 8 random *Friends* scenes, 214 lines.
- 83 gold nuance items: jokes, puns, idioms, slang, sarcasm, cultural references, catchphrases.
- A 14-item stress set: proverbs, running jokes.
- 60 MUStARD sarcasm items.

**Answers:**
1. **Is the understanding layer capable enough for nuance? No.**
   - recompo's meaning map flagged 20 % of the humorous items and flattened 23 % of them. Examples:
     "Bummer." → "too bad"; "like a dog in the street" became a droppable colour unit, which broke the "Woof, woof"
     callback.
   - Writing Spanish from the map kept 67 % of the effects. Plain line-by-line LLM translation kept 87 %.
2. **The old MT rule ("plain wording, no idioms") raised meaning but lowered jokes.** For example, Swahili laugh
   points went from 42 % to 32 %.
3. **What works:**
   - **LLM-strong targets (Spanish):** a nuance card per item (trigger, mechanism, function, dependencies,
     strategy), and the writer naturalizes. 100 % kept, a self-judged ceiling.
   - **MT-only targets (Amharic, Oromo, Swahili):** flatten the *form*, keep the *function*. Use compositional
     images, make sarcasm lexical, keep callback words identical, and make innuendo explicit enough to survive.
     This roughly doubles the jokes that survive. Amharic: 57 % vs 23 % (plain) vs 25 % (raw).
4. **Back-translation checks are only as good as the back-translator.** MADLAD-400 made correct Oromo look like
   nonsense, while NLLB checking its own output is optimistic.

## 5. recompo: the nuance layer in the dubber (built, D-28)

**Where:**
- `recomp/lang/llmdub.py`
- `recomp/verbs/dub.py`
- `recomp/workers/tasks_lang.py`
- `recomp/agent_kit/.claude/skills/recomp-dub/SKILL.md`
- `docs/DECISIONS.md` (D-28)
- `docs/research/P19-dubbing-and-meaning/APP.md` (Nuance section)

**What it does:**
- **Setting:** `nuance: off | mark | on`. The default is `on`; `off` is exactly the P19 dubber.
- **`dub understand`:** asks for nuance items beside the meaning units. The units stay the propositional layer.
- **`dub write`:** shows each item with a guide per writing language: naturalize for strong languages,
  function-preserving English for MT routes. It also shows the chain lines and a series glossary of running jokes.
- **Selection** (`select`, exact dynamic programming):
  - laugh units are promoted to support;
  - each kept nuance item is a small pseudo-unit (0.5 for a laugh, else 0.25), never core, so **a kept joke never
    outweighs meaning or fit**;
  - a declared substitution is not penalised as "added content" in conserve mode.
- **`dub verify`:** checks each item's effect as kept, partly or lost, and flags literal (calqued) idioms. A lost laugh
  gets a `keep_effect` rewrite within the steering rounds.
- **Tests:** unit and e2e, including brute-force equivalence of the selection with nuance on.

## 6. recompo: Google Translate vs offline NLLB (research)

**Where:** `recompo/docs/research/P20-nuance-transfer/GOOGLE.md`.

recompo's own keyless Google module was run on the same benchmark and judged blind with the same rubric.

| Effect kept: raw / plain / nuance pre-edit | NLLB-200 1.3B | Google |
|---|---|---|
| Amharic | 25 / 23 / 57 % | **48 / 49 / 70 %** |
| Oromo | 13 / 16 / 35 % | **31 / 31 / 57 %** |
| Swahili | 45 / 39 / 77 % | 52 / 48 / 72 % (a tie within judging drift) |
| Spanish raw | 67 % | **80 %** (LLM writing each line alone: 93 %) |

- **The nuance pre-edit adds about +20 points on either engine.** The engine adds 0 to +23, and the two gains add up.
- Google and NLLB produce the same output length, so timing is unaffected.
- **Recommendation:**
  - `--online --mt google` for Amharic and Oromo;
  - NLLB offline for Swahili;
  - LLM-written for strong targets.
- **Caveat:** the keyless endpoints are unofficial and rate-limit cloud IPs. Use the batched mode.

---

## 7. Where things stand and what is open

| Item | State |
|---|---|
| linger research + storylens app | pushed on `claude/llm-movie-recap-research-eo9g7v` |
| recompo P20 research, nuance layer, Google comparison | pushed on `claude/p20-nuance-transfer` (not merged to main) |
| **Cross-engine verify for online dubs** (back-translate with a different engine than the one that translated) | in progress, see `docs/BACKLOG.md` |
| Laugh detection on source audio (marks laugh points without the LLM) | open |
| Studio display of nuance marks and kept/lost | open |
| Per-language back-translator table (MADLAD for am/sw, not for om) | open |
| Native-speaker A/B on dubbed audio (es, am, om, sw) | needs people |
| Held-out recall test of the nuance pass, with gold written by someone else | open |
| storylens: real runs on your own titles, through the desktop app | needs your machine |

## 8. Where to start

| You want to… | Read |
|---|---|
| run recaps on a title | `linger/storylens/docs/QUICKSTART.md`, then `AGENTIC.md` |
| understand why storylens is built this way | `linger/research/recap/README.md`, `linger/storylens/docs/METHODOLOGY.md` |
| dub with recompo | `recompo/AGENTS.md` → `docs/STATE.md` → `recomp/agent_kit/.claude/skills/recomp-dub/SKILL.md` |
| understand the nuance layer | `recompo/docs/research/P20-nuance-transfer/README.md` → `DESIGN.md` → D-28 in `docs/DECISIONS.md` |
| choose an MT engine per language | `recompo/docs/research/P20-nuance-transfer/GOOGLE.md` |
