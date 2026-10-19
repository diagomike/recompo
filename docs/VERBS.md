# Verbs

Generated from the registry by `python scripts/gen_docs.py`. Every verb is available as
`recomp <noun> <verb>` (CLI), as the MCP tool `<noun>_<verb>`, and as
`POST /api/verb/<noun>.<verb>` on the studio server. All return the same JSON envelope.

Effects: `read` (no changes) · `write` (undoable op) · `heavy` (starts a job) ·
`network` (talks to the internet) · `publish` (shares beyond this machine).

| Noun | Verbs |
|---|---|
| `cache` | [`cache.prune`](#cacheprune), [`cache.size`](#cachesize) |
| `channel` | [`channel.set`](#channelset), [`channel.show`](#channelshow), [`channel.stats`](#channelstats) |
| `chapter` | [`chapter.add`](#chapteradd), [`chapter.auto`](#chapterauto), [`chapter.edit`](#chapteredit), [`chapter.list`](#chapterlist), [`chapter.merge`](#chaptermerge), [`chapter.remove`](#chapterremove), [`chapter.seed`](#chapterseed), [`chapter.set`](#chapterset), [`chapter.split`](#chaptersplit) |
| `config` | [`config.get`](#configget), [`config.set`](#configset) |
| `context` | [`context`](#context) |
| `cut` | [`cut.add`](#cutadd), [`cut.edit`](#cutedit), [`cut.list`](#cutlist), [`cut.merge`](#cutmerge), [`cut.remove`](#cutremove), [`cut.show`](#cutshow), [`cut.split`](#cutsplit), [`cut.suggest`](#cutsuggest), [`cut.tag`](#cuttag), [`cut.trim`](#cuttrim) |
| `doctor` | [`doctor`](#doctor) |
| `export` | [`export.caption-sheet`](#exportcaption-sheet), [`export.check`](#exportcheck), [`export.cuts`](#exportcuts), [`export.multitrack`](#exportmultitrack), [`export.run`](#exportrun), [`export.show`](#exportshow), [`export.status`](#exportstatus) |
| `find` | [`find.creators`](#findcreators) |
| `follow` | [`follow.add`](#followadd), [`follow.backfill`](#followbackfill), [`follow.check`](#followcheck), [`follow.edit`](#followedit), [`follow.list`](#followlist), [`follow.remove`](#followremove) |
| `hub` | [`hub.comment`](#hubcomment), [`hub.comments`](#hubcomments), [`hub.feed`](#hubfeed), [`hub.follow`](#hubfollow), [`hub.fork`](#hubfork), [`hub.link-post`](#hublink-post), [`hub.login`](#hublogin), [`hub.logout`](#hublogout), [`hub.publish`](#hubpublish), [`hub.pull`](#hubpull), [`hub.show`](#hubshow), [`hub.vote`](#hubvote), [`hub.whoami`](#hubwhoami) |
| `inbox` | [`inbox.dismiss`](#inboxdismiss), [`inbox.list`](#inboxlist), [`inbox.take`](#inboxtake) |
| `job` | [`job.cancel`](#jobcancel), [`job.list`](#joblist), [`job.retry`](#jobretry), [`job.run`](#jobrun), [`job.show`](#jobshow), [`job.tail`](#jobtail), [`job.wait`](#jobwait) |
| `journey` | [`journey.add`](#journeyadd), [`journey.delete`](#journeydelete), [`journey.duplicate`](#journeyduplicate), [`journey.edit`](#journeyedit), [`journey.from-search`](#journeyfrom-search), [`journey.from-topic`](#journeyfrom-topic), [`journey.guide`](#journeyguide), [`journey.list`](#journeylist), [`journey.move`](#journeymove), [`journey.new`](#journeynew), [`journey.remove`](#journeyremove), [`journey.reorder`](#journeyreorder), [`journey.review`](#journeyreview), [`journey.section`](#journeysection), [`journey.show`](#journeyshow), [`journey.transition`](#journeytransition), [`journey.trim-slot`](#journeytrim-slot), [`journey.validate`](#journeyvalidate) |
| `lang` | [`lang.clear`](#langclear), [`lang.edit`](#langedit), [`lang.lines`](#langlines), [`lang.replace`](#langreplace), [`lang.say`](#langsay), [`lang.status`](#langstatus), [`lang.translate`](#langtranslate), [`lang.voices`](#langvoices) |
| `library` | [`library.list`](#librarylist), [`library.remove`](#libraryremove), [`library.search`](#librarysearch), [`library.show`](#libraryshow) |
| `music` | [`music.bed-add`](#musicbed-add), [`music.bed-edit`](#musicbed-edit), [`music.bed-remove`](#musicbed-remove), [`music.get`](#musicget), [`music.library-add`](#musiclibrary-add), [`music.list`](#musiclist), [`music.search`](#musicsearch) |
| `op` | [`op.log`](#oplog), [`op.redo`](#opredo), [`op.undo`](#opundo) |
| `overlay` | [`overlay.add`](#overlayadd), [`overlay.auto-lower-thirds`](#overlayauto-lower-thirds), [`overlay.edit`](#overlayedit), [`overlay.list`](#overlaylist), [`overlay.remove`](#overlayremove) |
| `post` | [`post.cancel`](#postcancel), [`post.link`](#postlink), [`post.open`](#postopen), [`post.plan`](#postplan), [`post.queue`](#postqueue) |
| `preview` | [`preview`](#preview) |
| `profile` | [`profile.edit`](#profileedit), [`profile.list`](#profilelist), [`profile.new`](#profilenew), [`profile.show`](#profileshow) |
| `project` | [`project.agent-kit`](#projectagent-kit), [`project.backup`](#projectbackup), [`project.checklist`](#projectchecklist), [`project.forget`](#projectforget), [`project.init`](#projectinit), [`project.list`](#projectlist), [`project.reveal`](#projectreveal), [`project.set`](#projectset), [`project.show`](#projectshow), [`project.use`](#projectuse) |
| `recipe` | [`recipe.export`](#recipeexport), [`recipe.import`](#recipeimport), [`recipe.show`](#recipeshow) |
| `search` | [`search`](#search) |
| `setup` | [`setup.shim`](#setupshim) |
| `source` | [`source.add`](#sourceadd), [`source.browse`](#sourcebrowse), [`source.fetch-audio`](#sourcefetch-audio), [`source.fetch-video`](#sourcefetch-video), [`source.list`](#sourcelist), [`source.process`](#sourceprocess), [`source.refresh`](#sourcerefresh), [`source.relink`](#sourcerelink), [`source.remove`](#sourceremove), [`source.rights`](#sourcerights), [`source.show`](#sourceshow), [`source.status`](#sourcestatus) |
| `speaker` | [`speaker.assign`](#speakerassign), [`speaker.diarize`](#speakerdiarize), [`speaker.list`](#speakerlist), [`speaker.match`](#speakermatch), [`speaker.merge`](#speakermerge), [`speaker.name`](#speakername), [`speaker.people`](#speakerpeople), [`speaker.unlink`](#speakerunlink) |
| `topic` | [`topic.add`](#topicadd), [`topic.brief`](#topicbrief), [`topic.edit`](#topicedit), [`topic.list`](#topiclist), [`topic.remove`](#topicremove), [`topic.scan`](#topicscan), [`topic.suggest`](#topicsuggest) |
| `transcript` | [`transcript.align`](#transcriptalign), [`transcript.asr`](#transcriptasr), [`transcript.clean`](#transcriptclean), [`transcript.delete`](#transcriptdelete), [`transcript.edit`](#transcriptedit), [`transcript.edit-segment`](#transcriptedit-segment), [`transcript.export`](#transcriptexport), [`transcript.fetch-captions`](#transcriptfetch-captions), [`transcript.import`](#transcriptimport), [`transcript.list`](#transcriptlist), [`transcript.merge`](#transcriptmerge), [`transcript.outline`](#transcriptoutline), [`transcript.read`](#transcriptread), [`transcript.replace`](#transcriptreplace), [`transcript.resegment`](#transcriptresegment), [`transcript.set-primary`](#transcriptset-primary), [`transcript.shift`](#transcriptshift), [`transcript.split`](#transcriptsplit), [`transcript.sync-check`](#transcriptsync-check) |
| `trends` | [`trends.channel`](#trendschannel), [`trends.search`](#trendssearch), [`trends.youtube`](#trendsyoutube) |
| `ui` | [`ui.answer`](#uianswer), [`ui.ask`](#uiask), [`ui.note`](#uinote), [`ui.notes`](#uinotes), [`ui.select`](#uiselect), [`ui.selection`](#uiselection), [`ui.show`](#uishow) |
| `version` | [`version`](#version) |
| `worker` | [`worker.status`](#workerstatus) |

## cache

### cache.prune

`recomp cache prune` · effect: **write**

Delete the oldest render intermediates until the cache fits (exports are untouched).

| Field | Type | Default | Description |
|---|---|---|---|
| `--max-gb` | number | None | Keep the render cache under this size (default: config render.cache_max_gb) |

### cache.size

`recomp cache size` · effect: **read**

Disk used by caches (render intermediates, frames, thumbnails, peaks) and exports.

## channel

### channel.set

`recomp channel set` · effect: **write**

Name the channel you post to (one channel; a placeholder is used until you do).

| Field | Type | Default | Description |
|---|---|---|---|
| `--name` | string | None | What the channel is called |
| `--platform` | string | None | youtube, tiktok or instagram |
| `--handle` | string | None | @handle |
| `--url` | string | None |  |

```
recomp channel set --name "Ideas in a minute" --handle @ideasinaminute --platform youtube
```

### channel.show

`recomp channel show` · effect: **read**

Your channel (or the placeholder), its imported numbers and the post counts.

### channel.stats

`recomp channel stats` · effect: **write**

Your own channel's numbers (read-only): import a YouTube Studio CSV or read the public totals with your API key.
Posts you linked get their video's row. Nobody else's numbers are read (D-22).

| Field | Type | Default | Description |
|---|---|---|---|
| `--csv` | string | None | A YouTube Studio export (Analytics › Advanced › Export › Table data.csv) |
| `--api` | boolean | False | Read the channel's public totals with your YOUTUBE_API_KEY (read-only) |

```
recomp channel stats --csv C:\Users\me\Downloads\Table data.csv
recomp channel stats --api
```

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
| `--journey` | string | None | Also append the new cut to this journey (e.g. J1) |

```
recomp cut add S1 --quote-start "You either die a hero" --quote-end "become the villain" --title "Live long enough" --why "Harvey's thesis" --tags fate,heroism
recomp cut add S1 --from 01:02:10.5 --to 01:02:55 --snap words+shots
recomp cut add S1 --segments 412..430
recomp cut add S2 --from 3:10 --to 3:42 --why "the turn" --journey J1   # cut straight into a journey
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
| `--journey` | string | None | Only cuts in this journey |
| `--min` | number | None | Shortest, in seconds |
| `--max` | number | None | Longest, in seconds |
| `--by` | string | None | Made by: user, agent or machine |
| `--rating` | integer | None | At least this rating |
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

## export

### export.caption-sheet

`recomp export caption-sheet <journey>` · effect: **write**

One PNG of a journey's longest captions as they will be burned in (a profile, a language): check width in seconds, no render.

| Field | Type | Default | Description |
|---|---|---|---|
| `<journey>` | string | required |  |
| `--profile` | string | 'shorts' | Profile whose caption box to show |
| `--lang` | string | None | Language (default: the journey's) |
| `--count` | integer | 8 | How many caption screens (the longest lines first) |
| `--out` | string | None | PNG to write (default: exports/sheets/<J>-<profile>-<lang>.png) |

```
recomp export caption-sheet J1 --profile shorts --lang am
recomp profile edit shorts --caption-lang am:max_chars=20 && recomp export caption-sheet J1 --lang am
```

### export.check

`recomp export check <ref>` · effect: **write**

Re-run the automatic checks on an export.

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required |  |

### export.cuts

`recomp export cuts <cuts>` · effect: **heavy**

Export individual cuts (one video each) with their own credits.

| Field | Type | Default | Description |
|---|---|---|---|
| `<cuts>` | list[string] | required |  |
| `--profile` | string | 'clip' |  |

```
recomp export cuts C4 C9 --profile clip
```

### export.multitrack

`recomp export multitrack <journey>` · effect: **write**

One MP4 with every language's audio track and subtitle track, from finished exports (no re-render).
Use a profile with captions as sidecar (not burned) so the picture suits every language.

| Field | Type | Default | Description |
|---|---|---|---|
| `<journey>` | string | required |  |
| `--profile` | string | 'landscape' | Profile whose finished exports to combine |
| `--langs` | list[string] | required | Languages to include; the first one's picture is used |

```
recomp export multitrack J1 --profile landscape --langs en,am,sw,fr
```

### export.run

`recomp export run <journey>` · effect: **heavy**

Render a journey in every profile × language asked for (jobs). Outputs land in exports/<journey>/<profile>-<lang>/.

| Field | Type | Default | Description |
|---|---|---|---|
| `<journey>` | string | required |  |
| `--profiles` | list[string] | None |  |
| `--langs` | list[string] | None | Languages (default: the journey's) |
| `--dub` | boolean | True | Dub languages other than the journey's (needs translations); false = subtitles only |

```
recomp export run J1 --profiles shorts,landscape
recomp export run J1 --profiles shorts --langs en,am,sw,fr
```

### export.show

`recomp export show <ref>` · effect: **read**

One export in full: files, checks and the ready-to-paste description.

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required |  |

### export.status

`recomp export status <of>` · effect: **read**

Exports with status, outputs and failed checks (newest first).

| Field | Type | Default | Description |
|---|---|---|---|
| `<of>` | string | None | Only exports of this journey or cut |
| `--limit` | integer | 40 |  |

## find

### find.creators

`recomp find creators <query>` · effect: **network**

Find channels, podcasts and a person's appearances to follow. Each result says how its transcripts can be had
(published, lex, captions, asr); `recomp follow add <n>` follows result n.

| Field | Type | Default | Description |
|---|---|---|---|
| `<query>` | string | required | A subject, a channel or show name, or a person |
| `--kind` | string | 'all' | channels, podcasts, person or all |
| `--limit` | integer | 8 | Results per kind |
| `--routes` | boolean | True | Check which podcasts publish transcripts (reads the start of each feed) |

```
recomp find creators "philosophy podcast"
recomp find creators "Alex O'Connor" --kind person
recomp find creators "Lex Fridman" --kind podcasts
```

## follow

### follow.add

`recomp follow add <target>` · effect: **network**

Follow a creator or show: their YouTube channel and/or podcast feed, for the projects named. New posts land in
the inbox on `follow check` (and every 2 h while the studio runs).

| Field | Type | Default | Description |
|---|---|---|---|
| `<target>` | string | required | @handle or channel link, a podcast feed URL, a number from the last `find creators`, or a name |
| `--project` | list[string] | None | Projects this follow feeds (default: the current one) |
| `--name` | string | None | What to call it (default: the channel or show title) |
| `--person` | string | None | The person (host) this follow is about, e.g. "Alex O'Connor" |
| `--podcast` | string | None | Their podcast: feed URL or show name (looked up on iTunes) |
| `--appearances` | boolean | False | Also watch for the person as a guest on other channels |
| `--only` | string | 'videos' | videos, shorts or all |
| `--match` | string | None | Only items whose title matches (regex, case-insensitive) |
| `--rights` | string | 'private' | campaign, permitted or private (D-23); applies to sources it brings in |
| `--evidence` | string | None | Link to the clipping program's terms or the creator's permission |
| `--note` | string | '' |  |

```
recomp follow add @CosmicSkeptic --project alex-oconnor --person "Alex O'Connor" --podcast "Within Reason"
recomp follow add https://lexfridman.com/feed/podcast --project ai-and-ideas --name "Lex Fridman"
recomp follow add 3 --project ai-and-ideas
```

### follow.backfill

`recomp follow backfill <ref>` · effect: **network**

The back catalogue's transcripts (text only, no video) into the studio library, so "what did they say before"
is a search: `recomp library search "…"`. Resumable: each run fetches up to --limit more.

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required | Follow ref or name |
| `--since` | string | None | How far back: 2y, 18m, 90d or a date (default research.backfill_since) |
| `--limit` | integer | 20 | Transcripts to fetch in this run (run again to continue) |
| `--captions` | boolean | True | For YouTube-only creators, fetch the videos' captions (one request each) |

```
recomp follow backfill F2
recomp follow backfill "Lex Fridman" --since 2024-01-01 --limit 50
```

### follow.check

`recomp follow check` · effect: **network**

Look for new posts from followed creators; new ones go to the inbox of the follow's first project.
A follow's first check takes only the newest few (`research.first_check_items`) and marks the rest as seen.

| Field | Type | Default | Description |
|---|---|---|---|
| `--follow` | list[string] | None | Only these follows (default: all) |
| `--first` | integer | None | On a follow's first check, how many of the newest items to put in the inbox |

```
recomp follow check
recomp follow check --follow F2
```

### follow.edit

`recomp follow edit <ref>` · effect: **write**

Change a follow: name, person, projects, podcast feed, appearances, title filter, rights, note.

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required | Follow ref or name |
| `--name` | string | None |  |
| `--person` | string | None |  |
| `--project` | list[string] | None | Replace the projects it feeds |
| `--podcast` | string | None | Set the podcast feed (URL or show name) |
| `--appearances` | boolean | None |  |
| `--only` | string | None |  |
| `--match` | string | None | Title filter (regex); "" clears it |
| `--rights` | string | None | campaign, permitted or private |
| `--evidence` | string | None |  |
| `--note` | string | None |  |

```
recomp follow edit F1 --project alex-oconnor,ai-and-ideas
recomp follow edit F2 --match "AI|conscious"
```

### follow.list

`recomp follow list` · effect: **read**

Followed creators and shows: feeds, transcript route, new inbox items, library size, last check.

| Field | Type | Default | Description |
|---|---|---|---|
| `--project` | string | None | Only follows feeding this project |

```
recomp follow list
recomp follow list --project alex-oconnor
```

### follow.remove

`recomp follow remove <ref>` · effect: **write**

Stop following. Its inbox items go too (undo restores them); library transcripts stay unless --library.

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required |  |
| `--library` | boolean | False | Also drop its transcripts from the library |

## hub

### hub.comment

`recomp hub comment <recipe> <text>` · effect: **publish**

Comment on a recipe (or reply to a comment).

| Field | Type | Default | Description |
|---|---|---|---|
| `<recipe>` | string | required |  |
| `<text>` | string | required |  |
| `--reply-to` | string | None |  |

### hub.comments

`recomp hub comments <recipe>` · effect: **network**

The comments on a recipe.

| Field | Type | Default | Description |
|---|---|---|---|
| `<recipe>` | string | required | Recipe id or hub URL |

### hub.feed

`recomp hub feed` · effect: **network**

Recipes on the hub: trending, new, top, from people you follow, or yours; filter by tag, source or text.

| Field | Type | Default | Description |
|---|---|---|---|
| `--kind` | string | 'trending' | trending \| new \| top \| following \| mine |
| `--tag` | string | None |  |
| `--source` | string | None | Source key, e.g. youtube:T_7Fm1VujEs |
| `--query` | string | None |  |
| `--limit` | integer | 20 |  |

### hub.follow

`recomp hub follow <handle>` · effect: **publish**

Follow (or unfollow) someone on the hub.

| Field | Type | Default | Description |
|---|---|---|---|
| `<handle>` | string | required |  |
| `--undo` | boolean | False |  |

### hub.fork

`recomp hub fork <recipe>` · effect: **network**

Fork a hub recipe into your hub account (private) and pull it into this project to edit.

| Field | Type | Default | Description |
|---|---|---|---|
| `<recipe>` | string | required | Recipe id or hub URL |

### hub.link-post

`recomp hub link-post <journey> <url>` · effect: **publish**

Record where you posted a video made from this journey, on the journey and on its hub recipe.

| Field | Type | Default | Description |
|---|---|---|---|
| `<journey>` | string | required |  |
| `<url>` | string | required | Where you posted the video |
| `--lang` | string | None |  |

```
recomp hub link-post J1 https://youtube.com/shorts/…
```

### hub.login

`recomp hub login` · effect: **network**

Sign in to a hub (or register on a local one) and keep the session token in the studio home.

| Field | Type | Default | Description |
|---|---|---|---|
| `--handle` | string | required |  |
| `--password` | string | None | Default: env RECOMP_HUB_PASSWORD. Agents: only for local test accounts. |
| `--register` | boolean | False | Create the account first (local hubs) |
| `--display` | string | None |  |
| `--url` | string | None | Hub URL (default config hub.url) |

### hub.logout

`recomp hub logout` · effect: **network**

Sign out of the configured hub.

### hub.publish

`recomp hub publish <journey>` · effect: **publish**

Share a journey's recipe on the hub (sources, timecodes, text, credits; never the media). Re-publishing adds a version.
Recipes are private by default. Making one public or unlisted when it uses private sources (D-23) first lists what
changes for each and asks the user "Do you have permission to share this?"; their answer and the time are saved on
the recipe version. The agent cannot answer that for them.

| Field | Type | Default | Description |
|---|---|---|---|
| `<journey>` | string | required |  |
| `--visibility` | string | 'private' | private (default) \| unlisted \| public |
| `--confirm` | boolean | False | The user's own answer: they have permission to share the private sources (and agree to publish on a non-local hub). Only after they said so in chat |

```
recomp hub publish J1
recomp hub publish J1 --visibility public
```

### hub.pull

`recomp hub pull <recipe>` · effect: **network**

Bring a hub recipe into this project as a journey (link sources are added; files are matched or marked missing).

| Field | Type | Default | Description |
|---|---|---|---|
| `<recipe>` | string | required | Recipe id or hub URL |

```
recomp hub pull http://127.0.0.1:8790/r/01K…
```

### hub.show

`recomp hub show <recipe>` · effect: **network**

A hub recipe: card, slots, credits, votes, comments count, linked posts.

| Field | Type | Default | Description |
|---|---|---|---|
| `<recipe>` | string | required | Recipe id or hub URL |

### hub.vote

`recomp hub vote <recipe> <value>` · effect: **publish**

Vote a recipe up or down (or clear your vote).

| Field | Type | Default | Description |
|---|---|---|---|
| `<recipe>` | string | required |  |
| `<value>` | string | 'up' | up \| down \| clear |

### hub.whoami

`recomp hub whoami` · effect: **read**

Who the studio is signed in as on the configured hub.

## inbox

### inbox.dismiss

`recomp inbox dismiss <refs>` · effect: **write**

Not for us: dismissed items stay out of the inbox (a later check does not bring them back).

| Field | Type | Default | Description |
|---|---|---|---|
| `<refs>` | list[string] | required |  |

```
recomp inbox dismiss I5 I6
```

### inbox.list

`recomp inbox list` · effect: **read**

New posts from followed creators, waiting to be taken into a project or dismissed.

| Field | Type | Default | Description |
|---|---|---|---|
| `--project` | string | None |  |
| `--status` | string | 'new' | new, taken, dismissed or all |
| `--follow` | string | None |  |
| `--limit` | integer | 50 |  |

```
recomp inbox list
recomp inbox list --status all --follow F1
```

### inbox.take

`recomp inbox take <refs>` · effect: **network**

Take new posts into a project: the source (metadata first), its transcript by the cheapest route, the creator's
chapters, and cut candidates on the project's themes (`project set --themes`).

| Field | Type | Default | Description |
|---|---|---|---|
| `<refs>` | list[string] | required | Inbox items |
| `--project` | string | None | Take into this project (default: the item's) |
| `--suggest` | boolean | True | Suggest cuts on the project's themes when a transcript is ready |

```
recomp inbox take I3
recomp inbox take I3 I4 --project ai-and-ideas
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

Change a journey's title, intent, description, language, status or destinations.

| Field | Type | Default | Description |
|---|---|---|---|
| `<journey>` | string | required |  |
| `--title` | string | None |  |
| `--intent` | string | None |  |
| `--description` | string | None |  |
| `--language` | string | None |  |
| `--status` | string | None | draft \| ready \| published |
| `--formats` | list[string] | None | Where it will go: shorts, landscape, square, hub |

```
recomp journey edit J1 --formats shorts,landscape
```

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

### journey.from-topic

`recomp journey from-topic <topic>` · effect: **write**

Draft "What my creators think about X" from a topic brief: chosen passages become cuts (with why and who speaks)
in this project, grouped into a section per creator (or per stance); episodes not yet here are added first.

| Field | Type | Default | Description |
|---|---|---|---|
| `<topic>` | string | required |  |
| `--passages` | list[string] | None | Passage ids from the brief, in order (default: the best two per creator) |
| `--by` | string | 'creator' | Sections per creator, or per stance (needs --stances) |
| `--stances` | list[string] | None | Stance per passage for --by stance, e.g. "p1=worried,p4=hopeful" |
| `--title` | string | None | Journey title (default: What my creators think about <topic>) |
| `--formats` | list[string] | None |  |
| `--lower-thirds` | boolean | True | Name who speaks on every slot |

```
recomp journey from-topic T1
recomp journey from-topic T1 --passages p2,p5,p7,p9,p11,p12
recomp journey from-topic T1 --by stance --stances "p2=worried,p5=worried,p9=hopeful"
```

### journey.guide

`recomp journey guide <journey>` · effect: **read**

The guided flow for a journey — purpose → gather → order → look → check → export — with each step's state and
next action. The viewer's journey studio shows the same steps (`recomp ui show J1 --filter step=look`).

| Field | Type | Default | Description |
|---|---|---|---|
| `<journey>` | string | required |  |

```
recomp journey guide J1
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

Start a journey (optionally with its first cuts and where it will go).

| Field | Type | Default | Description |
|---|---|---|---|
| `<title>` | string | required |  |
| `--intent` | string | '' | What the journey is for, in a sentence |
| `--description` | string | '' |  |
| `--language` | string | 'en' |  |
| `--cuts` | list[string] | None | Cuts to start with, in order |
| `--formats` | list[string] | None | Where it will go: shorts, landscape, square, hub (sets length goals and export profiles) |

```
recomp journey new "Live long enough" --intent "What heroism costs" --cuts C4,C9,C2
recomp journey new "On free will" --intent "Three answers in a minute" --formats shorts,hub
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

### journey.review

`recomp journey review <journey> <step>` · effect: **write**

Mark a judgement step of the guided flow as reviewed (the order reads well, the look is right, the check is
enough without a preview), so the guide moves on.

| Field | Type | Default | Description |
|---|---|---|---|
| `<journey>` | string | required |  |
| `<step>` | string | required | order \| look \| check |
| `--done` | boolean | True | false reopens the step |

```
recomp journey review J1 look
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

## lang

### lang.clear

`recomp lang clear <journey> <lang>` · effect: **write**

Remove translations of a journey (all, some keys, or only one method's drafts) so they can be redone.

| Field | Type | Default | Description |
|---|---|---|---|
| `<journey>` | string | required |  |
| `<lang>` | string | required |  |
| `--keys` | string | None | Comma list of keys (default: every line of the journey in this language) |
| `--method` | string | None | Only lines written this way: google, agent, user |

```
recomp lang clear J1 om --method google
recomp lang clear J1 am --keys seg:5121,seg:5122
```

### lang.edit

`recomp lang edit <journey> <lang>` · effect: **write**

Set one or many translated lines (a shorter line, a better word). Lines the user wrote are kept unless you are the user.

| Field | Type | Default | Description |
|---|---|---|---|
| `<journey>` | string | required |  |
| `<lang>` | string | required |  |
| `--key` | string | None | One line's key (from `lang lines`) |
| `--text` | string | None | Its new text |
| `--lines` | object | None | Many lines: {key: text} (use --input) |

```
recomp lang edit J1 am --key seg:5121 --text <new line>
recomp lang edit J1 am --input fixes.json   # {lines: {key: text}}
```

### lang.lines

`recomp lang lines <journey> <lang>` · effect: **read**

Every line of a journey in one language: source, translation, length against its speaking budget, who wrote it.

| Field | Type | Default | Description |
|---|---|---|---|
| `<journey>` | string | required |  |
| `<lang>` | string | required | Language code |
| `--over` | boolean | False | Only lines too long to speak in their time (to shorten) |
| `--missing` | boolean | False | Only lines with no translation yet |
| `--profile` | string | None | Also count caption screens per line under this profile's caption box |
| `--find` | string | None | Only lines whose source or translation contains this text |

```
recomp lang lines J1 am --over
recomp lang lines J1 am --profile shorts
recomp lang lines J1 fr --missing
```

### lang.replace

`recomp lang replace <lang> <find> <replace>` · effect: **write**

Find and replace across a language's translations: terminology, name spellings, punctuation.

| Field | Type | Default | Description |
|---|---|---|---|
| `<lang>` | string | required | Language code |
| `<find>` | string | required |  |
| `<replace>` | string | required |  |
| `--journey` | string | None | Only this journey's lines (default: every translation in the language) |
| `--regex` | boolean | False |  |
| `--case` | boolean | False |  |
| `--whole` | boolean | False | Whole words only |
| `--dry-run` | boolean | False |  |

```
recomp lang replace am ንቃተ-ህሊና 'ንቃተ ህሊና' --dry-run
recomp lang replace fr 'Anil Set' 'Anil Seth' --journey J1
```

### lang.say

`recomp lang say <text>` · effect: **network**

Voice a single line into the project's cache (to audition a voice).

| Field | Type | Default | Description |
|---|---|---|---|
| `<text>` | string | required |  |
| `--lang` | string | 'en' |  |
| `--voice` | string | None |  |

```
recomp lang say "ሰላም" --lang am
```

### lang.status

`recomp lang status <journey>` · effect: **read**

Translation coverage per language for a journey, and who wrote it (agent, google, user).

| Field | Type | Default | Description |
|---|---|---|---|
| `<journey>` | string | required |  |

### lang.translate

`recomp lang translate <journey>` · effect: **write**

Translate a journey's spoken lines, overlays and title. Get the template, write the translations yourself (best), or draft with --engine google.

| Field | Type | Default | Description |
|---|---|---|---|
| `<journey>` | string | required |  |
| `--to` | string | required | Target language code (am, sw, fr, om, …) |
| `--template` | boolean | False | Return the lines to translate (with timing budgets) instead of writing |
| `--translations` | object | None | {key: text} from the template (use --input) |
| `--engine` | string | None | google: draft every untranslated line with Google's web endpoint |
| `--overwrite` | boolean | False | With --engine: also replace lines translated before (never the user's) |

```
recomp lang translate J1 --to am --template
recomp lang translate J1 --to am --input am.json
recomp lang translate J1 --to sw --engine google
```

### lang.voices

`recomp lang voices <lang>` · effect: **network**

Voices available for a language (edge neural voices; the configured default is marked).

| Field | Type | Default | Description |
|---|---|---|---|
| `<lang>` | string | required |  |

```
recomp lang voices am
```

## library

### library.list

`recomp library list` · effect: **read**

Transcripts in the studio library: creator, episode, date, route, size.

| Field | Type | Default | Description |
|---|---|---|---|
| `--follow` | string | None |  |
| `--limit` | integer | 100 |  |

```
recomp library list --follow F2
```

### library.remove

`recomp library remove <refs>` · effect: **write**

Drop transcripts from the library (run `follow backfill` to fetch them again).

| Field | Type | Default | Description |
|---|---|---|---|
| `<refs>` | list[string] | required |  |

### library.search

`recomp library search <query>` · effect: **read**

Search what the followed creators said, across their back catalogue (same as `search --scope library`).

| Field | Type | Default | Description |
|---|---|---|---|
| `<query>` | string | required | Words or "exact phrases" |
| `--creator` | list[string] | None | Only these creators (follow person or name) |
| `--since` | string | None | Only episodes since (2y, 2024-01-01) |
| `--until` | string | None | Only episodes until (date) |
| `--limit` | integer | 20 |  |
| `--context` | integer | 1 |  |

```
recomp library search "copy itself"
recomp library search consciousness --creator "Lex Fridman" --since 2y
```

### library.show

`recomp library show <ref>` · effect: **read**

Read a library transcript (a stretch of it), with speakers and times.

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required |  |
| `--from` | string | None | Start time (1:02:03) |
| `--to` | string | None |  |
| `--limit` | integer | 80 | Lines to show |

```
recomp library show L4 --from 35:00 --to 37:00
```

## music

### music.bed-add

`recomp music bed-add <journey> <track>` · effect: **write**

Lay a music bed under a journey (ducked automatically under speech).

| Field | Type | Default | Description |
|---|---|---|---|
| `<journey>` | string | required |  |
| `<track>` | string | required | Music track ref, e.g. M1 |
| `--at` | string | '0' | Start on the journey timeline |
| `--dur` | number | None | Seconds (default: to the end of the journey) |
| `--track-in` | string | '0' | Start this far into the track |
| `--gain` | number | -16 | Level in dB (under speech it is ducked further) |
| `--duck` | number | -10 | How much to duck under speech, in dB |
| `--fade-in` | number | 1.5 |  |
| `--fade-out` | number | 2.5 |  |

```
recomp music bed-add J1 M1 --gain -18
```

### music.bed-edit

`recomp music bed-edit <ref>` · effect: **write**

Change a bed's timing, level or ducking.

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required | Bed ref, e.g. B1 |
| `--at` | string | None |  |
| `--dur` | number | None |  |
| `--track-in` | string | None |  |
| `--gain` | number | None |  |
| `--duck` | number | None |  |
| `--fade-in` | number | None |  |
| `--fade-out` | number | None |  |

### music.bed-remove

`recomp music bed-remove <ref>` · effect: **write**

Remove a music bed.

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required |  |

### music.get

`recomp music get <pick>` · effect: **network**

Download a track (from the last search, or by Openverse id) into the project's music folder, with its licence.

| Field | Type | Default | Description |
|---|---|---|---|
| `<pick>` | string | required | Number from the last search, or an Openverse audio id |

```
recomp music get 3
```

### music.library-add

`recomp music library-add <file>` · effect: **write**

Add a local audio file you have the rights to, with its licence (copied into the project).

| Field | Type | Default | Description |
|---|---|---|---|
| `<file>` | string | required |  |
| `--title` | string | '' |  |
| `--artist` | string | '' |  |
| `--licence` | string | required | Licence you hold it under, e.g. 'CC BY 4.0' or 'own work' |
| `--licence-url` | string | '' |  |
| `--url` | string | '' |  |

```
recomp music library-add "D:\Music\theme.mp3" --title Theme --artist Me --licence "own work"
```

### music.list

`recomp music list` · effect: **read**

Tracks in the project's library and the journeys they play under.

### music.search

`recomp music search <query>` · effect: **network**

Search open-licensed music (Openverse: Freesound, Jamendo, ccMixter…). Results are numbered for `music get`.

| Field | Type | Default | Description |
|---|---|---|---|
| `<query>` | string | required | Mood, genre or instrument, e.g. "melancholic piano" |
| `--licence` | string | 'safe' | safe (CC0, CC BY, public domain) \| commercial (adds BY-SA) \| any |
| `--min-s` | number | None | Shortest track in seconds |
| `--max-s` | number | None | Longest track in seconds |
| `--limit` | integer | 12 |  |

```
recomp music search "melancholic piano" --min-s 60
recomp music search "ambient strings" --licence any
```

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
| `--studio` | boolean | False | The studio store's log (follows, inbox, library, topics) instead of the project's |

```
recomp op log --actor user --since 1h
recomp op log --studio
```

### op.redo

`recomp op redo` · effect: **write**

Redo the most recently undone change(s).

| Field | Type | Default | Description |
|---|---|---|---|
| `--n` | integer | 1 | How many ops to undo |
| `--studio` | boolean | False | Undo in the studio store (follows, inbox, library, topics) |

### op.undo

`recomp op undo` · effect: **write**

Undo the most recent change(s). Refuses to undo a higher-precedence actor's work.

| Field | Type | Default | Description |
|---|---|---|---|
| `--n` | integer | 1 | How many ops to undo |
| `--studio` | boolean | False | Undo in the studio store (follows, inbox, library, topics) |

```
recomp op undo
recomp op undo --n 3
recomp op undo --studio
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

## post

### post.cancel

`recomp post cancel <ref>` · effect: **write**

Take a post out of the queue (undo with `recomp op undo --studio`).

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required |  |

### post.link

`recomp post link <ref> <url>` · effect: **write**

Record where you posted it: on the post, on the journey and on its hub recipe (when published).

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required |  |
| `<url>` | string | required | Where you posted it |

```
recomp post link Q2 https://youtube.com/shorts/abc123def45
```

### post.open

`recomp post open <ref>` · effect: **write**

Everything to upload a post yourself: the file, the title, the description with credits, the upload page.

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required |  |
| `--reveal` | boolean | False | Also show the file in the file manager |

```
recomp post open Q2 --reveal
```

### post.plan

`recomp post plan <ref>` · effect: **write**

Put an export in the posting queue for your channel. Refuses private sources (E_RIGHTS): only campaign and
permitted sources can be posted (D-23); the description credits every creator.

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required | A finished export (X3), or a journey (J1: its newest finished export) |
| `--profile` | string | None | With a journey: which format (shorts, landscape…) |
| `--lang` | string | None | With a journey: which language |
| `--at` | string | None | When you plan to post it, e.g. 2026-10-20 18:00 |
| `--title` | string | None | Post title (default: the journey's) |

```
recomp post plan X4 --at "2026-10-20 18:00"
recomp post plan J2 --profile shorts --lang en
```

### post.queue

`recomp post queue` · effect: **read**

The posting queue: what you plan to upload, when, with which credits; and what you posted.

| Field | Type | Default | Description |
|---|---|---|---|
| `--status` | string | 'open' | open (planned and opened), planned, opened, posted, cancelled or all |
| `--project` | string | None |  |

```
recomp post queue
recomp post queue --status posted
```

## preview

### preview

`recomp preview <target>` · effect: **heavy**

A quick low-resolution render of a journey or cut in a profile's look (job); the viewer shows it when done.

| Field | Type | Default | Description |
|---|---|---|---|
| `<target>` | string | required | Journey or cut ref |
| `--profile` | string | 'landscape' | Which profile to approximate (rendered small and fast) |
| `--lang` | string | None |  |

```
recomp preview J1
recomp preview J1 --profile shorts
recomp preview C4
```

## profile

### profile.edit

`recomp profile edit <name>` · effect: **write**

Change an export profile.

| Field | Type | Default | Description |
|---|---|---|---|
| `<name>` | string | required |  |
| `--from` | string | None | Start from this profile |
| `--width` | integer | None |  |
| `--height` | integer | None |  |
| `--fps` | integer | None |  |
| `--reframe` | string | None | fit-blur \| fit-pad \| crop-center \| crop-x |
| `--captions` | string | None | burn \| sidecar \| off |
| `--caption-style` | string | None | clean \| karaoke |
| `--caption-max-chars` | integer | None | Characters per caption row (0 = automatic by format and script) |
| `--caption-max-lines` | integer | None | Rows per caption screen (longer lines become more screens) |
| `--caption-scale` | number | None | Caption font size factor, e.g. 0.9 |
| `--caption-margin` | number | None | Distance from the bottom as a fraction of the height, e.g. 0.12 |
| `--caption-lang` | string | None | Per-language caption override, lang:key=value,…  e.g. am:max_chars=24,scale=0.9 (key=none removes it) |
| `--overlays` | boolean | None |  |
| `--lower-thirds` | boolean | None |  |
| `--music` | boolean | None |  |
| `--endcard` | boolean | None |  |
| `--endcard-seconds` | number | None |  |
| `--title-card` | boolean | None |  |
| `--loudness` | number | None |  |
| `--crf` | integer | None |  |
| `--preset` | string | None |  |
| `--dub-mode` | string | None | voiceover \| replace |
| `--description` | string | None |  |

### profile.list

`recomp profile list` · effect: **read**

Export profiles: format and treatment, separate from journey content.

### profile.new

`recomp profile new <name>` · effect: **write**

Create an export profile (optionally from another).

| Field | Type | Default | Description |
|---|---|---|---|
| `<name>` | string | required |  |
| `--from` | string | None | Start from this profile |
| `--width` | integer | None |  |
| `--height` | integer | None |  |
| `--fps` | integer | None |  |
| `--reframe` | string | None | fit-blur \| fit-pad \| crop-center \| crop-x |
| `--captions` | string | None | burn \| sidecar \| off |
| `--caption-style` | string | None | clean \| karaoke |
| `--caption-max-chars` | integer | None | Characters per caption row (0 = automatic by format and script) |
| `--caption-max-lines` | integer | None | Rows per caption screen (longer lines become more screens) |
| `--caption-scale` | number | None | Caption font size factor, e.g. 0.9 |
| `--caption-margin` | number | None | Distance from the bottom as a fraction of the height, e.g. 0.12 |
| `--caption-lang` | string | None | Per-language caption override, lang:key=value,…  e.g. am:max_chars=24,scale=0.9 (key=none removes it) |
| `--overlays` | boolean | None |  |
| `--lower-thirds` | boolean | None |  |
| `--music` | boolean | None |  |
| `--endcard` | boolean | None |  |
| `--endcard-seconds` | number | None |  |
| `--title-card` | boolean | None |  |
| `--loudness` | number | None |  |
| `--crf` | integer | None |  |
| `--preset` | string | None |  |
| `--dub-mode` | string | None | voiceover \| replace |
| `--description` | string | None |  |

```
recomp profile new reel --from shorts --caption-style clean --no-music
```

### profile.show

`recomp profile show <name>` · effect: **read**

One profile's full settings.

| Field | Type | Default | Description |
|---|---|---|---|
| `<name>` | string | required |  |

## project

### project.agent-kit

`recomp project agent-kit` · effect: **write**

(Re)install the agent kit into the project folder: AGENTS.md, CLAUDE.md, skills, .mcp.json.

| Field | Type | Default | Description |
|---|---|---|---|
| `--overwrite` | boolean | True | Overwrite existing kit files (your own CLAUDE.md notes below the marker are kept) |

### project.backup

`recomp project backup` · effect: **write**

Zip the project's work (database, recipes, music with licences, captions) without source media or caches.
Restore by unzipping anywhere and `recomp project use <folder>`, then `source relink` if media moved.

| Field | Type | Default | Description |
|---|---|---|---|
| `--out` | string | None | Zip file to write (default: <project>/../<name>-backup-<date>.zip) |
| `--exports` | boolean | False | Include rendered exports (large) |

### project.checklist

`recomp project checklist` · effect: **read**

Where the project stands, step by step (sources → transcripts → speakers → chapters → cuts → journeys →
languages → exports), each with its next actions. The viewer's home page shows the same list.

```
recomp project checklist
```

### project.forget

`recomp project forget <target>` · effect: **write**

Remove a project from the studio's list (its folder and files are left untouched).

| Field | Type | Default | Description |
|---|---|---|---|
| `<target>` | string | required | Project name (from `project list`) or folder |

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

### project.reveal

`recomp project reveal <what>` · effect: **read**

Open a project folder (or an export's folder) in the file manager on this computer.

| Field | Type | Default | Description |
|---|---|---|---|
| `<what>` | string | 'root' | root, sources, recipes, exports, an export (X3), or a path inside the project |

```
recomp project reveal exports
recomp project reveal X3
```

### project.set

`recomp project set` · effect: **write**

Change the project's name, kind, languages, description or themes.

| Field | Type | Default | Description |
|---|---|---|---|
| `--name` | string | None |  |
| `--kind` | string | None |  |
| `--languages` | list[string] | None |  |
| `--description` | string | None |  |
| `--themes` | list[string] | None | What this project is about: cut suggestions for new posts from followed creators use these (e.g. consciousness,free will) |

```
recomp project set --themes "consciousness,free will"
```

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
`--scope library` searches the followed creators' back catalogue instead (no project needed).

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
| `--scope` | string | 'project' | project (this project's sources) or library (followed creators' back catalogue in the studio library) |

```
recomp search "free will"
recomp search forgiveness --sources S1,S4 --limit 10
recomp search "everlasting life" --speaker "Pastor Chris"
recomp search "copy itself" --scope library
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
| `<target>` | string | '' | File, folder, glob (quote it) or link (omit with --pick) |
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

### source.browse

`recomp source browse <path>` · effect: **read**

List a folder's subfolders, media and subtitle files (read-only), to pick sources without typing paths.

| Field | Type | Default | Description |
|---|---|---|---|
| `<path>` | string | None | Folder to list (default: drives on Windows, else the home folder) |
| `--all` | boolean | False | Show every file, not only media and subtitles |

```
recomp source browse D:\Movies
```

### source.fetch-audio

`recomp source fetch-audio <ref>` · effect: **network**

Download only the audio of a link source (about 1 MB a minute), then make its 16 kHz audio and waveform.

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required | Source ref, e.g. S1 |

```
recomp source fetch-audio S2
```

### source.fetch-video

`recomp source fetch-video <ref>` · effect: **network**

Download a link source's whole video once (≤720p by default) so its cuts render and play locally.

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required |  |
| `--height` | integer | 720 | Maximum height (720 is plenty for talks and shorts) |

```
recomp source fetch-video S2
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

### source.refresh

`recomp source refresh <ref>` · effect: **network**

Complete a link source's metadata (creator chapters, caption languages, date) and fetch captions if missing.

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required | Source ref, e.g. S1 |

```
recomp source refresh S2
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

Set a source's credit and rights details (used for attribution in every export) and its rights status (D-23):
only campaign and permitted sources can enter the posting queue; private ones work for everything else.

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
| `--status` | string | None | campaign (a clipping program by the rights holder covers it), permitted (the creator's permission is verified) or private (everything else) |
| `--evidence` | string | None | Link to the program's terms or the creator's permission |

```
recomp source rights S1 --owner "Warner Bros." --notice "The Dark Knight (2008), Warner Bros."
recomp source rights S3 --status permitted --evidence https://…/permission-email
recomp source rights S3 --status private
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

## speaker

### speaker.assign

`recomp speaker assign <ref> <name>` · effect: **write**

Say who speaks which lines, directly: by range, time, cut or text, from '>>' turns, or from 'NAME:' prefixes. No models needed.

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required | Source or transcript ref |
| `<name>` | string | None | Person or character to give the selected lines |
| `--by` | string | None | marks: YouTube '>>' turns, cycling --names · prefix: 'NAME:' line prefixes in subtitles (film characters) |
| `--names` | string | None | With --by marks: comma list in speaking order, e.g. "Alex O'Connor,Anil Seth" |
| `--lines` | string | None | Line indices: 12, 12-40, 3,7,9-11 |
| `--from` | string | None | Lines ending after this time |
| `--to` | string | None | Lines starting before this time |
| `--cut` | string | None | Lines inside this cut (C3) |
| `--match` | string | None | Lines containing this text |
| `--strip` | boolean | True | With --by prefix: remove the 'NAME:' prefix from the text |
| `--clear` | boolean | False | Remove the speaker from the selected lines instead |
| `--dry-run` | boolean | False |  |

```
recomp speaker assign S4 "Anil Seth" --from 12:30 --to 48:10
recomp speaker assign S5 --by marks --names "Alex O'Connor,Michael Pollan"
recomp speaker assign S1 --by prefix --dry-run
recomp speaker assign S1 "The Joker" --cut C4
```

### speaker.diarize

`recomp speaker diarize <ref>` · effect: **heavy**

Find who speaks when (pyannote, local) and label transcript lines; known people are recognised automatically.

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required | Source ref |
| `--speakers` | integer | None | Exact number of speakers, if known |
| `--min` | integer | None |  |
| `--max` | integer | None |  |
| `--on` | string | None | local or remote (default: config worker.default_backend) |

```
recomp speaker diarize S2 --speakers 2
```

### speaker.list

`recomp speaker list <ref>` · effect: **read**

Voices per source (label, seconds, linked person, match score, a sample line) and the people in the project.

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | None | Source ref (default: all) |

### speaker.match

`recomp speaker match` · effect: **write**

Re-run recognition: link unnamed voices to known people when they sound alike enough.

### speaker.merge

`recomp speaker merge <person> <other>` · effect: **write**

Merge two people who are the same person.

| Field | Type | Default | Description |
|---|---|---|---|
| `<person>` | string | required | Person to keep (P1) |
| `<other>` | string | required | Person to merge into it |

### speaker.name

`recomp speaker name <voice> <name>` · effect: **write**

Say who a voice is. The person is created if new; their voice is then recognised in other sources.

| Field | Type | Default | Description |
|---|---|---|---|
| `<voice>` | string | required | Voice, e.g. S2:SPEAKER_00 |
| `<name>` | string | required | The person's name |
| `--propagate` | boolean | True | Recognise this person in other sources' voices |

```
recomp speaker name S2:SPEAKER_01 "Alex O'Connor"
```

### speaker.people

`recomp speaker people <person>` · effect: **write**

List people and characters (lines, sources, aliases), or rename, alias, annotate or remove one.

| Field | Type | Default | Description |
|---|---|---|---|
| `<person>` | string | None | Person to change (P1 or name); omit to list everyone |
| `--rename` | string | None | New name (the old one becomes an alias) |
| `--alias` | string | None | Add an alias (another spelling, a character's other name) |
| `--note` | string | None | A note: who they are, the actor who plays them |
| `--remove` | boolean | False | Delete the person (their lines keep their voice label) |

```
recomp speaker people
recomp speaker people P2 --rename "Michael Pollan" --alias "Pollan"
recomp speaker people "The Joker" --note "played by Heath Ledger"
```

### speaker.unlink

`recomp speaker unlink <voice>` · effect: **write**

Remove a wrong person link from a voice.

| Field | Type | Default | Description |
|---|---|---|---|
| `<voice>` | string | required |  |

## topic

### topic.add

`recomp topic add <title>` · effect: **write**

Name a topic to compile: what the followed creators said about it, now and in the past.

| Field | Type | Default | Description |
|---|---|---|---|
| `<title>` | string | required | The topic in your words, or a number from the last `topic suggest` |
| `--terms` | list[string] | None | Words and phrases that mean it (default: from the title) |
| `--follows` | list[string] | None | Only these creators (default: everyone followed) |
| `--since` | string | '2y' | How far back to look: 2y, 18m or a date |
| `--news-query` | string | None | Headlines to keep as context (default: the title) |
| `--project` | list[string] | None | Where its journeys go (default: the current project) |
| `--note` | string | '' |  |

```
recomp topic add "AI models are getting good" --terms "AI,model,AGI,superintelligence,copy itself"
recomp topic add 3 --project ai-and-ideas
```

### topic.brief

`recomp topic brief <ref>` · effect: **read**

The topic brief: per creator, the episodes and passages (who speaks, times, links) and what could not be read.

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required |  |
| `--format` | string | 'json' | json or md |
| `--creator` | string | None | Only this creator's part |

```
recomp topic brief T1
recomp topic brief T1 --format md
```

### topic.edit

`recomp topic edit <ref>` · effect: **write**

Change a topic's title, terms, creators, time range, headline query or projects (scan again after).

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required |  |
| `--title` | string | None |  |
| `--terms` | list[string] | None | Replace the terms |
| `--follows` | list[string] | None | Replace the creators ([] = everyone) |
| `--since` | string | None |  |
| `--news-query` | string | None |  |
| `--project` | list[string] | None |  |
| `--note` | string | None |  |

```
recomp topic edit T1 --terms "AI,AGI,superintelligence,control"
```

### topic.list

`recomp topic list` · effect: **read**

Topics, their terms, last scan and the journeys made from them.

### topic.remove

`recomp topic remove <ref>` · effect: **write**

Drop a topic and its brief (journeys made from it stay in their projects).

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required |  |

### topic.scan

`recomp topic scan <ref>` · effect: **network**

Find what each followed creator said about the topic: their feeds and channel search for episodes on it,
transcripts fetched the cheap way into the library, plus project transcripts; ranks passages and writes the
brief (`recomp topic brief T1`). The ranking is a shortlist: read and choose.

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required |  |
| `--fetch` | integer | 3 | Missing transcripts to fetch per creator in this scan |
| `--episodes` | integer | 4 | Episodes to keep per creator in the brief |
| `--passages` | integer | 3 | Passages to keep per episode |
| `--news` | boolean | True | Keep this week's headlines on the topic as context |

```
recomp topic scan T1
recomp topic scan T1 --fetch 6
```

### topic.suggest

`recomp topic suggest` · effect: **network**

What is in the air, as prompts: headlines and lists, each with the followed creators who have talked about it
in the library. Pick one (`recomp topic add <n>`) or name your own; the news is a prompt, not a scoreboard.

| Field | Type | Default | Description |
|---|---|---|---|
| `--section` | string | 'top' | Google News section: top, world, nation, business, technology, science, health, entertainment, sports |
| `--query` | string | None | Search the news of the last 7 days instead of a section |
| `--sources` | list[string] | None | news, trends (Google Trends daily, US), wikipedia (most viewed; needs `config set research.contact`), hn |
| `--limit` | integer | 12 | Prompts per source |

```
recomp topic suggest --section technology
recomp topic suggest --query "AI models"
recomp topic suggest --sources news,trends
```

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
| `--on` | string | None | local or remote (a GPU notebook watching worker.remote_folder); default: config |

```
recomp transcript asr S3
recomp transcript asr S1 --from 10:00 --to 20:00 --language en
```

### transcript.clean

`recomp transcript clean <ref>` · effect: **write**

Tidy transcript text with presets (sound tags, >> marks, ♪, doubled words, fillers, spacing, casing). Empty lines are removed.

| Field | Type | Default | Description |
|---|---|---|---|
| `--lines` | string | None | Line indices: 12, 12-40 or 3,7,9-11 (the #idx from `transcript read`) |
| `--from` | string | None | Only lines ending after this time |
| `--to` | string | None | Only lines starting before this time |
| `--dry-run` | boolean | False | Show what would change without changing anything |
| `<ref>` | string | required | Source or transcript ref, or `all` |
| `--rules` | string | None | Comma list; default marks,tags,notes,doubles,spacing. Also: fillers, case. `--rules list` shows them all |

```
recomp transcript clean S2 --dry-run
recomp transcript clean all --rules tags,notes,spacing
recomp transcript clean S1 --rules list
```

### transcript.delete

`recomp transcript delete <ref>` · effect: **write**

Remove lines (credits, sound-only lines, a subtitle file's ads) by range, time or pattern.

| Field | Type | Default | Description |
|---|---|---|---|
| `--lines` | string | None | Line indices: 12, 12-40 or 3,7,9-11 (the #idx from `transcript read`) |
| `--from` | string | None | Only lines ending after this time |
| `--to` | string | None | Only lines starting before this time |
| `--dry-run` | boolean | False | Show what would change without changing anything |
| `<ref>` | string | required | Source or transcript ref |
| `--match` | string | None | Only lines containing this text (or --regex pattern) |
| `--regex` | boolean | False |  |

```
recomp transcript delete S1 --lines 0-3 --dry-run
recomp transcript delete S1 --match "^\[.*\]$" --regex
```

### transcript.edit

`recomp transcript edit <ref>` · effect: **write**

Change many lines at once (text, start, end, speaker) from one JSON input; one undo reverts them all.

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required | Source or transcript ref |
| `--edits` | list[any] | required | Lines to change (use --input edits.json: {edits: [{idx, text, …}]}) |
| `--dry-run` | boolean | False |  |

```
recomp transcript edit S1 --input edits.json
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

### transcript.export

`recomp transcript export <ref>` · effect: **write**

Write a transcript to a file (srt, vtt, txt, json) for an outside editor; `transcript import` reads it back.

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required | Source or transcript ref |
| `--format` | string | 'srt' | srt \| vtt \| txt \| json (json keeps words and speakers; import reads it back) |
| `--out` | string | None | File to write (default: <project>/exports/transcripts/<ref>.<format>) |
| `--from` | string | None |  |
| `--to` | string | None |  |

```
recomp transcript export S1 --format srt
recomp transcript export S4 --format json --out s4.json
```

### transcript.fetch-captions

`recomp transcript fetch-captions <ref>` · effect: **network**

Fetch a link's captions (manual first, then the original-language auto captions) as a job. On HTTP 429 fall back to `transcript asr`.

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required | Link source ref |
| `--language` | string | None | Caption language (default: the source's) |

```
recomp transcript fetch-captions S2
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

### transcript.merge

`recomp transcript merge <ref> <lines>` · effect: **write**

Join consecutive lines into one (a sentence the subtitles broke apart). Words keep their timings.

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required | Source or transcript ref |
| `<lines>` | string | required | Consecutive lines to join, e.g. 12-14 |

```
recomp transcript merge S1 12-14
```

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

### transcript.replace

`recomp transcript replace <ref> <find> <replace>` · effect: **write**

Find and replace across a transcript (or all of them): names, misheard words, punctuation. Word timings follow.

| Field | Type | Default | Description |
|---|---|---|---|
| `--lines` | string | None | Line indices: 12, 12-40 or 3,7,9-11 (the #idx from `transcript read`) |
| `--from` | string | None | Only lines ending after this time |
| `--to` | string | None | Only lines starting before this time |
| `--dry-run` | boolean | False | Show what would change without changing anything |
| `<ref>` | string | required | Source or transcript ref, or `all` (every source's primary transcript) |
| `<find>` | string | required | Text (or --regex pattern) to find |
| `<replace>` | string | required | Replacement (regex groups as \1) |
| `--regex` | boolean | False |  |
| `--case` | boolean | False | Case-sensitive |
| `--whole` | boolean | False | Whole words only |

```
recomp transcript replace all "Anil Seth" "Anil Seth" --whole --dry-run
recomp transcript replace S4 "conscious ness" "consciousness"
recomp transcript replace S1 "^- " "" --regex
```

### transcript.resegment

`recomp transcript resegment <ref>` · effect: **write**

Rebuild lines from word timings (rolling auto captions → sentence-like lines). Writes a new transcript; the old one stays.

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required | Source or transcript ref (needs word timings) |
| `--max-chars` | integer | 84 | Longest line in characters (two caption rows ≈ 84) |
| `--max-dur` | number | 7.0 | Longest line in seconds |
| `--gap` | number | 0.8 | A pause this long always starts a new line |
| `--primary` | boolean | True | Make the result the primary transcript |
| `--dry-run` | boolean | False |  |

```
recomp transcript resegment S2 --dry-run
recomp transcript resegment S2 --max-chars 70
```

### transcript.set-primary

`recomp transcript set-primary <ref>` · effect: **write**

Make a transcript the one search, reading and captions use for its source.

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required | Transcript ref |

### transcript.shift

`recomp transcript shift <ref> <by>` · effect: **write**

Shift (and optionally stretch) a transcript's times, whole or from/to a point. Shift back to undo a whole shift.

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required |  |
| `<by>` | string | '0' | Seconds to add to every time (negative = earlier) |
| `--scale` | number | 1.0 | Multiply times first (frame-rate drift: 25/23.976 = 1.04271) |
| `--from` | string | None | Only lines starting at or after this time |
| `--to` | string | None | Only lines starting before this time |

```
recomp transcript shift S1.t1 -1.5
recomp transcript shift S1 0 --scale 1.04271
recomp transcript shift S1 0.8 --from 1:02:10   # only the lines after a reel change
```

### transcript.split

`recomp transcript split <ref> <idx>` · effect: **write**

Split one line in two, after given words or at a time. Later lines are renumbered.

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required | Source or transcript ref |
| `<idx>` | integer | required | Line to split |
| `--after` | string | None | Split after these words (the end of the first part) |
| `--at` | string | None | Or split at this time (words decide the text) |

```
recomp transcript split S1 412 --after "Why so serious?"
recomp transcript split S1 412 --at 1:02:03.4
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

## trends

### trends.channel

`recomp trends channel <url>` · effect: **network**

A channel's recent videos ranked by views (per day when dates are known).

| Field | Type | Default | Description |
|---|---|---|---|
| `<url>` | string | required | Channel or playlist link |
| `--since` | string | None |  |
| `--limit` | integer | 30 |  |

```
recomp trends channel https://www.youtube.com/@CosmicSkeptic/videos
```

### trends.search

`recomp trends search <topic>` · effect: **network**

Recent videos on a topic, ranked by views per day (no key needed). Pick them with `source add --pick`.

| Field | Type | Default | Description |
|---|---|---|---|
| `<topic>` | string | required |  |
| `--since` | string | '30d' | Only videos newer than this (7d, 30d) |
| `--limit` | integer | 25 |  |

```
recomp trends search "free will" --since 7d
```

### trends.youtube

`recomp trends youtube` · effect: **network**

YouTube's 'most popular' chart for a region (needs your YOUTUBE_API_KEY in the studio home's .env).

| Field | Type | Default | Description |
|---|---|---|---|
| `--region` | string | 'US' | Region code, e.g. US, ET, KE, FR |
| `--category` | string | None | YouTube category id (22 People & Blogs, 27 Education, 25 News…) |
| `--limit` | integer | 25 |  |

```
recomp trends youtube --region ET --category 27
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

Leave a note for the agent (the viewer calls this); with a verb, it is an action handed to the agent.

| Field | Type | Default | Description |
|---|---|---|---|
| `<text>` | string | required | Note for the agent |
| `--refs` | list[string] | None |  |
| `--verb` | string | None | A verb the user hands to the agent to run (with args) |
| `--args` | object | None | Its arguments |

### ui.notes

`recomp ui notes` · effect: **read**

Open questions you pinned, the user's answers, and notes the user left for you.

| Field | Type | Default | Description |
|---|---|---|---|
| `--mark-seen` | boolean | True | Mark the user's notes as seen |

### ui.select

`recomp ui select` · effect: **write**

Set the shared selection: a time range on a source and/or refs. The viewer records the user's selection here,
and the agent can select for the user (cuts ticked in the cut bin, a range in a source room).

| Field | Type | Default | Description |
|---|---|---|---|
| `--source` | string | None | Source ref, e.g. S1 |
| `--start` | string | None | Range start (time) |
| `--end` | string | None | Range end (time) |
| `--refs` | list[string] | None | Selected refs (cuts, slots, chapters) |
| `--t` | string | None | Playhead time |

```
recomp ui select --refs C3,C7,C9   # tick cuts in the user's cut bin
recomp ui select --source S1 --start 12:03 --end 12:48
```

### ui.selection

`recomp ui selection` · effect: **read**

What the user currently has selected in the viewer (a time range on a source, and/or refs).

### ui.show

`recomp ui show <ref>` · effect: **write**

Move the user's viewer to a ref or a view (optionally a time, list filters, and a button to point at).

| Field | Type | Default | Description |
|---|---|---|---|
| `<ref>` | string | required | What to show: S1, S1.c3, C17, J2, J2#3, X1 …, or a view: home, sources, cuts, search, journeys, exports, translations, jobs, activity |
| `--at` | string | None | Time to seek to (source time for sources/chapters/cuts) |
| `--play` | boolean | False | Start playing |
| `--filter` | string | None | Filters for a list view, e.g. "source=S1&tag=fear" or "q=consciousness" |
| `--highlight` | string | None | Point at the button that runs this verb, e.g. export.run |

```
recomp ui show C17
recomp ui show S1 --at 1:02:10
recomp ui show cuts --filter "source=S2&min=20"
recomp ui show J1 --highlight export.run
```

## version

### version

`recomp version` · effect: **read**

Version and where things are.

## worker

### worker.status

`recomp worker status` · effect: **read**

The local job runner, and the remote folder: live remote workers and jobs waiting there.
