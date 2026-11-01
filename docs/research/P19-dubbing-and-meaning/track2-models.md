# Track 2: a model path — pretrained encoders without training, or a model trained on your dubbed movies

**Branch:** `ccr-327cc642-xnfs3i-track2-models` (your request: this track on its own branch). It builds on the shared
P19 report on `ccr-327cc642-xnfs3i` (`docs/research/P19-dubbing-and-meaning/README.md`).

**Your premise, confirmed by the literature and our pilot:** subtitles and professional dubs are different texts.

- Subtitles are condensed for reading.
- Dubs are adapted to be *spoken in the time the actor speaks*. A dialogue adaptor rewrites the literal translation
  ("dubbese"); voice actors adjust again.
- Öktem et al. (Heroes) found the Spanish subtitles matched the Spanish audio in only ~80 % of segments, and had to
  correct them by hand.
- Our pilot: the Heroes dub says 162 words where its subtitle has 127 ("Le telefoneé" → "Le he telefoneado").
- The thing to learn is exactly **source speech + timing → what a dubber says, and when**.

## 1. The task, stated precisely

Input per stretch of dialogue:

- Source speech: words with times, speakers, pauses, speaking rate; optionally on/off-screen, emotion and pitch.
- A translation reference: the target subtitle cue(s), an MT output, or none.

Output: the target **dub script** as phrases, each with text and a time window, such that:

1. the meaning is preserved (adequacy);
2. it is natural spoken target language (fluency, register);
3. each phrase is speakable at a natural rate inside its window (isochrony without speed-up);
4. pauses fall where the source pauses, the long ones at least (pause compliance);
5. optionally, on-screen: open and closed mouth shapes roughly agree (weak, ~12 % in human dubs).

There are two sub-problems with very different difficulty:

- **A. Placement:** given target text, split it into phrases, assign windows and rates. This is optimisation, and
  needs no training.
- **B. Wording:** produce target text of the right length and rhythm, rephrasing when needed. This is generation:
  an LLM (Track 1) or a trained model.

## 2. Literature map (architectures)

| Family | Representative work | Needs | Strength | Fit for us |
|---|---|---|---|---|
| Prosodic alignment (post-hoc placement) | Öktem 2019 (attention-based phrase mapping), Federico 2020, Virkar 2021/2022 (log-linear DP: break LM score, cross-lingual semantic match, rate variation, rate match; relaxations; on/off-screen) | a break scorer, a semantic matcher, a duration model | No MT training; works on any translation | **Core of the no-training path** |
| Length-controlled MT | Lakew 2019/2022 (length tags, isometric self-learning); Rao 2023 (length-ratio tags, rerank, duration scaling: overlap 0.92–0.98) | parallel text + tags | Simple; n-best friendly | Tags trainable on your dubs (dub/source length ratio as a tag) |
| Duration-aware decoding | Tam 2022 (pause markers in the input, simplest best); VideoDubber 2023 (duration positional embeddings, pause token, film test set); Chronopoulou 2023 and Pal 2023 (phonemes + durations as target factors, auxiliary counters: overlap ~0.99 on read speech) | word or phoneme durations from aligned target speech | The model itself respects time | Your dub audio provides exactly these durations |
| LLM + duration | Won 2025 (phoneme budget, iterate); HW-TSC 2024 (LLM post-edit, pause selector); APSIPA 2025 (N-best + paraphrase + synchrony rerank); **SSPO 2025** (segment-level preference optimisation of an LLM for duration) | an LLM; for SSPO, preference pairs scored by duration | Best wording quality | SSPO-style tuning on your corpus is the strongest trained option |
| End-to-end speech-to-speech translation with isochrony | TransVIP 2024 (isochrony embeddings, voice), SeamlessExpressive (pauses and rate), Dub-S2ST 2025 (discrete diffusion, duration control) | large paired speech; few languages | Keeps voice and prosody | Not for am/om now; revisit if your pairs are fr/es/en |
| Video-aware TTS | Neural Dubber 2021, DubWise 2024 (lip-guided durations), FunCineForge 2026 (multimodal-LLM dubbing, 4,700 h CineDub-CN) | video + speech | Lip-level timing in the voice | Later; complements whichever script model wins |

Datasets for comparison:

| Dataset | Size | Pair | Notes |
|---|---|---|---|
| Heroes | 7 k segments | en→es | Hand-corrected |
| Anim-400K | 425 k clips | ja→en | ASR-aligned, 125 ms merge rule |
| Min et al. 2025 | ~300 h | en→es, movies | ASR/subtitle agreement filter |
| CineDub-CN | 4,700 h | zh TV | |
| Brannon | 320 h | en→de/es, Amazon | Private |
| IWSLT | 200 test clips | de→en | Read speech |

**A thousand feature films come to roughly 2,000 hours per language pair**, at the scale of the largest of these,
and possibly the only such corpus for some of your language pairs.

## 3. Turning your library into training data (the corpus builder)

Per title, steps in order with the tool for each:

