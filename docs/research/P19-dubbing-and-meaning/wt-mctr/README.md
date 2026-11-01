# Worktree `mctr`: meaning-conserving, top-down timed rephrasing (spec, implementation, bench run)

**Your request (2026-10-31):** an *optional* meaning-understanding, meaning-conserving, top-down rephrasing for
timing adjustment in rounds, optimised and implementable.

**What it is:** rephrase a line to fit a speaker's speech segments by working from **meaning down to words**.

1. Decide what the line means and which parts matter.
2. Decide which parts each segment can carry in its time.
3. Write words.
4. Measure the real voice and choose the best combination exactly.
5. Revise only what still misses.

"Optional" is a switch: **fit mode** (timing first) or **conserve mode** (silence before invention).

Code: `scripts/research/p19/mctr.py` (library + CLI), `test_mctr.py` (5 unit tests).
Data: `maps.json`, `variants_r1.json`, `variants_r2.json`, `chosen_*.json`, `meaning_verify.json`,
`meaning_scores.json`, `compare.json`.

## 1. Algorithm

```
for each line (source text + speech segments of the speaker):
  A UNDERSTAND   (LLM, once)   meaning map = gist, locked terms, units u = {text, src words, tier}
                               tier ∈ core (must survive) | support (keep if time) | colour (droppable); w = 3/2/1
  B ALLOCATE     (algorithm)   u.seg = segment whose timeline share contains the middle of u.src
                               (char position of src in source → fraction of speech time; monotone)
                               budget(seg) = dur × voice_rate (syllables/s measured on the dub voice)
  C REALISE      (LLM)         per segment 2–3 variants {text, units, added?}: tight / normal / full,
                               told: must-carry units, may-carry units, syllable band, previous segment's end
  D MEASURE      (voice)       duration of every variant with the voice that will speak it (cached)
  E SELECT       (exact)       argmax over one variant per segment:
                                 Σ w(covered units) − α·Σ fit(voice/dur) − β·duplicates − γ·additions
                                 s.t. every core unit covered (fallback: best without the constraint)
  F REVISE       (LLM, rounds) segments still outside the band get a request with numbers:
                                 "×1.07: shorten ~2 syl: drop colour, then support; core [u5,u6]; optional [u4,u7]"
                               new variants join the pool → back to D; stop when none or no improvement
  G VERIFY       (LLM-judge)   on the final line: covered units, additions, meaning errors → coverage score
```

**Fit penalty:** 0 inside the band 0.8–1.05. Outside it, 25·log² of the distance to the band, ×3 when running long,
+0.25.

**Conserve mode** (`--conserve`):

- γ = 2 per added piece of content (variants declare `added`);
- under-fill down to 0.65× costs only 0.1 + 2·log² (a short silence);
- revision requests are not raised for soft under-fill.

**Complexity:** E enumerates ∏ |variants(seg)| ≤ 3–5 per segment, k ≤ 3–4 segments, so ≤ 625 combinations per line;
exact and instant. All LLM steps are per line (A) or per segment (C, F) and can be batched; D is cached.

**Why top-down helps**

- The writer is told exactly which meaning each segment must and may carry, so first-round variants mostly fit:
  **89 % in band after round 1** vs 45 % for a plain timed pass (R1).
- The optimiser trades meaning against time with explicit weights instead of the writer's guesswork.
- Revision requests name the units to drop or add, so fixes stay inside the source meaning.
- Verification uses the same units, giving a meaning score that does not depend on one reference translation.

## 2. Bench results

The same 45 lines and German speaker frames as all other worktrees. Voice = VITS LJSpeech (fresh synthesis).
Meaning = **blind** unit-coverage judgement: four outputs per line shuffled A–D, key applied afterwards; Claude
judged.

| Method | Overlap (voice) | Within ±20 % | > 1.1× speed-up | Units kept (weighted) | Core kept | Added content / line | Meaning errors / line | Sequential rounds |
|---|---|---|---|---|---|---|---|---|
| Plain translation + placement | 0.83 | 65 % | 22 % | 99.8 % | 100 % | 0.00 | 0.00 | 0 |
| Algorithmic + voice | 0.87 | 80 % | 14 % | 92.6 % | 92 % | 0.04 | **0.38** | — |
| LLM multi-round (R6) | **0.92** | **99 %** | 4 % | **99.3 %** | **100 %** | 0.22 | 0.02 | 6 |
| **MCTR fit mode** | 0.91 | 98 % | **2 %** | 98.6 % | 99 % | 0.16 | 0.02 | **2** |
| **MCTR conserve mode** | 0.90 | 94 % | **2 %** | 98.6 % | 99 % | **0.07** | 0.02 | **2** |

