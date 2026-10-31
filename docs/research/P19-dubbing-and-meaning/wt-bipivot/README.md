# Worktree `bipivot`: English and Spanish as two middle languages

**Your request (2026-10-31):** don't trust English alone as the middleman. Read the source through two languages the
LLM understands best (English and Spanish), so the meaning is consolidated before it is conserved, with Spanish as a
middle language and not the target. Test it.

## 1. Setup (all real MT, no stand-ins)

- **Source, standing in for a weak language:** German speech. 24 fresh lines (subset2-81…100, subset1-18…21) with
  real ASR (Parakeet). I never saw the German.
- **Middle language 1, English:** the IWSLT Sockeye de→en model (system A). Views: whole line, each speech segment,
  terse/full, glosses.
- **Middle language 2, Spanish:** Mozilla Firefox Translations (system B, `mt_bergamot.py`, offline), de→en→es.
  Views: whole line and each speech segment.
  - Mozilla's models are English-centric, so its Spanish comes through its own English. It is a second, different
    MT system, but not a path that avoids English.
  - On your PC, NLLB-200 am→spa is a truly direct path.
- **Target:** French (MMS French voice on the German speakers' segments).
  - MT: Mozilla en→fr, and es→en→fr for Spanish-written options (no direct es→fr model exists).
  - **Meaning check:** back-translation fr→en, judged only from the back-translation, as for Oromo.

## 2. Understanding: does a second middle language consolidate the meaning?

Each map was written before seeing the next set of views. Each best line was then scored blind against the hidden
CoVoST references (`understanding_meaning.json`).

| Understanding | Reads | Adequacy (0–3) | Full meaning | Major loss or wrong |
|---|---|---|---|---|
| MT A alone (Sockeye whole line) | — | 1.50 | 8 % | 54 % |
| MT B alone (Mozilla whole line, English) | — | 2.46 | 54 % | 8 % |
| **U1, English only** (A views) | en | 2.54 | 75 % | 17 % |
| **U2, English + Spanish** (A views + B Spanish views) | en + es | **2.88** | **92 %** | **4 %** |
| U3, + B's English views | en + es + en | 2.96 | 96 % | 0 % |

**What Spanish fixed** (U1 → U2), each confirmed by the reference:

- **95:** "committed itself *against* apartheid" (polarity wrong) → "the commitment against apartheid **was
  dropped**"; Spanish "fue abolido" supplied the missing verb.
- **86:** "*close* the shutters" → "**open** the shutters and turn off the lights".
- **99:** "others in church circles accused him" → "accused him **of blasphemy**"; English had "god's environment",
  Spanish had "blasfemia".
- **subset1-20:** "what you're heading for" → "**what's happening**".

Adding B's English afterwards (U3) fixed one more line, the proverb on line 83, whose fat/lean contrast was clearer
in English.

The understanding's confidence also improved and stayed calibrated:

| Map | Lines high / medium / low | Adequacy at high confidence |
|---|---|---|
| U1 | 7 / 12 / 5 | 3.0 |
| U2 | 14 / 9 / 1 | 3.0 (all 14 lines) |

Two systems that agree are a real signal.

## 3. The dub into French: does writing in two languages help?

The U3 map was written as English options and as Spanish options, translated by real MT, timed with the French
voice, and checked by back-translation (185 options checked; 28 had MT errors that the selector then avoided). Two
rounds each.

| Pipeline | Adequacy (0–3) | Full meaning | Major loss | Within ±20 % | In band | > 1.1× | Overlap |
|---|---|---|---|---|---|---|---|
| P0-A cascade (Sockeye → en→fr) | 1.12 | 8 % | 75 % | 36 % | 25 % | 7.5 % | 0.74 |
| P0-B cascade (Mozilla de→en→fr, "Firefox") | 2.42 | 54 % | 12.5 % | 38 % | 26 % | 9.4 % | 0.77 |
| **English options** (round 2) | **2.83** | **83 %** | **0 %** | 79 % | 77 % | 1.9 % | 0.87 |
| Spanish options (es→en→fr) | 2.67 | 75 % | 8 % | 58 % | 53 % | 3.8 % | 0.82 |
| **English + Spanish pooled** | 2.79 | **83 %** | 4 % | **81 %** | **79 %** | 1.9 % | **0.87** |

Pooled and English differ on one line only. The French outputs are labelled by condition only, but I had already
seen the references in §2.

## 4. Findings

1. **Two middle languages consolidate the meaning, at the understanding step.** Adding the Spanish views took
   adequacy from 2.54 to 2.88, and lines with major loss from 17 % to 4 %. The fixes were polarity, missing verbs and
   wrong actions: the errors a single English pivot passes on silently.
2. **What helps is a second, independent MT path, not Spanish as such.** The Spanish views came from a different
   (and stronger) MT system. Reading them in Spanish worked as well as reading that system's English (U2 already got
   most of U3's gain). So pick the second middle language for whichever direct MT from the source is best (NLLB
   am→spa or am→fra), and read it in the LLM's strong languages.
