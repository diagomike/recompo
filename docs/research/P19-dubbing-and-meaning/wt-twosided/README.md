# Worktree `twosided`: two-sided dub optimiser for MT-only target languages

**Your request (2026-10-31):** make timed rephrasing work for languages where LLMs are weak and only machine
translation exists (Amharic, Oromo). Rephrase on the **source** side with options, translate each with MT, time the
**target** with its own voice, and choose; let the source rephrasing anticipate what the target needs. Prove it on
German and Spanish, and you transfer it.

## 1. Design: who does what

| Side | Engine | Job |
|---|---|---|
| Source (en/de: LLM-strong) | **LLM** | Meaning map; source options per segment (orig / compact / plain = MT-friendly / full); steering rewrites to syllable targets; **MT-robust** rewrites that avoid what this MT garbles |
| Crossing | **MT** (black box) | Translate every option chunk independently (one chunk = one speech segment). No timing given to it |
| Target (am/om: LLM-weak) | **Voice** | Speak every translation; its measured duration is the only ruler |
| Back to source | **MT back-translation + LLM** | Check meaning in the source language: which units survived, any wrong word or polarity. Here the target is English or Spanish, which can be read directly, so this is equivalent to a perfect back-translation |
| Selection | **Exact optimiser** (`mctr.select`) | One option per segment: max verified meaning, band 0.8–1.05, core units kept, errors cost 3 each, optional conserve mode |

**Loop**

```
options → MT → voice → select → verify only what was chosen → reselect … until the choice is all verified
       ↘ steering: e = target seconds per source syllable (measured on this line's own options)
                   → write source of ≈ 0.95·dur / e syllables, avoiding the MT's observed traps
```

**"Target-optimising" source options** (what the rounds taught; the transferable part for Amharic and Oromo):

1. **Length steering through MT.** The expansion e is measured per line from its own options (0.15–0.28 s per source
   syllable here), not assumed. One steering round moved 26 segments into band.
2. **MT-robust wording.** Common words over rare ones ("Amsel" → "amsl", "Chamäleon" → "chamberlion"); no
   separable verbs or idioms ("steckte … ein" → "plunged", "hören … auf" → "listen", "fehl am Platz" → "missing
   in the square"); no brackets ("(ich empfinde überhaupt nichts)" garbled); explicit subject and standard word
   order; one clause per segment.
3. **Compaction where the target is longer** (Spanish ≈ 15 % longer than English): compact source options won 15 of
   29 segments, and only colour and support units were dropped.
4. **Lazy verification.** Checking only the options the optimiser wants: 167 checks for 45 lines × ~5 options.
   Without verification the optimiser happily picks fitting garbage.

## 2. Arm A: German → English, real black-box MT

**MT:** the IWSLT 2023 Sockeye model, used as plain MT: each chunk gets its *natural* length bin, never the target
timing (`mt_sockeye.py`). **Frames:** the German speakers' speech segments (the shared bench, 45 lines).
**Voice:** VITS LJSpeech.

| Condition | Within ±20 % | > 1.1× speed-up | Meaning kept (weighted) | Core kept | MT errors / line | Lines clean and complete |
|---|---|---|---|---|---|---|
| MT of the whole line + placement (today's Google-style path) | 57 % | 9 % | 73 % | 75 % | 1.13 | 24 % |
| MT per segment (original chunks) | 58 % | 24 % | 80 % | 82 % | 0.96 | 24 % |
| Two-sided, timing only (no target check) | **96 %** | **0 %** | 80 % | 82 % | 0.93 | 22 % |
| **Two-sided + target check** | 87 % | 6 % | **93 %** | **94 %** | **0.40** | **60 %** |
| Two-sided + target check, conserve | 81 % | 5 % | 93 % | 94 % | **0.36** | **64 %** |

**Rounds** (fit, before verification):

| Round | In band |
|---|---|
| Original chunks | 40 % |
| + options | 64 % |
| + steering | 86 % |
| + steering 2 | 92 % |

Verification then trades some fit for meaning, and the MT-robust round (round 4) recovers part of it.

## 3. Arm B: English → Spanish (MT stand-in)

No Spanish MT is reachable offline here, so Claude acted as a **literal, timing-blind MT**: shuffled chunks only,
no durations, word-for-word style. **Frames:** the English speakers' segments (Common Voice alignments) for 20
lines / 29 segments. **Voice:** MMS Spanish (sherpa-onnx). Meaning is from the source-side unit labels (the stand-in
MT is faithful).

| Condition | Within ±20 % | > 1.1× speed-up | Speech overlap | Meaning kept |
|---|---|---|---|---|
| MT of the whole line + placement | 59 % | **55 %** | 0.84 | 100 % |
| MT per segment (original chunks) | 54 % | 57 % | 0.84 | 100 % |
| Two-sided, round 1 | 82 % | 7 % | 0.88 | 97.8 % |
| **Two-sided, round 2** | **93 %** | **0 %** | **0.91** | 97.8 % |

## 4. What is proven, and what is not

- **Proven with a real MT black box (arm A):**
  - Source-side options + target-voice timing + exact selection fix timing (57 → 96 % within ±20 %).
  - With target-side verification they also fix meaning (73 → 93 % kept; clean, complete lines 24 → 60 %), by
    routing around what the MT garbles.
  - The LLM never writes a word of the target language.
- **Proven for a longer target language (arm B):** compaction on the source side removes the speed-up problem
  (55 % → 0 % of segments needing > 1.1×) at a cost of 2 % of the meaning (colour and support only).
- **Not proven here:**
  - Real Google MT and real Amharic or Oromo voices; arm B's MT was a stand-in.
  - Meaning verification through back-translation (here the target was readable directly).
  - Claude wrote the options and judged the verifications (not blind to its own options).
  - The bench is read sentences, not film dialogue.

## 5. Transfer to Amharic and Oromo (on your PC)

1. **MT:** `scripts/research/p19/mt_google.py --src en --tgt am|om` (Recomposer's own Google client, one chunk per
   call). NLLB-200 (`amh_Ethi`, `gaz_Latn`) on the worker python is the offline alternative; it fits the same JSONL
   contract.
2. **Voice:**
   - Amharic: edge-tts `am-ET-MekdesNeural` / `am-ET-AmehaNeural`, already in `recomp/lang/tts.py`.
   - Oromo: MMS-TTS `facebook/mms-tts-orm` (worker env).
   - Wrap either like `wt_multiround.Voice` (duration of the synthesized clip, cached).
3. **Syllables for steering:** `timing.syllables` already counts Ethiopic (sixth-order fidel discounted). The
   expansion e is measured per line anyway.
4. **Verification:** back-translate each chosen option with `mt_google.py --src am --tgt en`, and let the LLM mark
   covered units and errors against the English meaning map (the `--verified` file). Same loop.
5. **Run:**
   ```
   twosided.py chunks → write options → mtjobs → mt_google → select --verified … --verify-out …
   → back-translate + check → repeat
   ```
   Expect the MT trap list to differ per language: collect it from the first verified round, then write the
   "robust" options against it.

Files:

- `opts_de_r1…r4.json`, `mt_de_en.jsonl`, `verified.json`, `verified_wholeline.json`, `chosen_*.json`,
  `scores_armA.json`, `durations_freq.pkl` (the rebuilt bins);
- `frames_en.json`, `maps_en.json`, `opts_en_r1/r2.json`, `mt_en_es.jsonl`, `es_chosen_*.json`,
  `scores_armB.json`.
- Code: `twosided.py`, `mt_sockeye.py`, `mt_google.py`, `eval_twosided.py`, `mctr.py` (errors in the objective).
