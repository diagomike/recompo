# Worktree `routes`: choose the working language(s), not "the two sides"

**Your idea (2026-10-31):** don't fix the work to "source side + target side". Run the LLM in whatever language(s) it
understands best. That can be the source, the target, a pivot like English, or two languages (English and
Spanish) pooled for the best output. Use one language when tokens matter.

## 1. The rule

The LLM **reads** (understands) and **writes** (proposes timed lines) only in languages it is strong in. MT bridges
everything else, and the target voice is always the ruler.

| Source | Target | Route | LLM reads in | LLM writes in | MT hops |
|---|---|---|---|---|---|
| strong | strong | **direct** | source | target | 0 |
| weak (am) | strong (es) | **target-direct** | pivot (MT views) | **target** | 1 (understanding only) |
| strong (de) | weak (om) | **source-side** | source | source (+ pivot in quality mode) | 1 + back-translation check |
| weak (am) | weak (om) | **pivot** | pivot(s) (MT views) | pivot(s) | 2 + back-translation check |

**Budget knob:**

- **economy:** one writing language. Fewest tokens.
- **quality:** two writing languages, options pooled; the exact selector picks per segment from either. In
  pivot mode the second pivot also adds a second independent set of understanding views (am→en and am→es are
  different MT paths).

`routes.py plan --src am --tgt om --budget quality --pivots en,es` prints the route and its steps. The strength
table is editable per model.

## 2. The test (24 fresh lines, references hidden until scoring)

- **Lines:** German speech (subset2-57…80), new to me, standing in for the weak source. Real ASR, real offline MT
  into English views, understanding from English only (`pivot_maps.json`).
- **Target:** Spanish, MMS voice on the German speakers' segments.

Three writing routes from the same understanding, 2 rounds each:

- **E, economy pivot:** English options → literal timing-blind MT → Spanish. The same machinery as am→en→om.
- **D, target-direct:** Spanish written directly.
- **X, pooled:** E + D options in one selection. **X + prior** adds a small cost (0.5) on MT-route options, so a
  directly written line wins near-ties.

**Timing** (56 speech segments; `timing.json`):

| Route | Within ±20 % | In band 0.8–1.05 | > 1.1× speed-up | < 0.65× | Speech overlap |
|---|---|---|---|---|---|
| P0 naive cascade | 61 % | 50 % | 12.5 % | 12.5 % | 0.81 |
| E economy (pivot English), round 1 → **round 2** | 75 → **86 %** | 66 → 80 % | 3.6 % | 0 % | 0.88 |
| D target-direct, round 1 → **round 2** | 63 → **91 %** | 57 → 89 % | **0 %** | 1.8 % | 0.88 |
| X pooled, round 1 → **round 2** | 80 → **95 %** | 75 → 95 % | **0 %** | **0 %** | **0.90** |
| **X + prior** | **95 %** | **95 %** | **0 %** | **0 %** | 0.89 |

**Meaning and fluency.** Blind and shuffled against the hidden CoVoST English references; adequacy 0–3, fluency
0–2 (`meaning.json`):

| Route | Adequacy | Full meaning | Major loss | Fluency | Natural lines |
|---|---|---|---|---|---|
| P0 naive cascade | 1.38 | 8 % | 62 % | 0.21 | 0 % |
| E economy | 2.54 | 62 % | 8 % | 1.46 | 50 % |
| D target-direct | **2.58** | **67 %** | 8 % | **1.88** | **88 %** |
| X pooled | **2.58** | **67 %** | 8 % | 1.62 | 62 % |
| X + prior ¹ | **2.58** | **67 %** | 8 % | 1.79 | 79 % |

¹ 6 of its 24 lines are new mixes and were judged after the references were seen.

The understanding's own confidence predicts adequacy in every route: high 3.0, medium 2.6, low 1.8.

**Tokens** (approx. characters/4, 24 lines; `tokens.json`):

| Step | Tokens | Other calls |
|---|---|---|
| Understanding (read the views, write the meaning map), shared by all routes | 5.9 k | 257 MT view calls |
| Writing, E economy | 2.8 k | 137 MT calls; on a weak target, also back-translation and its check |
| Writing, D target-direct | 3.2 k | 0 MT calls |
| Writing, X pooled | 6.0 k | 137 MT calls |
| **Total per line** | E ≈ 370 · D ≈ 380 · X ≈ 500 | |

## 3. Findings

1. **Write in the target whenever the LLM is strong in it** (target-direct). Compared with the pivot route:
   - better fit: 91 vs 86 % within ±20 %, no speed-ups;
   - same meaning: 2.58 vs 2.54;
   - far more natural Spanish: 88 vs 50 % natural lines;
   - zero second-hop MT calls, at about the same tokens.

   An extra MT hop costs fluency even when the meaning survives.
2. **Two working languages pooled give the best timing:** 95 % within ±20 % and 0 % outside 0.65–1.1×. Two
   languages give the selector more candidate lengths per segment. Writing tokens go up about 2× (whole
   pipeline +35 %).
3. **Pooling needs a route prior.** Without one, the selector (blind to fluency) took MT-route options for 43 of 56
   segments, because they happened to fit, and fluency fell (1.62). A prior of 0.25–1.0 keeps the same 95 % fit and
   picks the directly written line for 46 of 56 segments (fluency 1.79). In pure pivot mode (both pivots via MT)
   the options are on an equal footing and no prior is needed.
4. **Understanding is about two-thirds of the tokens** in economy mode, so it is where to save:
   - **adaptive views:** the whole-line and per-segment views first; terse/full/gloss views only where those two
     disagree;
   - skip glosses on high-confidence lines.
5. **Confidence stays calibrated** across routes (high 3.0, low 1.8). Low-confidence lines are an understanding
   limit, and no writing route fixes them, so they go to a human.

**Recommendation per pair:**

| Pair | Mode | Writes in |
|---|---|---|
| am → es | target-direct, economy | Spanish |
| de → om | source-side | German, economy; + English in quality mode |
| am → om | pivot | English (economy) or English + Spanish pooled (quality) |
| any | when tokens matter | one writing language, adaptive views |

**Caveats:**

- 24 read sentences.
- The en→es MT was me acting as a deliberately literal stand-in, which understates real Google fluency, so E's
  fluency gap is an upper bound.
- I wrote the options and judged them, blind to the route but not to my own style.
- No real Oromo run: on your PC, use Google/NLLB en→om and es→om with the MMS Oromo voice, then back-translate.

Files:

- `ids.txt`, `asr.json`, `prosody.json`, `mt_views.jsonl`, `sheet.txt` (everything the LLM read),
  `pivot_maps.json`;
- `opts_en_r1/r2.json`, `mt_en_es.jsonl`, `opts_es_r1/r2.json`, `steer_*_r1.txt`;
- `chosen_*.json`, `timing.json`, `meaning.json`, `tokens.json`, `voice_cache_es.json`.
- Code: `routes.py` (plan / select E·D·X / cascade / report / tokens), `test_routes.py`; `mctr.select` now accepts a
  per-option `penalty` (the route prior).
