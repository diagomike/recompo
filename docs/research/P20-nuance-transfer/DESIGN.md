# P20 design: a nuance layer and a transfer policy for dubbing

This turns the P20 findings (`README.md`, `RESULTS.md`) into something buildable. It adds one layer to the
understanding and changes four places in the dubber. Everything stays inside the existing "the agent writes, the
machine measures" loop (D-26): Claude writes the nuance cards in the same `dub understand` batches.

## 1. Why a separate layer (and not "better units")

The P19 meaning map is a *propositional* layer: units say **what** is asserted (core/support/colour). A joke, an
idiom or a sarcastic line is about **how** it is said and **why it lands**. That information has four parts, and
the map has a slot for none of them:

| Needed for transfer | Example (Friends) | Where the map puts it today |
|---|---|---|
| the **trigger**: the exact words the effect lives in | "lose her" / "loser" | paraphrased away: unit "I won't lose her?" |
| the **mechanism**: why it works | mishearing of a near-homophone | nowhere (notes 17 % of the time) |
| the **dependencies**: setup and callback lines | L19 "like a dog in the street" → L24 "Woof, woof" | nowhere; L19's image is a *colour* unit, dropped first |
| the **function**: what the audience must get | "Rachel's comfort reveals she thinks he's a loser" | nowhere |

A better unit text cannot fix this, because the optimiser and the verifier treat units as content to keep or drop.
The correct humour strategies, substitution and compensation, deliberately change content: they are scored as
errors ("added content", "unit not covered"). So the nuance layer sits **beside** the units and changes what the
optimiser and the verifier count.

## 2. The nuance card (per item, attached to a line)

```json
{
  "id": "S3E4c6-L23#n1",
  "line": "S3E4c6-L23",
  "trigger": "you're not a total loser",
  "kind": "pun:mishearing",            // joke:*, pun:*, wordplay:*, idiom, idiom:literalized, slang, euphemism,
                                         // simile, metaphor, hyperbole, irony, sarcasm, catchphrase, cultural-ref,
                                         // collocation, register, callback, absurd, taboo
  "bound": "L",                         // L language-form | C culture | P prosody | U universal
  "laugh": true,                        // a laugh point (in a sitcom: the laugh track follows)
  "mechanism": "'lose her' heard as 'loser'",
  "function": "Rachel's reassurance accidentally reveals she sees him as a loser",
  "deps": ["S3E4c6-L22", "S3E4c6-L24"], // setup / correction lines that must change together
  "keep_words": ["lose her", "loser"],  // words that must stay identical across the chain (callbacks)
  "payoff_last": true,                  // the trigger must stay at the end of its line (timing)
  "prosody": "",                        // e.g. "stress BE; Chandler's sarcastic cadence" for P items
  "strategy": {
    "strong": "substitute",             // keep | equivalent | substitute | compensate | generalize | cue
    "mt":     "substitute_compositional" // keep_literal | literalize | substitute_compositional | exaggerate
                                         //   | generalize | keep_loan | accept_loss
  },
  "confidence": "high"
}
```

Cost: in the benchmark 81 of 214 sitcom lines carry at least one item (83 items). That is about one card per 2.6
lines, written in the same batch as the map.

## 3. Strategy policy (what to do with each item)

### Strong target (the LLM writes the target: `direct`, `target` routes)

| Item | Strategy | Example |
|---|---|---|
| U (universal: situational, character, absurd, logic) | **keep**: translate the meaning, keep the payoff last and the pause before it | "grandmother to the vet" → "llevar a mi abuela al veterinario" |
| idiom / slang / collocation, not the joke | **equivalent**: a target idiom of the same register and function | "cheating on Rachel in her house of worship" → "ponerle los cuernos a Rachel en su templo sagrado" |
| L: pun, mishearing, polysemy that *is* the joke | **substitute**: a target-language device with the same function at the same laugh point; rewrite the chain | bassinet/basset → *moisés* (crib) / *Moisés* (the prophet), then "the baby would keep falling off the dog" → "…sleeping on the prophet" |
| L that the target happens to share | **keep** (check first) | "lose her / loser" → "perderla / perdedor"; "prep" → "preparar (al paciente)"; "services" → "servicios" |
| C: cultural reference | **generalize** if the reference is the joke's vehicle only; **keep** if it is famous in the target | "Century 21 jackets" → "vendedor de pisos con chaqueta"; *Planet of the Apes* → "monos gobernando el planeta" |
| P: catchphrase cadence | **cue**: keep the sentence frame consistent across the series, and send a stress cue to the voice | "Could that report BE any later?" + `prosody: stress BE` |
| sarcasm / irony | **keep + cue**: keep the literal words; the tone carries it. If the voice cannot carry tone, use exaggeration | "Bummer." → "Vaya... qué pena." + cue "barely hidden glee" |
| loss unavoidable | **compensate** in the same scene, *before* the next laugh point, never moving a laugh away from the laugh track | |

### MT-only target (Claude writes English that MT carries into am/om/sw)

MT renders non-compositional language literally (Baziotis et al. 2023; Tide, 2023), and it drops tone. So the
English handed to MT must be compositional and the effect must be visible in the words.

