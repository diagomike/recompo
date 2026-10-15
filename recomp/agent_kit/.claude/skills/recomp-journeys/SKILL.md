---
name: recomp-journeys
description: Compose journeys (recipes) in Recomposer — arc design, cross-source compilations, sections, overlays and music — and review them with the recipe player and previews.
---

# Journeys

A journey is an authored sequence of cuts: the recipe. Reordering is cheap (renders cache per
slot), so draft fast and refine with the user.

## Arc patterns
| Pattern | Shape | Good for |
|---|---|---|
| Hook → build → turn → resolve | open on the strongest line, deepen, flip, land | shorts, single theme |
| Thesis / antithesis / synthesis | one view, the counter, the reconciliation | debates, podcast compilations |
| Every time X on Y | same speaker, many sources, ordered by argument | speaker projects |
| Emotional staircase | gentle → intense → release | movie moments (heartbreak, romance) |

## Building
```
recomp journey new "Live long enough" --intent "What heroism costs, in Harvey's words and Bruce's choices"
recomp journey add J1 C4 C9 C2 C11
recomp journey move J1#4 --to 1          # strongest line first
recomp journey section J1 "The bargain" --at 2
recomp journey show J1                   # timeline, total duration, per-slot sources
```
`recomp journey from-search "forgiveness" --limit 8` drafts a journey from search hits; you then edit it.

## Look and sound
- `recomp overlay auto-lower-thirds J1` credits each slot's source and speaker.
- `recomp overlay add J1 --kind title --text "…"` (opening card), `--kind quote` on a slot for a pull-quote.
- Music: `recomp music search "melancholic strings" --licence commercial`, then `recomp music bed add J1 M1`.
  Beds duck under speech automatically; keep gain around −16 dB.
- Transitions: hard cuts by default; `recomp journey transition J1#3 --type fade --dur 0.5` where a breath helps.

## Review with the user
`recomp ui show J1` (the viewer's recipe player plays slots straight from the sources without
rendering), then `recomp preview J1` for a real low-res render. Ask with `recomp ui ask` before
long exports if the arc is a judgment call.
