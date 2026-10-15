---
name: recomp-chapters
description: Write good chapters for a source in a Recomposer project (film scenes and beats, podcast topics), reading transcripts economically and submitting chapters in bulk.
---

# Chapters

Chapters are the map every later step uses: search results, cut suggestions and journeys all
show them. Write them once, well.

## Read economically
1. `recomp transcript outline S1`: duration, transcript coverage, creator chapters, shot density,
   and silences: the shape before the words.
2. Read in windows: `recomp transcript read S1 --from 0 --to 15:00` (compact lines
   `[00:01:10.6] text`). For a 90-minute film, six to eight windows; skim fast and note boundaries
   as you go.
3. Links often have creator chapters: `recomp chapter seed S2` imports them. Refine instead of rewriting.

## Granularity
| Media | Chapter = | Typical length |
|---|---|---|
| Film | a scene or a dramatic beat (location/time change, a turn in the conflict) | 2–8 min |
| Podcast / interview | one question or topic, including the answer's tangents | 4–15 min |
| Sermon / lecture | one point or illustration | 3–10 min |

## Style
- **Title:** concrete and short ("Harvey offers his deal", "Is a plant aware it is eaten?"). No clickbait.
- **Summary:** one or two sentences: what happens, or what is argued and by whom.
- **Tags:** themes and emotions you would search for later (`sacrifice`, `grief`, `free-will`).

## Submit in bulk
```json
[{"start": "00:01:10", "end": "00:06:40", "title": "…", "summary": "…", "tags": ["…"]}]
```
`recomp chapter set S1 --input chapters.json` replaces the chapters *you or the machine* wrote. Chapters the
user wrote are kept (`E_PRECEDENCE` lists them). Boundaries snap to transcript segment edges.
Afterwards: `recomp chapter list S1` and `recomp ui show S1.c1`.
