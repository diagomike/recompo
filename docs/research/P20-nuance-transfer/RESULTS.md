# P20 results: every number, how it was measured

Benchmark: 8 random *Friends* scenes (S1–S3, EmoryNLP transcripts, seed 20), 214 lines.
- **83 gold nuance items** on 81 lines: jokes, puns, idioms, slang, figures of speech, cultural references,
  catchphrases, collocations.
  - 70 humorous; 62 laugh points.
  - Bound to: English wording (L) 21, culture (C) 6, prosody (P) 3, universal (U) 53.
  - 29 depend on another line (setup, callback, chain).
- **Stress set:** 14 items picked for proverbs, idioms and running jokes (silver lining, other fish in the sea,
  like father like son, every cloud…, once in a blue moon, piece of cake, the ball is in his court, we were on a
  break, Pivot!, unagi, lobster).
- **External check:** 60 MUStARD *Friends* utterances with human sarcasm labels.

Scoring: blind. Candidates for each item are shuffled under letters, with each candidate's own rendering of the
item's dependency lines. The key is kept apart.
- **Meaning:** 0–3, the line's propositional content.
- **Effect:** 0–3, does the item's *function* land for a target-language viewer (the rubric is the gold `function`).
- **Effect kept:** effect ≥ 2.
- **Natural:** 0/1, Spanish only.

Claude annotated, wrote and judged everything (see Caveats).

## 1. Does the existing understanding carry nuance? (audit, `data/audit_*.json`)

| | storylens P1 fact ledger | recompo `dub understand` map |
|---|---|---|
| Item flagged at all (joke/quote fact; map note) | 47 % (humorous 53 %) | 18 % (humorous 20 %) |
| Trigger wording kept somewhere visible | 41 % | 90 % (in `best`) |
| Mechanism stated (why it is funny / what the figure means) | 24 % | 17 % |
| Dependency stated (setup/callback), of 29 | 28 % | 7 % |
| Trigger wording **paraphrased away or only in droppable colour units** (automatic) | — | 49 % |
| …confirmed by hand as flattening the nuance | — | **23 %** (19 items; 16 of them humorous) |

The units carrying a trigger were tier core 39, support 3, colour 4, and none (paraphrased) 37.

Examples of flattening in the units:
- "played the Gunther card too soon" → "you used Gunther too early";
- "Bummer." → "too bad";
- "lose her" → "I won't lose her?" (this destroys the "loser" pun);
- "like a dog in the street" → tier colour, so it is dropped first under time pressure, and that breaks the
  "Woof, woof" callback two lines later.

**Structural:**
- Neither schema has a field for trigger, mechanism, dependency or transfer strategy.
- recompo's `select` (conserve mode) and `verify` score substitution and compensation, the standard humour
  strategies, as added content and missing units.

## 2. Strong target: Spanish (`data/es_*`, `judged_es.json`, `scores_es.json`)

| Condition | Meaning | Effect | **Effect kept** | Natural | Est. length vs source (median) | In band 0.8–1.05 |
|---|---|---|---|---|---|---|
| NLLB-200 1.3B, line by line | 2.29 | 1.59 | 54 % | 75 % | 0.92 | 35 % |
| S0: Claude, each line alone (no scene, no analysis) | 2.92 | 2.47 | 87 % | 84 % | 0.99 | 48 % |
| S1: recompo writer from the map (full/compact chosen by fit) | 2.76 | 2.01 | 67 % | 98 % | 0.74 | 16 % |
| **S2: writer + nuance card** (scene, mechanism, deps, strategy) | **2.99** | **2.92** | **100 %** | 100 % | 0.96 | 48 % |

Effect kept, by item group:

| Group | NLLB | S0 | S1 | S2 |
|---|---|---|---|---|
| L (bound to English wording) | 48 % | 71 % | 57 % | 100 % |
| C (culture) | 67 % | 83 % | 67 % | 100 % |
| U (universal) | 58 % | 96 % | 74 % | 100 % |
| P (prosody) | 0 % | 33 % | 33 % | 100 % |
| with dependencies | 38 % | 79 % | 62 % | 100 % |

Stress set (14): NLLB 64 %, S0 93 %, S2 100 % effect kept.

**Reading it:**
- A strong LLM translating line by line already keeps most universal jokes (96 %).
- Losses concentrate where the card helps: language-bound puns, prosody, and chains.
- The current map-driven writer is **worse than no analysis** (67 % vs 87 %), because it writes from compressed
  units.
- Raw MT calques idioms: "once in a blue moon" → "una vez en una luna azul", "silver lining" → "revestimiento de
  luz", "butt cheeks" → "mejillas", and "turtles scare me" was negated.

