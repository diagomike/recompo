# Recomposer

An agent-operated studio for turning films, podcasts and talks into **journeys**: authored
sequences of meaningful cuts with captions, overlays and music. Journeys export in any
format and language, and are shared on a hub as **recipes** (sources and timecodes, never the media).

You work with an agent (Claude Code, or any MCP/CLI-capable agent) in a project folder: it
reads transcripts, writes chapters, makes cuts and composes journeys through the `recomp`
verbs, while you watch, select and correct in the local viewer.

```
recomp project init dark-knight --kind movies
recomp source add "D:\Recomp\Video\The.Dark.Knight*.mp4"
recomp context
```

- **Plan and status:** [docs/PLAN.md](docs/PLAN.md) · [docs/STATE.md](docs/STATE.md) · [docs/BACKLOG.md](docs/BACKLOG.md)
- **Every verb:** [docs/VERBS.md](docs/VERBS.md)
- **For agents:** [AGENTS.md](AGENTS.md) (code) · [recomp/agent_kit/AGENTS.project.md](recomp/agent_kit/AGENTS.project.md) (operating a project)

## Install (Windows, Python 3.13, ffmpeg on PATH)

```
py -3.13 -m venv .venv
.venv\Scripts\python.exe -m pip install -e .[dev]
.venv\Scripts\recomp.exe setup shim      # `recomp` launchers in %USERPROFILE%\bin (Git Bash PATH)
.venv\Scripts\recomp.exe doctor
```

Local ASR and speaker detection run under a *worker python* with faster-whisper and pyannote
(default: `D:\LangBridgeLocal\.venv`; change with `recomp config set worker.python <path>`).

## Test

```
.venv\Scripts\python.exe -m pytest -q
```
