# P16b — UX rework: a guided journey studio, Word-style progressive disclosure

Date: 2026-10-15 · branch `claude/ux-rework-680a59` · checked on `p16-check` (two fixture clips) and `alex-oconnor`
(four long link sources) at 1280×800, 1024×768 and 390×844. Screenshots: `docs/runs/img/before-*` and `after-*`
(light theme; `after-dark-*` for dark).

## What you asked for
After P16 you said the UI was compacted and making a journey was not guided. You then clarified: keep the dense,
industry-grade feel (13 px type, tight padding); what is missing is **clarity, flow and guidance**: things
progressively revealed, like Microsoft Word. No padded, rounded cards.

So this pass keeps the density and changes the structure.

## What changed

### The journey flow (the main fix)
- **New journey** is one dialog, reachable from anywhere (top bar button, `n`, the home page, the cut bin's
  "Add to journey ▸ New journey with these…", `recomp ui show home --filter new=1`): name, **what it is for**, **where
  people will see it** (Shorts/Reels/TikTok, YouTube landscape, square feeds, community hub), and how to start
  (gather step by step, with the cuts ticked in the cut bin, or a draft from a theme).
- **The journey studio** replaces the old journeys page. It works like a document editor:
  - a **ribbon of six step tabs** — Purpose › Gather cuts › Order › Look › Check › Export & share — each with its state
    (✓ done, amber in progress, red problem, blue next);
  - a **one-line step header** saying what the step is for, with the step's commands on the right;
  - the **work area**, plus a **preview pane** (the recipe player and a length meter) that can be hidden;
  - a **status bar** at the bottom: back, what is true now, and the one next action.
- **Gather** takes cuts from three places through one switch: *Suggested* (`cut suggest` on the journey's intent,
  one click cuts and adds), *Cut bin* (tick several, add in that order), *From a source* (opens the source room in
  gathering mode: a banner says new cuts go into the journey, the cut form has "Add to J2" ticked, "Back to J2"
  returns). Cuts from any number of sources get coloured source badges everywhere.
- **Order**: drag, ↑/↓, and a ⋯ menu per cut for sections, trims (dialog), fades, opening it in its source, removing.
  "Order looks right" confirms the step.
- **Look** is a property sheet: title card, who is speaking (auto lower thirds), music bed (library or open-licence
  search). Level, ducking, the individual lower thirds and other text overlays are folded away.
