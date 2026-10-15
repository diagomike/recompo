@AGENTS.md

## Claude Code specifics
- Launch configs in `.claude/launch.json`: `studio` (recomp serve, 8770), `web-dev` (Vite, 5180), `hub` (8790).
- The project-operating skills live in `recomp/agent_kit/.claude/skills/`; `recomp project init` installs
  them into project folders.
- Long commands (ASR, downloads, renders) run in the background; don't sit polling.
- Keep `docs/STATE.md` and `docs/BACKLOG.md` current at every phase boundary.
