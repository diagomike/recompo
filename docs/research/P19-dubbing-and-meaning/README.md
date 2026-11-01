# P19: timed, meaning-conserving dubbing with LLMs (and LLM cuts)

**Research from 2026-10-31 to 2026-11-01, now built into the app** (`recomp dub …`, see `APP.md`).

The question: can an LLM understand what is said in a source and write target-language lines that fit the
speaker's speaking time and pauses, the way a professional dub does? Can it do this even when the LLM is weak in
the source, the target, or both (Amharic, Oromo)? We answered it in 11 parallel worktrees on one benchmark of real
speech timing.

## Read in this order

| Document | What it is |
|---|---|
| **`JOURNEY.md`** | The path we travelled: each request, what we tried, the result, the lesson |
| `RESULTS.md` | Every headline number in one place |
| `APP.md` | How the findings became the app's LLM dubber: routes, settings, verbs |
| `BRANCHES.md` | Every branch and worktree, its tip commit, and the folder that holds its work |
| `feasibility-report.md` | The first report: verdicts, literature, film pilot, go/no-go plan |
| `track1-llm-timed-translation.md`, `track2-models.md`, `track3-llm-cuts.md` | The three original tracks |
| `mechanisms-compared.md` | The cross-worktree comparison as it grew |
| `wt-<name>/README.md` | Each worktree's own write-up, with its result files (JSON) next to it |

## The answer in one screen

| Problem | What works | Evidence |
|---|---|---|
| Fit the speaker's time | LLM writes per speech segment and is **measured with the real voice**; exact selection; 2 rounds | 98 % of segments in band, 0 % over 1.1× (`wt-llm-multiround`, `wt-mctr`) |
| Keep the meaning while fitting | **MCTR**: meaning units (core / support / colour) → allocation → variants → exact choice; conserve mode prefers silence to invention | 98.6 % of units kept, 0.07 additions per line (`wt-mctr`) |
| Target with MT only (Oromo) | LLM writes in a strong language → MT → target voice → choose → **back-translation check** | Meaning kept 73 → 93 %, fit 57 → 87 % (`wt-twosided`) |
| Source with MT only (Amharic) | Understand through **several independent MT views**, pin units to the speaker's segments | Adequacy 1.17 → 2.71 of 3, fit 52 → 88 % (`wt-pivot`) |
| Which language should the LLM work in? | Write in the target if the LLM is strong in it, else in the middle language; one language for economy, two for quality | Target-direct: 91 % fit and 88 % natural vs 86 % and 50 % (`wt-routes`) |
| Don't trust one middleman | **Two middle languages from two MT systems** (English + Spanish) | Understanding 2.54 → 2.88; French dub 2.83 vs 2.42 for the best cascade (`wt-bipivot`) |
| What doesn't work | Text-only duration models (15 % floor); a trained duration NMT from scratch (meaning loss); rule/WordNet edits (27 % ungrammatical) | `wt-duration`, `wt-trained-mt`, `wt-algorithmic` |

## Benchmark and method notes

- **Timing frame:** German speakers' speech segments (IWSLT 2023 dubbing test set, Silero VAD, pauses ≥ 0.3 s).
- **Rulers:** real TTS voices (VITS LJSpeech English; MMS Spanish and French).
- **Meaning:** blind 0–3 adequacy against hidden CoVoST references (pivot, routes, bipivot); unit coverage
  (MCTR); chrF only as a secondary signal. It misses meaning damage.
- **MT:** IWSLT Sockeye de→en; Mozilla Firefox Translations (bergamot) de/en/es/fr. Where no MT was reachable,
  Claude acted as a deliberately literal, timing-blind stand-in, and the write-ups say so.
- **Limits:** read speech rather than film dialogue; 24–45 lines per test; Claude both wrote and judged (blind to
  the condition, not to its own style).

## Open (needs your PC or your library)

- The Amharic → Oromo run: Google am↔en, NLLB am→spa, MMS Oromo voice.
- The corpus pilot on 20–50 of your dual-audio titles (language pairs?).
- Lip-synced or narrated dubs?
- A human A/B on the audio.
