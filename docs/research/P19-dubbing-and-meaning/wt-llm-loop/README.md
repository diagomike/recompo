# Worktree `llm-loop`: Claude writes timed English for German speakers, in measured rounds

**Question:** can an LLM, told the speaker's timing, write a translation that fits the speech segments of a real
speaker, and at what cost in meaning? Does a measure-and-revise loop matter?

**Benchmark:** the IWSLT 2023 dubbing test set (CoVoST2 de→en).

- 45 lines: 30 from subset2 (with pauses) and 15 from subset1.
- Each line has a **real recording of a German speaker**. Its speech segments (Silero VAD, pauses ≥ 0.3 s) are
  the frame the English must fit. ASR on the recordings matched their text (median syllable ratio 1.00).
- Claude saw only the German line and the segment durations with syllable budgets (4.4 syl/s; `wt_llm_loop.py
  sheet`), never the English reference.
- **Contamination note:** two reference lines (subset2-31 and -32) appeared in an error log *after* all rounds were
  written; three subset1 references (0–2) seen earlier were excluded from the set.

**Conditions**

| | What it is |
|---|---|
| R0 | Plain translation (Claude), no timing given, spoken from the start of the first segment |
| R0+place | The same words split across the segments by the placement DP (no rewording) |
| REF | The human CoVoST reference translation, placed by the same DP (a translation, not a dub) |
| R1 | Claude writes per segment against the syllable budgets |
| R2 | R1 after one revision round on lines the *text ruler* measured outside ±20 % (6 lines) |
| R3 | R2 after one revision round on segments the *real TTS voice* ran more than 10 % over (41 segments) |

**Results.** Two rulers are reported:

- **Text ruler:** phone-mean duration model from real English speech, 15 % MAPE (`wt-duration`).
- **Real voice:** every phrase synthesized with VITS LJSpeech (sherpa-onnx, speed 1.0) and its audio measured
  (`wt_tts_check.py`). VITS sampling is stochastic, so expect ±0.005 between runs.

chrF is computed against the single human reference: rewording and padding lower it even when the meaning is kept.

| Condition | Overlap (ruler) | ±20 % (ruler) | **Overlap (voice)** | **±20 % (voice)** | **Segments needing > 1.1× speed-up** | Voice/real median | chrF |
|---|---|---|---|---|---|---|---|
| R0 plain | 0.689 | 9 % | 0.720 | 13 % | 69 % | 1.63 | 70.7 |
| R0 + placement | 0.808 | 54 % | 0.823 | 62 % | 21 % | 0.92 | 70.7 |
| REF + placement | 0.780 | 53 % | 0.797 | 51 % | 26 % | 0.96 | 100 |
| R1 timed | 0.921 | 91 % | 0.905 | 88 % | 35 % | 1.05 | 65.0 |
| R2 + ruler revision | **0.929** | **99 %** | 0.911 | 88 % | 35 % | 1.05 | 64.9 |
| **R3 + voice revision** | 0.889 | 82 % | **0.915** | **89 %** | **5 %** | **0.96** | 63.5 |

**Findings**

1. **Telling the LLM the timing works.** Speech overlap goes from 0.72 (plain) and 0.82 (plain + placement) to
   0.91, well above professional human dubs (~0.7–0.8). The human reference translation, placed the same way,
   reaches only 0.80. Fitting is not a property of a good translation; it has to be written for.
2. **Placement alone gets half the way** (0.72 → 0.82) and costs no meaning. Rewording takes it to 0.91.
3. **The ruler must be the voice.** Revising against the text ruler (R2) perfected the ruler score (99 % within
   ±20 %) but changed nothing for the real voice: 35 % of segments still needed speed-up. One round against the
   actual voice (R3) cut that to **5 %**.
4. **Meaning cost:** about 7 chrF points against the reference (70.7 → 63.5). Some of that is legitimate
   rephrasing and some is padding for slow speakers ("The couple had a daughter, Grace, and also a son, Henry."
   for a 4.5 s line). Short lines read slowly invite padding; a dub director would rather let the actor pause.
   Allowing silence inside a segment (a budget floor) is the next design knob.
5. **Effort:** one LLM pass plus one revision round with real-voice measurements. In a product: the plan uses a
   cheap duration model, then synthesize, measure and revise the failing segments once.

Files: `r0.json` … `r3.json` (Claude's outputs), `cands.json`, `results.json` (per-item phrases and ratios), `ruler.json`,
`tts_check.json`. Scripts: `scripts/research/p19/wt_llm_loop.py`, `wt_tts_check.py`.
