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
- [ ] Still open from P16b: music search needs the network (no offline library seed yet). (Done in P18b: the
      Look step previews each lower third on its slot.) (Fixed 2026-10-19: the room's command row stays on one line down to 1024 px.)
- [ ] **P17 research wing** (approved 2026-10-19 with defaults P17-Q1–Q6; plan §6, [research](research/P17-research-wing.md)):
  - [x] P17a find and follow: `find creators`, follows, checks (every 2 h while the studio runs), inbox take
        (source, transcript by route, chapters, cut candidates on project themes), back-catalogue library and search.
  - [x] P17b topics: `topic suggest` (news prompts with who has talked about them), `topic add/edit/list/remove`,
        `topic scan` (episodes, cheap transcripts, ranked passages) and `topic brief`, `journey from-topic`.
  - [x] P17c rights and posting: `source rights --status --evidence`, `post plan/queue/open/link/cancel` with the
        E_RIGHTS gate, `channel set/show/stats`, `hub publish` private by default with the permission question (E_CONFIRM).
  - [x] P17d viewer: Follows and Topics pages, publish confirmation dialog, posting queue on the Exports page.
  - [x] M5 acceptance run ([report](runs/M5-follows-and-topics.md), 2026-10-20): four follows, journeys from a taken
        episode and from topic T1, shorts + landscape exports with credits, the posting gate, and (2026-10-21) the
        live hub permission step: J3 public on the local hub after your yes.
- [x] **P18 backlog run** (organised 2026-10-21; plan §6 P18; all built 2026-10-21), in this order:
  - [x] P18a faster re-exports: `export run --speed fast` (final pass at `superfast`, CRF −2): 100 s vs 249 s on J2.
  - [x] P18b viewer: speaker lanes and names coloured by person (same colour in every source), formats × languages
        matrix with progress in the Export step, Look-step lower thirds previewed on a frame of their slot.
  - [x] P18c cross-release matching: recipes carry transcript anchors; importing on another copy shifts the cuts by
        the offset near each (edits and PAL drift too); `source match-release S…` re-runs it.
  - [x] P18d recipe player seams: two players take turns (local video and YouTube); the next slot waits loaded at
        its in point and starts on the out point.
  - [x] P18e dub fixes: shortened the J1 lines the dub check flagged (am 2, sw 2, fr 4, om 15) and re-dubbed:
        0 overflowing lines in all four, every check passes (X36–X39).
  - [x] P18f face-centred vertical crop: the `shorts-face` profile (reframe `crop-face`), an extra option next to the
        blurred-fill Shorts; YuNet finds the speaker per shot (ai-and-ideas J3 → X7).
  - [x] P18g multilingual semantic search: `transcript embed` (jobs) and `search --semantic`, "By meaning" on the
        Search page; multilingual-e5-small. Queries go to a resident embedder that keeps the model loaded: the first
        waits ~9 s for it, later ones take ~0.6 s from the CLI (it stops after 10 idle minutes).
  - [x] P18h voice-cloned dubs: `export run --voice clone` ("Original voices (AI)" in the Export step) voices each
        line from its speaker's own audio with OmniVoice, saved beside the usual dub (`…-clone`), credited as AI
        voices. Dark Knight J1 fr: 1 line over, round-trip WER 0.26 (studio voice: 0 over, 0.04). Your ears decide.

## Research (P19, 2026-10-31; research only)
- [x] Literature and feasibility report: `docs/research/P19-dubbing-and-meaning/` (tracks 1 and 3 here, track 2 on
      branch `ccr-327cc642-xnfs3i-track2-models`); pilot on two real en→es dubbed excerpts.
- [x] Mechanisms compared in worktrees (duration, placement, LLM loop, trained MT):
      `docs/research/P19-dubbing-and-meaning/mechanisms-compared.md`.
- [x] Trained duration-aware MT (IWSLT Sockeye) on the same bench (2026-10-31): 0.80 voice overlap, chrF 53.5.
- [x] Fully algorithmic rephrasing (worktree `algorithmic`, 2026-10-31): not competitive without a neural judge.
- [ ] BERT-pluggable rephrasing (XLM-R masked-LM edits + LaBSE/e5 meaning check) and NLLB n-best + rerank — need
      HuggingFace: run on your PC (`D:\LangBridgeLocal\cache\hf`) or with huggingface.co allowed in the cloud env.
- [x] Multi-round LLM refinement with a band (0.8–1.05×, silence allowed) and de-padding (worktree `llm-multiround`):
      best method so far.
- [x] MCTR, meaning-conserving top-down rephrasing (worktree `mctr`): spec, module, tests, blind meaning check.
      When building resumes: verbs `lang understand/variants/revise/verify`, per-run dub placement (see its README §3).
- [x] Two-sided optimiser for MT-only languages (worktree `twosided`), proven on de→en (real MT) and en→es.
- [x] End to end between two MT-only languages through an English pivot (worktree `pivot`), proven on
      German speech → Spanish: multi-view understanding, units pinned to source segments, two-sided timing.
- [ ] Pivot run Amharic → Oromo on your PC: Ethio-ASR, `mt_google.py` am→en views (or NLLB short/long), en→om,
      MMS orm voice, om→en back-translation; a human reviews low-confidence lines.
- [ ] Calibrate the prosody question cue per speaker (it over-fires on read speech).
- [x] Working-language routing (worktree `routes`): `routes.py plan`, economy/quality budgets, route prior for pooling.
- [ ] Adaptive MT views (extra views only where whole-line and per-segment views disagree) to cut understanding tokens.
- [x] Two middle languages for understanding (worktree `bipivot`): English + Spanish from two MT systems, French target.
- [ ] On your PC: understanding am→en (Google) + am→spa (NLLB, direct); verification om→en and om→spa through both systems.
- [ ] Quality-mode pivot on your PC: am→om through English + Spanish pooled (Google/NLLB both hops, MMS orm voice).
- [ ] Two-sided run on Amharic/Oromo on your PC: `mt_google.py` (forward + back-translation), edge-tts am / MMS orm voice.
- [ ] Corpus pilot on 20–50 of your dual-audio titles (needs: language pairs, a list of files).
- [ ] Track 1 A/B on 10 held-out dubbed titles (Claude's timed script vs today's pipeline vs the human dub's words).
- [ ] Track 3 blind comparison: unit cards + LLM selection vs `cut suggest` on alex-oconnor and ai-and-ideas.

## Waiting on the user
- [ ] Name the channel you post to (P17-Q3; a placeholder is used until then).
- [ ] F2 (The Diary of a CEO) is labelled "DOAC": rename it to Steven Bartlett? (`recomp follow edit F2 --person "Steven Bartlett" --as-user`)
- [ ] Cookies for YouTube when it blocks: export a cookies.txt from Chrome (its background processes lock the database).
- [ ] Real Kaggle/Colab run of `notebooks/recomp_worker.ipynb` (the protocol is tested locally with a stand-in worker).
- [ ] Listening check of the am/sw/fr/om dubs (automated checks pass; human ears decide). Since 2026-10-21 the J1
      Oromo bar scene is agent-shortened (15 lines): an Oromo speaker should read it (`recomp lang lines J1 om`).
- [ ] Rights holder for *The Dark Knight (2026)*: `recomp source rights S1 --owner …`.

## Next (after P18)
0. Cloned dubs: ~1 min per line on this CPU and slower speech than the studio voices; on a GPU (the Colab worker)
   or with fewer steps, and line shortening aimed at the cloned voice's pace.
0. Semantic search: try a larger multilingual model for Amharic/Oromo queries (e5-small reaches across languages
   only moderately). (Done 2026-10-21: the resident embedder, ~0.6 s per query instead of ~20 s.)
1. Public hub deployment (host, Postgres, OAuth, moderation queue for reports): the user's decision.
2. Offline music library seed (CC0 tracks downloaded once), so music search works without the network.
