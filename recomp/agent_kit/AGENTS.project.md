# Recomposer project — operating guide for agents

This folder is a **Recomposer project**: media sources, their transcripts, chapters, cuts,
journeys (compositions) and exports, all held in `recomp.db` and operated through the
`recomp` command. You work *with* a person who watches the same project in the viewer
(`recomp serve`, http://127.0.0.1:8770). Treat it as co-work: do the heavy lifting, show
what you did, and leave the person's own choices alone.

- CLI: `recomp` (full path: `{{RECOMP}}`), or the `recomposer` MCP server (same verbs).
- Project folder: `{{PROJECT}}`
- Code and full docs: `{{REPO}}` (`docs/VERBS.md` lists every verb with its fields).

## Golden rules

1. **Only use verbs.** Never edit `recomp.db` or the files under `sources/`, `cache/`, `exports/` by hand.
2. **Start with `recomp context`.** It tells you what exists, what is running, what the user has
   selected, and what to do next. Run it again whenever you lose track.
3. **Every command prints one JSON envelope.** Check `ok`. On failure, read `error.code` and `error.hint`:
   - `E_PRECEDENCE`: the user wrote that field or row. Don't work around it; ask the user. Use
     `--as-user` only after they confirm in chat.
   - `E_NOT_FOUND` / `E_INVALID`: fix the input (`recomp help <verb>` shows its fields).
   - `E_EXTERNAL` / `E_NETWORK`: a site refused (YouTube 429, bot check). Back off and report; never bypass bot checks.
4. **Read before you cut.** Use `transcript outline` for the shape of a source and
   `transcript read --from --to` for windows. Don't dump whole transcripts into context when a
   search or a window will do.
5. **Long work is a job.** Verbs that return `"job"` keep running. Use `recomp job wait <id> --timeout 90`
   (it returns early with progress) and do other useful work in between.
6. **Show, don't describe.** `recomp ui show <ref>` moves the user's viewer to what you mean;
   `recomp preview <ref>` renders a quick look. `recomp ui ask "…"` pins a question in the viewer.
7. **Everything is undoable.** `recomp op log`, `recomp op undo`. Prefer small ops the user can follow.
8. **Nothing leaves this machine without the user's go-ahead in chat**: publishing to a non-local hub,
   or anything posted publicly. You never upload videos; the user does.

## Refs and times

`S1` source · `S1.t1` transcript · `S1.c4` chapter · `C17` cut · `J2` journey · `J2#3` third slot ·
`O5` overlay · `M1` music track · `B1` music bed · `P3` person · `X4` export · `job12` job.
Times: `4323.4`, `01:12:03.4`, `12:03`, `72m3.4s`. Outputs give seconds plus a clock string.

## The pipeline

```
source add ─► (probe · audio · shots · peaks jobs) ─► transcript import | fetch-captions | asr
   ─► transcript sync-check ─► search index ─► chapters ─► cuts ─► journey ─► overlays · music
   ─► preview ─► export run (profiles × languages) ─► hub publish (local hub by default)
```

| Step | Typical commands |
|---|---|
| Ingest | `recomp source add "D:\Movies\*.mp4"` · `recomp source add https://youtube.com/@channel/videos --limit 30` · `recomp source status` |
| Transcripts | `recomp transcript import S1 file.srt` · `recomp transcript fetch-captions S2` · `recomp transcript asr S3` · `recomp transcript sync-check S1 --fix` |
| Read | `recomp transcript outline S1` · `recomp transcript read S1 --from 10:00 --to 14:00` · `recomp search "forgiveness" --limit 20` |
| Chapters | `recomp chapter seed S2` (creator chapters) · write yours: `recomp chapter set S1 --input chapters.json` |
| Cuts | `recomp cut add S1 --quote-start "Why so" --quote-end "that face" --title … --why … --tags …` · `recomp cut add S1 --from 12:03 --to 12:48` · `recomp cut suggest "everlasting life"` |
| Journeys | `recomp journey new "Title" --intent …` · `recomp journey add J1 C3 C9 C4` · `recomp journey move J1#3 --to 1` · `recomp journey section J1 "Part two" --at 3` · `recomp journey show J1` |
| Look | `recomp overlay auto-lower-thirds J1` · `recomp overlay add J1#1 --kind quote --text …` · `recomp music search "warm piano" --licence commercial` · `recomp music bed add J1 M1` |
| Export | `recomp profile list` · `recomp preview J1` · `recomp export run J1 --profiles shorts,landscape --langs en,am,sw,fr` · `recomp export status` |
| Languages | `recomp lang translate J1 --to am --input am.json` (your own translation) · `recomp lang dub J1 --lang am` |
| Share | `recomp hub publish J1 --visibility public` (ask first) · `recomp hub link-post J1 <url the user posted>` |

## Writing chapters, cuts and journeys

- **Chapters** follow the media: scenes and dramatic beats for films, topics and questions for
  conversations. Titles are short and concrete; summaries say what happens or what is argued
  in one or two sentences. Bulk input:
  `[{"start": "00:01:10", "end": "00:04:02", "title": "…", "summary": "…", "tags": ["…"]}]`.
- **Cuts** are complete thoughts or beats that stand on their own: a clear opening, a
  landing, no dangling reference to something off-screen. Shorts like 15–90 s. Quote-based
  cutting snaps to word boundaries; `--snap shots` aligns film cuts to shot changes. Say *why*
  the cut matters in `--why`: it is the most useful field later.
- **Journeys** are authored sequences: hook → build → turn → resolve. For compilations
  ("every time X speaks about Y") order by argument, not by date, unless the change over time
  is the point. Keep each slot's source credited (lower thirds) and let the music sit under
  speech (beds duck automatically).

## When to ask the user

Ask (in chat, or with `recomp ui ask`) when: a theme or tone is ambiguous enough that a long
render could be wasted; a site blocks access (cookies are the user's decision); something
would be published beyond this machine; you would need to overwrite their work.

<!-- generated by `recomp project agent-kit`; reinstall to update -->
