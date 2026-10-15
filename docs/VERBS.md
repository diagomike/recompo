# Verbs

Generated from the registry by `python scripts/gen_docs.py`. Every verb is available as
`recomp <noun> <verb>` (CLI), as the MCP tool `<noun>_<verb>`, and as
`POST /api/verb/<noun>.<verb>` on the studio server. All return the same JSON envelope.

Effects: `read` (no changes) · `write` (undoable op) · `heavy` (starts a job) ·
`network` (talks to the internet) · `publish` (shares beyond this machine).

| Noun | Verbs |
|---|---|
| `config` | [`config.get`](#configget), [`config.set`](#configset) |
| `context` | [`context`](#context) |
| `doctor` | [`doctor`](#doctor) |
| `op` | [`op.log`](#oplog), [`op.redo`](#opredo), [`op.undo`](#opundo) |
| `project` | [`project.agent-kit`](#projectagent-kit), [`project.init`](#projectinit), [`project.list`](#projectlist), [`project.set`](#projectset), [`project.show`](#projectshow), [`project.use`](#projectuse) |
| `setup` | [`setup.shim`](#setupshim) |
| `ui` | [`ui.answer`](#uianswer), [`ui.ask`](#uiask), [`ui.note`](#uinote), [`ui.notes`](#uinotes), [`ui.select`](#uiselect), [`ui.selection`](#uiselection), [`ui.show`](#uishow) |
| `version` | [`version`](#version) |

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

## setup

### setup.shim

`recomp setup shim` · effect: **write**

Write `recomp` launchers (sh and .cmd) into a folder on PATH so agents can call `recomp` anywhere.

| Field | Type | Default | Description |
|---|---|---|---|
| `--bin-dir` | string | 'C:\\Users\\pc\\bin' | Folder on PATH for the launchers |

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
