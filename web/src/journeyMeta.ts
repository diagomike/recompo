// Where a journey goes (mirrors DESTINATIONS in recomp/verbs/journey.py): the destination sets the length goal,
// the export profiles, and whether the recipe is shared with the community hub.
export const DESTINATIONS: { key: string; label: string; note: string; ideal?: [number, number]; profile?: string }[] = [
  { key: "shorts", label: "Shorts, Reels, TikTok", note: "Vertical 9:16 · one idea, a hook in the first seconds · 30–90 s", ideal: [30, 90], profile: "shorts" },
  { key: "landscape", label: "YouTube (landscape)", note: "16:9 · room for an argument, sections and lower thirds · 2–15 min", ideal: [120, 900], profile: "landscape" },
  { key: "square", label: "Feeds (square)", note: "1:1 for Instagram, X, LinkedIn · 30–120 s", ideal: [30, 120], profile: "square" },
  { key: "hub", label: "Community hub", note: "Share the recipe: others play it from the original sources; no media is copied" },
];

export const STEP_HELP: Record<string, { title: string; verb: string }> = {
  purpose: { title: "Purpose", verb: "What it is for and where it goes" },
  gather: { title: "Gather cuts", verb: "Moments from any of your sources" },
  order: { title: "Order", verb: "The sequence that tells it best" },
  look: { title: "Look", verb: "Title, who is speaking, music" },
  check: { title: "Check", verb: "Validate and preview" },
  export: { title: "Export & share", verb: "Render for each destination" },
};
