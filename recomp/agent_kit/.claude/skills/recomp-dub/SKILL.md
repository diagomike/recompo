---
name: recomp-dub
description: The LLM dubber — timed, meaning-conserving dub lines in any language pair (Amharic, Oromo, any MT-only language included). Routes by language strength (direct, source/src-en, target/tgt-en, middle/mid-en, multi-language middle), economy or quality budget, MT views, voice-measured exact selection, back-translation checks.
---

# The LLM dubber

You write; the machine measures. Every line is split into **speech frames** at the speaker's pauses. The target
voice speaks every option you write, and an exact optimiser picks the combination that keeps the most meaning
inside each frame's time. You only ever read and write languages you are strong in; MT crosses the rest.

## 1. Settings and route
`recomp dub settings J1 --to om` shows, for each source in the journey, the effective settings (with the layer each
comes from: studio → project → source → journey) and the **route**:

| Route | When | You read | You write |
|---|---|---|---|
| `direct` | both languages strong | the source | the target |
| `source` (src-en) | source strong, target MT-only | the source | the source (MT carries it; you check back-translations) |
| `target` (tgt-en) | source MT-only, target strong | MT views of the source in the middle language | the target |
| `middle` (mid-en) | both MT-only | MT views in one middle language (en) | the middle language |
| `multi` | both MT-only, meaning first | MT views in two middle languages from two MT systems (e.g. en via google, es via nllb) | the first middle |

`--budget quality` adds a second writing language and pools the options. Change settings with
`recomp dub settings --at project|S1|J1|studio --route multi --middle en,es --views-mt google,nllb`. Ask the user
which route they want if it matters (meaning-critical films: `multi`; token budget: `economy`).

**Offline by default:** NLLB and M2M-100 (two independent systems) and Mozilla bergamot for MT, MMS voices.
`recomp dub models` says what is missing; `--download` fetches it once (ask the user first: it goes online).
`--online true` allows Google and edge voices; only use it if the user asks.
Voices: `recomp lang voices om` lists the offline ones (MMS-TTS per language, `clone` for the original speakers'
voices at export) and whether they are downloaded; audition with `recomp lang say "…" --lang om --voice mms:…`;
set one with `recomp dub settings --at project --voice mms:facebook/mms-tts-orm`.

**Several movies at once:** `recomp dub next --limit 40` gives the next batch across every journey with dub languages
(each with its stage: understand, write, verify). Write all the answers into one file and send
`recomp dub submit --input batch.json` (`{"batch": {"J1:om": {"maps"|"options"|"checks": {…}}}}`). Fits run as jobs
meanwhile. Repeat until `dub next` returns no batch. This is the normal way to dub whole films.

## 2. Understand (meaning map)
`recomp dub understand J1 --to om --template` gives each line's frames and either the source text or the MT views.
**Read every view**: they come from independent systems and disagree exactly where the meaning is at risk
(polarity, who did what, idioms, names). Write `{maps: {key: {best, confidence, notes, units: [{id, text, tier, frame}]}}}`:
- `tier`: `core` (the line is wrong without it), `support` (detail), `colour` (tone).
- `frame`: the frame where the speaker says it. Per-frame views tell you this.
- `confidence`: `low` when the views cannot be reconciled; those lines go to the user.
- `nuance` (setting `nuance: mark|on`, default on): also mark what a literal rendering would lose: jokes, puns and
  mishearings, sarcasm, idioms, slang, proverbs, figures of speech, innuendo, catchphrases, cultural references,
  callbacks. `{id, trigger (exact words), kind, bound: L|C|P|U, laugh, function (what the audience must get), units
  (ids it lives in), deps (setup/callback line keys), keep_words, canon (a running joke's name)}`. Units stay *what*
  is said; nuance marks *how it lands*. Mark only what matters: universal jokes need little more than `laugh` and
  `deps`.

`recomp dub understand J1 --to om --input maps.json`

A whole film: work in batches. `--template --limit 40` gives the next 40 lines still to map (or to write in stage 3);
repeat until done. You are the only LLM here: there is no API to hand this to.

## 3. Write options
`recomp dub write J1 --to om --template`: per frame its seconds, a syllable target for the target voice, its units and
the language(s) to write in. Write 2–4 options per frame: orig, compact (drop colour, then support), full (support
units explicit). Use plain, MT-friendly wording when the target is reached by MT (explicit subjects, no brackets).
Add no new facts. `--input options.json` with `{options: {key: {"1": [{text, lang, units, strategy, nuance}]}}}`.

Lines with `nuance` items carry a `guide` per writing language, the setup/callback lines (`deps_text`) and earlier
renderings of the same running joke (`glossary`, keep them):
- **naturalize** (you write the target directly, a language you know well): target idioms of the same register, a
  substitute joke with the same function at the same laugh point (rewrite the whole chain the same way), payoff last.
- **function-preserving** (MT carries what you write): an idiom that is not the joke → its plain meaning; an idiom or
  pun that *is* the joke → an image or meaning-joke that works word for word; sarcasm → exaggerate it so it is in the
  words; callback words identical across lines; innuendo explicit enough to survive.

Write such options as extra options (strategy `naturalize|substitute|compensate|exaggerate`) next to the plain ones,
with `nuance: [ids they keep]`, carrying the same units. The machine still chooses by meaning and the voice; a kept
item only wins when meaning and fit are equal, and a laugh point is never dropped as colour.

## 4. Fit, check, rewrite
- `recomp dub fit J1 --to om` (a job): MT, voice, exact choice; writes the lines as translations (method `llmdub`).
- `recomp dub verify J1 --to om --template`: back-translations of chosen lines that crossed MT. Mark
  `{checks: {id: {covered, errors, added}}}`, where errors are wrong words, reversed polarity or a wrong subject.
  Options that keep nuance items also get `effect: {item id: kept|partly|lost}`; `literal` lists items whose own
  words came back (a word-for-word rendering). Then fit again; it routes around errors, and a laugh point no chosen
  option keeps becomes a `keep_effect` rewrite in the next `dub write --template`.
  Each back-translation is labelled with its engine. Online, it comes from a different engine than the one that
  translated (google checks NLLB, NLLB checks google), so MT never grades its own output; offline it can be the same
  engine, which is optimistic: read it more strictly.
- `recomp dub write J1 --to om --template` again lists only frames still out of band, with syllable targets; write
  `steer` options; fit. Two rounds are usually enough.
- `recomp dub status J1 --to om` says what is next.

## 5. Finish
Translate the title and overlays with `lang translate` (the dubber does spoken lines), then
`recomp export run J1 --profiles shorts --langs om`. The export voices each frame at the speaker's own pause. Tell
the user about `low_confidence` lines and any `missing_core` ones before calling it done.
