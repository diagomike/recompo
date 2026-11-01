# P19 research: understanding speech for dubbing and for cuts — feasibility

**Started:** 2026-10-31. **Status:** research only (your direction, 2026-10-31: no app building until the
feasibility is clear). Nothing in `recomp/` changed for this.

You asked about three things:

1. **LLM-timed dubbing script**: Claude reads the ASR transcript, understands the thought flow, and writes a
   target-language script timed to the speaker: the right amount of words for when the mouth moves, pauses kept.
   → [track1-llm-timed-translation.md](track1-llm-timed-translation.md)
2. **A model / no-training path** (own branch): pretrained encoders (BERT-family) and timed window placement
   without training, or a model trained on your dual-audio movies, learning how professional dubs differ from
   subtitles. → on branch **`ccr-327cc642-xnfs3i-track2-models`**,
   `docs/research/P19-dubbing-and-meaning/track2-models.md`
3. **Smarter LLM cut creation**, built on the same understanding of thought flow.
   → [track3-llm-cuts.md](track3-llm-cuts.md)

## Verdicts in one screen

| Track | Feasible? | Why | Main risk |
|---|---|---|---|
| 1 LLM timed script | **Yes: high for voice-over and off-screen lines, medium-high for on-screen** | Published LLM systems reach large isochrony gains while keeping translation quality (duration-based translation +24 % speech overlap, EMNLP 2025; N-best + LLM paraphrase + synchrony reranking, APSIPA 2025; LLM post-editor + pause selector won IWSLT 2024). Human dubs only reach ~0.7 speech overlap themselves, so the target is reachable. In our probe the LLM held per-run syllable budgets easily. | Not the LLM. It is the **timing frame** (word timings, speaker turns) and the **duration estimate in the target language** (Amharic, Oromo: no calibrated rate yet). Both can be fixed with tools you already have plus calibration from your corpus. |
| 2 Model / no-training | **No-training: yes for placement (where and how fast), weak for rewording. Training: yes, and your corpus is the rare ingredient.** | Timed placement is a solved-in-principle optimisation (prosodic alignment by dynamic programming, Öktem 2019 → Virkar 2022). Pretrained multilingual encoders align words without parallel data (SimAlign / awesome-align; **XLM-R or LaBSE for Amharic/Oromo; mBERT has no Amharic**). Rewording to fit needs a generator: an LLM, or a model trained on dubs. Trained duration-aware MT works (VideoDubber, target factors with counters ~0.99 overlap on read speech; SSPO preference-tunes an LLM for duration). The largest public dub corpora are 7 k segments (Heroes) and 425 k clips (Anim-400K, ja→en); thousands of your titles would be among the largest dub corpora anywhere. | Data quality at scale: ASR of noisy dub tracks, track offsets and drift, foreign-language passages and songs, and subtitles that are really dub transcripts. Rights: train and use privately. |
| 3 LLM cuts | **Yes, high** | Industry and research converge on one design: the LLM reads the transcript and picks spans **by line IDs** (never invents times), the machine snaps the boundaries, and a ranked, explained shortlist goes to the editor (RankCut, IUI 2026; highlightr; ButterCut/ClaudeCut on Claude Code). Recomposer already has the mechanics (`cut suggest`, snapping, semantic search, chapters, journeys). | Evaluation: there is no ground truth, so we need your accept/reject judgements as the metric (and later as preference data). Zero-shot LLM topic boundaries agree only moderately with human ones; fine-tuning with pause cues helps. |

**The common core:** all three tracks need the same understanding layer for a source: thought units, who speaks,
intent, register and emotion, aligned to word timings and pauses. Built once per source, it serves the dub script
(Track 1), the training features (Track 2) and the cut candidates (Track 3).

## What the literature says about professional dubbing (the target we imitate)

- **Brannon, Virkar & Thompson 2023** (TACL; 320 h, 54 Amazon Studios shows, en→de/es) is the key study:
  - Human dubbers keep **translation quality and vocal naturalness first**. They do **not** speed up their speech
    to fit, and do not sacrifice translation accuracy on-screen.
  - Isochrony is real but loose: overlap ~0.66 off-screen vs ~0.69 on-screen.
  - **Isometry (character count) is a poor proxy for timing.**
  - **Lip sync is weak:** only ~12 % of on-screen speech time shares a viseme.
  - The source's speaking rate, pitch and energy carry over into the dub (r = 0.58 for speaking rate on lines over
    1 s). Dubbers imitate the delivery.
- **Öktem et al. 2019** (Heroes, en→es): pauses longer than 0.1 / 0.2 / 0.4 s show up in the dub 70 / 81 / 91 % of
  the time. Long pauses are near-hard constraints.
- **Karakanta et al. 2020; Virkar et al. 2022:** on-screen and off-screen lines need different strategies. Timing
  constraints applied off-screen cost translation quality for nothing. We already detect faces (`render/faces.py`,
  YuNet), so an on-screen/off-screen flag per line is cheap.
- **Practitioners:** the dub script is an adaptation of a literal translation ("dubbese"), made by a dialogue
  adaptor and then changed again by actors. Subtitles are condensed for reading. This is exactly the gap between
  your subtitles and your dubs.

Full literature tables are in the track notes.

## Pilot on real dual-audio media (2026-10-31, this sandbox, CPU)

