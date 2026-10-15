# Recipe spec — `recomposer/1`

A recipe is a journey as portable JSON: which sources, which moments, in what order, with what text
and music, credited how. It never contains media or local file paths. Renders are disposable; the
recipe is the work.

Produced by `recomp recipe show J1`, mirrored to `recipes/J1-<slug>.recipe.json` on every change,
exported with `recomp recipe export J1 --format json|edl|otio`, published with `recomp hub publish J1`,
and rebuilt with `recomp recipe import <file>` or `recomp hub pull <id>`.

```json
{
  "recipe": "recomposer/1",
  "id": "01K…", "ref": "J2", "title": "Justice outside the law",
  "intent": "…", "description": "", "language": "en",
  "sources": {
    "S1": {"kind": "file", "title": "The Dark Knight", "year": 2026, "creator": "", "duration": 5341.66,
           "language": "en", "fingerprint": "pf1:<size>:<sha256 of first+last 4 MB>",
           "rights": {"owner": "", "notice": "The Dark Knight (2026)", "licence": "…"}},
    "S2": {"kind": "link", "platform": "youtube", "id": "T_7Fm1VujEs", "url": "https://www.youtube.com/watch?v=…",
           "title": "Are Plants Conscious? - Michael Pollan", "creator": "Alex O'Connor", "rights": {"owner": "Alex O'Connor"}}
  },
  "slots": [
    {"source": "S1", "in": 389.4, "out": 405.0, "cut": "C1", "title": "I do this for you",
     "quote": "Everything that I do, I do for you…", "why": "…", "people": [], "tags": ["creed"],
     "section": "The promise", "transition": {"type": "cut"}}
  ],
  "overlays": {"O1": {"kind": "section", "text": "The promise", "slot": 1, "at": 0.2, "dur": 2.6, "style": {}}},
  "music": [{"track": "M1", "title": "Dark Space", "artist": "CAIMO1", "licence": "CC BY 3.0",
             "licence_url": "https://creativecommons.org/licenses/by/3.0/", "url": "https://www.jamendo.com/track/…",
             "provider": "openverse", "at": 0, "track_in": 0, "dur": null, "gain_db": -22, "duck_db": -12,
             "fade_in": 1.5, "fade_out": 2.5}],
  "settings": {},
  "hash": "sha256:<32 hex>",
  "credits": [{"type": "source", "ref": "S1", "text": "The Dark Knight (2026)", "url": null, "moments": ["00:06:29–00:06:45"]},
              {"type": "music", "ref": "M1", "text": "Music: \"Dark Space\" by CAIMO1 (CC BY 3.0)", "url": "…"}],
  "author": {"handle": "local"},
  "links": {"hub": "http://127.0.0.1:8790/r/01K…", "posts": [{"url": "…", "lang": "am"}]},
  "duration": 261.1
}
```

## Rules

- **Times** are seconds in the *source* (`in` and `out`). Output positions are derived: slots play in order;
  a `fade` or `dip` transition overlaps the previous slot by its `dur`.
- **Slots carry their own text** (`quote`, `title`, `why`), so a recipe stays readable without its sources.
- **Credits are derived** from source rights and music licences; never typed by hand.
- **`hash`** covers the content (title, intent, sources, slots, overlays, music, settings), not `links`, `author`,
  `credits`, `id`, `ref` or `duration`. Two recipes with the same hash render the same.
- **File sources** are identified by `fingerprint` (size and the hash of the first and last 4 MB). Importers
  match by fingerprint, then by title, year and length (±3 s); otherwise the source is added as *missing* and
  the user relinks their own copy.
- **Link sources** are identified by `platform` + `id`. Players use the official embed with start and end times;
  renders fetch only the slot's range.
- **No paths.** The hub refuses recipes containing local paths or `file://` URLs.

## Validation

`recomp journey validate J1` checks media availability, slot lengths, missing *why*, music licences and the
structure (`recomp.compose.recipe.validate`, mirrored by the JSON Schema `recomp.compose.recipe.SCHEMA`).

## Interchange

- `--format edl`: CMX3600, 30 fps, record timeline from 01:00:00:00, clip names and source files as comments.
- `--format otio`: OpenTimelineIO JSON (`Timeline.1`) with one video and one audio track, external references to
  the source files (or URLs), and each clip's cut, *why* and section in metadata. Opens in DaVinci Resolve,
  Premiere (via the OTIO plugin) and Kdenlive.
