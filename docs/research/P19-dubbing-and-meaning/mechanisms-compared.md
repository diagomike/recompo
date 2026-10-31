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
| `ccr-327cc642-xnfs3i-p19-trained-mt` | Trained duration-aware NMT (IWSLT Sockeye baseline: phonemes + durations, time counters) | yes (after your OK) | **0.80** speech overlap with a real voice (0.86 with its own durations), normalised chrF **53.5**: fits like placement alone, loses the most meaning |
| `ccr-327cc642-xnfs3i-p19-algorithmic` | Fully algorithmic rephrasing: placement + rule/WordNet edits judged by a trigram LM (no neural model) | yes | Safe edits: **0.85** overlap (+0.02 over placement), 94 % fluent segments; aggressive edits: 0.90 but only 73 % fluent (blind check). chrF misses the damage |
| `ccr-327cc642-xnfs3i-p19-llm-multiround` | **Multi-round LLM refinement**: each round measures every segment with the voice; the LLM rewrites only out-of-band ones from 2–4 measured alternatives and restores plain wording where possible | yes | **Best overall:** 98 % of segments in band (0.8–1.05×), 0 % over 1.1×, 0.92–0.93 overlap, 98 % fluent, chrF 64.1; converges in 3 rounds |

## The comparison that matters (45 German-speaker lines, measured with a real TTS voice)

| Mechanism | Speech overlap | Segments within ±20 % | Segments needing > 1.1× speed-up | chrF vs reference |
|---|---|---|---|---|
| Plain translation | 0.72 | 13 % | 69 % | 70.7 |
| Human reference translation + placement | 0.80 | 51 % | 26 % | 100 (is the reference) |
| Plain translation + **placement** (no rewording) | 0.82 | 62 % | 21 % | 70.7 |
| **Trained duration-aware NMT** (IWSLT baseline) | 0.80 | 49 % | 12 % | 47.8 (53.5 normalised) |
| Fully algorithmic edits, safe (v2) | 0.85 | 66 % | 18 % | 69.8 |
| Fully algorithmic edits, aggressive (v1) | 0.90 | 89 % | 19 % | 68.2 (but 27 % of segments ungrammatical) |
| **LLM timed** (one pass) | 0.91 | 88 % | 35 % | 65.0 |
| LLM timed + revision against the text ruler | 0.91 | 88 % | 35 % | 64.9 |
| LLM timed + revision against the voice (one round, R3) | 0.92 | 89 % | 5 % | 63.5 |
| **LLM multi-round refinement (R6)** | **0.92** | **97 %** | **1 %** | 64.1 |

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

6. **A from-scratch trained model is not the way to train.** The IWSLT duration-aware baseline (trained on
   CoVoST, ~300 k sentences) keeps its own clocks (0.86) but, with a real voice, fits no better than placement
   alone (0.80). It loses the most meaning (normalised chrF 53.5 vs 65–72). The architecture idea (timing tokens,
   countdown counters) is sound. The model to train on your corpus is a **pretrained** multilingual model (NLLB/mT5
   or an LLM) fine-tuned with timing tokens or preference-tuned for duration (SSPO-style), scored against the
   real voice.

7. **Fully algorithmic rephrasing is not competitive** (worktree `algorithmic`). Safe rule/synonym edits change a
   phrase by ~5 % and add +0.02 overlap. Forcing bigger changes breaks the English (blind fluency check: 73 %
   fluent segments vs 100 % for the LLM loop and 99 % for placement only). chrF hides it. The weak part is the
   trigram-LM judge; a pretrained masked LM (XLM-R/BERT) plugged into the same search is the variant to test on
   your PC (HuggingFace is blocked here).

8. **Multi-round LLM refinement is the strongest method** (worktree `llm-multiround`). Three more measured rounds
   after R3 took segments in band from 74 % to 98 % and cut overruns to zero, with fluency at 98 % and slightly
   better chrF (de-padding). Each round only touches what the voice flags (22 → 9 → 3 segments). Overlap plateaus
   near 0.93 because of the frame itself (a voice cannot fill "he said," in 0.73 s without padding).

**Blind fluency** (Claude judging 290 shuffled unlabelled phrases): LLM loop R3 100 % fluent segments, placement
only 99 %, algorithmic safe 94 %, algorithmic + voice 81 %, algorithmic aggressive 73 %, trained NMT 28 %.

Numbers from a second run of the voice check (`wt-trained-mt/compare.json`, VITS sampling ±0.01): R3 0.92 overlap,
93 % within ±20 %, 6 % needing speed-up.

## Next steps
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