1. **Inventory** (`scripts/research/p19/inventory.py`, read-only, done):
   - audio languages and titles (skips commentary and audio description)
   - text vs bitmap subtitles (PGS/VobSub need OCR)
   - external `.srt` files
   - usable pairs and total hours per pair
2. **Extract** both dialogue tracks (ffmpeg `-map 0:a:N`), 16 kHz mono for analysis, plus text subtitles.
3. **Separate voices** from music and effects on each track: audio-separator (MDX/Demucs, in your worker env). The
   pilot showed that subtracting the tracks does **not** isolate the dub voice, because the mixes differ. The
   separated *background* of both tracks is still useful for the next step.
4. **Offset and drift:** cross-correlate the background envelopes in windows across the film and fit
   offset + rate. A PAL vs film master is a 4 % speed difference; `compose/release.py` already handles release
   drift for transcripts.
5. **VAD + ASR with word times on both tracks.** faster-whisper large-v3 / turbo (word timestamps) for most
   languages. Parakeet TDT v3 for 25 European languages (the pilot model, 0.25 RTF on 4 CPU threads). Ethio-ASR CTC
   or MMS for Amharic/Oromo.
6. **Forced alignment** for precise word boundaries and pauses: MMS forced aligner (torchaudio, uroman, 1,100+
   languages incl. am/om). The pilot showed transducer token times are too coarse for 0.25 s pauses.
7. **Diarisation:** pyannote 4 (in your worker env). Speaker turns stop two people merging into one run.
8. **On/off-screen:** YuNet faces per shot (`render/faces.py`), plus a mouth-open signal later if needed.
9. **Pairing:** overlap blocks of source and dub utterances, as in the pilot's `pair()`, Öktem's correlation rule,
   or Anim-400K's 125 ms merge. Attach the target subtitle cues overlapping each block.
10. **Filters and flags:**
    - foreign-language passages (language ID on both tracks), songs and music, narration
    - overlapping speech; ASR confidence
    - **"dubtitles"**: subtitles transcribed from the dub (subtitle-vs-dub WER near 0). These are useful as clean
      dub transcripts but are not translations.
11. **Output triplets:** `{source words+times+speakers, subtitle text+cues, dub words+times+speakers, flags}`, one
    JSONL per title.

Compute, from measured speeds:

- **This sandbox:** Parakeet 0.25 RTF on 4 threads.
- **Your PC:** whisper-turbo int8 RTF 0.33; separation is the slowest step.
- **Per film (2 h, two tracks):** ~2–3 CPU-hours on your PC, about 10 GPU-minutes on a T4 (Colab/Kaggle, already
  wired through `notebooks/recomp_worker.ipynb`).
- **20 titles:** ~2 days of CPU, or a single GPU session.
- **1,000 titles:** GPU only, ~150–200 GPU-hours, spread over free-tier sessions.

## 4. The no-training path (what pretrained models alone can do)

