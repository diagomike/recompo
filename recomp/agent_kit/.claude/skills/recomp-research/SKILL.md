---
name: recomp-research
description: The Recomposer research wing — find creators and shows to follow, check them for new posts, take new episodes into a project (transcript by the cheapest route, creator chapters, cut candidates), search their back catalogue in the studio library, and compile what they said about a topic into a journey (topic suggest, scan, brief, journey from-topic).
---

# Following creators

**Stance (D-22).** We are an active creation team: we follow people we love and make journeys from what they
say, from their new posts and from topics they have opinions on. We don't rank what performs or study other
clippers. Follows, the inbox and the library are studio-level (no project needed); refs `F1` follow, `I3` inbox
item, `L2` library transcript, `T1` topic (its passages: `p4`).

## Find and follow
- `recomp find creators "philosophy podcast"`: channels (with subscribers), podcasts (with their feed and
  transcript route) and a person's appearances on other channels, numbered.
- `recomp follow add 2 --project alex-oconnor` follows result 2. Or directly:
  `recomp follow add @CosmicSkeptic --project alex-oconnor --person "Alex O'Connor" --podcast "Within Reason"`,
  `recomp follow add https://lexfridman.com/feed/podcast/ --project ai-and-ideas --name "Lex Fridman"`.
  `--appearances` also watches the person's guest spots; `--match "AI|conscious"` filters titles.
- `recomp follow list` · `recomp follow edit F1 …` · `recomp follow remove F1` (undo: `recomp op undo --studio`).

## Transcript routes, cheapest first
| Route | Where | Clock |
|---|---|---|
| `lex` | lexfridman.com transcript page (speakers, chapters, the YouTube id) | the video's |
| `published` | the podcast feed's `<podcast:transcript>` (e.g. The Diary of a CEO) | the podcast's: align before cutting video |
| `captions` | YouTube captions (one request per video; refused when YouTube blocks this machine) | the video's |
| `asr` | the feed's audio, transcribed locally (~0.8× real time on this CPU) | the podcast's |

## New posts → a project
1. `recomp follow check` (also runs every 2 h while the studio is open). A follow's first check puts only the
   newest few in the inbox.
2. `recomp inbox list` → `recomp inbox take I3 [--project P]`: adds the source (metadata first; from the listing
   when YouTube refuses), the transcript by its route, creator chapters, and `cut suggest` candidates on the
   project's themes (`recomp project set --themes "consciousness,free will"`). `recomp inbox dismiss I4` for
   the rest.
3. Read the candidates (`transcript read`), then cut with a *why* and draft the journey as usual.

## The back catalogue
- `recomp follow backfill F2 [--since 2y] [--limit 20]`: transcripts only (no video) into the studio library;
  run again to continue. Episodes that only have audio are counted as `needs_asr` and skipped.
- `recomp library search "copy itself"` (or `recomp search … --scope library`): hits with creator, episode, time,
  speaker and a link at that moment. `recomp library show L2 --from 35:00 --to 37:00` reads a stretch.
- To cut from a library hit, take that episode into a project first (its video becomes the source).

## Topics: what my creators said about X
1. Prompts: `recomp topic suggest [--section technology] [--query "AI models"]` lists headlines (Google News, Hacker
   News; `--sources trends,wikipedia` too), each with the followed creators who have talked about it. The news is a
   prompt, never a scoreboard. Or name your own topic.
2. `recomp topic add "AI models are getting good" --terms "AI,AGI,superintelligence,frontier model,copy itself"`
   (or `topic add 3` from the list). Good terms decide the brief: add the phrases people actually say.
3. `recomp topic scan T1 [--fetch 3]`: each creator's episodes about it (feed titles, their channel's search, the
   library, project transcripts), missing transcripts fetched the cheap way, passages ranked. Audio-only episodes
   are listed as `needs ASR`.
4. `recomp topic brief T1 [--format md]`: per creator, episodes and passages (`p1`…) with speakers, times, links.
   **Read them**; the ranking is only a shortlist. Pick passages that argue something.
5. `recomp journey from-topic T1 --passages p2,p5,p7,p9,p11,p12 --project P` (or `--by stance --stances
   "p2=worried,p9=hopeful"`): cuts with a why and who speaks, a section per creator (or stance), lower thirds. Then
   order it into an argument (`recomp journey guide J…`). Podcast-timed passages are shifted onto the video's clock
   when the video has a word-timed transcript; otherwise the result warns: check those cuts.

## Network
YouTube per-video requests may answer 429 or a bot check: report it and back off; never work around it.
Cookies are the user's call (`recomp config set network.cookies_file <cookies.txt>`).
