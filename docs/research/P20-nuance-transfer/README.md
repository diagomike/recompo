# P20: do jokes, idioms and nuance survive the dub? (Friends)

**Research, 2026-11-02.** Builds on P19 (timed, meaning-conserving dubbing).

The question: is our understanding layer able to carry jokes, sarcasm, idioms, slang, figures of speech, proverbs
and collocations into another language? The two layers examined are storylens's fact ledger and recompo's
`dub understand` meaning map. Does it instead rephrase metaphorical speech into flat meaning?

There are two ways to make nuance survive:
- for languages the LLM knows: **naturalizing** (substitute, localize, compensate);
- for languages reached only through MT: **flattening or smoothing**.

Which works best, measured on *Friends*?

## Read in this order

| Document | What it is |
|---|---|
| **this README** | the answers |
| `RESULTS.md` | every number, method, caveats |
| `DESIGN.md` | the nuance card, the strategy policy, and the exact changes to `recomp dub` |
| `GOOGLE.md` | Google Translate (keyless, recompo's `google` engine) vs offline NLLB on the same benchmark |
| `LITERATURE.md` | humour/idiom/pun translation, sitcom dubbing, pre-editing for MT: what earlier work found |
| `data/` | scenes, gold items, both baselines, every output, blind sheets, judgements, scores |
| `scripts/research/p20/` | sampling, audit, MT runs (NLLB / MADLAD / M2M via CTranslate2), blind sheets, scoring |

## The answers

### 1. Is the current understanding layer capable enough? **No, not for nuance.**

It was built to keep *what is said*. Jokes and figures live in *how* it is said, and the layer has no place for
that.
- **recompo's map** flags 20 % of humorous items, explains the mechanism for 17 % and records a dependency for 7 %.
- It **flattens 23 % of items** in the units the dubber actually optimises:
  - "played the Gunther card too soon" → "you used Gunther too early";
  - "Bummer." → "too bad";
  - "like a dog in the street" → a droppable *colour* unit, which then breaks the "Woof, woof" callback.
- Writing Spanish from the map kept **67 %** of the effects. Translating each line alone with no analysis kept
  87 %. The map is currently a bottleneck for humour, not a help.
- **storylens's fact ledger** does better (53 % of jokes flagged, mechanism 27 %, dependency 31 %) but has no
  transfer fields either.

### 2. Does it rephrase metaphorical speech? **Yes, and so does recompo's MT rule.**

- The map paraphrases figurative wording into literal units.
- The rule for MT-crossing lines ("plain, MT-friendly wording, no idioms") flattens deliberately. In all three
  MT-only languages that **raised meaning but lowered the jokes that land** (Swahili laugh points 42 % → 32 %).
- Flattening keeps the proposition and drops the punchline.

### 3. What works best

| Target | Best option | Effect kept (vs today) |
|---|---|---|
| LLM-strong (Spanish) | A **nuance card** per item: trigger, mechanism, function, dependencies, strategy. The writer naturalizes: target idioms (*ponerle los cuernos*, *no hay mal que por bien no venga*); substitutions with the same function at the same laugh point (bassinet/basset → *moisés*/Moisés, with the next line rewritten to match); payoff last; stress cues for catchphrases | **100 %** (self-judged ceiling) vs 67 % map-driven, 87 % line-alone, 54 % raw MT |
| MT-only (Amharic, Swahili, Oromo) | **Flatten the form, keep the function.** The English handed to MT is compositional but still funny: an image that works literally ("used your secret weapon, Gunther, too early"), sarcasm made lexical ("Oh no. What a terrible, terrible tragedy."), a meaning joke replacing a sound joke ("A dog bed? For a dog?"), callback words kept identical, innuendo explicit enough to survive | Amharic **57 %** vs 23 % (plain) / 25 % (raw); Swahili **77 %** vs 39 / 45 %; Oromo **35 %** vs 16 / 13 % |

The stress set agrees: proverbs, idioms and the show's running jokes. Effect kept:

| | Spanish | Amharic | Swahili | Oromo |
|---|---|---|---|---|
| current / raw | S0 93 % | 43 % | 50 % | 21 % |
| proposed | S2 100 % | 79 % | 86 % | 57 % |

### Where the losses are, and so where the effort should go

- **Universal jokes** (situational, character, absurd: two-thirds of sitcom humour here) survive any decent
  translation. Don't over-engineer them; protect them from being compressed or dropped (laugh points are core).
- **Language-bound items** (puns, mishearings, idioms that *are* the joke, catchphrases) need the card and
  substitution. That is where line-alone translation falls to 71 % and MT to 14–29 %.
- **Chains** (setup → callback) break silently when any link is paraphrased. The card's `deps` and `keep_words`
  fix this: 100 % in Spanish, and 66 % (Amharic) / 69 % (Swahili) vs 14–28 % for the raw and plain inputs.
- **Prosody** (Chandler's "Could it BE any…") cannot be carried by text at all. It needs a voice cue, and a
  consistent series-level rendering of the catchphrase frame.
- **Back-translation checks are only as good as the back-translator.** MADLAD-400 is fine for Amharic and Swahili,
  but useless for Oromo→English, where it made correct Oromo look like nonsense. Pick the verifier per language.

## What to build (details in `DESIGN.md`)

1. **A nuance pass in `dub understand`:** one card per item, written in the same batch as the map. That is about
   one card per 2.6 sitcom lines.
2. **Laugh points are core; chains move together; payoff stays last.**
3. **Strategy by route:**
   - strong target: keep / equivalent / substitute / compensate / generalize / cue;
   - MT route: keep_literal / literalize / substitute_compositional / exaggerate / generalize.

   This replaces the blanket "no idioms".
4. **`select` and `verify` count a declared substitution as covering what it replaces**, and check `effect_kept`.
5. **A series glossary** for running jokes and catchphrases ("on a break" → *dándonos un tiempo*, "lobster"),
   reused across episodes.
6. **Laugh-track detection on the source audio** (recompo has it), to mark laugh points without an LLM and to
   check the nuance pass.
7. **Per-language back-translator choice** for `dub verify`.

## Open (needs people or your PC)

- Native-speaker A/B (Spanish, Amharic, Oromo, Swahili) on the dubbed audio, not text.
- Run the MT arm with NLLB-3.3B. (Google is done: `GOOGLE.md`. It is better for Amharic and Oromo and ties for
  Swahili, and the function-preserving pre-edit adds about +20 points on either engine.)
- A held-out test of the nuance pass's recall on new episodes, with gold written by someone else.
