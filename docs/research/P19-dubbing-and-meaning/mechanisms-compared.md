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
| `ccr-327cc642-xnfs3i-p19-mctr` | **Meaning-conserving top-down rephrasing (MCTR)**: meaning units with tiers → units allocated to speech segments → unit-labelled variants → voice-measured exact selection (max meaning, band, core kept, optional cost on added content) → targeted revisions | yes | **Same fit as multi-round in 2 rounds instead of 6** (98 % within ±20 %, 2 % >1.1×), fewer additions (0.16/line; **0.07 in conserve mode** vs 0.22), 98.6 % of meaning units kept (blind), overlap 0.90–0.91 |
| `ccr-327cc642-xnfs3i-p19-twosided` | **Two-sided optimiser for MT-only targets** (Amharic/Oromo path): LLM writes source-side options (compact, MT-friendly, steered to measured MT expansion, MT-robust) → black-box MT → target voice timing → exact selection with lazy target-side verification | yes (de→en real MT; en→es stand-in MT) | de→en: within ±20 % 57 → **87 %**, meaning kept 73 → **93 %**, MT errors/line 1.13 → 0.40; en→es: >1.1× speed-up 55 → **0 %**, within ±20 % 59 → 93 % |
| `ccr-327cc642-xnfs3i-p19-pivot` | **End to end between two MT-only languages through English**: source ASR → several independent English MT views (whole, per segment, terse/full, glosses) + prosody cues → LLM pivot meaning map pinned to source segments, with confidence → two-sided timing into the target on the source speaker's segments | yes (de→en real ASR+MT as the "low-resource" source; en→es stand-in MT) | 24 unseen lines, blind adequacy 0–3: naive cascade **1.17** (71 % badly wrong) → **2.71**; within ±20 % 52 → **88 %**, 0.81 → 0.88 overlap; confidence predicts failures (high 3.0, low 1.5) |
| `ccr-327cc642-xnfs3i-p19-routes` | **Working-language routing**: the LLM reads and writes only in languages it is strong in; per pair a route (direct / target-direct / source-side / pivot) and a budget (economy = one writing language, quality = two pooled) | yes (24 fresh de-speech lines → es) | Target-direct vs pivot route: within ±20 % **91 vs 86 %**, natural Spanish **88 vs 50 %**, same meaning (2.58 vs 2.54); pooled two languages **95 %** fit, needs a route prior to keep fluency; understanding is ~⅔ of tokens |

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

9. **Top-down, meaning-conserving rephrasing (MCTR) is the implementable form** (worktree `mctr`). Starting from
   a meaning map (units tiered core/support/colour) and allocating units to segments before writing, it reaches
   the multi-round result in 2 rounds, chooses variants by exact optimisation, and in conserve mode prefers a
   short silence to invented words. A blind unit-coverage check (the meaning measure chrF could not give):
   plain 99.8 %, R6 99.3 % (+0.22 additions/line), MCTR 98.6 % (+0.16; conserve +0.07), algorithmic 92.6 % (0.38
   errors/line). Spec, module, tests and the integration plan: `wt-mctr/README.md` on its branch.

10. **Two-sided optimisation works with a real MT black box** (worktree `twosided`). For targets where only MT exists,
    the LLM writes options in the source language only; MT translates each, the target voice times them, the
    exact optimiser selects, and a lazy target-side check (back-translation on the PC) removes what MT garbled. The
    check is essential: without it timing improves but meaning stays at plain-MT level. Transfer steps for Amharic
    and Oromo (Google MT via the repo client, edge-tts/MMS voices, back-translation) are in its README.

11. **End to end between two MT-only languages works through an English meaning pivot** (worktree `pivot`). The
    LLM never reads either language: it understands the source by triangulating independent English MT views (whole
    line, each speech segment, terse and full renderings, word glosses) plus language-free prosody cues, and writes a
    meaning map whose units are pinned to the source speaker's segments by the per-segment views. Understanding is
    the meaning win (blind adequacy 1.17 → 2.75 of 3); two-sided timing is the fit win (52 → 88 % within ±20 %) at
    almost no meaning cost (2.71). Its own confidence flag is calibrated (high 3.0, low 1.5), so low-confidence lines
    go to a human. The pitch-rise question cue over-fires on read speech; use it as weak evidence. Amharic → Oromo
    steps are in its README.

12. **Choose the working language per pair** (worktree `routes`). When the target is LLM-strong, write it directly
    (no second MT hop): better fit and far more natural lines at the same meaning and tokens. Two writing languages
    pooled give the best fit (95 % within ±20 %) for ~35 % more tokens; give MT-route options a small prior so the
    fluency-blind selector prefers directly written lines on near-ties. Save tokens in understanding (adaptive views),
    which is about two-thirds of the cost.

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
