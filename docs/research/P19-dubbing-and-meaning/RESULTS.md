# All headline results (P19)

**Metrics:**

| Metric | Meaning |
|---|---|
| Within ±20 % | Share of speech segments whose dubbed voice lasts 0.8–1.2× the speaker's segment |
| In band | 0.8–1.05× |
| > 1.1× | Would need a speed-up |
| Overlap | Speech-interval overlap with the speaker (human dubs ≈ 0.7–0.8) |
| Adequacy | Blind 0–3 against the hidden reference: 3 full, 2 minor loss, 1 major loss, 0 wrong |

## A. Timed rephrasal into English (45 German-speaker lines, VITS voice)

| Mechanism | Overlap | Within ±20 % | > 1.1× | chrF |
|---|---|---|---|---|
| Plain translation | 0.72 | 13 % | 69 % | 70.7 |
| Human reference + placement | 0.80 | 51 % | 26 % | 100 |
| Plain translation + placement | 0.82 | 62 % | 21 % | 70.7 |
| Trained duration NMT (IWSLT Sockeye) | 0.80 | 49 % | 12 % | 47.8 (53.5 normalised) |
| Algorithmic edits, safe / aggressive | 0.85 / 0.90 | 66 / 89 % | 18 / 19 % | 69.8 / 68.2 (27 % ungrammatical) |
| LLM one pass | 0.91 | 88 % | 35 % | 65.0 |
| LLM + one voice revision | 0.92 | 89 % | 5 % | 63.5 |
| **LLM multi-round (R6)** | **0.92** | **97 %** | **1 %** | 64.1 |
| **MCTR, 2 rounds** | 0.90–0.91 | **98 %** | 2 % | — (98.6 % of meaning units kept; additions 0.16 per line, conserve 0.07) |

**Supporting results:**

- **Duration from text:** 15–18 % error for every model.
- **Placement:** 94–97 % of breaks within one word.
- **Blind fluency:**

  | Mechanism | Fluent segments |
  |---|---|
  | LLM loop | 100 % |
  | Placement only | 99 % |
  | Algorithmic, safe | 94 % |
  | Algorithmic, aggressive | 73 % |
  | Trained NMT | 28 % |

## B. Two-sided: target reachable only by MT

| Arm | Condition | Within ±20 % | > 1.1× | Meaning kept | MT errors per line |
|---|---|---|---|---|---|
| de→en (real MT) | whole-line MT + placement | 57 % | 9 % | 73 % | 1.13 |
| | two-sided, no check | 96 % | 0 % | 80 % | 0.93 |
| | **two-sided + check** | 87 % | 6 % | **93 %** | **0.40** |
| en→es (stand-in MT) | whole-line MT + placement | 59 % | 55 % | 100 % | — |
| | **two-sided, round 2** | **93 %** | **0 %** | 97.8 % | — |

## C. Pivot: both ends MT-only (24 unseen lines, de speech → es)

| Pipeline | Adequacy | Major loss | Within ±20 % | Overlap |
|---|---|---|---|---|
| Naive cascade | 1.17 | 71 % | 52 % | 0.81 |
| Understood via MT views, untimed | 2.75 | 4 % | 54 % | 0.80 |
| **Full pipeline** | 2.71 | 4 % | **88 %** | **0.88** |

Adequacy by the understanding's own confidence: high 3.0, medium 2.6, low 1.5.

## D. Routes (24 fresh lines, de speech → es)

| Route | Within ±20 % | Adequacy | Natural lines | Tokens per line |
|---|---|---|---|---|
| Naive cascade | 61 % | 1.38 | 0 % | — |
| Economy (English options → MT) | 86 % | 2.54 | 50 % | ~370 |
| **Target-direct** (Spanish written directly) | 91 % | **2.58** | **88 %** | ~380 |
| Pooled two languages + route prior | **95 %** | 2.58 | 79 % | ~500 |

## E. Two middle languages (24 fresh lines, de speech → fr, all real MT)

**Understanding:**

| Read through | Adequacy | Full meaning | Major loss |
|---|---|---|---|
| MT A alone (Sockeye) | 1.50 | 8 % | 54 % |
| MT B alone (Mozilla) | 2.46 | 54 % | 8 % |
| English only (U1) | 2.54 | 75 % | 17 % |
| **English + Spanish (U2)** | **2.88** | **92 %** | **4 %** |
| + B's English (U3) | 2.96 | 96 % | 0 % |

**French dub:**

| Pipeline | Adequacy | Major loss | Within ±20 % | Overlap |
|---|---|---|---|---|
| Cascade, Sockeye → fr | 1.12 | 75 % | 36 % | 0.74 |
| Cascade, Mozilla de→en→fr | 2.42 | 12.5 % | 38 % | 0.77 |
| **English options** | **2.83** | **0 %** | 79 % | 0.87 |
| Spanish options (es→en→fr, two hops) | 2.67 | 8 % | 58 % | 0.82 |
| English + Spanish pooled | 2.79 | 4 % | **81 %** | 0.87 |

Back-translation checks: 185 options checked, 28 with MT errors, all avoided by the selector in the English and
pooled runs.
