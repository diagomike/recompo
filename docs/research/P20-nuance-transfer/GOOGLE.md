# P20-G: Google Translate (keyless) vs offline NLLB on the same nuance benchmark

**Research, 2026-11-02.** Question: is there a difference between the online engine recompo already has
(`recomp/lang/google.py`, keyless, the `google` MT engine when `online` is on) and the offline NLLB-200 1.3B? And does
the nuance layer (D-28) still matter once the engine is better?

## Method

- The same 83 gold items on 81 lines, and the same 14-item stress set, as `RESULTS.md`.
- The same English inputs:
  - **M0** raw source;
  - **M1** recompo's old "plain, MT-friendly" rule;
  - **M2** the function-preserving pre-edit (what the nuance layer writes for MT routes).
- Google was called through recompo's own module: batched tagged requests, endpoints `clients5.google.com` and
  `translate.googleapis.com`.
- Back-translation for the judging: MADLAD-400 3B for Amharic and Swahili, NLLB for Oromo. For Google's Oromo this
  is an **independent** view. NLLB's Oromo row in `RESULTS.md` was judged through NLLB's own back-translation, which
  is optimistic.
- Judging used the same blind protocol: letters shuffled, keys kept apart, meaning 0–3, effect 0–3, "kept" means
  effect ≥ 2.
- Spanish raw MT was judged in one sheet with three candidates: NLLB, Google and S0 (Claude, each line alone).
- Data: `data/google_outputs.json`, `google_stress_outputs.json`, `sheet_g_*`, `judged_g_*`, `scores_g_*`,
  `google_auto.json`. Scripts: `scripts/research/p20/run_google2.py`, `judge_sheet_g.py`,
  `judge_sheet_g_stress.py`, `score_g_stress.py`, `analyze_google.py`.

## Results

### Effect kept (jokes, idioms and figures that land), 83 items

| | NLLB M0 / M1 / M2 | **Google M0 / M1 / M2** |
|---|---|---|
| Amharic | 25 / 23 / 57 % | **48 / 49 / 70 %** |
| Oromo | 13 / 16 / 35 % (self-back-translated, optimistic) | **31 / 31 / 57 %** (independent back-translation) |
| Swahili | 45 / 39 / 77 % | 52 / 48 / 72 % |
| Spanish raw (same sheet as S0) | 67 % | **80 %** (S0: 93 %) |

### Meaning (0–3), M0 / M1 / M2

| | NLLB | Google |
|---|---|---|
| Amharic | 1.52 / 1.81 / 2.10 | 1.84 / 1.99 / 2.23 |
| Oromo | 1.37 / 1.61 / 1.80 | 1.69 / 1.63 / 2.00 |
| Swahili | 2.12 / 2.17 / 2.57 | 2.04 / 2.08 / 2.22 |
| Spanish raw | 2.39 | 2.61 |

### Breakdown for Google M2, effect kept

| | Laugh points | Language-bound (L) | With dependencies |
|---|---|---|---|
| Amharic | 66 % | 76 % | 72 % |
| Oromo | 56 % | 71 % | 52 % |
| Swahili | 69 % | 67 % | 55 % |

### Stress set (14 items: proverbs, idioms, running jokes), effect kept

| | NLLB M0 / M1 / M2 | Google M0 / M1 / M2 |
|---|---|---|
| Spanish raw | 64 % | 86 % |
| Amharic | 57 / 43 / 79 % | 43 / 64 / 86 % |
| Oromo | 21 / 21 / 57 % | 36 / 57 / 64 % |
| Swahili | 50 / 50 / 86 % | 36 / 71 / 86 % |

The stress set has only 14 items: one item is 7 points, so read it as a direction, not a measurement.

### Timing (estimated from syllables, `google_auto.json`)

- Google's output is about as long as NLLB's. The median voice/source ratio is within ±0.1 in every cell, for
  example Amharic M2 1.22 vs 1.20 and Spanish 0.99 vs 0.92.
- In band (0.8–1.05) unfitted: 15–40 %, the same range as NLLB. The fit loop is needed either way.
- Degenerate loops ("እሺ እሺ እሺ…"): Google 0–3 per 81 lines, NLLB 0–4. Both are rare and the fit and verify steps catch them.

## What the differences are

1. **Google is clearly better for Amharic and Oromo**:
   - +23 points raw Amharic, +18 raw Oromo;
   - +13 and +22 points with the M2 pre-edit;
   - meaning +0.1 to +0.3.

   NLLB-1.3B's typical failures for these two were missing the second half of a line, a looping output, and a callback
   word lost. Google loses those less often.