Two professionally dubbed excerpts with both audio tracks and subtitles in both languages: a scene from *The Man Who Knew
Too Much* (1956, 18 s) and *Heroes* S2E7 (61 s), English → Spanish. They ship with
[movie2parallelDB](https://github.com/alpoktem/movie2parallelDB). Script:
`scripts/research/p19/pilot_dub_pairs.py`. It takes the same input your library would: the two audio tracks
and the two subtitle files. Raw output: [pilot-m2p-excerpts.json](pilot-m2p-excerpts.json). The ASR was Silero
VAD plus NeMo Parakeet TDT 0.6B v3 (25 European languages) through sherpa-onnx, about 20 s for 79 s of audio.

| Measure | Film scene | Heroes | Reading |
|---|---|---|---|
| Track offset (envelope → waveform) | −0.187 s | 0.000 s | Found automatically. Your titles will have offsets, and some PAL drift. |
| Shared music and effects cancel when subtracting tracks? | No (waveform peak 0.02) | Barely (−3.9 dB with a 64-tap fitted filter) | **Subtraction cannot isolate the dub voice.** Use a voice separator (audio-separator is in your worker env). |
| Human dub speech overlap (time both speak / time either speaks) | 0.72 | 0.81 | In line with Brannon's ~0.7. |
| Per-block dub / source duration (median) | 0.97 | 1.11 | Dubs run about the same length, slightly longer. |
| Dialogue speaking rate, syllables/s (en / es) | 4.1 / 4.6 | 4.8 / 5.2 | **Far below the read-speech tables (6.2 / 7.8).** Budgets need rates calibrated on dialogue. |
| Words: Spanish subtitle vs Spanish dub | 36 vs 37 | 127 vs 162 | In Heroes the dub says **28 % more words** than the subtitle. Example: "Le telefoneé" (subtitle) → "Le he telefoneado" (dub). |
| Dub length predicted from source syllables × es/en ratio (ratio from the *other* clip) | 20 % error | 9 % error | A one-number calibration per language pair already predicts length well. |
| Same, using read-speech rate × duration × tempo | 43 % | 10 % | Read-speech tables mislead. |

Also learned:

- **ASR on a dub track works** (clean Spanish transcripts).
- **The timing frame is the weak link.** Transducer token times are coarse (80 ms frames; "you're not going" got
  0.08 s), and without diarisation two speakers merged into one 7 s run. Use forced alignment (MMS forced aligner,
  1,100+ languages including Amharic) and pyannote (already in your worker env).
- **Films contain hazards:** the Heroes English track has Japanese dialogue and a recap montage. The corpus builder
  must flag foreign-language speech, music, songs and narration.

Two clips are a smoke test of the method, not statistics. The real feasibility numbers come from running the same
script on 20–50 of your titles (plan below).

## Recommended next experiments (in order; each has a go/no-go)

1. **Corpus pilot on 20–50 of your titles** (Track 2 branch, `corpus` plan). Extract the tracks, separate the
   voices, run ASR on both tracks, force-align, diarise, and estimate offset and drift. Then measure, per language
   pair: subtitle-vs-dub word gap, compression, pause reflection, dialogue speaking rates, and on-screen vs
   off-screen differences.
   **Go if** at least 70 % of dialogue lines pair cleanly and dub-track ASR passes a spot check.
   **Cost:** about 1 CPU-day per 10 titles on your PC, or hours on a Colab/Kaggle GPU.
2. **Track 1 A/B on 10 held-out titles.** Compare three scripts, all voiced by the same TTS: Claude's timed script
   (written from the source alone), the current pipeline (subtitle-length budget plus speed-up), and the professional
   dub's own words. Measure speech overlap with the real TTS durations, speed-up needed, a meaning score vs the human
   dub, and your blind preference.
   **Go if** Claude's script reaches overlap ≥ 0.7 with speed-up ≤ 1.1× and you prefer it to the current pipeline.
3. **No-training placement baseline** (Track 2). Split the translation into phrases and place them on the source's
   pauses with a dynamic programme: XLM-R/LaBSE alignment, break scores, and a rate match calibrated in step 1.
   Score it against where the dubbers really paused.
4. **Small trainings** (Track 2), only if 1–3 show signal: a pause/break predictor (XLM-R token classifier) and a
   target-language duration model from the dub audio. After that: a dub-script generator, either an LLM fine-tuned
   with LoRA or NLLB with timing tokens, trained on (source + timing frame + subtitle → dub) triplets.
5. **Track 3:** thought-unit cut candidates vs today's `cut suggest`, on alex-oconnor and ai-and-ideas, judged by
   your accept rate and how much you trim.

## Questions that change the plan

- **Which language pairs are in your dual-audio library?** For example English → Hindi, French, Spanish,
  Arabic, Amharic. This decides the ASR models (Whisper and Parakeet are weak or absent for some), the aligners and
  the encoders.
- Are the dubs lip-synced (theatrical) or voice-over (narrated)? Ethiopian translated films are often narrated
  voice-over, which changes the target.
- Should Track 1 run through the agent (Claude Code operating the app, as today) or through direct API calls (better
  for whole films)? This is a direction choice for when building resumes.

## Files

- `track1-llm-timed-translation.md`, `track3-llm-cuts.md` (this branch), `track2-models.md` (Track 2 branch).
- `pilot-m2p-excerpts.json`: pilot output (all measures, word timings of both tracks).
- `track1-llm-probe.json`: the timed translations written by Claude for the film scene (fr, am) with syllable counts.
- `scripts/research/p19/timing.py`: runs, units, syllable estimates (Ethiopic-aware), budgets, isochrony scores.
- `scripts/research/p19/pilot_dub_pairs.py`: the pilot (E1–E5), single title or a TSV of titles.
