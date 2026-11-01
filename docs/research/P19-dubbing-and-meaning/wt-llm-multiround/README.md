# Worktree `llm-multiround`: multi-round LLM refinement against the real voice

**Question (your note, 2026-10-31):** multi-round LLM refinement of the words should be one of the best methods.
How far does it go when pushed to convergence?

**Setup:** the same 45 IWSLT lines and German speaker frames as `llm-loop`, continuing from its R3. Each round:

- Synthesize every segment with the real voice (VITS LJSpeech via sherpa-onnx). Durations are **cached**, so every
  round sees the same measurements.
- Flag segments outside the band **0.8–1.05 × the speaker's time**. Up to 20 % silence is allowed; overruns are not.
- Claude writes 1–4 alternatives per flagged segment, has them **spoken and measured**, and keeps the most faithful
  one that fits. The LLM gets a "say it and time it" tool.
- **De-padding:** lines padded in R1 to fill slow speakers get their plain-translation wording back wherever the
  band allows ("That damn little mouse could sense how angry I was" → "That damn mouse could sense how angry I
  was").

Script: `scripts/research/p19/wt_multiround.py` (`sheet`, `curve`).

**Convergence** (cached voice, `curve.jsonl`)

| Round | Voice overlap | In band 0.8–1.05 | Over 1.05 | Over 1.1 | Under 0.8 | Segments revised |
|---|---|---|---|---|---|---|
| R0 + placement | 0.826 | 37 % | 35 % | 25 % | 28 % | — |
| R1 (timed, one pass) | 0.908 | 45 % | 52 % | 35 % | 4 % | all |
| R3 (llm-loop's best) | 0.918 | 74 % | 17 % | 5 % | 10 % | 41 |
| R4 | 0.914 | 87 % | 6 % | 4 % | 7 % | 22 + de-padding |
| R5 | 0.927 | 95 % | 2 % | 1 % | 2 % | 9 |
| **R6** | **0.929** | **98 %** | **1 %** | **0 %** | **1 %** | 3 |

The last miss is "he said," in a 0.73 s slot: two words that are naturally a little short. Silence is the right
answer there.

**Against everything else** (fresh re-synthesis with the same voice, `compare.json`; fluency = blind judgement of
shuffled unlabelled phrases, `blind_fluency.json`)

| Condition | Voice overlap | Within ±20 % | Needing > 1.1× | chrF | Fluent segments |
|---|---|---|---|---|---|
| R0 + placement | 0.82 | 62 % | 22 % | 70.7 | 99 % |
| Trained duration-aware NMT | 0.80 | 43 % | 14 % | 47.8 | 28 % |
| Algorithmic (safe) | 0.84 | 71 % | 21 % | 69.8 | 94 % |
| Algorithmic + voice | 0.86 | 81 % | 14 % | 66.9 | 81 % |
| R3 (LLM, one voice round) | 0.92 | 91 % | 6 % | 63.5 | 100 % |
| **R6 (LLM, multi-round)** | **0.92** | **97 %** | **1 %** | 64.1 | 98 % |

**Findings**

1. **Multi-round LLM refinement is the best method we have tested.** Three extra rounds took segments in band from
   74 % to 98 % and overruns needing speed-up from 5 % to 0–1 %, with fluency kept (98 % of segments; the two
   marginal lines are "starts giving orders, heavily accented", "looked in the space under the floor").
2. **The gains come from the measure step, not from more writing.** Each round only touches what the voice flags
   (22 → 9 → 3 segments). Given 2–4 alternatives and their real durations, the LLM picks a fitting one almost
   every time. The loop is cheap and converges in ~3 rounds.
3. **De-padding recovers only a little meaning** against the single reference (chrF 63.5 → 64.1; R5 64.6). Most of
   the remaining gap to the plain translation (70.7) is rewording that a single reference counts as error. A
   human or LLM-judge meaning check is needed to know how much is real loss.
4. **Overlap plateaus near 0.92–0.93.** The rest is the frame itself: the voice cannot start exactly when a
   segment starts, and short segments ("he said,") cannot be filled without padding. That is above professional
   human dubs (~0.7–0.8), which also trade timing for naturalness.

**Caveats:** 45 read sentences, one TTS voice, and the cached measurements the rounds were tuned on; the fresh
re-synthesis (0.920) is the fairer number. The same Claude wrote the lines and judged fluency blind. The meaning
metric is chrF against one reference.

**For a product:** plan with a cheap duration model → write timed lines → synthesize with the dub voice → revise
only the out-of-band segments, with 2–4 measured alternatives each → repeat until under ~2 % remain (≈ 3
rounds). The same loop works with any voice (OmniVoice clones, edge-tts) and any target language whose voice can
be synthesized.
