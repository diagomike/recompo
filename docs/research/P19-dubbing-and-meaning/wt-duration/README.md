# Worktree `duration`: predicting how long a phrase takes to say

**Question:** how well can text alone predict a phrase's spoken duration? Every timed-rephrasal mechanism needs
this ruler: to set budgets before writing and to check lines afterwards.

**Data:** Montreal Forced Aligner alignments of Common Voice English (IWSLT 2023 dubbing release):

- Training: 35,625 speech segments (between pauses ≥ 0.3 s) from 30,000 utterances.
- Testing: segments from 5,000 held-out utterances, and the 192 IWSLT test items.

Script: `scripts/research/p19/wt_duration.py`; numbers and the learned per-phone means: `results.json`.

| Model | Held-out MAPE | within ±20 % | IWSLT test MAPE | within ±20 % |
|---|---|---|---|---|
| D0 syllables × 0.221 s (today's `timing.py` idea) | 17.5 % | 65 % | 18.1 % | 64 % |
| D1 CMUdict phones × 0.0885 s | 16.2 % | 68 % | 16.9 % | 63 % |
| D2 learned mean duration per phone | 15.9 % | 70 % | 16.5 % | 65 % |
| D3 ridge regression on phone/syllable/word features | 16.0 % | 71 % | 15.6 % | 69 % |
| D4 gradient boosting, same features | 16.0 % | 71 % | **15.2 %** | **72 %** |

**Findings**

- **A floor near 15 %.** Learned models gain only ~2 points over counting syllables. The rest of the variation is
  the speaker (tempo, emphasis, hesitation), not the text. No text-only model will make lines fit reliably.
- **The speaker's own tempo helps, if there is enough of it.** Rescaling by the rate in the rest of the utterance
  helps on the longer IWSLT sentences (D2: 16.5 → 13.1 %; within ±20 % 65 → 80 %) but hurts on short held-out
  utterances, where the "rest" is one short segment. In dubbing, tempo should come from many seconds of the source
  speaker.
- **Dialogue-like read speech runs at 4.4 syllables/s** (0.221 s per syllable). That is far below the 6.19 syl/s of
  read-speech tables (Pellegrino 2011) and matches our film pilot (4.1–4.8). Budgets must use rates measured on
  real dialogue.
- **Consequence for the design:** use a cheap model (D0/D2) to *plan* lines, and **measure the actual voice**
  (TTS clip or its duration predictor) to *verify*. The llm-loop worktree shows why: lines tuned to this ruler
  still ran long in a real TTS voice until one round was revised against the voice itself.
