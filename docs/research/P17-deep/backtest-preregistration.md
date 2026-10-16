# Backtest pre-registration (written before any heatmap, clip or comment data was read)

**Date:** 2026-10-16 · Committed to git before the analysis scripts read the collected data.

## Question
Do any of these methods rank sentence-aligned windows of an episode so that the top of the ranking lands on the
moments people really clipped, weighted by how well those clips did, better than random windows and creator
chapter starts?

## Corpus
- **Lex Fridman** (main corpus): the 18 episodes in `episodes/lex-episodes.txt`, each with ≥ 20 uploads on the
  official Lex Clips channel. Real clips = Lex Clips uploads plus third-party clips found by YouTube search, mapped
  back to the episode.
- **Alex O'Connor**: S1–S5 of the `alex-oconnor` project; real clips = Alex's own Shorts and third-party clips mapped
  to those episodes. Too few clips for a test of its own; reported as a description.

## Split (fixed now)
Episodes sorted by `sha1(video id)`: the first 12 are **train** (any tuning: peak prominence, blend weight,
comment bandwidth), the last 6 are **held out** and are scored once:
`m_CFCyc2Shs, _bBRVNkAfkQ, 14OPT6CcsH4, NYFGCESmikA, l6USUAIKJls, 1SJiTwbSI58`.

## Windows
Sentences from the episode's word-timed YouTube captions (a sentence ends at . ? ! or a pause ≥ 1.2 s); one
candidate window per starting sentence, grown to ≥ 45 s and ≤ 90 s (min 20 s): the `cut suggest` rule.

## Methods (each returns the top-k non-overlapping windows)
1. **replay**: mean "Most replayed" value over the window, windows centred on `find_peaks` peaks first
   (prominence tuned on train, default 0.05).
2. **comments**: mean timestamp-mention density (Gaussian, bandwidth tuned on train, default 20 s, weight 1 + log(1+likes)).
3. **blend**: z(replay) + w·z(comments), w tuned on train (default 1).
4. **agent**: the agent's picks from reading the transcript, made before looking at any clip, heatmap or comment of
   that episode (held-out episodes only; Alex: the 12 cuts made in M2 on 2026-10-15).
5. **chapters**: windows starting at each creator chapter start, in chapter order.
6. **random**: 1,000 draws of k random non-overlapping windows; the mean and its 95 % interval are reported.

## Ground truth and weights
Each matched clip gets weight = its outlier score: log10(views per day since upload) minus the median of the same
for its own channel, clipped at 0 and plus 1 (so every real clip counts at least 1, outliers count more).

## Scores
A predicted window hits a clip when ≥ 50 % of the window lies inside the clip or ≥ 50 % of the clip lies inside the
window; its gain is the largest weight among the clips it hits. **precision@k** (share of top-k that hit) and
**NDCG@k** (gains discounted by rank, normalised by the ideal ordering of real clip weights), k = 5 and 10, averaged
over held-out episodes. 95 % intervals by bootstrap over episodes (and over random draws for `random`).

## What counts as "a margin that matters"
A method beats a baseline when its held-out NDCG@10 exceeds the baseline's by ≥ 0.10 **and** the bootstrap interval
of the paired difference excludes 0. With 6 held-out episodes this is a coarse test; train-set results are reported
next to it, labelled as such.
