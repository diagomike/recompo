# Worktree `trained-mt`: a trained duration-aware NMT on the P19 bench

**What it is:** the public IWSLT 2023 automatic-dubbing baseline (`baseline_factored_noised0.1`, Amazon), the
published form of the *trained* mechanism.

- A Sockeye transformer reads German BPE text plus one duration bin per speech segment.
- It writes English **phonemes with a duration per phoneme** (target factors) while counting down auxiliary clocks:
  frames left in the line, frames left in the segment, pauses left (Chronopoulou et al. 2023; Pal et al. 2023).
- It was trained on CoVoST2 de→en with real English phone timings and noise (σ = 0.1) on the target durations.
- A second Sockeye model turns phonemes back into words.

**How it ran here** (you allowed installing the authors' fork, 2026-10-31):

- Environment: Python 3.10, torch 1.13.1 (CPU), `github.com/Proyag/sockeye@factor-pe`, under the session
  scratchpad.
- Duration bins: rebuilt from 150,000 training alignments (175,063 segments) with the authors' own code, because
  the original bin file is not in the release.
- Input: the **same 45 lines and the same German speaker frames** the LLM loop wrote for (`in.json`), decoded with
  beam 5 and `--force-factors-stepwise frames total_remaining segment_remaining pauses_remaining`, in 89 s on CPU.
- Output: phonemes converted to words per segment (`segments.words`), scored with the same ruler, the same real
  voice (VITS LJSpeech) and chrF. Normalised chrF (lower case, no punctuation) is the fair column, because the
  phoneme→word model outputs neither.

Script: `scripts/research/p19/wt_trained_mt.py` (bins, inputs, post, collect) and `wt_compare_all.py`; numbers:
`compare.json`.

| Condition | Speech overlap (voice) | Within ±20 % (voice) | Segments needing > 1.1× speed-up | chrF normalised |
|---|---|---|---|---|
| R0 plain LLM translation | 0.72 | 16 % | 69 % | 72.3 |
| REF human translation + placement | 0.81 | 61 % | 23 % | 100 |
| R0 + placement | 0.83 | 64 % | 19 % | 72.3 |
| **TRAINED_MT** (IWSLT duration-aware baseline) | 0.80 | 49 % | 12 % | **53.5** |
| R1 LLM timed | 0.91 | 86 % | 40 % | 66.9 |
| **R3 LLM timed + voice revision** | **0.92** | **93 %** | **6 %** | 65.2 |

Speech overlap of TRAINED_MT using **its own predicted phoneme durations**: 0.855. In the authors' pipeline a
FastSpeech2 voice speaks those durations directly; any other voice gets 0.80.

**Findings**

- The published trained model fits the timing about as well as **placement alone** (0.80 vs 0.83 with a real
  voice). It is far below an LLM told the budgets (0.92).
- It loses the most meaning of all conditions (normalised chrF 53.5 vs 65–72). Sample: "the amsl watched it all
  from the tree / moved her head to the left / blind and tested her wings before eventually went into the air".
  It was trained from scratch on CoVoST-sized data (~300 k sentences), with no pretrained language knowledge.
- Its durations are internally consistent (0.855 with its own clocks) but tied to its phoneme timings. They do not
  transfer to another voice, the same "the ruler must be the voice" lesson as the LLM loop.
- **What this means for training on your corpus:** the duration-aware architecture works, but a model trained from
  scratch lacks the language quality. The trained path worth pursuing is **a pretrained multilingual model
  (NLLB/mT5 or an LLM) fine-tuned with timing tokens or preference-tuned for duration** (SSPO-style), not a
  from-scratch transformer. Train against the voice that will speak.

Caveats: 45 read sentences, German speaker frames from VAD (not the frames the model was tuned on), bins rebuilt
from a sample, one voice. Phoneme→word conversion adds errors (e.g. "amsl" for "blackbird"'s German "Amsel").
