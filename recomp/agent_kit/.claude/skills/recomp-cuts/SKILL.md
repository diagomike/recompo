---
name: recomp-cuts
description: Make meaningful cuts in a Recomposer project — choosing moments that stand alone, cutting by quote or time with snapping, and labelling why each cut matters.
---

# Cuts

A cut is a moment worth keeping: a complete thought, a turn, a line that lands. It must make
sense on its own, because journeys re-order cuts from many sources.

## Finding them
- `recomp search "free will" --limit 20` across all sources (hits carry context and a ready `cut add` command).
- `recomp cut suggest "what it costs to be good" --limit 10` expands hits to whole thoughts (sentence and
  speaker-turn boundaries, 15–90 s).
- Inside a chapter: `recomp transcript read S1 --chapter S1.c4`.

## Making them
- **By quote** (preferred; exact word timing):
  `recomp cut add S1 --quote-start "You either die a hero" --quote-end "become the villain" --title "Live long enough" --why "Harvey's thesis; the film answers it" --tags fate,heroism`
- By time: `recomp cut add S1 --from 01:02:10.5 --to 01:02:55`.
- By segments: `recomp cut add S1 --segments 412..430`.
- Snapping: `--snap words` (default; starts just before the first word and ends after the last),
  `--snap shots` (films: align to the nearest shot change within 0.6 s), `--snap none`.
  `--pad 0.2,0.4` adjusts lead-in and tail.

## Quality bar
- **Opens clean**: no "and so…", no reference to something unseen. **Lands**: ends on the line, laugh or beat.
- Shorts: 15–90 s. Long-form slots: up to 4 min.
- `--why` is mandatory in spirit: why does this moment matter to the journey? It is what search and the
  user will read later.
- Add `--people "Alex O'Connor"` for compilations by speaker and `--emotions awe,grief` where it fits.

## Reviewing
`recomp cut list --source S1`, `recomp ui show C17 --play`, `recomp preview C17`. Trim with
`recomp cut trim C17 --start +0.3 --end -1.2` (relative) or absolute times.
