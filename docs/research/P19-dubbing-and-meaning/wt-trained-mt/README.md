# Worktree `trained-mt`: a trained duration-aware translation model (not run yet: needs your permission)

**What it would test:** the strongest published *trained* mechanism that is publicly available. The IWSLT 2023
dubbing baseline is a Sockeye transformer, German text with speech-segment durations → English phonemes with a
duration per phoneme. Target factors plus auxiliary counters ("time left in this segment", "pauses left") let the
decoder see the clock as it writes; Pal et al. 2023 report ~0.99 speech overlap on CoVoST.

Comparing it with the LLM loop and the no-training placement on the same German speaker frames answers the
question: does a model trained on timing beat an LLM told the timing?

**Fetched and ready** (from the public `amazon-science/iwslt-autodub-task` release via GitHub media downloads):
- `models/sockeye/trained_baselines/baseline_factored_noised0.1/model/params.00078` (381 MB) and its vocabularies;
- `models/phoneme_to_grapheme/params.00048` (218 MB), the phoneme → word model used to score translation quality;
- BPE codes, the test sets, and the 192 German test recordings (frames in `bench_frames.py`).

**Blocked step:** the model needs the authors' Sockeye fork (`github.com/Proyag/sockeye@factor-pe`) and PyTorch in
a Python 3.10 environment. Installing that fork from GitHub was refused in this session by the auto-mode safety
check ("code from external"). Nothing was worked around.

**To run it**, either:
1. allow it here (say so in chat, or add a permission rule), and I install the fork into a separate environment
   under the scratchpad and decode the 192 test lines on CPU (expected minutes to an hour); or
2. run on your PC or Colab:
   ```
   conda env create -f environment.yml   # from the iwslt-autodub-task repo
   bash sockeye_scripts/decoding/...      # decode subset1/subset2 with the factored baseline
   ```
   then score the output with `scripts/research/p19/wt_llm_loop.py score` (same frames, same ruler).

**What we already know from the literature** (track2-models.md): trained duration-aware models reach near-perfect
isochrony on read speech, with a 3–9 % translation-quality cost (Chronopoulou 2023). They need phoneme-level target
durations to train, which your dub audio would provide via forced alignment.