| Item | Strategy | Example (input to NLLB) |
|---|---|---|
| U | **keep_literal**: unchanged wording, payoff last, callback words identical | "She will kill you like a dog in the street." … "Woof, woof." |
| idiom / slang (not the joke) | **literalize**: the plain meaning (today's rule, correct here) | "show your faces" → "come to this coffee house again" |
| idiom that *is* the joke | **substitute_compositional**: an image that is funny when read literally | "played the Gunther card too soon" → "used your secret weapon, Gunther, too early" |
| pun / mishearing | **substitute_compositional**: replace the sound joke with a meaning joke that has the same function | basset/bassinet → "a little baby bed" / "A dog bed? For a dog?"; lose her/loser → "you are not completely pathetic" … "I asked if I will lose HER" |
| sarcasm | **exaggerate**: make the insincerity lexical | "Bummer." → "Oh no. What a terrible, terrible tragedy." |
| innuendo / euphemism | explicit enough to survive, delayed realization kept | "services" → "I do not sell sex." / "Sex? …Oh. Sex." |
| C | **generalize** | "Judy Jetson thermos" → "my cartoon thermos" |
| P | text cannot carry it; keep the frame, add `prosody` for the voice | |

### Shared rules

1. **Laugh points are core.** Any unit that carries a `laugh` item's trigger or its dependency is promoted to
   core, never colour.
2. **Chains move together.** A substitution rewrites every line in `deps` in the same pass, and `keep_words` stay
   identical across the chain (thermos, dog, terminal, "good things").
3. **Payoff last.** If the target word order would move the trigger forward, restructure the sentence.
4. **Do not explain jokes.** No narration and no brackets. The only out-of-band channel is the voice cue.

## 4. Changes to recompo (`recomp/lang/llmdub.py`, `recomp/verbs/dub.py`, the `recomp-dub` skill)

| Where | Change |
|---|---|
| `dub understand` template | ask for `nuance: [card]` per line, with the scene's previous lines as context (sitcom chains span 2–10 lines). Store as `dub_work` kind `nuance` |
| map → units | units that carry a `laugh` trigger or a dependency → tier `core`; also lock `keep_words` |
| `dub write` template | show the cards next to each frame. Add `strategy: substitute|compensate` options, which may carry `replaces: [unit ids]` and `chain: [line keys]` |
| `select` (exact DP) | a declared substitution covers the units it replaces, so it is not an "addition" in conserve mode. A chain is chosen as one decision (all its lines from the same strategy) |
| `dub verify` | add per card: `effect_kept: yes/partly/no` and `literalism: [spans]`. Back-translations are read for the *function* sentence, not only the units |
| MT routes | replace the blanket "no idioms" with the MT column above |
| voice | pass `prosody` cues to voices that take them (edge SSML emphasis). MMS and OmniVoice ignore them (documented) |
| storylens (linger) | the P1 fact `kind: joke` gets the same card fields (`trigger, mechanism, deps, bound, function`). Lenses such as "all of Chandler's sarcasm" then come for free |

## 5. Additions the experiments asked for

| Finding (RESULTS.md) | Addition |
|---|---|
| Running jokes and catchphrases recur across episodes ("on a break", "lobster", "Pivot!", "Could it BE…") and must be rendered the same way every time | a **series glossary** (`dub_work` kind `glossary`, per source series and language): source phrase → chosen rendering + prosody cue. The nuance pass looks it up first; the first rendering becomes canonical |
| Live-audience laugh tracks mark laugh points (Alnajjar et al. 2022, 7,422 in *Friends*) | **laugh detection on the source audio** (a small CNN laugh detector or VAD energy pattern after a line). It sets `laugh` without an LLM, flags lines the nuance pass missed, and weights the dub check |
| Text-only sarcasm detection: F1 0.73 (MUStARD) | the nuance pass also reads **prosody cues** of the source line (pitch range, lengthening), when the audio is there, as a hint for `sarcasm`/`irony` |
| MADLAD makes correct Oromo look like nonsense; NLLB-back is optimistic | `dub verify` picks the **back-translator per language** from a small table (MADLAD for am/sw; NLLB or Google for om), and shows two views when it can |
| Universal jokes survive plain translation (96 % line-alone) | **budget the cards**: for `bound: U` items the card only needs `laugh`, `payoff_last` and `deps`. Full mechanism/strategy only for L/C/P items and chains (46 of 83 items here, 55 %) |
| The map-driven writer lost 20 points vs line-alone in Spanish | the writer always sees the **source line** (strong routes) or the **function-preserving English** (MT routes) next to the units; units bound the meaning, they are not the text to translate |
| Function-preserving English is ~12 % longer on average | the fit loop treats `laugh` items as core (never dropped) and shortens **around** them; compact options must keep `keep_words` |

## 6. Where Claude's effort goes (cost)

| Step | When | Size |
|---|---|---|
| Nuance cards | once per source line, in the `understand` batch | ~0.4 items per sitcom line; short for U items |
| Glossary | once per running joke per language | tiny |
| Substitution writing | only for L/C/P items and chains | ≤ 55 % of items (fewer need a real substitution) |
| Effect check in `verify` | only for lines with cards that crossed MT | one line per card |