2. **For Swahili, Google and NLLB are about even**:
   - raw +7, plain +9, M2 −5;
   - this is within the judging drift (caveat 1), so treat it as a tie;
   - NLLB-1.3B is already decent in Swahili.
3. **Spanish raw: Google is better than NLLB, worse than the LLM writing the line** (80 vs 67 vs 93 %, same sheet).
   - Google knows more target idioms: "No un basset, un moisés" (a real substitution for the pun), "Guau, guau"
     kept where NLLB wrote "Eso es todo", and "Para mí sí es para tanto…" kept.
   - It still calques and mis-hears slang:
     - "Bummer" → *Gorrón* ("freeloader");
     - "butt cheeks" → *mejillas* (both engines);
     - "once in a blue moon" → *una vez cada luna azul*;
     - "turtles scare me" negated (both engines).
   - Spanish is a strong language, so the dubber writes it directly. Google does not change that.
4. **The nuance layer matters as much with Google as with NLLB.**
   - M2 vs raw with Google: Amharic 48 → 70 %, Oromo 31 → 57 %, Swahili 52 → 72 %.
   - The pre-edit is worth about +20 points on either engine. The engine is worth +0 to +23.
   - The two add up: **Google + nuance pre-edit is the best MT route measured for Amharic and Oromo.**
5. **Plain rewriting (M1) still does not help jokes**, with Google as with NLLB: 49 vs 48 % Amharic, 31 vs 31 %
   Oromo, 48 vs 52 % Swahili. The current "no idioms" rule was right to be replaced by the function-preserving one.
6. **Google's own failure modes**, which the nuance layer and verify exist for:
   - it transliterates slang instead of translating it: "Bummer." → ቡመር, back-translated "Boomer";
   - it reads idioms literally: "kick your ass" → "hit the donkey" in Amharic, "lobster" → "rope" in Swahili;
   - it inverts tone: "What a bitch" → "What a genius" with the raw input in Amharic.

   It also reproduces explicit and crude content more faithfully than NLLB, which often drops it: "What a bitch" kept
   in Amharic under M1, where NLLB wrote only "Thank you."

## Caveats

1. **Judging drift.**
   - The Google sheets were judged in a later session than the NLLB ones.
   - The Spanish sheet re-judged NLLB and S0 next to Google: NLLB 54 → 67 %, S0 87 → 93 %. So the later judging ran
     about 6–13 points more generous.
   - The within-sheet Spanish comparison (Google 80 vs NLLB 67) is unaffected.
   - In the MT arms, Google's lead in Amharic and Oromo (+13 to +23) is larger than the drift. Swahili's is not.
2. **One judge** (Claude), as in `RESULTS.md`. The blinding hides the engine, not the judge's taste.
3. **Back-translation is a lossy view.** Puns and prosody are under-measured for every engine.
4. **The keyless endpoints are unofficial.**
   - After a few hundred per-line requests, Google answered this cloud IP with a 302 to `google.com/sorry`.
   - The batched mode recompo already uses (`Translator.translate`, tagged batches) needed only a few dozen requests
     for everything here.
   - On a residential IP it should be fine, but it can break at any time. NLLB stays the offline fallback.

## What this means for recompo

The dubber already has everything needed. Nothing in the dubber had to change for this result:
- `google` is an MT engine;
- `engine_for` falls back to NLLB when offline;
- D-28's nuance layer writes the M2-style English.

Recommendations:

1. **Online dubs into Amharic/Oromo (and other low-resource targets): `recomp dub settings --online --mt google`.**
   - Keep `nuance on`. The gains add up.
   - For Swahili, NLLB offline is as good. Keep it, and avoid the network dependency.
2. **Verify with a different engine than the one that translated.**
   - Today the back-translation engine follows the view engines (`prefer = views' mt`). With `mt nllb` and the
     default views, NLLB checks NLLB's own output.
   - P20 showed that self-back-translation is optimistic (Oromo) and that a weak independent one is pessimistic
     (MADLAD's Oromo).
   - Proposal (BACKLOG): when the forward engine is `nllb` and `online` is on, back-translate with `google`, and the
     reverse. Offline, keep today's behaviour.
3. **Strong targets (Spanish, etc.) stay LLM-written** (direct route). Google's Spanish (80 %) is below the line-alone
   LLM (93 %) and far below the nuance-card writer. Use it only as a draft or as a second view.