| Component | No-training option | Evidence | Language notes |
|---|---|---|---|
| Duration of target text | syllables × dialogue rate per language (2 numbers fitted from your corpus); or the TTS's own duration (edge-tts synth, MMS-TTS duration predictor as in IsoChronoMeter) | Pilot: a cross-title es/en syllable ratio predicts dub length within 9–20 %; read-speech rate tables 10–43 % | Ethiopic counted per fidel with sixth-order discounted (`timing.py`); calibrate on dubs or TTS |
| Where the source pauses fall in the translation | word alignment from pretrained multilingual embeddings: SimAlign / awesome-align (no parallel data; AER ~0.17 de-en, ~0.06 fr-en zero-shot) | SimAlign 2020; awesome-align 2021; zero-shot on unseen Romansh AER 0.22 | **mBERT lacks Amharic. Use XLM-R (has am, om, so, sw) or LaBSE (has am, so, sw)**; check om |
| Is a break plausible here (target side) | punctuation; masked-LM score of inserting a comma/pause with XLM-R; parse constituents (HW-TSC's parse-informed pause selector) | Virkar's break LM feature; HW-TSC 2024 | XLM-R MLM works for am/om text |
| Phrase ↔ phrase meaning match | LaBSE / e5 sentence similarity of source phrase vs candidate target phrase | Virkar's cross-lingual semantic feature | e5-small is already in the worker env |
| **Placement optimiser** | DP over break positions: maximise w₁·break + w₂·semantic match + w₃·rate match − w₄·rate variation, with ±δ relaxations into pauses; off-screen lines relaxed globally | Virkar 2021/2022; the pilot's `place_breaks` is the rate-only core | The 4–5 weights are tuned by grid search on your corpus. That is fitting, not training a network |
| Wording to fit | (i) MT n-best with length penalties (NLLB-200 covers amh, gaz [Oromo], swh, som, tir); (ii) **retrieval from your dub corpus**: the k nearest source lines (LaBSE) and their real dubs as candidates, or as few-shot examples for an LLM; (iii) rule-based compression (fillers, vocatives, contractions) | APSIPA 2025 (candidates + rerank) | Retrieval is where your corpus pays off with zero training |

**Verdict for no-training.** Placement (sub-problem A) is feasible and well understood. With your corpus to tune a
handful of weights and two rate numbers per language, it should approach human pause behaviour.

Wording (B) without any generator is the weak link. MT n-best gives limited length variety, and rule compression is
crude. In practice "no training" means **no-training placement + an LLM or retrieval for wording**, i.e. Track 1
with Track 2's placement underneath.

## 5. The training ladder (cheapest first; each rung is useful on its own)

| Rung | What is trained | From your corpus | Size / compute | What it buys |
|---|---|---|---|---|
| T0 | Calibration only: dialogue syllable rates per language (and per speaker sex), pause-reflection probabilities by pause length, duration-ratio distributions, on/off-screen differences | statistics | minutes, CPU | Correct budgets; the numbers that decide everything else |
| T1 | **Break predictor**: XLM-R-base token classifier, "pause after this target word?", with source-side pause features (projected through alignment) | dub word times → pause labels | ~1 M tokens; a few GPU-hours on a T4 | Learns where dubbers breathe in *your* languages; drops into the DP |
| T2 | **Duration model**: target word/phrase duration from text (+ speaker tempo) | dub word times | small (GBM or tiny transformer); CPU-hours | Replaces syllable heuristics, especially for am/om |
| T3 | **Dub-script generator (seq2seq):** NLLB-600M/1.3B or mT5 fine-tuned. Input: source text with timing tokens (`<p dur=1.2> … <pause 0.4> …`) + optional subtitle; output: dub text with pause markers (Tam 2022's simple scheme) | triplets | 100 k–1 M pairs; 1–2 days on one 16–24 GB GPU (600M) | A local model that writes dubbese at the right length; no API cost |
| T4 | **LLM fine-tune (LoRA)** on the same triplets, 3–8 B open model (e.g. Qwen/Llama/Gemma class), then **SSPO/DPO** preference tuning with a duration + meaning reward | triplets + sampled candidates scored by T2 and COMET | LoRA on 4-bit 7 B fits a free T4/P100 slowly; a rented 24–48 GB GPU makes it ~1 day | The strongest wording model; prompting alone is not enough (SSPO 2025) |
| T5 | End-to-end or multimodal (speech units, lip-guided TTS) | paired speech + video | large | Later research; only for high-resource pairs |

Data hygiene for all rungs:

- Split by **title**, not by line (lines of one film leak style and names).
- Hold out whole genres to test generalisation.
- Drop dubtitles from translation training, but keep them as clean dub transcripts.
- Weight on-screen lines when the goal is on-screen dubbing.

## 6. Evaluation (shared with Track 1)

- **Timing:**
  - speech overlap and pause compliance vs the source (with real TTS durations)
  - SLC₀.₂ / SLC₀.₄
  - speed-up factor needed
  - smoothness (rate variation between neighbouring phrases)
- **Meaning:**
  - chrF and COMET against the professional dub's words (COMET's XLM-R covers am)
  - reference-free COMET-Kiwi against the source
  - an LLM-judge for adequacy
- **Human:** your blind A/B on scenes, and VOX-DUB-style aspects (naturalness, emotion).
- **The bar:** professional dubs themselves (overlap ~0.7–0.8 in our pilot and in Brannon). A system above the human
  overlap with worse meaning is overfitting to timing.

## 7. Go/no-go plan

1. **Inventory** your library (`inventory.py`, minutes, read-only). This decides the language pairs, the subtitle
   OCR need, and the hours per pair.
2. **Corpus pilot, 20 titles of the largest pair** (`pilot_dub_pairs.py`, after adding separation, forced alignment
   and diarisation on your PC).
   - **Go if** ≥ 70 % of dialogue time pairs cleanly and a 50-line spot check of dub ASR is ≥ 90 % usable.
   - It also produces T0, which answers "how different are subtitles from dubs in this pair?" with numbers.
3. **No-training baseline:**
   - Placement DP + MT n-best, and placement DP + LLM wording (Track 1) + retrieval examples, on 5 held-out titles.
   - Compare with the human dub (timing, meaning) and with today's pipeline.
4. **T1 + T2** (cheap trainings) if step 3 shows placement errors matter. Rerun step 3.
5. **T3 or T4** only if 3–4 leave a wording gap the LLM path cannot close, or if API cost and offline use matter.
   Train on 200–1,000 titles.

## 8. Risks

- **Rights:** the films are copyrighted. Training and using models privately on your own copies is your call;
  do not publish the corpus or the weights (the same stance as D-23 for private sources).
- **Language coverage:**
  - Whisper is weak for am/om; Parakeet has neither.
  - The Ethio-ASR CTC (in your setup) and MMS are the fallbacks.
  - Forced alignment via MMS works with uroman for any script.
- **Dub style varies:** voice-over/narrated dubs (common for some Ethiopian releases) vs lip-synced theatrical dubs.
  The inventory and T0 statistics will show which you have; the model targets differ.
- **Sandbox limits for this research:** HuggingFace, arXiv, ACL Anthology, zenodo and dataverse were blocked here, so
  no XLM-R/LaBSE experiments ran in this session. They run on your PC (`D:\LangBridgeLocal\cache\hf`) or Colab.
