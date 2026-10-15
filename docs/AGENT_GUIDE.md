# Agent guide: two worked sessions

What an agent session in a Recomposer project actually looks like, verb by verb. The operating rules are in
[recomp/agent_kit/AGENTS.project.md](../recomp/agent_kit/AGENTS.project.md) and the six skills.

## 1. A film: from a file to a dubbed short (M1, condensed)

```
recomp project init dark-knight --kind movies
recomp source add "D:\Recomp\Video\The.Dark.Knight*.mp4"      # S1, the .srt imported as S1.t1; jobs queued
recomp job wait job1 job2 job3 job4 --timeout 120
recomp transcript sync-check S1                                # runs ASR on 3 windows, or uses an ASR transcript
recomp transcript asr S1 --language en                          # optional: full ASR (S1.t2) for word timings
recomp transcript align S1.t1 --using S1.t2                     # subtitles get spoken word timings
recomp transcript outline S1                                    # shape first: density, silences, shots
recomp transcript read S1 --from 0 --to 15:00                   # then read in windows
recomp chapter set S1 --input chapters.json                     # 22 scenes with summaries and tags
recomp cut add S1 --segments 105..110 --snap words+shots --title "And what do you do? Nothing." \
      --why "The accusation at the heart of the film" --tags apathy,do-something
recomp journey new "Do something" --intent "…" --cuts C3,C5,C15,C7
recomp music search "sad piano" && recomp music get 1 && recomp music bed-add J1 M2 --gain -20
recomp overlay auto-lower-thirds J1
recomp ui show J1                                               # the user watches the recipe in the viewer
recomp preview J1 --profile shorts                              # low-res check
recomp export run J1 --profiles shorts,landscape
recomp lang translate J1 --to am --template                     # lines with time budgets
recomp lang translate J1 --to am --input am.json                # the agent's own translation
recomp export run J1 --profiles shorts --langs am,sw,fr
recomp export show X19                                          # checks: dub fit, round-trip intelligibility
# shorten the overflowing lines it lists, then re-export (voiced lines are cached)
recomp hub publish J1                                           # local hub; ask before any public one
```

## 2. A channel: a compilation across conversations (M2 path)

```
recomp project init alex-oconnor --kind channel
recomp source add https://www.youtube.com/@CosmicSkeptic/videos --limit 30    # a pick list; nothing added yet
recomp source add --pick 1,12,20,24                                          # metadata, creator chapters, captions job
recomp chapter seed S1                                                       # creator chapters as a start
recomp transcript asr S4 --on remote                                         # or local; captions blocked → ASR
recomp speaker diarize S1 --speakers 2 && recomp speaker list S1
recomp speaker name S1:SPEAKER_00 "Alex O'Connor"                             # recognised in other episodes
recomp search "consciousness" --speaker "Alex O'Connor"
recomp cut suggest "is consciousness an illusion" --limit 10
recomp journey from-search "consciousness illusion" --limit 8 --title "Is consciousness an illusion?"
recomp export run J1 --profiles shorts                                       # downloads only the slots' ranges
```

## When things go wrong

| Envelope | What it means | What to do |
|---|---|---|
| `E_PRECEDENCE` on an edit | the user wrote that field | ask; `--as-user` only with their go-ahead |
| `E_EXTERNAL` "confirm this is not a bot" | YouTube blocks this machine | stop and tell the user; cookies are their call |
| `E_EXTERNAL` 429 on captions | rate limited | `recomp transcript asr <S>` (audio only) |
| export `done-with-problems`, `dub fit` | lines too long for their time | shorten those lines (`lang translate --input`) and re-export |
| export `failed`, "no … lines to voice" | not translated | `lang translate … --template` first |
| `E_CONFLICT` on undo | the row changed since | look at `op log`; do the inverse explicitly |