## 3. MT-only targets: Amharic, Swahili, Oromo (NLLB-200 1.3B forward)

The English handed to MT:
- **M0:** the source line as is.
- **M1:** recompo's current rule, "plain, MT-friendly wording (no idioms, explicit subjects)".
- **M2:** the proposed function-preserving pre-edit.

Judged blind from back-translations. Amharic and Swahili use MADLAD-400 3B, an independent model family. Oromo:
see the note under the table.

| Effect kept | Amharic | Swahili | Oromo (NLLB view) |
|---|---|---|---|
| M0 raw | 25 % | 45 % | 13 % |
| M1 plain (current) | 23 % | 39 % | 16 % |
| **M2 function-preserving** | **57 %** | **77 %** | **35 %** |
| Meaning M0 / M1 / M2 | 1.52 / 1.81 / 2.10 | 2.12 / 2.17 / 2.57 | 1.37 / 1.61 / 1.80 |
| Laugh points kept M0 / M1 / M2 | 27 / 19 / 56 % | 42 / 32 / 76 % | 13 / 8 / 32 % |
| With dependencies M0 / M1 / M2 | 24 / 21 / 66 % | 28 / 14 / 69 % | 10 / 7 / 31 % |
| Language-bound (L) M0 / M1 / M2 | 14 / 24 / 62 % | 29 / 33 / 81 % | 14 / 24 / 48 % |

Stress set:

| Effect kept M0 / M1 / M2 | |
|---|---|
| Amharic | 57 / 43 / 79 % |
| Swahili | 50 / 50 / 86 % |
| Oromo | 21 / 21 / 57 % |

**Reading it:**
- Plain rewriting raises meaning (+0.29 Amharic) but **lowers** the share of jokes that land, most at laugh points
  (Swahili 42 → 32 %).
- Function-preserving pre-editing raises both, and roughly doubles the jokes that survive.
- It does not need the target language. It uses compositional images, lexical sarcasm, consistent callback words
  and explicit innuendo.

**Oromo note (a finding in itself):**
- With MADLAD as back-translator, every Oromo condition scored about 2 % (`scores_mt_om_madlad.json`). The cause
  was MADLAD's Oromo→English, not NLLB's Oromo.
- Proof: "Mooniikaa, akka saree daandii irra jiruutti si ajjeessi" is a correct "she'll kill you like a dog on the
  road" (`om_diagnosis.json`).
- The Oromo row above uses NLLB's own Oromo→English. That is the same system as the forward pass, so it is
  optimistic in absolute terms; the comparison between conditions still holds.

**Length:**
- M2 English averages 1.12× the source syllables (median 0.94×).
- Median estimated target length vs source:

  | | M0 | M1 | M2 |
  |---|---|---|---|
  | Amharic | 1.19 | 1.01 | 1.20 |
  | Swahili | 1.14 | 1.09 | 1.19 |
  | Oromo | 1.10 | 1.05 | 1.23 |

- So the pre-edit costs little length over raw MT. All conditions still need P19's fit loop: only 14–26 % land in
  band unfitted.

## 4. External check: sarcasm (MUStARD, *Friends*, 60 items, labels hidden)

An explicit nuance pass (Claude, text only, context + utterance) scored:

| Accuracy | Precision | Recall | F1 |
|---|---|---|---|
| 0.80 | 0.73 | 0.73 | 0.73 |

The confusion matrix was 16 / 6 / 6 / 32. Compared with the audit, an explicit question finds sarcasm far more
often than the map's free-text notes (20 %). A quarter of sarcastic lines are still missed from text alone; MUStARD
reports that audio cues reduce the error.

## 5. Judge consistency

- Spanish re-judged on 20 items under new letters: 100 % exact agreement on effect.
- This is **consistency, not validity**: the first-pass judgements were in context.

## Caveats

1. **One model wrote, annotated and judged.**
   - Blinding hides the condition, not Claude's own style.
   - S2's 100 % in Spanish is a ceiling inflated by self-preference: the card and the rubric come from the same
     annotation.
   - The MT-arm comparisons are more robust: Claude wrote only the English inputs, and judged machine outputs
     through a back-translator.
2. **The nuance card in S2/M2 is oracle quality.** It was written from the gold annotation. A real nuance pass will
   miss some items. MUStARD gives one estimate: 73 % recall for sarcasm.
3. **Back-translation is a lossy view.**
   - Puns and prosody cannot be seen through it, so P items are under-measured everywhere.
   - Oromo depends on the back-translator (above).
4. **Timing** is estimated from syllables (±15–18 % per P19), not voiced. No TTS was run in P20.
5. **Size.** 83 + 14 items, one sitcom, one variety of Spanish. Human A/B with native speakers per language is the
   next step.
