# The path we travelled (P19, 2026-10-31 → 2026-11-01)

Each step below records what you asked, what we did, what came out, and what it taught. The numbers come from the
worktree folders (`wt-*/`), which hold every result file. The branch for each step is in `BRANCHES.md`.

---

## 0. Starting point: meaningful cuts across sources

**You:** research and build meaningful cuts across many sources, like a documentary that spans several people's
stories.

**Then the direction changed** to three long explorations:

1. an LLM that understands the source transcript and writes **timed** target-language lines that fit the speaker's
   speaking time and pauses;
2. a **model path** (pretrained encoders, timed placement, or training on your thousands of dual-audio films). Dubs
   differ from subtitles because they are time-aligned to the speaker;
3. **LLM-based smarter cuts**.

Mid-run you asked for **research and feasibility, not app building**.

## 1. Feasibility and literature (tracks 1–3)

**Did:**

- Literature map:
  - Brannon 2023: human dubs reach only ~0.7 speech overlap and never speed up;
  - isometric MT;
  - VideoDubber and target-factor duration models;
  - IWSLT 2023/2024 dubbing tasks;
  - SSPO;
  - duration-based translation (EMNLP 2025);
  - N-best + paraphrase reranking (APSIPA 2025);
  - prosodic alignment (Öktem 2019, Virkar 2022);
  - SimAlign/awesome-align;
  - RankCut and highlightr for cuts.
- A pilot on two real dubbed film excerpts (en→es).
- A probe of Claude writing per-run syllable budgets.
- A read-only inventory script for your MKV library.

**Found:**

- All three tracks are feasible.
- The hard part is not the LLM but the **timing frame** (word timings, pauses) and the **target-language duration
  ruler**.
- Human dubs measured 0.72/0.81 speech overlap in the pilot.

**Files:**

- `feasibility-report.md`
- `track1-llm-timed-translation.md`
- `track2-models.md` (corpus builder and training ladder)
- `track3-llm-cuts.md`

## 2. A shared benchmark from real speech timing

**Did:**

- Built the bench from the IWSLT 2023 dubbing test set: German speakers reading CoVoST2 lines, Silero VAD
  segments (pauses ≥ 0.3 s), and MFA phone alignments for English.
- Every mechanism since has been scored on it with a **real TTS voice** as the ruler.

**Files:** `scripts/research/p19/bench.py`, `bench_frames.py`, `timing.py`.

## 3. Parallel worktrees: which mechanism does timed rephrasal best?

**You:** run parallel worktrees for each path, especially the smart modelling mechanisms. Later: allow the IWSLT
Sockeye fork, push everything.

| Worktree | Question | Answer |
|---|---|---|
| `duration` | Can text predict how long a person takes? | Every model sits at 15–18 % error. Text has a floor; **the ruler must be the actual voice** |
| `placement` | Can we lay words onto a speaker's pauses with no training? | Yes: a rate-matching DP puts **94–97 % of breaks within one word** of the real pause. Zero meaning cost, so it belongs under everything |
| `llm-loop` | Can an LLM write to per-segment budgets? | Yes: **0.92 speech overlap**. The text ruler fooled it in a third of segments; one revision against the measured voice fixed most (35 → 5 % needing speed-up) |
| `trained-mt` | Does the trained duration-aware NMT (IWSLT Sockeye) do better? | No: 0.80 overlap and the worst meaning (chrF 53.5). From-scratch training on small data loses meaning |

## 4. Did we try language-agnostic or algorithmic rephrasing?

**You asked;** we ran what was possible in the sandbox.

- **`algorithmic`:** placement + rule and WordNet edits judged by a trigram LM.
  - Safe edits: +0.02 overlap.
  - Aggressive edits: 0.90 overlap, but **27 % of segments ungrammatical** in a blind check.
  - chrF did not see the damage.
- **Lesson:** rewording needs a neural judge at least. The BERT-pluggable variant (XLM-R masked LM + LaBSE) needs
  HuggingFace, so it is listed for your PC.

## 5. Multi-round LLM refinement: the best timing

**You:** multi-round LLM refinement should be among the best.

- **`llm-multiround`:** each round measures every segment with the voice; the LLM rewrites only out-of-band
  segments, from measured alternatives, restoring plain wording where possible.
- **Result:** **98 % in band (0.8–1.05×), 0 % over 1.1×, 98 % fluent, chrF 64.1.** Converges in about 3 rounds.

## 6. MCTR: meaning-conserving top-down rephrasing (the implementable form)

**You:** an optional meaning-understanding, meaning-conserving top-down rephrasal in rounds, made optimal and
implementable.

**`mctr`** works like this:

1. Meaning units tiered core / support / colour (weights 3 / 2 / 1).
2. Units allocated to speech segments.
3. Unit-labelled variants per segment.
4. **Exact voice-measured selection** (maximum meaning, the band, core units kept, optional costs on additions).
5. Targeted revisions.

