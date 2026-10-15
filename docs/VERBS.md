# Verbs

Generated from the registry by `python scripts/gen_docs.py`. Every verb is available as
`recomp <noun> <verb>` (CLI), as the MCP tool `<noun>_<verb>`, and as
`POST /api/verb/<noun>.<verb>` on the studio server. All return the same JSON envelope.

Effects: `read` (no changes) · `write` (undoable op) · `heavy` (starts a job) ·
`network` (talks to the internet) · `publish` (shares beyond this machine).

| Noun | Verbs |
|---|---|
| `chapter` | [`chapter.add`](#chapteradd), [`chapter.auto`](#chapterauto), [`chapter.edit`](#chapteredit), [`chapter.list`](#chapterlist), [`chapter.merge`](#chaptermerge), [`chapter.remove`](#chapterremove), [`chapter.seed`](#chapterseed), [`chapter.set`](#chapterset), [`chapter.split`](#chaptersplit) |
| `config` | [`config.get`](#configget), [`config.set`](#configset) |
| `context` | [`context`](#context) |
| `cut` | [`cut.add`](#cutadd), [`cut.edit`](#cutedit), [`cut.list`](#cutlist), [`cut.merge`](#cutmerge), [`cut.remove`](#cutremove), [`cut.show`](#cutshow), [`cut.split`](#cutsplit), [`cut.suggest`](#cutsuggest), [`cut.tag`](#cuttag), [`cut.trim`](#cuttrim) |
| `doctor` | [`doctor`](#doctor) |
| `job` | [`job.cancel`](#jobcancel), [`job.list`](#joblist), [`job.retry`](#jobretry), [`job.run`](#jobrun), [`job.show`](#jobshow), [`job.tail`](#jobtail), [`job.wait`](#jobwait) |
| `journey` | [`journey.add`](#journeyadd), [`journey.delete`](#journeydelete), [`journey.duplicate`](#journeyduplicate), [`journey.edit`](#journeyedit), [`journey.from-search`](#journeyfrom-search), [`journey.list`](#journeylist), [`journey.move`](#journeymove), [`journey.new`](#journeynew), [`journey.remove`](#journeyremove), [`journey.reorder`](#journeyreorder), [`journey.section`](#journeysection), [`journey.show`](#journeyshow), [`journey.transition`](#journeytransition), [`journey.trim-slot`](#journeytrim-slot), [`journey.validate`](#journeyvalidate) |
| `op` | [`op.log`](#oplog), [`op.redo`](#opredo), [`op.undo`](#opundo) |
| `overlay` | [`overlay.add`](#overlayadd), [`overlay.auto-lower-thirds`](#overlayauto-lower-thirds), [`overlay.edit`](#overlayedit), [`overlay.list`](#overlaylist), [`overlay.remove`](#overlayremove) |
| `project` | [`project.agent-kit`](#projectagent-kit), [`project.init`](#projectinit), [`project.list`](#projectlist), [`project.set`](#projectset), [`project.show`](#projectshow), [`project.use`](#projectuse) |
| `recipe` | [`recipe.export`](#recipeexport), [`recipe.import`](#recipeimport), [`recipe.show`](#recipeshow) |
| `search` | [`search`](#search) |
| `setup` | [`setup.shim`](#setupshim) |
| `source` | [`source.add`](#sourceadd), [`source.list`](#sourcelist), [`source.process`](#sourceprocess), [`source.relink`](#sourcerelink), [`source.remove`](#sourceremove), [`source.rights`](#sourcerights), [`source.show`](#sourceshow), [`source.status`](#sourcestatus) |
| `transcript` | [`transcript.align`](#transcriptalign), [`transcript.asr`](#transcriptasr), [`transcript.edit-segment`](#transcriptedit-segment), [`transcript.import`](#transcriptimport), [`transcript.list`](#transcriptlist), [`transcript.outline`](#transcriptoutline), [`transcript.read`](#transcriptread), [`transcript.set-primary`](#transcriptset-primary), [`transcript.shift`](#transcriptshift), [`transcript.sync-check`](#transcriptsync-check) |
| `ui` | [`ui.answer`](#uianswer), [`ui.ask`](#uiask), [`ui.note`](#uinote), [`ui.notes`](#uinotes), [`ui.select`](#uiselect), [`ui.selection`](#uiselection), [`ui.show`](#uishow) |
| `version` | [`version`](#version) |

## chapter

### chapter.add

`recomp chapter add <ref>` · effect: **write**

Add one chapter.

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required | Source ref |
| `--start` | string | required | Start time |
| `--end` | string | required | End time |
| `--title` | string | '' |  |
| `--summary` | string | '' |  |
| `--tags` | list[string] | None |  |

### chapter.auto

`recomp chapter auto <ref>` · effect: **write**

Machine draft chapters from pauses and shot rhythm (titles are placeholders: rewrite them).

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required |  |
| `--target-min` | number | 0 | Target chapter length in minutes (default: 5 for films, 8 for talks) |

### chapter.edit

`recomp chapter edit <ref>` · effect: **write**

Change a chapter's span, title, summary or tags.

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required | Chapter ref, e.g. S1.c4 |
| `--start` | string | None |  |
| `--end` | string | None |  |
| `--title` | string | None |  |
| `--summary` | string | None |  |
| `--tags` | list[string] | None |  |

### chapter.list

`recomp chapter list <ref>` · effect: **read**

Chapters of one source (or all), with spans, titles, summaries and tags.

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | None | Source ref (default: all sources) |
| `--tag` | string | None |  |

### chapter.merge

`recomp chapter merge <ref> <other>` · effect: **write**

Merge two chapters of the same source (the first keeps its title).

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required | First chapter |
| `<other>` | string | required | The chapter to absorb |

### chapter.remove

`recomp chapter remove <ref>` · effect: **write**

Delete a chapter.

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required |  |

### chapter.seed

`recomp chapter seed <ref>` · effect: **write**

Import the chapters the creator published (YouTube chapters, or chapters embedded in the file).

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required |  |

### chapter.set

`recomp chapter set <ref>` · effect: **write**

Replace a source's chapters in bulk (chapters the user wrote are kept and reported). Ends default to the next chapter's start.

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required | Source ref |
| `--items` | list[any] | required | Chapters (use --input chapters.json: a list or {items: [...]}) |
| `--snap` | boolean | True | Snap boundaries to transcript segment starts |
| `--method` | string | 'written' | written \| seed \| auto |

```
recomp chapter set S1 --input chapters.json
```

### chapter.split

`recomp chapter split <ref>` · effect: **write**

Split a chapter in two at a time.

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required |  |
| `--at` | string | required | Time to split at |
| `--title` | string | '' | Title for the second half |

## config

### config.get

`recomp config get <key>` · effect: **read**

Studio settings (projects root, worker python, hub URL, TTS voices…).

| Field | Type | Default | Description |
|---|---|---|---|
| `<key>` | string | None | Dotted key, e.g. worker.python (omit for everything) |

### config.set

`recomp config set <key> <value>` · effect: **write**

Change a studio setting.

| Field | Type | Default | Description |
|---|---|---|---|
| `<key>` | string | required |  |
| `<value>` | string | required | Value (JSON accepted: numbers, true/false, objects) |

```
recomp config set worker.python D:\LangBridgeLocal\.venv\Scripts\python.exe
```

## context

### context

`recomp context` · effect: **read**

One-call briefing: the project, every source's pipeline status, journeys, jobs, the user's selection and notes, and suggested next steps.

```
recomp context
```

## cut

### cut.add

`recomp cut add <ref>` · effect: **write**

Make a cut by quote, segment range or times. Edges snap to words (and shots); the spoken text is stored with it.

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required | Source ref |
| `--from` | string | None | Start time |
| `--to` | string | None | End time |
| `--segments` | string | None | Segment range from `transcript read`, e.g. 412..430 |
| `--quote-start` | string | None | Words the cut starts with (exact from the transcript) |
| `--quote-end` | string | None | Words the cut ends with |
| `--near` | string | None | Look for the quote near this time (± 10 min) |
| `--snap` | string | 'words' | words \| shots \| words+shots \| none |
| `--pad` | string | None | Lead-in,tail seconds (default 0.15,0.35) |
| `--title` | string | '' |  |
| `--why` | string | '' | Why this moment matters |
| `--tags` | list[string] | None |  |
| `--emotions` | list[string] | None |  |
| `--people` | list[string] | None |  |
| `--rating` | integer | None | 1–5 |
| `--note` | string | '' |  |

```
recomp cut add S1 --quote-start "You either die a hero" --quote-end "become the villain" --title "Live long enough" --why "Harvey's thesis" --tags fate,heroism
recomp cut add S1 --from 01:02:10.5 --to 01:02:55 --snap words+shots
recomp cut add S1 --segments 412..430
```

### cut.edit

`recomp cut edit <ref>` · effect: **write**

Change a cut's labels (title, why, note, tags, emotions, people, rating).

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required | Cut ref |
| `--title` | string | None |  |
| `--why` | string | None |  |
| `--note` | string | None |  |
| `--tags` | list[string] | None |  |
| `--emotions` | list[string] | None |  |
| `--people` | list[string] | None |  |
| `--rating` | integer | None |  |

### cut.list

`recomp cut list` · effect: **read**

Cuts with spans, titles, why, tags and chapter; filter by source, tag, person, emotion, text, or unused.

| Field | Type | Default | Description |
|---|---|---|---|
| `--source` | string | None | Source ref |
| `--tag` | string | None |  |
| `--person` | string | None |  |
| `--emotion` | string | None |  |
| `--chapter` | string | None |  |
| `--match` | string | None | Text in title, why or quote |
| `--unused` | boolean | False | Only cuts not in any journey |
| `--limit` | integer | 200 |  |

```
recomp cut list --source S1
recomp cut list --tag sacrifice --unused
```

### cut.merge

`recomp cut merge <ref> <other>` · effect: **write**

Merge two cuts from the same source into one spanning both.

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required |  |
| `<other>` | string | required |  |

### cut.remove

`recomp cut remove <ref>` · effect: **write**

Delete a cut (refused while a journey uses it).

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required |  |

### cut.show

`recomp cut show <ref>` · effect: **read**

One cut in full, with the lines around it and the journeys that use it.

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required |  |

### cut.split

`recomp cut split <ref>` · effect: **write**

Split a cut into two at a source time.

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required |  |
| `--at` | string | required | Source time to split at |

### cut.suggest

`recomp cut suggest <query>` · effect: **read**

Turn search hits into whole-thought cut candidates (sentence and pause boundaries, min/max length). Nothing is created.

| Field | Type | Default | Description |
|---|---|---|---|
| `<query>` | string | required |  |
| `--sources` | list[string] | None |  |
| `--min-s` | number | 15 | Shortest suggestion |
| `--max-s` | number | 90 | Longest suggestion |
| `--limit` | integer | 10 |  |

```
recomp cut suggest "what it costs to be good" --limit 8
```

### cut.tag

`recomp cut tag <refs_>` · effect: **write**

Add or remove tags on several cuts at once.

| Field | Type | Default | Description |
|---|---|---|---|
| `--refs` | list[string] | required | Cut refs |
| `--add` | list[string] | None |  |
| `--remove` | list[string] | None |  |

```
recomp cut tag C3 C9 --add sacrifice --remove draft
```

### cut.trim

`recomp cut trim <ref>` · effect: **write**

Move a cut's edges (absolute or relative); optionally re-snap.

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required |  |
| `--start` | string | None | New start: absolute time, or +0.3 / -1.2 relative |
| `--end` | string | None | New end: absolute time, or relative |
| `--snap` | string | 'none' | Snap the new edges: words \| shots \| words+shots \| none |

```
recomp cut trim C17 --start +0.3 --end -1.2
```

## doctor

### doctor

`recomp doctor` · effect: **read**

Check the tools, worker environment, models, disk and (optionally) network this app needs.

| Field | Type | Default | Description |
|---|---|---|---|
| `--net` | boolean | False | Also check network endpoints (Openverse, YouTube, edge-tts) |
| `--worker` | boolean | True | Check the worker python and its packages |

```
recomp doctor
recomp doctor --net
```

## job

### job.cancel

`recomp job cancel <ref>` · effect: **write**

Cancel a queued or running job.

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required | Job ref, e.g. job7 |

### job.list

`recomp job list` · effect: **read**

Jobs, newest first: open ones plus anything finished in the last hour.

| Field | Type | Default | Description |
|---|---|---|---|
| `--status` | string | None | queued, running, done, failed, cancelled |
| `--all` | boolean | False | Include finished jobs older than an hour |
| `--limit` | integer | 30 |  |

### job.retry

`recomp job retry <ref>` · effect: **heavy**

Queue a failed or cancelled job again.

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required | Job ref, e.g. job7 |

### job.run

`recomp job run` · effect: **heavy** · hidden (viewer use)

Drain queued jobs in this process now (normally a background runner does this).

| Field | Type | Default | Description |
|---|---|---|---|
| `--lanes` | list[string] | None |  |

### job.show

`recomp job show <ref>` · effect: **read**

One job in full: params, progress, result or error.

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required | Job ref, e.g. job7 |

### job.tail

`recomp job tail <ref>` · effect: **read**

The end of a job's log.

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required |  |
| `--lines` | integer | 30 |  |

### job.wait

`recomp job wait <refs>` · effect: **read**

Wait for job(s) to finish, returning early at the timeout with their progress.

| Field | Type | Default | Description |
|---|---|---|---|
| `<refs>` | list[string] | required | Job ref(s) |
| `--timeout` | number | 60 | Return after this many seconds even if not finished |

```
recomp job wait job7 --timeout 90
```

## journey

### journey.add

`recomp journey add <journey> <cuts>` · effect: **write**

Add cuts to a journey (append, or insert before slot --at).

| Field | Type | Default | Description |
|---|---|---|---|
| `<journey>` | string | required |  |
| `<cuts>` | list[string] | required | Cut refs in order |
| `--at` | integer | None | Insert before this slot number (default: append) |
| `--section` | string | None | Section heading for the first added slot |

```
recomp journey add J1 C3 C9 C4
recomp journey add J1 C7 --at 2
```

### journey.delete

`recomp journey delete <journey>` · effect: **write**

Delete a journey (its cuts stay). Undo restores it.

| Field | Type | Default | Description |
|---|---|---|---|
| `<journey>` | string | required |  |

### journey.duplicate

`recomp journey duplicate <journey>` · effect: **write**

Copy a journey (slots, overlays and music) to try a variation.

| Field | Type | Default | Description |
|---|---|---|---|
| `<journey>` | string | required |  |

### journey.edit

`recomp journey edit <journey>` · effect: **write**

Change a journey's title, intent, description, language or status.

| Field | Type | Default | Description |
|---|---|---|---|
| `<journey>` | string | required |  |
| `--title` | string | None |  |
| `--intent` | string | None |  |
| `--description` | string | None |  |
| `--language` | string | None |  |
| `--status` | string | None | draft \| ready \| published |

### journey.from-search

`recomp journey from-search <query>` · effect: **write**

Draft a journey from search: whole-thought cuts for the best hits, in search order. Edit it afterwards.

| Field | Type | Default | Description |
|---|---|---|---|
| `<query>` | string | required |  |
| `--title` | string | None |  |
| `--limit` | integer | 8 | How many cuts |
| `--sources` | list[string] | None |  |
| `--min-s` | number | 15 |  |
| `--max-s` | number | 75 |  |

```
recomp journey from-search "forgiveness" --limit 8 --title "On forgiveness"
```

### journey.list

`recomp journey list` · effect: **read**

All journeys with slot counts and lengths.

| Field | Type | Default | Description |
|---|---|---|---|
| `--status` | string | None |  |

### journey.move

`recomp journey move <slot>` · effect: **write**

Move a slot to another position.

| Field | Type | Default | Description |
|---|---|---|---|
| `<slot>` | string | required | Slot ref, e.g. J1#4 |
| `--to` | integer | required | New position (1-based) |

```
recomp journey move J1#4 --to 1
```

### journey.new

`recomp journey new <title>` · effect: **write**

Start a journey (optionally with its first cuts).

| Field | Type | Default | Description |
|---|---|---|---|
| `<title>` | string | required |  |
| `--intent` | string | '' | What the journey is for, in a sentence |
| `--description` | string | '' |  |
| `--language` | string | 'en' |  |
| `--cuts` | list[string] | None | Cuts to start with, in order |

```
recomp journey new "Live long enough" --intent "What heroism costs" --cuts C4,C9,C2
```

### journey.remove

`recomp journey remove <slot>` · effect: **write**

Remove a slot from a journey (the cut itself stays).

| Field | Type | Default | Description |
|---|---|---|---|
| `<slot>` | string | required | Slot ref, e.g. J1#3 |

### journey.reorder

`recomp journey reorder <journey>` · effect: **write**

Reorder all slots at once.

| Field | Type | Default | Description |
|---|---|---|---|
| `<journey>` | string | required |  |
| `--order` | list[integer] | required | New order as current slot numbers, e.g. 3,1,2,4 |

```
recomp journey reorder J1 --order 3,1,2,4
```

### journey.section

`recomp journey section <journey> <heading>` · effect: **write**

Start a titled section at a slot (shown as a heading; long-form exports can show a card).

| Field | Type | Default | Description |
|---|---|---|---|
| `<journey>` | string | required |  |
| `<heading>` | string | required | Section heading ('' clears it) |
| `--at` | integer | required | The slot the section starts at |

```
recomp journey section J1 "The bargain" --at 3
```

### journey.show

`recomp journey show <journey>` · effect: **read**

A journey's timeline: slots (source span, output position, section), overlays, music, total length.

| Field | Type | Default | Description |
|---|---|---|---|
| `<journey>` | string | required |  |

```
recomp journey show J1
```

### journey.transition

`recomp journey transition <slot>` · effect: **write**

Set the transition *into* a slot.

| Field | Type | Default | Description |
|---|---|---|---|
| `<slot>` | string | required |  |
| `--type` | string | 'fade' | cut \| fade \| dip (to black) |
| `--dur` | number | 0.5 | Seconds |

```
recomp journey transition J1#3 --type fade --dur 0.6
```

### journey.trim-slot

`recomp journey trim-slot <slot>` · effect: **write**

Trim one slot inside its cut (the cut itself is unchanged; other journeys are unaffected).

| Field | Type | Default | Description |
|---|---|---|---|
| `<slot>` | string | required |  |
| `--start` | string | None | Source time, or +/− seconds relative to the cut's start ('reset' clears) |
| `--end` | string | None | Source time, or +/− relative to the cut's end ('reset' clears) |

```
recomp journey trim-slot J1#2 --start +1.5 --end -2
```

### journey.validate

`recomp journey validate <journey>` · effect: **read**

Check a journey before export: media available, sane lengths, labels, music licences, recipe structure.

| Field | Type | Default | Description |
|---|---|---|---|
| `<journey>` | string | required |  |

## op

### op.log

`recomp op log` · effect: **read**

The operation log, newest first: verb, actor, refs, summary and undo state.

| Field | Type | Default | Description |
|---|---|---|---|
| `--limit` | integer | 20 | How many ops to show (newest first) |
| `--actor` | string | None | Only ops by this actor: user, agent or machine |
| `--since` | string | None | Only ops newer than this, e.g. 10m, 2h, 90s |
| `--ref` | string | None | Only ops that touched this ref |

```
recomp op log --actor user --since 1h
```

### op.redo

`recomp op redo` · effect: **write**

Redo the most recently undone change(s).

| Field | Type | Default | Description |
|---|---|---|---|
| `--n` | integer | 1 | How many ops to undo |

### op.undo

`recomp op undo` · effect: **write**

Undo the most recent change(s). Refuses to undo a higher-precedence actor's work.

| Field | Type | Default | Description |
|---|---|---|---|
| `--n` | integer | 1 | How many ops to undo |

```
recomp op undo
recomp op undo --n 3
```

## overlay

### overlay.add

`recomp overlay add <target>` · effect: **write**

Add text over a journey or one slot: title card, lower third, pull quote, free text.

| Field | Type | Default | Description |
|---|---|---|---|
| `<target>` | string | required | Journey (J1: whole-journey overlay) or slot (J1#3) |
| `--kind` | string | 'text' | title \| lower_third \| quote \| text \| endcard \| section |
| `--text` | string | required | Text; use \n for a second line |
| `--at` | string | '0' | Seconds into the slot (or the journey) |
| `--dur` | number | None | Seconds shown (default depends on kind) |
| `--position` | string | None | top \| middle \| bottom (default by kind) |
| `--size` | number | None | Relative text size (1.0 = default) |

```
recomp overlay add J1 --kind title --text "Live long enough"
recomp overlay add J1#2 --kind quote --text "You either die a hero…" --at 1
```

### overlay.auto-lower-thirds

`recomp overlay auto-lower-thirds <journey>` · effect: **write**

Credit every slot on screen: who is speaking and where it is from (people · source (year)).

| Field | Type | Default | Description |
|---|---|---|---|
| `<journey>` | string | required |  |
| `--replace` | boolean | True | Replace lower thirds made earlier by this verb |
| `--template` | string | '{people}{title_sep}{source}' | Fields: {people} {source} {year} {creator} {cut} |

```
recomp overlay auto-lower-thirds J1
```

### overlay.edit

`recomp overlay edit <ref>` · effect: **write**

Change an overlay's text, timing, kind or style.

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required |  |
| `--text` | string | None |  |
| `--at` | string | None |  |
| `--dur` | number | None |  |
| `--kind` | string | None |  |
| `--position` | string | None |  |
| `--size` | number | None |  |

### overlay.list

`recomp overlay list <journey>` · effect: **read**

Overlays of a journey.

| Field | Type | Default | Description |
|---|---|---|---|
| `<journey>` | string | required |  |

### overlay.remove

`recomp overlay remove <ref>` · effect: **write**

Delete an overlay.

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required |  |

## project

### project.agent-kit

`recomp project agent-kit` · effect: **write**

(Re)install the agent kit into the project folder: AGENTS.md, CLAUDE.md, skills, .mcp.json.

| Field | Type | Default | Description |
|---|---|---|---|
| `--overwrite` | boolean | True | Overwrite existing kit files (your own CLAUDE.md notes below the marker are kept) |

### project.init

`recomp project init <path>` · effect: **write**

Create a project folder and make it the current project.

| Field | Type | Default | Description |
|---|---|---|---|
| `<path>` | string | required | Folder for the project (relative names go under projects_root) |
| `--name` | string | None | Display name (default: folder name) |
| `--kind` | string | 'mixed' | movies, channel, speaker, topic or mixed |
| `--languages` | list[string] | None | Working languages, e.g. en,am |
| `--agent-kit` | boolean | True | Write AGENTS.md, CLAUDE.md, skills and .mcp.json into the folder |

```
recomp project init dark-knight --kind movies
recomp project init C:\Recomposer\projects\alex-oconnor --kind channel
```

### project.list

`recomp project list` · effect: **read**

Registered projects and which one is current.

### project.set

`recomp project set` · effect: **write**

Change the project's name, kind, languages or description.

| Field | Type | Default | Description |
|---|---|---|---|
| `--name` | string | None |  |
| `--kind` | string | None |  |
| `--languages` | list[string] | None |  |
| `--description` | string | None |  |

### project.show

`recomp project show` · effect: **read**

The current project's manifest and folder.

### project.use

`recomp project use <target>` · effect: **write**

Make a project the current one (by registered name or by folder).

| Field | Type | Default | Description |
|---|---|---|---|
| `<target>` | string | required | Project name (from `project list`) or folder |

## recipe

### recipe.export

`recomp recipe export <journey>` · effect: **write**

Write the recipe as JSON, a CMX3600 EDL or an OpenTimelineIO file (to finish in Resolve/Premiere/Kdenlive).

| Field | Type | Default | Description |
|---|---|---|---|
| `<journey>` | string | required |  |
| `--format` | string | 'json' | json \| edl (CMX3600) \| otio (OpenTimelineIO) |
| `--out` | string | None | Write to this file (default: recipes/ folder) |

```
recomp recipe export J1 --format otio
```

### recipe.import

`recomp recipe import <file>` · effect: **write**

Rebuild a journey from a recipe file: link sources are added; file sources are matched by fingerprint or title.

| Field | Type | Default | Description |
|---|---|---|---|
| `<file>` | string | required | A recipe JSON file |

### recipe.show

`recomp recipe show <journey>` · effect: **read**

The journey as a recipe (portable JSON: sources, timecodes, overlays, music, credits).

| Field | Type | Default | Description |
|---|---|---|---|
| `<journey>` | string | required |  |

```
recomp recipe show J1
```

## search

### search

`recomp search <query>` · effect: **read**

Find where something is said, across all sources. Each hit has its chapter, surrounding lines and a ready `cut add` command.

| Field | Type | Default | Description |
|---|---|---|---|
| `<query>` | string | required | Words or "exact phrases" |
| `--sources` | list[string] | None | Limit to these source refs |
| `--chapter` | string | None | Limit to one chapter |
| `--speaker` | string | None | Limit to a speaker label or person name |
| `--all-transcripts` | boolean | False | Search every transcript, not only the primary ones |
| `--context` | integer | 1 | Segments of context before and after |
| `--limit` | integer | 20 |  |
| `--mode` | string | 'auto' | all (every word), any, or auto (all, then any if nothing found) |

```
recomp search "free will"
recomp search forgiveness --sources S1,S4 --limit 10
recomp search "everlasting life" --speaker "Pastor Chris"
```

## setup

### setup.shim

`recomp setup shim` · effect: **write**

Write `recomp` launchers (sh and .cmd) into a folder on PATH so agents can call `recomp` anywhere.

| Field | Type | Default | Description |
|---|---|---|---|
| `--bin-dir` | string | 'C:\\Users\\pc\\bin' | Folder on PATH for the launchers |

## source

### source.add

`recomp source add <target>` · effect: **write**

Add media: files are referenced in place (never copied); subtitles beside them are imported; processing jobs are queued. Links and channels: see the recomp-ingest skill.

| Field | Type | Default | Description |
|---|---|---|---|
| `<target>` | string | required | File, folder, glob (quote it) or link |
| `--title` | string | None | Title (default: parsed from the file name / link metadata) |
| `--year` | integer | None |  |
| `--creator` | string | None | Director, channel, speaker… |
| `--language` | string | None | Spoken language code (default: project language) |
| `--subs` | string | None | Subtitle file to import (default: find sidecars and embedded) |
| `--subtitles` | boolean | True | Import sidecar/embedded subtitles automatically |
| `--process` | boolean | True | Queue audio, peaks, shots and thumbnails jobs |
| `--jobs` | list[string] | None | Which processing jobs |
| `--limit` | integer | None | Links: how many entries of a channel/playlist to list |
| `--match` | string | None | Links: only entries whose title matches (regex, case-insensitive) |
| `--since` | string | None | Links: only entries newer than e.g. 90d |
| `--pick` | list[string] | None | Links: add these entries from the last pick list (numbers or ids) |

```
recomp source add "D:\Recomp\Video\The.Dark.Knight*.mp4"
recomp source add D:\Movies --jobs audio,peaks
recomp source add https://www.youtube.com/@CosmicSkeptic/videos --limit 30
recomp source add --pick 2,5,9
```

### source.list

`recomp source list` · effect: **read**

Sources with duration, transcript and counts.

| Field | Type | Default | Description |
|---|---|---|---|
| `--kind` | string | None | file or link |
| `--match` | string | None | Title contains |

### source.process

`recomp source process <ref>` · effect: **heavy**

(Re)queue processing jobs for a source: audio, peaks, shots, thumbs.

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required |  |
| `--jobs` | list[string] | None |  |
| `--force` | boolean | False | Redo even if already done |

```
recomp source process S1 --jobs shots --force
```

### source.relink

`recomp source relink <ref> <path>` · effect: **write**

Point a source at its file's new location (checked by fingerprint).

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required |  |
| `<path>` | string | required |  |
| `--force` | boolean | False | Accept a file whose fingerprint differs |

### source.remove

`recomp source remove <ref>` · effect: **write**

Remove a source from the project (the media file itself is never touched). Its chapters and cuts go too; undo restores those, but transcripts/shots must be re-imported.

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required | Source ref, e.g. S1 |

### source.rights

`recomp source rights <ref>` · effect: **write**

Set a source's credit and rights details (used for attribution in every export).

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required |  |
| `--owner` | string | None | Rights holder, e.g. the studio or channel |
| `--notice` | string | None | Credit line shown in exports |
| `--licence` | string | None |  |
| `--url` | string | None | Canonical page for the work |
| `--title` | string | None |  |
| `--year` | integer | None |  |
| `--creator` | string | None |  |

```
recomp source rights S1 --owner "Warner Bros." --notice "The Dark Knight (2008), Warner Bros."
```

### source.show

`recomp source show <ref>` · effect: **read**

Everything about one source: media facts, rights, transcripts, stages, counts, files.

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required | Source ref, e.g. S1 |

### source.status

`recomp source status` · effect: **read**

Pipeline stage per source (probe, audio, peaks, shots, thumbs, transcript…) and running jobs.

## transcript

### transcript.align

`recomp transcript align <ref>` · effect: **write**

Give a subtitle transcript per-word timings: matched against ASR words, or spread proportionally.

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required | Transcript (or source → primary) to give word timings |
| `--using` | string | None | ASR transcript with word timings (default: newest ASR of the source) |
| `--method` | string | 'auto' | auto (asr if available, else proportional), asr, proportional |

```
recomp transcript align S1.t1 --using S1.t2
```

### transcript.asr

`recomp transcript asr <ref>` · effect: **heavy**

Transcribe a source locally (faster-whisper with word timings) as a job.

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required | Source ref |
| `--language` | string | None | Spoken language (default: detect) |
| `--from` | string | None | Only this range: start |
| `--to` | string | None | Only this range: end |
| `--model` | string | None | Model repo/path (default: config worker.asr_model) |
| `--engine` | string | 'whisper' | whisper or ctc (character models, e.g. badrex/Ethio-ASR-amharic) |
| `--primary` | boolean | None | Make the result primary (default: only if none) |
| `--allow-download` | boolean | False | Allow the worker to download a missing model |

```
recomp transcript asr S3
recomp transcript asr S1 --from 10:00 --to 20:00 --language en
```

### transcript.edit-segment

`recomp transcript edit-segment <ref> <idx>` · effect: **write**

Correct one segment's text, timing or speaker (word timings are re-spread if the text changes).

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required | Source or transcript ref |
| `<idx>` | integer | required | Segment index (#idx in transcript read) |
| `--text` | string | None |  |
| `--start` | string | None |  |
| `--end` | string | None |  |
| `--speaker` | string | None |  |

```
recomp transcript edit-segment S1 412 --text "Why so serious?"
```

### transcript.import

`recomp transcript import <ref> <file>` · effect: **write**

Import a subtitle or caption file as a transcript of a source.

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required | Source ref |
| `<file>` | string | required | Subtitle/caption file (.srt .vtt .ass .json3) |
| `--language` | string | None |  |
| `--primary` | boolean | None | Make it the primary transcript (default: only if none) |
| `--offset` | string | None | Shift all times by this much on import (e.g. -1.5) |

```
recomp transcript import S1 film.en.srt
```

### transcript.list

`recomp transcript list <ref>` · effect: **read**

Transcripts of a source: origin, language, primary, word timing, sync result.

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required | Source ref (or a transcript ref) |

### transcript.outline

`recomp transcript outline <ref>` · effect: **read**

The shape of a source before reading it: speech density, long silences, shot rhythm, creator/embedded and existing chapters, in 5-minute buckets.

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required | Source ref (or a transcript ref) |

```
recomp transcript outline S1
```

### transcript.read

`recomp transcript read <ref>` · effect: **read**

Read a window of a transcript as compact timed lines `#idx [hh:mm:ss.s] text` (cheap on context).

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required | Source (primary transcript) or transcript ref |
| `--from` | string | None | Start time |
| `--to` | string | None | End time |
| `--chapter` | string | None | Read one chapter, e.g. S1.c4 |
| `--around` | string | None | Centre time; reads ± --span seconds |
| `--span` | number | 45 | Half-width for --around |
| `--limit` | integer | 250 | Max segments |
| `--cursor` | integer | None | Continue from this segment index (from next_cursor) |
| `--words` | boolean | False | Include per-word timings |

```
recomp transcript read S1 --from 10:00 --to 15:00
recomp transcript read S1 --chapter S1.c4
recomp transcript read S1 --around 1:02:10 --span 30
```

### transcript.set-primary

`recomp transcript set-primary <ref>` · effect: **write**

Make a transcript the one search, reading and captions use for its source.

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required | Transcript ref |

### transcript.shift

`recomp transcript shift <ref> <by>` · effect: **write**

Shift every segment and word of a transcript in time (its own inverse: shift back to undo).

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required |  |
| `<by>` | string | required | Seconds to add to every time (negative = earlier) |

```
recomp transcript shift S1.t1 -1.5
```

### transcript.sync-check

`recomp transcript sync-check <ref>` · effect: **heavy**

Measure whether subtitles match the speech (offset and drift); --fix shifts them. Uses an existing ASR transcript if there is one, otherwise runs ASR on three 60-second windows (a job).

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required | Source or transcript ref |
| `--against` | string | None | Use this ASR transcript instead of running ASR on 3 windows |
| `--fix` | boolean | False | Shift the transcript by the measured offset |

```
recomp transcript sync-check S1
recomp transcript sync-check S1 --fix
```

## ui

### ui.answer

`recomp ui answer <id> <answer>` · effect: **write** · hidden (viewer use)

Answer a pinned question (the viewer calls this).

| Field | Type | Default | Description |
|---|---|---|---|
| `<id>` | string | required | Ask id |
| `<answer>` | string | required | The answer |

### ui.ask

`recomp ui ask <text>` · effect: **write**

Pin a question for the user in the viewer. Answers show up in `recomp ui notes`.

| Field | Type | Default | Description |
|---|---|---|---|
| `<text>` | string | required | The question for the user |
| `--refs` | list[string] | None | Refs the question is about |
| `--options` | list[string] | None | Optional answer choices |

```
recomp ui ask "Keep the laugh at the end of C4?" --refs C4 --options keep,trim
```

### ui.note

`recomp ui note <text>` · effect: **write** · hidden (viewer use)

Leave a note for the agent (the viewer calls this).

| Field | Type | Default | Description |
|---|---|---|---|
| `<text>` | string | required | Note for the agent |
| `--refs` | list[string] | None |  |

### ui.notes

`recomp ui notes` · effect: **read**

Open questions you pinned, the user's answers, and notes the user left for you.

| Field | Type | Default | Description |
|---|---|---|---|
| `--mark-seen` | boolean | True | Mark the user's notes as seen |

### ui.select

`recomp ui select` · effect: **write** · hidden (viewer use)

Record a selection (the viewer calls this as the user selects).

| Field | Type | Default | Description |
|---|---|---|---|
| `--source` | string | None | Source ref, e.g. S1 |
| `--start` | string | None | Range start (time) |
| `--end` | string | None | Range end (time) |
| `--refs` | list[string] | None | Selected refs (cuts, slots, chapters) |
| `--t` | string | None | Playhead time |

### ui.selection

`recomp ui selection` · effect: **read**

What the user currently has selected in the viewer (a time range on a source, and/or refs).

### ui.show

`recomp ui show <ref>` · effect: **write**

Move the user's viewer to a ref (and optionally a time). Use it to point at what you mean.

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required | What to show: S1, S1.c3, C17, J2, J2#3, X1 … |
| `--at` | string | None | Time to seek to (source time for sources/chapters/cuts) |
| `--play` | boolean | False | Start playing |

```
recomp ui show C17
recomp ui show S1 --at 1:02:10
```

## version

### version

`recomp version` · effect: **read**

Version and where things are.
