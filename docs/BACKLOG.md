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
- [ ] **P15 editing toolkit** (plan §6): transcript replace/edit/clean/delete/merge/split/resegment/export, shift
      --scale/--from/--to, speaker assign (ranges, `>>` turns, `NAME:` prefixes) and people, lang
      lines/edit/replace/clear, caption box per profile and language, caption sheet. Verbs built and tested;
      viewer parts (inline line editing, translation editor) go with P16.
- [ ] **P16 UX perfecting pass** (plan §6): one workspace, cut bin across sources → journeys, filters everywhere,
      action bars whose buttons are verbs the agent can also run, guided project checklist, shortcuts.

## Waiting on the user
- [ ] Real Kaggle/Colab run of `notebooks/recomp_worker.ipynb` (the protocol is tested locally with a stand-in worker).
- [ ] Listening check of the am/sw/fr/om dubs (automated checks pass; human ears decide).
- [ ] Rights holder for *The Dark Knight (2026)*: `recomp source rights S1 --owner …`.

## Next (by priority)
1. Dub: lines in the bar scene of J1 still overflow by 0.3–0.9 s in am/sw/fr; a human pass in the dub review panel
   (Exports page) can close them.
2. Oromo: an agent-reviewed translation (the Google draft runs long; MMS has no rate control → shorten lines).
3. Final pass speed: optional faster preset for re-exports (reorder gate measured at 55–73 % of cold; see M1 report).
4. Viewer: speaker lane colours by person, a translation editor, export matrix progress per language.
5. Face-aware reframe for vertical exports (currently blurred fill or centre/offset crop).
6. Voice cloning dubs through lang_bridge (OmniVoice / Seed-VC), labelled as AI voices in credits.
7. Cross-release matching: estimate the offset between two copies of a film from subtitles/audio when a pulled recipe's
   file fingerprint differs.
8. Multilingual semantic search (embeddings) for Amharic/Oromo transcripts.
9. Public hub deployment (host, Postgres, OAuth, moderation queue for reports): the user's decision.
10. Recipe player seams: double-buffered video elements for gapless local playback.
