# BACKLOG

Every open task by priority. Done phases are summarised; their detail is in git history and the run reports.

## Done
- [x] P0 foundations and agent contract · P1 ingest and media · P2 transcripts, search, ASR · P3 chapters and cuts
- [x] P4 studio server and viewer · P5 journeys and recipes · P6 render and export · P7 music
- [x] M1 Dark Knight acceptance run ([report](runs/M1-dark-knight.md))
- [x] P8 links (code + mocked tests) · P9 speakers · P10 translation and dubbing · P11 hub · P12 remote workers · P13 trends
- [x] M3 three-language dubs + Oromo stretch · M4 local hub ([report](runs/M3-M4-languages-and-hub.md))

## Waiting on the user
- [ ] **M2 Alex O'Connor**: YouTube bot check blocks per-video requests from this PC. Decide: wait, browser cookies,
      another network, or the remote notebook. Then: `recomp source refresh S1..S5`, captions/ASR, speakers, the
      consciousness journey, section downloads, exports, hub publish with YouTube embeds.
- [ ] Real Kaggle/Colab run of `notebooks/recomp_worker.ipynb` (the protocol is tested locally with a stand-in worker).
- [ ] Listening check of the am/sw/fr/om dubs (automated checks pass; human ears decide).
- [ ] Rights holder for *The Dark Knight (2026)*: `recomp source rights S1 --owner …`.

## Next (by priority)
1. Dub: re-voice only the lines that changed (now: clips are cached per text, but the dub track is rebuilt whole — fine);
   a viewer panel listing overflowing lines with inline editing.
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
