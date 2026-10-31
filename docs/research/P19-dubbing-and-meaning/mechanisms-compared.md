# Timed rephrasal for dubbing: mechanisms compared (2026-10-31)

Your request: explore the different modelling mechanisms for timed rephrasal in parallel worktrees. Each mechanism
has its own branch and worktree. All of them are scored on one benchmark built from **real speech timing**:

- **Lines:** the IWSLT 2023 dubbing test set (CoVoST2 de→en).
- **Frame:** recordings of **German speakers** reading each line. Their speech segments are what the English must
  fit.
- **Training data:** 30,000 English utterances with forced-aligned phone timings, for the duration and placement
  models.
- **Shared code** (main research branch): `scripts/research/p19/bench.py`, `bench_frames.py`.

| Branch (worktree) | Mechanism | Ran? | Headline |
|---|---|---|---|
| `ccr-327cc642-xnfs3i-p19-duration` | Text → duration models (syllables, phones, learned phone means, ridge, boosting) | yes | All within **15–18 % error**; learning gains ~2 points. Text cannot predict a person's timing better than ~15 %. |
| `ccr-327cc642-xnfs3i-p19-placement` | No-training prosodic alignment: split a line onto a speaker's segments | yes | Rate-matching DP: **94–97 % of breaks within one word** of the real pause (59–69 % exact). Lexical priors add a little exactness but hurt elsewhere. |
| `ccr-327cc642-xnfs3i-p19-llm-loop` | LLM (Claude) writes per segment against budgets, then revises with measured durations | yes | **0.92 speech overlap** with a real TTS voice, 5 % of segments needing > 1.1× speed-up, at −7 chrF vs the reference |
| `ccr-327cc642-xnfs3i-p19-trained-mt` | Trained duration-aware NMT (IWSLT Sockeye baseline: phonemes + durations, time counters) | **no** | Model and data downloaded. Installing its Sockeye fork from GitHub was refused by this session's safety check: needs your OK |

## The comparison that matters (45 German-speaker lines, measured with a real TTS voice)

| Mechanism | Speech overlap | Segments within ±20 % | Segments needing > 1.1× speed-up | chrF vs reference |
|---|---|---|---|---|
| Plain translation | 0.72 | 13 % | 69 % | 70.7 |
| Human reference translation + placement | 0.80 | 51 % | 26 % | 100 (is the reference) |
| Plain translation + **placement** (no rewording) | 0.82 | 62 % | 21 % | 70.7 |
| **LLM timed** (one pass) | 0.91 | 88 % | 35 % | 65.0 |
| LLM timed + revision against the text ruler | 0.91 | 88 % | 35 % | 64.9 |
| **LLM timed + revision against the voice** | **0.92** | **89 %** | **5 %** | 63.5 |

The professional-dub reference point is speech overlap ~0.7–0.8 (Brannon 2023; our film pilot 0.72 / 0.81).

## What this says about the mechanisms

1. **Placement is solved enough without training.** A duration model plus a dynamic programme lays words on a
   speaker's pauses (94–97 % within a word). On its own it lifts a plain translation from 0.72 to 0.82 overlap with
   zero meaning cost. Every system should have it underneath.
2. **Length has to be written, not squeezed.** Translations, human ones included, don't fit a speaker's time by
   themselves (only ~half the segments within ±20 %). An LLM told the budgets gets ~90 %. This is where an LLM, or a
   trained model, earns its place.
3. **The ruler must be the real voice.** Text-only duration models have a ~15 % floor. Lines perfected against the
   text ruler still overran the real voice in a third of segments; one revision round against measured TTS audio
   fixed nearly all of them (35 % → 5 %). **The loop is: plan with a cheap model → synthesize → measure → revise
   the failures once.**
4. **The cost is meaning, mainly through padding.** −7 chrF against a single reference. Part of that is legitimate
   rewording; part is filler added for slow speakers. The next knob is allowing silence inside a segment (a budget
   floor) instead of padding. A dubbing director would let the actor pause.
5. **Learning helps where the signal is not timing.** Duration (+2 points) and lexical break models (± a few points)
   gain little from training on read speech. The places where your dub corpus should pay off are:
   - **what dubbers say** (wording and compression style, the subtitle→dub gap: 28 % more words in the Heroes dub);
   - **where dubbers choose to pause** in film dialogue (deliberate, unlike read speech);
   - **voice-specific durations** for am/om.

   Those are the trained-model experiments to run on your library.

## Next steps

- **Trained-mt worktree:** say "allow installing the IWSLT Sockeye fork" and I run it on the same 45 lines (or all
  192), so a trained duration-aware model sits in the same table. Or run it on your PC or Colab
  (`wt-trained-mt/README.md`).
- **Budget floor experiment** (llm-loop): allow up to ~25 % silence per segment instead of padding; expect chrF to
  recover with little loss of overlap.
- **On your library:** the same loop with the dub corpus as few-shot examples (retrieval) and as training data, in
  your real language pairs.

## Caveats

- 45 lines, one TTS voice (VITS LJSpeech, stochastic ±0.005). The German frames come from read sentences, not film
  dialogue.
- chrF against one reference penalises valid paraphrase. A human A/B on the audio is the real test.
- Claude both wrote the lines and acted as the planner. It never saw the English references while writing; two
  references surfaced in an error log after all rounds were done.
