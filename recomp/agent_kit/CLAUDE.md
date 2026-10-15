@AGENTS.md

## Claude Code specifics

- Skills in `.claude/skills/`: `recomp-operate`, `recomp-ingest`, `recomp-chapters`, `recomp-cuts`,
  `recomp-journeys`, `recomp-export`. Load the matching one before a stage of work.
- The `recomposer` MCP server (`.mcp.json`) exposes the same verbs as tools; the CLI is often
  simpler in Bash. Both print the same envelope.
- To show the user the viewer: start it with `recomp serve` in the background (or open
  http://127.0.0.1:8770 if it is already running), then use `recomp ui show <ref>`.
- Do not spawn subagents unless the user names one explicitly.

<!-- your notes below this line are kept when the kit is reinstalled -->
