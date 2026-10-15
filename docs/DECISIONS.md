# Decisions

D-01 … D-16 were agreed on 2026-10-15 and are listed in [PLAN.md §1](PLAN.md#1-decisions-agreed-in-conversation-2026-10-15).
Decisions taken during the build are appended here.

| # | Date | Decision | Why |
|---|---|---|---|
| D-17 | 2026-10-15 | Short refs (`S1`, `S1.c4`, `C17`, `J2#3`) are allocated per kind from a `refseq` table and never reused. | Refs are how the user and agent talk about things in chat; a reused ref would point at the wrong thing in an old message. |
| D-18 | 2026-10-15 | Undo works at row level (each op stores before/after rows). Undo refuses if a row changed since (E_CONFLICT), and refuses to undo a higher-precedence actor's op. Bulk machine data (segments, words, shots) is not op-logged. | A generic, verifiable inverse for every verb, without hand-written inverse functions. |
| D-19 | 2026-10-15 | CLI positionals are optional at the argparse level; pydantic reports missing fields. All CLI failures, including usage errors, print a JSON envelope. | Agents always get parseable output and a hint. |
| D-20 | 2026-10-15 | The viewer learns about changes by tailing the `event` table (SSE in the studio server polls it). | The CLI, the MCP server and jobs are separate processes; the database is the one place they all write. |
| D-21 | 2026-10-15 | `recomp` launchers go in `~/bin` (on Git Bash's PATH), via `recomp setup shim`; Windows PATH is not modified. | Agents in any project folder can call `recomp` without touching system settings. |
