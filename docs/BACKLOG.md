# BACKLOG

Every open task by priority. Done phases are summarised; their detail is in git history and the run reports.

## Done
- [x] P0 foundations and agent contract · P1 ingest and media · P2 transcripts, search, ASR · P3 chapters and cuts
- [x] P4 studio server and viewer · P5 journeys and recipes · P6 render and export · P7 music
- [x] M1 Dark Knight acceptance run ([report](runs/M1-dark-knight.md))
- [x] P8 links (code + mocked tests) · P9 speakers · P10 translation and dubbing · P11 hub · P12 remote workers · P13 trends
- [x] M3 three-language dubs + Oromo stretch · M4 local hub ([report](runs/M3-M4-languages-and-hub.md))
- [x] M2 Alex O'Connor links ([report](runs/M2-alex-oconnor.md)) · P14 docs, launcher, backup, multitrack, dub review panel

## In progress
- [x] **P15 editing toolkit** verbs (transcript bulk edits, manual speakers, translation editing, caption box) and their
      viewer parts (inline line editing, speakers panel, translation editor).
- [x] **P16 UX pass** built: project home and checklist, cut bin across sources, drag cuts into journeys, filters in
      the URL everywhere, buttons that show their command and can be handed to the agent, `ui show` with views,
      filters and highlights, file browser, shortcuts, two-click confirms, phone widths.
- [x] **P16b UX rework** after your review ([report](runs/P16b-ux-rework.md)): the guided journey studio (purpose →
      gather → order → look → check → export, `journey guide`/`journey review`), destinations on journeys
      (`--formats`), `cut add --journey`, New journey dialog, nav rail and agent drawer, Word-style progressive disclosure
      (ribbon of steps, command rows, menus, dialogs, "More filters", collapsible advanced options), dense tables and
      lists instead of cards. **Your review is the remaining step.**
- [x] P16b follow-ups done 2026-10-16: the source room, transcript pane and translation editor in the P16b structure
      (command rows by task, ⋯ menus, dialogs for cut/chapter/replace/speakers/new language, folded caption box, phone
      layouts), studio keys `1`–`6` and `Enter` ([report](runs/P16b-ux-rework.md#follow-up-source-room-and-translation-editor-2026-10-16)).
- [ ] Still open from P16b: a "Look" preview of lower thirds per slot; music search needs the network (no offline
      library seed yet); the room's command row wraps its zoom group to a second line below ~1100 px with the
      transcript pane at its default width.
- [ ] **P17 research wing** (re-planned 2026-10-16, plan §6, [research](research/P17-research-wing.md)): find and follow
      creators, inbox from their new posts, transcript library (back catalogue, text only), topics from the news or
      from you, topic briefs ("what my creators said about X"), journeys from topics, rights statuses with the
      posting gate and the hub publish confirmation (D-23). Awaiting your approval; open questions P17-Q1–Q6.

## Waiting on the user
- [ ] Approve the new P17 plan (or answer P17-Q1–Q6); name the channel you post to.
- [ ] Cookies for YouTube when it blocks: export a cookies.txt from Chrome (its background processes lock the database).
- [ ] Real Kaggle/Colab run of `notebooks/recomp_worker.ipynb` (the protocol is tested locally with a stand-in worker).
- [ ] Listening check of the am/sw/fr/om dubs (automated checks pass; human ears decide).
- [ ] Rights holder for *The Dark Knight (2026)*: `recomp source rights S1 --owner …`.

## Next (by priority)
1. Dub: lines in the bar scene of J1 still overflow by 0.3–0.9 s in am/sw/fr; a human pass in the dub review panel
   (Exports page) can close them.
2. Oromo: an agent-reviewed translation (the Google draft runs long; MMS has no rate control → shorten lines).
3. Final pass speed: optional faster preset for re-exports (reorder gate measured at 55–73 % of cold; see M1 report).
4. Viewer: speaker lane colours by person, export matrix progress per language.
5. Face-aware reframe for vertical exports (currently blurred fill or centre/offset crop).
6. Voice cloning dubs through lang_bridge (OmniVoice / Seed-VC), labelled as AI voices in credits.
7. Cross-release matching: estimate the offset between two copies of a film from subtitles/audio when a pulled recipe's
   file fingerprint differs.
8. Multilingual semantic search (embeddings) for Amharic/Oromo transcripts.
9. Public hub deployment (host, Postgres, OAuth, moderation queue for reports): the user's decision.
10. Recipe player seams: double-buffered video elements for gapless local playback.
