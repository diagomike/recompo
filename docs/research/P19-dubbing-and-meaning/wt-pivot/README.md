# Worktree `pivot`: end to end between two MT-only languages, through English

**Your request (2026-10-31):** make it work end to end from a little-resourced language to another, with English
as the medium, and think about what changes. Above all: really understand the nuance of the source and transfer
its timing accurately to the target.

## 1. What changes when both ends are MT-only

| New problem | Why it matters | What the pipeline does |
|---|---|---|
| **The LLM cannot read the source** | One MT pass into English loses who did what, negation, idiom and tone, and the error then compounds through a second MT | **Multi-view understanding**: the LLM reads the source only through several *independent* English views and triangulates. The views are the whole line; each speech segment alone; terse and full renderings (length-controlled MT); and glosses of the key words. It records a confidence level and the ambiguities it resolved or could not resolve |
| **Timing must be transferred without reading the source** | Units must land where the source speaker says them | **Per-segment MT views align meaning to time**: whatever the MT says for segment 2 is what the speaker said in segment 2. The pivot meaning units are pinned to the source segments from those views. No source-language knowledge is needed |
| **Nuance beyond words** | Questions, emphasis and pauses carry meaning | **Language-free prosody cues** from the audio: final pitch rise (question?), loud segments (emphasis), the pauses themselves (the frame) |
| **Two MT hops** | Errors multiply; a fluent second MT hides the first MT's mistakes | The pivot meaning map is the single source of truth. Target outputs are verified against it (back-translation into English on the PC), not against the first MT |
| **Some lines cannot be recovered** | Garbled views (rare words, broken ASR) | The confidence flag sends those lines to a human, instead of guessing silently |

```
source audio ─VAD frames─ASR→ text per speech segment
   ├─MT views → English: whole · per segment · short · long · glosses         (pivot.py views / sheet)
   ├─prosody cues: final rise, emphasis                                       (pivot.py prosody)
   └─LLM (English only) → pivot meaning map: best English line, units pinned to source segments,
                          confidence, resolved/unresolved ambiguities          (pivot_maps.json)
 → LLM English options per source segment (orig / compact / full / steered)    (opts_en_*.json)
 → MT English→target → target voice timed on the SOURCE speaker's segments
 → exact selection (mctr.select) + steering by the measured expansion, both directions
 → target-side check: back-translate → compare with the pivot units           (twosided.py)
```

## 2. The run (proof of concept)

- **Source "low-resource" language:** German, with real recordings of German speakers, real ASR (Parakeet v3) and
  the real offline MT into English (IWSLT Sockeye). 24 lines Claude had **never seen**; the German was never
  printed. The LLM saw only the English views.
- **Target:** Spanish, via Claude as a **literal, timing-blind MT** (shuffled chunks, no durations; Google on the
  PC), timed with the MMS Spanish voice on the **German speakers'** segments.
- **Meaning:** a blind 0–3 adequacy judgement of the three pipelines' Spanish (shuffled per line) against the
  **hidden** CoVoST English references, which Claude first saw at scoring time.

| Pipeline | Adequacy (0–3) | Full meaning | Major loss or wrong | Within ±20 % | > 1.1× speed-up | In band 0.8–1.05 | Speech overlap |
|---|---|---|---|---|---|---|---|
| **P0 naive cascade** (ASR → MT → MT → placement) | 1.17 | 8 % | **71 %** | 52 % | 8 % | 46 % | 0.81 |
| P1 understood via MT views, untimed | **2.75** | **79 %** | 4 % | 54 % | 12 % | 40 % | 0.80 |
| **P2 full pipeline** (understand + pin to segments + two-sided timing) | 2.71 | 75 % | 4 % | **88 %** | **5 %** | **78 %** | **0.88** |
| P2 conserve mode | — | — | — | 86 % | 5 % | 78 % | 0.87 |

Adequacy by the understanding step's own confidence (P2):

| Confidence | Adequacy |
|---|---|
| high | **3.0** |
| medium | 2.6 |
| low | **1.5** |

**Findings**

1. **The naive cascade is not usable** between MT-only languages: 71 % of lines lose meaning badly. For example
   "sales" for *sails*; "john me young jordan rudesmike potnoy"; "no man and no woman is your tears and the one
   who is saving your tears".
2. **Triangulated understanding is the big win** (adequacy 1.17 → 2.75). The views disagree in useful ways:
   - per-segment vs whole: *"the main line will be constructed for the speed"* → *ships built for speed*;
   - terse vs full: *"follow the boy's reputation"* vs *"follow their destiny"*;
   - glosses: *"destiny"*.

   World knowledge resolves names and sayings (Dream Theater members; "better to stay silent and be thought a
   fool…").
3. **Timing transfer is nearly free in meaning** (2.75 → 2.71) and fixes the fit: 54 → 88 % within ±20 %. Steering
   ran **both ways**: these source speakers were slow, so the target mostly *under*-filled, and the steered
   options were fuller but faithful (restored support units, explicit phrasing, no new facts).
4. **Confidence is calibrated.** High-confidence lines were perfect (3.0); low-confidence lines were the real
   failures (1.5: "after bumping into an attendant named William…", "by the light of their own destruction…").
   The pipeline knows which lines need a human.
5. **The prosody cue was weak.** The final-rise detector fired on many declarative read sentences. Use it as weak
   evidence only (or calibrate per speaker). Emphasis flags were rarer and plausible ("It's true").

**Caveats:**

- 24 read sentences.
- One source/target pair (de→es) standing in for am→om.
- The target MT was a literal stand-in.
- Claude was both the understander/writer and the blind judge.
- Low-confidence lines were not sent to a human here.

## 3. Transfer to Amharic → English → Oromo (on your PC)

| Step | Tool on your PC |
|---|---|
| Source ASR with word times | Ethio-ASR CTC (`badrex/Ethio-ASR-amharic`, already in `dubcheck.py`) or MMS; VAD frames as in `bench_frames.py` |
| MT views am→en | `mt_google.py --src am --tgt en` for whole and per segment. Google has no length control, so get terse/full views from **context variants** instead (the line alone vs with the previous line, or NLLB-200 `amh_Ethi→eng_Latn` with short and long length penalties on the worker python). Glosses: content words one by one |
| Prosody | `pivot.py prosody` (language-free) |
| Understanding | the LLM writes `pivot_maps.json` from `pivot.py sheet` (English only); low confidence → ask a human speaker |
| Target MT en→om | `mt_google.py --src en --tgt om` (one chunk per segment), or NLLB `gaz_Latn` |
| Target voice | MMS-TTS `facebook/mms-tts-orm` (worker env); Amharic targets: edge-tts `am-ET-*` |
| Selection and steering | `twosided.py select --src-lang en --maps pivot_maps.json --frames <source frames> …` |
| Verification | back-translate om→en (`mt_google.py --src om --tgt en`); the LLM marks covered units/errors → `--verified` |

Files:

- `ids.txt`, `asr.json`, `prosody.json`, `mt_views.jsonl` (all English views), `pivot_maps.json`;
- `opts_en_r1/r2.json`, `mt_en_es.jsonl`, `chosen_r*.json`, `steer_*.txt`;
- `e2e_timing.json`, `e2e_meaning.json`.
- Code: `pivot.py`, plus `twosided.py`, `mctr.py` (units with explicit segments), `mt_sockeye.py` (length-scaled
  views).
