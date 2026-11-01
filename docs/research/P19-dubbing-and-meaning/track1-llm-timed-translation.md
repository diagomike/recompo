# Track 1: an LLM writes the timed dubbing script

**Question:** can Claude read a source transcript (ASR, with word timings), understand what is going on, and write
a target-language script whose phrases fit the time the speaker's mouth moves, pauses included, instead of
translating caption lines and speeding the voice up?

**Short answer: yes.** The LLM part is the easy part. Feasibility hinges on three non-LLM pieces: an accurate
timing frame, a duration estimate for the target language, and a measure-and-revise loop. The literature, and our
pilot, point to the same design.

## 1. Where Recomposer is today (baseline)

- Translation unit: a **caption line** (`lang translate --template`). Budget: line duration × chars/s
  (`CPS`: am 11, om 13, else 15).
- Dub (`lang/dub.py`): the TTS voices each line. If it is too long, edge `rate` goes up to +35 %, then `atempo` up
  to 1.25×, and the agent shortens lines the check lists. Lines can start up to 1 s late.
- **Missing:**
  - Pauses inside a line (word timings exist but are unused).
  - Meaning across line breaks (a thought split over three captions is translated as three fragments).
  - The speaker's own pace.
  - The fact that professional dubbers avoid speeding up (Brannon 2023).

## 2. The proposed method (what the LLM sees and does)

```
source words (timed) ─► runs: speech between pauses ≥ 0.25 s          ┐
                       units: whole thoughts (sentence end,          ├─ timing frame
                              speaker change, pause ≥ 1.2 s)          │
                       per run: duration, pause after, budget        ┘
      │
      ▼
LLM pass A — understand (once per source, cached):
  per unit: speaker, addressee, intent, register/formality, emotion, on/off-screen,
  names and terms to keep, jokes and idioms to localise
      │
      ▼
LLM pass B — write: translate each unit as one thought into natural spoken target language,
  then share it across the unit's runs in speaking order, each run ≈ its syllable budget
  (never above max), 2–3 variants per unit (tight / natural / loose)
      │
      ▼
measure: duration of each variant (calibrated syllable model → TTS duration predictor → real TTS clip)
  → pick the best fit per unit; send the failures back to the LLM with numbers
    ("run r7 is 0.6 s over: say it in ~5 syllables") — at most 2 rounds
      │
      ▼
timed target script: per run start/end/text → TTS per run → placed at the run's start
```

Why each step:

- **Units before runs.** Translating fragments loses grammar: verb-final languages like Amharic need the whole
  clause. Sharing a unit across runs is what a dialogue adaptor does.
- **Syllable budgets at the speaker's tempo, not characters.** Isometry is a poor proxy (Brannon 2023). The source
  speaker's rate carries over into human dubs (r = 0.58).
- **Variants plus measurement, not one shot.** LLMs lack direct duration awareness: SSPO (ACL 2025) found prompting
  and fine-tuning on subtitles "do not handle duration alignment well". Every working LLM system uses a loop or
  reranking:
  - Duration-based Translation (EMNLP 2025 demo) iteratively targets a phoneme count: +24 % relative speech overlap
    at competitive COMET.
  - HW-TSC (IWSLT 2024): LLM post-editor for length variants, parse-aware pause selector, reranking by lip-sync
    error. Best in the task.
  - APSIPA 2025: N-best plus in-context paraphrasing plus synchrony reranking improves synchrony and naturalness.
- **Pass A (understanding)** carries what human dubs keep and pipelines lose: gender and formality of addressees,
  emphasis, emotion (Brannon §5).

## 3. Literature (LLM and length-control dubbing)

| Work | Method | Result relevant to us |
|---|---|---|
| Lakew et al. 2022, *Isometric MT* | self-learning length match (±10 % chars) | Beats n-best reranking. But isometry ≠ isochrony (Brannon). |
| Tam et al. 2022, *Isochrony-aware NMT* (Interspeech) | pause markers and segment info in the input | The simplest approach worked best. Human-confirmed. |
| Chronopoulou et al. 2023 | joint translation plus phoneme durations | +55 % relative speech overlap, 3–9 % quality cost. |
| Pal et al. 2023 | target factors plus auxiliary time counters | ~0.99 speech overlap (CoVoST, read speech). |
| Wu et al. 2023, *VideoDubber* (AAAI) | duration-aware positional embeddings, pause token | Built a real film test set; better length control in 4 directions. |
| Rao et al. 2023 (IWSLT) | length-ratio tags, rerank, scale durations | Speech overlap 0.92–0.98 after rerank and scaling. |
| HW-TSC 2024 (IWSLT) | NMT, LLM post-editor for length, pause selector, rerank | Best lip-sync error in the task. |
| Won et al. 2025 (EMNLP demo) | LLM, predicted phoneme budget, iterate | +24 % speech overlap; no language-specific tuning. |
| SSPO 2025 (ACL) | preference optimisation of an LLM for per-line duration | Prompting alone is not enough; training fixes it (see Track 2). |
| APSIPA 2025, *Beyond one-shot dubbing* | N-best MT plus LLM paraphrases, synchrony rerank | Better synchrony and naturalness without retraining MT or TTS. |
| IsoChronoMeter 2024 (WMT) | reference-free isochrony via MMS-TTS duration predictor | Best MT systems still ~18 % off. MMS covers am, om, sw, ti, so. |