3. **At the writing step, a second language only helps if its MT into the target is direct.** Here es→fr went
   through English (two hops).
   - Spanish options alone were worse: 2.67 adequacy, and 4 chosen segments still carried errors.
   - Pooling matched English on meaning (2.79 vs 2.83) and gave slightly better timing (81 vs 79 %).
   - Use the second writing language when its MT to the target is direct (NLLB spa→gaz on your PC); otherwise keep
     it for understanding and verification.
4. **The understanding step beats the stronger MT.** The best cascade (Mozilla, 2.42) is much better than the
   Sockeye one (1.12). The full pipeline on top of it reaches 2.83 with 0 % major loss, and 79–81 % fit vs 38 %.
5. **Back-translation checking works with real MT.** It caught:
   - "honte" (shame) for sorrow;
   - "the boy brought the girl closer";
   - "not a few" (= many) for "not just a few";
   - "playing Getafe" (against Getafe);
   - lost negations;
   - wrong subject pronouns.

   The selector routed around all of them in the English and pooled runs.
6. **Cost:**
   - The second middle language adds about 50 % to the understanding tokens: about 5.3 k for English-only
     understanding of 24 lines, plus about 2.8 k for the Spanish views.
   - Writing in a second language adds about 4 k more.
   - At about 2.5 cents per 1 k tokens, that is pennies per minute of film, for the largest meaning gain in this
     test.

**Recommendation for Amharic → Oromo:**

| Stage | Working languages | MT paths |
|---|---|---|
| Understand | English + Spanish (or French) | **two independent systems**: Google am→en and NLLB am→spa (direct) |
| Write | English (economy); + Spanish only if NLLB spa→gaz is used directly | Google or NLLB en→om |
| Verify | back-translate om→en with one system and om→spa with the other | flag disagreements |
| Human | low-confidence lines (rare once two systems agree) | |

**Caveats:**

- 24 read sentences.
- Mozilla's Spanish is English-mediated, so this tests "second system read in Spanish" rather than a fully
  independent route.
- I wrote the maps and options and judged them; the understanding scores are blind, the dub scores only label-blind.
- The French voice under-filled at first (slow German speakers): two steering rounds were needed.

Files:

- `ids.txt`, `asr.json`, `prosody.json`;
- `mt_views_A_en.jsonl`, `mt_views_B_en.jsonl`, `mt_views_B_es.jsonl`;
- `sheet_U1.txt`, `sheet_U2.txt`, `sheet_U3_extra.txt` (exactly what the LLM read);
- `maps_U1/U2/U3.json`, `understanding_meaning.json`;
- `opts_{en,es,pool}_r{1,2}.json`, `mt_fr.jsonl`, `backtrans_fr_en.jsonl`, `verified.json`, `steer_*`;
- `chosen_*.json`, `cascade_B_fr.jsonl`, `timing.json`, `dub_meaning.json`, `tokens.json`.
- Code: `mt_bergamot.py`. It loads only the compiled engine, because the package's import fetches online model
  catalogues; models come from Mozilla's public registry, base-memory.