- **Check**: validation (problems, notes against the destination's length goal, passes) and a preview render shown
  inline. A finished preview checks the step by itself.
- **Export & share**: the destinations' formats are preselected; more formats and languages fold away; exports of the
  journey list below with Watch, folder and the ready-to-paste description; a separate row publishes the recipe to the
  community hub. When an export is done, a banner offers the exports folder, translation, or the next journey.

### New verbs (the agent sees the same guide)
- `journey guide J1`: the six steps with state, detail, hint, next actions and an agent request each; `next`.
- `journey review J1 order|look|check [--done false]`: confirm (or reopen) a judgement step.
- `journey new|edit --formats shorts,landscape,square,hub`: destinations; they set the length goal (tightest wins),
  `journey validate` notes, the export profiles in the guide, and the hub hand-off.
- `cut add … --journey J1`: cut straight into a journey (one op, one undo).
- `project checklist` now lists journeys with their step states and leads into the flow ("Continue J2", "Start a
  journey"; the export step opens the studio's export tab).

### The rest of the viewer
- **Shell**: a navigation rail (Make · Material · Deliver; Jobs, Activity and the hub at the bottom with a running-jobs
  badge), icons-only below 1180 px with tooltips, a bottom bar on phones. The **agent** lives in a drawer: docked at
  ≥ 1440 px, a slide-over below, closed by default, a badge when the agent asks something.
- **Progressive disclosure everywhere**: lists show their main filters and fold the rest under *More filters* (it opens
  itself when one of them is set); secondary actions sit in ⋯ menus; destructive ones confirm in a dialog or with a
  second click; advanced options sit in collapsible sections that remember being opened; the home page shows only the
  open setup steps (finished ones folded).
- **Tooltips** on every command button say what it does and show the exact `recomp` command (and the shortcut); the
  robot hand-off to the agent appears on hover.
- **Home**: journeys table with step progress and "Continue", then project setup, then the folders (folded).
- **Cut bin**: an "Add to journey ▾" menu (every journey, or a new one with the selection), Tag, and a ⋯ menu (export
  as clips, delete); a list instead of the table on phones.
- **Sources**: an "Add sources" panel that folds away once there are sources; one table row per source with its
  transcript state and pipeline summarised ("ready", or the stages still running).
- **Search**: "Moments to cut" (Cut, Into a journey ▾) beside the matching lines.
- **Exports**: Renders / Translations tabs, a pointer into each journey's export step, quick export under *Advanced*.
- Design system rewritten as tokens for light and dark: 13 px type, 26 px controls, 3 px radius, flat bordered panels,
  tables and lists; no shadows except on overlays.

## Acceptance walk (done in the browser pane, as a new user)
On `p16-check`: Home → **New journey** → "Heroes and plants", intent, Shorts + community hub → Gather: *Suggested*
showed moments from both clips for the intent; **Add** on the S1 moment → *From a source* → S2 → selected a line →
`C` → the cut form had "Add to J2" ticked → saved (C4 went into J2) → **Back to J2** → Order: moved a cut, **Order looks
right** → Look: title card, **Credit every speaker and source** (lower thirds), **Looks good** → Check: validation
passed with a note that Shorts work best at 30–90 s (the clips are 10 s) → **Make a preview** (rendered in a few
seconds, the step ticked itself) → Export: Shorts preselected → **Export 1 video** → X4 done, the banner offered the
next steps. Every step shows in the Activity log as a verb (`journey.new --formats`, `cut.add --journey`,
`journey.move`, `journey.review`, `overlay.add`, `overlay.auto-lower-thirds`, `preview`, `export.run`).

## Screens
| | before | after |
|---|---|---|
| Home 1280 | ![](img/before-home-1280.png) | ![](img/after-home-1280.png) |
| Journey 1280 | ![](img/before-journeys-1280.png) | ![](img/after-gather-1280.png) |
| Order / Look 1280 | | ![](img/after-order-1280.png) ![](img/after-look-1280.png) |
| Check / Export 1280 | | ![](img/after-check-1280.png) ![](img/after-export-1280.png) |
| New journey | | ![](img/after-newjourney-1280.png) |
| Cut bin 1280 | ![](img/before-cuts-1280.png) | ![](img/after-cuts-1280.png) |
| Sources 1280 | ![](img/before-sources-1280.png) | ![](img/after-sources-1280.png) |
| Exports 1280 | ![](img/before-exports-1280.png) | ![](img/after-exports-1280.png) |
| Search 1280 | ![](img/before-search-1280.png) | ![](img/after-search-1280.png) |
| Home 1024 | ![](img/before-home-1024.png) | ![](img/after-home-1024.png) |
| Journey 1024 | ![](img/before-journeys-1024.png) | ![](img/after-gather-1024.png) |
| Phone | ![](img/before-cuts-390.png) | ![](img/after-gather-390.png) ![](img/after-cuts-390.png) |
| Real data (alex-oconnor) | ![](img/before-alex-journeys-1280.png) | ![](img/after-alex-order-1280.png) |
| Dark | | ![](img/after-dark-gather-1280.png) |

## Checks
- `pytest -q`: 92 passed (new: `test_guided_journey_flow`, checklist assertions for the flow hand-off).
- `npx tsc --noEmit` clean; `npm --prefix web run build` built; `scripts/gen_docs.py` regenerated `docs/VERBS.md`.

## Not done / next
- The source room and the translation editor keep their P16 structure (restyled by the new tokens only).
- Studio shortcuts (1–6 to switch steps, Enter for the status bar's action) are not wired yet.
- Music search needs the network; there is no offline music library seed.
- Your review of the flow is the remaining step.
