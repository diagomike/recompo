# Worktree `placement`: no-training prosodic alignment on real speech

**Question:** given the words of a line and a speaker's speech segments (separated by pauses ≥ 0.3 s), can we put
the breaks where a real speaker paused, without training a translation model?

**Data:** Montreal Forced Aligner alignments of Common Voice English (IWSLT 2023 dubbing task release). The models
were fitted on 29,929 utterances and tested on 1,195 held-out utterances (1,443 real pauses) plus the 60 IWSLT test
lines that contain pauses. Script: `scripts/research/p19/wt_placement.py`; numbers: `results.json`.

| Method | Held-out exact | Held-out ±1 word | IWSLT test exact | IWSLT test ±1 word |
|---|---|---|---|---|
| P0 uniform (words ∝ segment time) | 45.4 % | 92.0 % | 56.2 % | 93.2 % |
| **P1 rate DP** (phone-mean durations, log-ratio² cost) | 58.7 % | **93.5 %** | 68.9 % | **97.3 %** |
| P2 rate DP + hand rules (conjunctions, determiners, punctuation) | **61.5 %** | 85.5 % | **70.3 %** | 86.5 % |
| P3 rate DP + learned break model (logistic regression) | 61.1 % | 84.1 % | 67.6 % | 79.7 % |
| P4 learned break model only (no durations) | 33.2 % | 51.8 % | 32.4 % | 40.5 % |

**Findings**

- **Timing is the dominant signal.** A duration model plus a DP puts ~94–97 % of breaks within one word of the
  speaker's real pause, with no training beyond averaging phone durations.
- Lexical priors add a few points of exact hits but move a tenth of the breaks further away. The prior weight
  (0.5 here) should be tuned, or the prior only used to break ties between positions with the same rate cost.
- Lexical cues alone are weak (33 % exact). Where people pause is driven by timing more than syntax here.
- The learned model's weights are sensible: breaks before conjunctions (+1.34) and pronouns (+0.99), never after an
  auxiliary (−1.16), determiner (−0.73) or preposition (−0.78).
- **Caveat:** Common Voice is read speech, where pauses are rare (2.4 % of word boundaries) and partly hesitations.
  Film dialogue pauses are more deliberate; your dub corpus will show whether priors help more there.

**For dubbing:** placement is not the hard part. Once a translation has the right total length, a DP lays it on the
speaker's pauses well. The hard part is getting the length right (see `wt-duration`, `wt-llm-loop`).
