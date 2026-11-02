# P20 literature: humour, idioms and figurative language across languages, in dubbing

What earlier work says about each part of the question, and what P20 takes from it.

## 1. Jokes and puns: LLMs are better than MT, but far from solved

| Work | Finding | Used in P20 |
|---|---|---|
| CLEF JOKER 2023–2025, pun translation EN→FR/ES (Ermakova et al.) | Manual evaluation: at best **6 % (FR) / 18 % (ES)** of machine translations kept both form and sense of a pun (2023). Only 10–23 % of outputs contained a punning word from the references, despite BLEU ~42 / BERTScore 0.82. In 2025 the best CoT-prompted LLM (GPT-4o) reached ~30 % exact match on onomastic wordplay | BLEU/chrF/BERTScore reward literal translations that kill the joke. P20 judges the **function**, not overlap |
| Delabastita (1996) typology: pun→pun, pun→non-pun, pun→related device, zero, compensation, editorial | The strategy vocabulary used in JOKER and in AVT | P20's `strategy` field (keep / equivalent / substitute / compensate / generalize) |
| Pituxcoosuvarn & Murakami 2025, *Jokes or Gibberish?* (850 jokes EN→TH) | Retention: NMT 50 %, plain GPT 41 %, **GPT with an explanation first 63 %** | Explaining the mechanism before translating is the single biggest lever → the nuance card's `mechanism` + `function` |
| Benavides et al. 2025, Humour Decomposition Mechanism (CoT: mine the joke's knowledge → translate it → rebuild the joke) | +7.75 % humour, +2.81 % fluency (EN→ZH, also ES/DE) | Same three-step shape as P20's card → strategy → write |
| Rudenko & Semenova 2024 (EN→RU pun jokes, 150 raters) | GPT-4o translations perceived as calqued and literal; humans translate holistically | Literalism is the failure to measure |
| *Pun Unintended* (EMNLP 2025) | LLM pun "understanding" is often shallow and breaks under small perturbations | Detection is not enough. P20 also measures recall on external labels (MUStARD) |

## 2. Idioms: the model often knows the meaning and still translates literally

| Work | Finding |
|---|---|
| Dankers et al. 2022; Baziotis et al. 2023 (LitTER metric) | NMT treats idioms compositionally. Literal-translation errors are measurable automatically with blocklists of the literal words |
| Tide (*That was the last straw*, 2023) | MT systems translate idioms literally **even when the context disambiguates**; LLMs are far more context-aware, but less so for lower-resource targets |
| IdiomKB (Li et al., AAAI 2024) | Retrieving the idiom's figurative meaning and translating that meaning ("KB-CoT") fixes most errors of smaller models |
| Donthi et al. 2025 (LoResLM) | Meaning-only translation loses the idiomatic flavour. Aligning to a **target idiom** (embedding retrieval + LLM choice) preserves style better (ZH/UR/HI) |
| *Idioms Understood, Yet Translated Literally* (IdiomDIT, 2026) | "Literal Translation Bias": errors persist **after** correct detection and interpretation. Error-targeted ("anti-literal") prompts beat generic meaning-first prompts but do not eliminate it |
| *It's Not a Walk in the Park* (ACL 2025) | Speech translation systems fall back to literal idiom translations more than text MT or LLMs |

P20 takes from this: (a) detection + meaning must be stored, not re-derived per line; (b) the writer needs an
explicit *anti-literal* instruction tied to the specific span; (c) for MT-only targets, do not hand an idiom to MT
at all.

## 3. Sitcom dubbing practice: the laugh track is a hard constraint

| Work | Finding |
|---|---|
| Zabalbeascoa 1996, *Translating Jokes for Dubbed Television Situation Comedies* | Joke typology for TV; priorities set by a "stylebook". With canned laughter, the translator must put a joke **where the laugh is**; compensation elsewhere leaves laughter over nothing |
| Zabalbeascoa 2001; Chiaro 2005–2010 (verbally expressed humour) | Compensation and substitution are the normal tools for VEH. Omitting a joke under a laugh track is the worst outcome |
| Baños 2013, compensation in *Friends* (ES dub, S8) | Spanish dubbers **add** colloquial markers (diminutives, vocatives like *tío*, set phrases like *¡qué va!*). 40 % of these are not motivated by the original: "generalized compensation" for naturalness |
| Friends IT dub thesis (S1, GTVH analysis); Friends/BBT ES studies | Dubbers manipulate heavily to keep humour potential; cultural references are translated inconsistently |
| Żmudzin-Zielińska (House M.D., dubbing ES vs voice-over PL) | Humour loss: 16 % of humorous scenes in the Spanish dub, 25 % in the Polish voice-over. Losses concentrate in language-dependent and culture-bound jokes |

P20 takes from this: `laugh` items are core and never droppable; substitution must land at the same laugh point;
naturalizing additions are legitimate for strong targets and are how professional dubs sound native.

## 4. Laughter and sarcasm as data

| Work | Finding |
|---|---|
| Alnajjar et al. 2022 (*Friends*, all 10 seasons) | The live laugh track labels humour automatically: 7,422 laughter segments, and laughter length ≈ how funny. Text-only humour detection works far worse than audio+text |
| MUStARD (Castro et al. 2019) | Sarcasm labels with context for *Friends*/BBT; multimodal cues reduce the error |
| SMILE (Hyun et al. 2024) | Laughter **reasons** for sitcom clips (from MUStARD) |

For recompo, which has the audio, the laugh track can be read off the soundtrack (P20 recommends it). It marks
laugh points without an LLM and checks the nuance pass's `laugh` flags.

## 5. Pre-editing for MT-only targets

| Work | Finding |
|---|---|
| Mehta et al. 2020 (Simplify-then-Translate) | Automatic simplification of idiomatic, non-compositional source text improves black-box MT into low-resource languages |
| Štajner & Popović 2019 | Simplification before EN→SR MT improves fluency; adequacy depends on the system |
| Ki & Carpuat 2025 (NAACL), 21 rewriting methods | Simplification is the most reliable MT-agnostic rewrite. Quality-estimation-based selection helps further. Meaning is largely preserved |
| Koretaka et al. 2025 (WMT) | Targeted source editing guided by the MT system's actual errors (span QE) beats blind rewriting |

All of this optimizes **adequacy**. None of it asks whether the *joke* survives. P20 measures that and finds plain
simplification (recompo's current "no idioms" rule) flattens the jokes too.

## 6. Timing (from P19, unchanged)

Isochrony work (Federico et al. 2020; Lakew et al. 2021–22; Chronopoulou et al. 2023; Brannon et al. 2023) and the
P19 results stay valid. P20 adds two comic-timing constraints that isochrony models ignore:
- the payoff word stays **last**, before the laugh;
- a pause before the payoff ("never leave your hand... on the desk") is kept as a frame boundary.
