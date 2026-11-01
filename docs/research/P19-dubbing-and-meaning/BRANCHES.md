# Branches and worktrees used in P19

Every research branch was merged into `ccr-327cc642-xnfs3i` with a merge commit (history kept) and from there into
`main`. The branches also stay on GitHub. Tips are listed as they were merged.

| Branch | Tip | Grew from | Folder here | What it holds |
|---|---|---|---|---|
| `ccr-327cc642-xnfs3i` (session) | — | `main` | this folder | Feasibility report, tracks 1 and 3, the pilot, the shared bench, the comparison across worktrees; now also the app integration |
| `ccr-327cc642-xnfs3i-track2-models` | `43aadbe` | session | `track2-models.md`, `scripts/research/p19/inventory.py` | Model path: no-training placement, training ladder, corpus builder for your dual-audio library |
| `…-p19-duration` | `2c27a1f` | session | `wt-duration/` | Text → duration predictors (15–18 % floor) |
| `…-p19-placement` | `90151ed` | session | `wt-placement/` | Rate-matching DP placement (94–97 % within a word) |
| `…-p19-llm-loop` | `619b703` | session | `wt-llm-loop/` | LLM budgets + measure-and-revise against the voice; the 45-line frames |
| `…-p19-trained-mt` | `8da02f0` | session | `wt-trained-mt/` | IWSLT Sockeye duration-aware NMT, run as a black box; all-mechanism comparison |
| `…-p19-algorithmic` | `6557729` | session | `wt-algorithmic/` | Rules + WordNet + trigram LM (blind fluency check) |
| `…-p19-llm-multiround` | `017a29d` | llm-loop | `wt-llm-multiround/` | Multi-round refinement with the voice (best timing) |
| `…-p19-mctr` | `7b3a628` | multiround | `wt-mctr/` | Meaning-conserving top-down rephrasing: spec, module, tests, blind meaning check |
| `…-p19-twosided` | `d355cec` | mctr | `wt-twosided/` | Source-side options → MT → target voice → selection + back-translation checks |
| `…-p19-pivot` | `eef0c13` | twosided | `wt-pivot/` | Weak → weak through English: multi-view understanding, prosody cues, confidence |
| `…-p19-routes` | `aa3b044` | pivot | `wt-routes/` | Working-language routing, economy and quality budgets, route prior |
| `…-p19-bipivot` | `a0f41ae` | routes | `wt-bipivot/` | English + Spanish middle languages from two MT systems; French target with real MT |

The local worktrees lived at `/home/user/recompo-wt-<name>` in the cloud session; they are not needed any more.

## Shared code (`scripts/research/p19/`)

| File | Role |
|---|---|
| `timing.py` | Syllables (Ethiopic-aware), speech runs, budgets, isochrony metrics |
| `bench.py`, `bench_frames.py` | The benchmark: IWSLT/CoVoST lines, German speakers' segments, scoring |
| `pilot_dub_pairs.py` | Parakeet ASR + VAD wrapper; the film pilot |
| `inventory.py` | Read-only inventory of an MKV library (audio and subtitle tracks per language) |
| `wt_duration.py`, `wt_placement.py`, `wt_llm_loop.py`, `wt_tts_check.py`, `wt_trained_mt.py`, `wt_compare_all.py`, `wt_algorithmic.py`, `ngram_lm.py`, `wt_multiround.py` | One per worktree (see the folders) |
| `mctr.py` (+ `test_mctr.py`) | Meaning units, allocation, exact selection: the core the app reuses |
| `twosided.py`, `eval_twosided.py`, `mt_google.py`, `mt_sockeye.py` | Two-sided optimiser, MT wrappers |
| `pivot.py` | ASR, prosody cues, MT views, evidence sheets |
| `routes.py` (+ `test_routes.py`) | Route planner, E/D/X selection, cascade baseline, tokens |
| `mt_bergamot.py` | Mozilla Firefox Translations models offline (second MT system) |

Research scripts are kept as they ran, so they are not part of the app. The app's own implementation is in
`recomp/lang/llmdub.py` and `recomp/verbs/dub.py` (see `APP.md`).