Metrics we will use (implemented in `scripts/research/p19/timing.py`):

- **Speech overlap:** interval intersection over union of source and dub speech.
- **IWSLT duration overlap:** 1 − |Δd| / d.
- **SLC_p:** the share of lines within ±p of the source duration.
- **Pause compliance:** the share of source pauses where the dub is silent too.
- **Speed-up needed:** naturalness.
- **Meaning:** COMET or chrF against the professional dub, and LLM-judge adequacy.

## 4. Probe (2026-10-31): Claude as the LLM on a real scene

The frame came from the English track of *The Man Who Knew Too Much* excerpt (pilot ASR). Claude wrote French
and Amharic timed lines run by run, without a reference dub. The Spanish professional dub is the yardstick
(`track1-llm-probe.json`):

| Run | Dur (s) | English (syl) | French (Claude) | syl | Amharic (Claude) | syl |
|---|---|---|---|---|---|---|
| r1 | 1.12 | Good afternoon, sir. (5) | Bonjour, monsieur. | 4 | ደህና ዋሉ፣ ጌታዬ። | 7.4 |
| r2 | 1.68 | I am Ambrose Chappell. (6) | Je suis Ambrose Chappell. | 6 | እኔ አምብሮስ ቻፕል ነኝ። | 7.2 |
| r3 | 1.12 | What can I do for you? (6) | Que puis-je pour vous ? | 5 | ምን ልርዳዎት? | 4.0 |
| r4–r5 | 0.24 + 0.08 | Well, I… (2) | Eh bien / je… | 3 | እንግዲህ / እኔ… | 3.8 |
| r6–r7 | 1.04 + 0.08 | If you gave me your name, that might be a start. (11) | Dites-moi votre nom, / on commence. | 8 | ስምዎን ይንገሩኝና / እንጀምር። | 8.6 |
| r8 | 6.96 | Oh yes, of course… I phoned you. Oh yes, yes. (22) | Ah oui, bien sûr… Je vous ai appelé. Ah oui, oui. | 27 | አዎ፣ እርግጥ ነው… ደውዬልዎት ነበር። አዎ፣ አዎ። | 29.6 |
| **total** | | **52** | | **53** | | **60.6** |

The Spanish professional dub of the same scene comes to 59 syllables.

- The LLM easily writes per-run text near a syllable target, and adapts rather than translating literally (r6:
  "If you gave me your name…" → "Dites-moi votre nom, on commence.", the same move the Spanish dubber made:
  "Dígame su nombre y podemos empezar").
- **The frame was the problem:** r7 is 0.08 s for 4 syllables (coarse token times), and r8 merges two speakers into
  7 s. So: forced alignment for word times and diarisation for turns, before any LLM work.
- **The duration estimate was the second problem.** The first Ethiopic syllable count treated every fidel as a
  syllable (81 for the Amharic). Counting sixth-order fidel as 0.4 inside a word and 0.2 at the end gives 60.6,
  close to the Spanish dub. Real Amharic timing must come from the voice that will speak it: an edge-tts or MMS
  duration measurement, or calibration from Amharic dubs.

## 5. Feasibility assessment

| Part | Feasible | Notes |
|---|---|---|
| Understanding pass (units, intent, register, emotion) | high | Standard LLM reading. Keep it hierarchical (chapters → units) for long films; cache per source. |
| Timed writing with budgets | high | Shown in the probe and in the published LLM systems. |
| Timing frame | high, with tools you have | faster-whisper word times + `transcript/refine.py` onsets, or MMS forced alignment; pyannote turns; YuNet on/off-screen. |
| Duration estimate, en/fr/es/sw | high | Calibrated syllable rates; TTS durations as the final check. |
| Duration estimate, am/om/ti | medium | No published dialogue rates. Measure edge/MMS voice durations per syllable, then calibrate on Amharic or Oromo dubs if your library has them. |
| Strict lip sync (visemes) | low priority | Humans do it ~12 % of the time; the payoff is small (Brannon). |
| Cost | moderate | A 1 h film is ~9 k source words. Frame plus understanding plus 2–3 variants plus one revision round comes to roughly 10–20× the source tokens. Batch it and cache per source. Prices: check the current model list when we choose. |

**Recommended mode later:** the understanding and writing passes as verbs the agent drives (as today) for clips and
journeys. For whole films, a batch API path.

## 6. Experiment to decide (go/no-go)

On 10 titles from your library that have a professional dub in a target language:

1. Build the frame from the original track (forced alignment and diarisation).
2. Claude writes the timed script (passes A and B, ≤ 2 revision rounds) **without seeing the dub or its subtitles**.
3. Voice three scripts with the same TTS: (a) Claude's, (b) today's pipeline from the target subtitles, (c) the
   professional dub's words (its ASR) placed at the dub's own timings.
4. Measure:
   - Speech overlap and pause compliance against the source.
   - The speed-up the TTS needed.
   - COMET/chrF against the professional dub's words.
   - Your blind A/B preference on 20 scenes.

**Go if** (a) reaches overlap ≥ 0.7 at a speed-up ≤ 1.1× and you prefer (a) to (b). (c) shows how much of the gap is
the voice rather than the script.
