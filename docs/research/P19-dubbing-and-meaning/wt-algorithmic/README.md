# Worktree `algorithmic`: timed rephrasing with no neural model

**Question (2026-10-31):** can rephrasing for dubbing time be done fully algorithmically, language-agnostic in
method, with no neural MT, LLM or BERT? (Neural pluggable options, BERT/XLM-R masked-LM edits and NLLB n-best,
need HuggingFace, which this sandbox blocks; they are the next step on your PC.)

**Method** (`scripts/research/p19/wt_algorithmic.py`, `ngram_lm.py`)

1. **Input:** a given translation. Here R0 (Claude's plain translation, standing in for "any MT") and the human
   reference.
2. **Placement DP** onto the German speaker's segments (worktree `placement`).
3. **Per-segment beam search** over small edits from a swappable **language pack** (English here):
   - contractions/expansions;
   - phrase shortcuts ("in order to" → "to");
   - optional-word drops; deletion of 2–3-word spans (sentence compression);
   - one inserted filler at most;
   - WordNet synonyms.
4. **Judges:**
   - **Fluency:** a word trigram LM with stupid backoff, trained on 400 k English Common Voice sentences. The
     5,767 sentences identical to a test reference were excluded (Common Voice reuses sentences).
   - **Meaning drift:** edit costs.
   - **Fit:** the duration ruler. Optionally the ruler is calibrated per segment to the real voice, and the top
     candidates are synthesized (the analogue of the LLM's R3).
5. **Versions:** v1 had no fluency veto. v2 adds a veto on any single edit the LM rates 4 nats worse, blocks
   misfiring rules ("to" → "in order to", "Don't you" → "Do not you", "I had the" → "I'd the"), and allows one
   filler insert per phrase.

**Results:** the same 45 lines and German frames. Voice = VITS LJSpeech measured audio. Fluency = **blind**
judgement of 290 shuffled unique phrases from five conditions (Claude as judge, no labels; `blind_fluency.json`).

| Condition | Overlap (voice) | Within ±20 % | Needing > 1.1× speed-up | chrF | Fluent segments | Lines fully fluent |
|---|---|---|---|---|---|---|
| R0 + placement (no rewording) | 0.83 | 60 % | 19 % | 70.7 | 99 % | 98 % |
| ALGO v1, λ = 0.01 (no veto) | 0.90 | 89 % | 19 % | 68.2 | **73 %** | **53 %** |
| ALGO v2, λ = 0.03 (veto) | 0.85 | 66 % | 18 % | 69.8 | 94 % | 89 % |
| ALGO v2 + voice calibration | 0.87 | 76 % | 11 % | 66.9 | 81 % | 64 % |
| R3 (LLM timed + voice revision) | **0.92** | **91 %** | **5 %** | 63.5 | **100 %** | **100 %** |
| TRAINED_MT (IWSLT baseline) | 0.80 | 41 % | 12 % | 47.8 | 28 % | 16 % |

(Sweeping λ = 0.1 / 0.03 / 0.01 gave a trade-off curve: more allowed LM loss means better fit and worse English.
v2 at λ = 0.1 and 0.03 came out the same.)

**Findings**

1. **The safe algorithmic edits are too small.** With the fluency veto, only ~12 of 85 segments find an acceptable
   edit, and they gain +0.02 overlap over placement alone. Contractions, fillers and synonyms change a phrase by
   ~5 %; real segments often need ±20–40 %.
2. **Pushing harder breaks the English.** Without the veto, fit rises to 0.90 but a quarter of segments become
   ungrammatical ("is going in order in order to ruin…", "Do not you dare", "also also kissed"). The calibrated
   voice step also reached for riskier edits (81 % fluent).
3. **chrF does not see it.** v1's broken lines lost only 2.5 chrF points: character n-grams survive inserted
   junk. Any automatic evaluation of rephrasing needs a fluency check (human, LLM-judge, or a strong LM).
4. **The weak link is the fluency/meaning judge, not the search.** A 4 M-token trigram LM cannot tell "I'd the
   urge" or "I was able to just publish" from good English. This is exactly the slot where a pretrained model plugs
   in: an **XLM-R / BERT masked LM** to propose and score edits, and **LaBSE / e5** to check meaning. Expect much
   of v1's fit at v2's fluency or better. It needs HuggingFace (your PC).
5. **Language-agnostic in method, not in resources.** The search, LM and placement work for any language with a
   text corpus. The edit pack (contractions, shortcuts, fillers) and the synonym source are per language. For
   am/om there is no WordNet; synonyms and shortcuts would have to be mined from a parallel or dub corpus.

**Verdict:** fully algorithmic rephrasing is not competitive. Use it only as a light, safe touch after placement
(+0.02). The two working paths remain: an LLM told the timing and checked against the voice, or a pretrained
masked LM plugged into this same search (to test on your PC).