**Result:**

- Same fit as multi-round in **2 rounds instead of 6**.
- Fewer additions: 0.16 per line, 0.07 in conserve mode.
- 98.6 % of meaning units kept, in a blind check.

This is the algorithm the app now runs (`recomp/lang/llmdub.py`).

## 7. Two-sided: languages where only MT exists

**You:** make it work for Amharic and Oromo, where we only have MT. Rephrase options on the source side, translate
each, time the target, and let the source anticipate the target. Mid-turn: prove it on German and Spanish.

**`twosided`:** the LLM writes options in the source only; MT translates each; the target voice times them; exact
selection; lazy back-translation verification.

| Arm | Within ±20 % | Other effects |
|---|---|---|
| de→en, real MT | 57 → **87 %** | meaning kept 73 → **93 %**, MT errors per line 1.13 → 0.40 |
| en→es | 59 → 93 % | speed-up need 55 → **0 %** |

**Lessons:**

- Verification is essential: without it, the optimiser happily picks fitting garbage.
- The source can be written to be MT-robust: no idioms or brackets, explicit subjects.

## 8. Pivot: weak language → weak language through English

**You:** the final part, end to end from a little-known language to another through English. Really understand
the nuance of the source and transfer its timing.

**`pivot`:**

- The LLM never reads either end language.
- It triangulates **several independent English MT views**: whole line, each speech segment, terse and full, word
  glosses. It adds language-free prosody cues.
- It pins meaning units to the source segments, which is how the timing transfers.
- It rates its own confidence.

| Pipeline (24 unseen lines) | Adequacy (0–3) | Within ±20 % |
|---|---|---|
| Naive cascade | 1.17 (71 % badly wrong) | 52 % |
| Understanding | 2.75 | — |
| Understanding + two-sided timing | 2.71 | **88 %** |

Confidence is calibrated: high 3.0, low 1.5, so low-confidence lines go to a human.

## 9. Routes: choose the working language(s), not "two sides"

**You:** run in whatever language the LLM understands best, one or two of them, and use one when tokens matter.

**`routes`:** a route per pair, with an economy or quality budget.

| Route | When | LLM writes in |
|---|---|---|
| direct | both ends strong | the target |
| target-direct | target strong | the target |
| source-side | source strong | the source |
| pivot | both ends weak | the middle language |

Results on 24 fresh lines:

- **Target-direct beats the pivot route:** fit 91 vs 86 %, natural lines 88 vs 50 %, same meaning.
- **Pooling two languages:** 95 % fit, but it needs a small prior so the fluency-blind selector prefers directly
  written lines.
- **Understanding is about two-thirds of the tokens.**

## 10. Two middle languages: consolidate meaning before conserving it

**You:** don't trust English alone as the middleman; add Spanish as a middle (not target) language and test it.

**`bipivot`:**

- **Middle languages:** a second offline MT system (Mozilla Firefox Translations via bergamot, which you allowed)
  gave Spanish views next to the Sockeye English views.
- **Target:** French, with real MT and back-translation checks.

**Understanding**, blind against the references (adequacy 0–3):

| Read through | Adequacy | Major loss |
|---|---|---|
| English only | 2.54 | 17 % |
| **English + Spanish** | **2.88** | **4 %** |

Spanish fixed what English alone passed on silently: a reversed polarity ("committed against apartheid" → "the
commitment against apartheid was dropped"), a wrong action ("close" → "open the shutters") and a lost key word
("of blasphemy").

**French dub:**

- **2.83** with 0 % major loss, against 2.42 for the best plain cascade.
- 79–81 % within ±20 %, against 38 %.

**Lessons:**

- The gain comes from an **independent second MT path**; the language it is read in matters less.
- Writing in a second language helps only where its MT into the target is direct.

## 11. Into the app (2026-11-01)

**You:** merge the LLM dubber into the app with all its options by language situation (source English, target
English, English middle, multi-language middle), part of the settings whenever media is loaded for detailed
processing; merge to main; document everything here.

**Did:** see `APP.md` for:

- the layered dub settings (studio → project → source → journey);
- the `dub` verbs;
- how the research maps onto the code.

---

## What the whole path says

1. **Write length, don't squeeze it**, and measure with the real voice (§3, §5).
2. **Plan top-down from meaning units and choose by exact optimisation** (§6): the fit with the least meaning lost.
3. **Where the LLM is weak in a language, let MT cross it and verify by back-translation** (§7).
4. **Understand weak sources through several independent MT views, ideally in two middle languages from two
   systems** (§8, §10). Pin the units to the speaker's segments to carry the timing.
5. **Write in the target when the LLM is strong in it; otherwise in the best middle language** (§9). Pool a second
   writing language only with direct MT into the target.
6. **Confidence flags work:** low-confidence lines are the ones a human should check.