(Cached voice: MCTR fit mode has 83/85 segments in band. The two misses are a 0.22 s breath segment that stays
silent by design, and "he said," in 0.73 s.)

Round by round (cached voice):

| | Round 1 | Round 2 |
|---|---|---|
| Segments in band | 76/85 (89 %) | 83/85 (98 %) |
| Revision requests | 8 | 1 (accepted) |
| Core units kept | 45/45 lines | 45/45 lines |

**Findings**

1. **Top-down reaches the multi-round result in 2 rounds instead of 6.** Fit within ±20 % is 98 % vs 99 %, and
   overruns are lower (2 % vs 4 %). The meaning map front-loads the work that otherwise takes measured trial and
   error.
2. **It invents less.** Added content falls from 0.22 per line (R6) to 0.16 in fit mode and 0.07 in conserve
   mode, where silence is cheaper than padding ("too afraid to do anything ~~at all~~", "the ~~honest~~ truth",
   "~~both~~ philosophy", "the ~~very~~ first light").
3. **The price is small and explicit:** about 0.01–0.02 speech overlap (dropped colour words and short silences)
   and 0.7 % weighted unit coverage. Every dropped unit was colour or support except one core slip. You can see
   exactly what was dropped and why.
4. **Plain translations are the meaning ceiling (99.8 %) but do not fit** (22 % need speed-up). Algorithmic edits
   damage meaning (0.38 errors/line). All LLM-based methods keep ≥ 98.6 % of the meaning while fitting.
5. **chrF is not the meaning measure.** R6 64.1, MCTR 63.1, conserve 64.0, while unit coverage separates them
   clearly and catches additions chrF ignores.

## 3. Implementable design (for when building resumes)

| Piece | Where it would live in Recomposer | Notes |
|---|---|---|
| Meaning map (A) | `lang understand <journey> --to <lang>`: a verb that returns the map template; the agent (or an API backend) writes `maps.json`; stored per segment/unit (translation table or a new `meaning_unit` table) | Cache per source transcript; reuse for cuts (Track 3: same units) |
| Allocation (B) | pure function (`mctr.allocate`) over the transcript's word timings (better than char position when word times exist) | Needs runs/segments from forced alignment + diarisation (pilot finding) |
| Variants (C, F) | `lang variants` / `lang revise`: templates with must/may units and syllable bands; the agent fills them | `PROMPTS` in `mctr.py`; JSON in, JSON out |
| Voice measure (D) | `lang/dub.py` already synthesizes per line; add a duration-only pass with the *same* voice (edge-tts, OmniVoice clone, MMS) and cache by (voice, text) | The ruler must be the voice (llm-loop finding) |
| Selection (E) | `mctr.select` (exact) | Parameters α, β, γ, band, soft floor in config; `--conserve` = journey setting |
| Rounds | a job: measure → select → requests → agent → repeat; stop at ≤ 2 % out of band or no change | Converged in 2 rounds here |
| Verify (G) | optional `lang verify`: LLM-judge coverage per line, shown in the translation editor next to each line | Gives a meaning score per line for review |
| Placement | the dub places each chosen phrase at its segment's start (per-run placement) instead of per caption line | Replaces atempo speed-up in most cases |

**Defaults:** band 0.8–1.05, α = 4, β = 1, fit mode γ = 0, conserve mode γ = 2 with soft floor 0.65, 3 variants per
segment, at most 3 rounds.

**Cost per line** (LLM): one understanding call, one realisation call for all segments, revisions only for the
~10 % of segments that miss. That is fewer sequential calls than the multi-round loop.

## 4. Caveats

- 45 read sentences, one voice. Claude wrote the maps and variants and judged meaning (blind, but the same
  model). The conserve-mode meaning numbers re-use the blind annotations, with 5 re-chosen lines (plain wording)
  annotated non-blind.
- Allocation by character position is a proxy. With word-timed source transcripts, allocate by word times.
- Unit tiers are judgement calls by the understanding step. A human pass on tiers for important content (names,
  numbers, negation) is cheap and worthwhile.
