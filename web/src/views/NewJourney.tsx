import { useEffect, useState } from "react";
import { ArrowRight, Scissors, Sparkles, SquarePlus } from "lucide-react";
import { must } from "../api";
import { useApp } from "../App";
import { useActions } from "../actions";
import { DESTINATIONS } from "../journeyMeta";
import { Dialog, Disclosure } from "../ui";

// Step 1 of the guided flow, from anywhere (the + New journey button, `n`, or `recomp ui show home --filter new=1`):
// name it, say what it is for, pick where it goes, and choose how to start.
export default function NewJourney({ onClose }: { onClose: () => void }) {
  const { go } = useApp();
  const { run } = useActions();
  const [title, setTitle] = useState("");
  const [intent, setIntent] = useState("");
  const [formats, setFormats] = useState<string[]>(["shorts"]);
  const [start, setStart] = useState<"empty" | "selection" | "search">("empty");
  const [theme, setTheme] = useState("");
  const [language, setLanguage] = useState("en");
  const [picked, setPicked] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [tried, setTried] = useState(false);

  // Cuts ticked in the cut bin (shared selection) can seed the journey.
  useEffect(() => {
    must<any>("ui.selection").then((s) => {
      const refs = (s?.refs || []).filter((r: string) => /^C\d+$/.test(r));
      setPicked(refs);
      if (refs.length) setStart("selection");
    }).catch(() => {});
  }, []);

  const toggle = (k: string) => setFormats(formats.includes(k) ? formats.filter((x) => x !== k) : [...formats, k]);
  const ok = title.trim() && (start !== "search" || theme.trim());
  const create = async () => {
    setTried(true);
    if (!ok || busy) return;
    setBusy(true);
    let ref: string | undefined;
    if (start === "search") {
      const env = await run("journey.from-search", { query: theme.trim(), title: title.trim(), limit: 6 }, { label: "Draft from a theme" });
      ref = env.ok ? env.refs?.[0] : undefined;
      if (ref) await run("journey.edit", { journey: ref, intent: intent.trim(), formats, language }, { label: "Purpose", quiet: true });
    } else {
      const env = await run("journey.new", { title: title.trim(), intent: intent.trim(), formats, language,
                                             cuts: start === "selection" ? picked : [] }, { label: "New journey" });
      ref = env.ok ? env.refs?.[0] : undefined;
    }
    setBusy(false);
    if (ref) go("journeys", ref, { step: start === "empty" ? "gather" : "order" });
  };

  return (
    <Dialog wide title="New journey"
            sub="A journey strings moments from your sources into one piece. Say what it is for and where it goes; the studio guides you from there."
            onClose={onClose}
            footer={<>
              <span className="muted2 grow">Next: {start === "empty" ? "gather cuts" : "put them in order"}. You can change all of this later.</span>
              <button className="btn" onClick={onClose}>Cancel</button>
              <button className="btn primary" disabled={busy} onClick={create}>{busy ? "Creating…" : "Create journey"}<ArrowRight size={14} /></button>
            </>}>
      <div className="stack lg">
        <div className="field">
          <label htmlFor="nj-title">Name</label>
          <input id="nj-title" className={"input" + (tried && !title.trim() ? " on" : "")} placeholder="e.g. Can a machine be conscious?" value={title}
                 onChange={(e) => setTitle(e.target.value)} onKeyDown={(e) => e.key === "Enter" && create()} />
          {tried && !title.trim() && <span className="help" style={{ color: "var(--red)" }}>Give it a name to continue.</span>}
        </div>
        <div className="field">
          <label htmlFor="nj-intent">What is it for?</label>
          <textarea id="nj-intent" className="input" rows={2} placeholder="One sentence: the idea, the question or the feeling you want people to leave with."
                    value={intent} onChange={(e) => setIntent(e.target.value)} />
          <span className="help">It shapes the cut suggestions and the export description.</span>
        </div>
        <div className="field">
          <span className="label">Where will people see it?</span>
          <div className="grid2">
            {DESTINATIONS.map((d) => (
              <button key={d.key} type="button" className={"tile" + (formats.includes(d.key) ? " on" : "")} onClick={() => toggle(d.key)} aria-pressed={formats.includes(d.key)}>
                <span className="tt"><input type="checkbox" readOnly checked={formats.includes(d.key)} tabIndex={-1} />{d.label}</span>
                <span className="td">{d.note}</span>
              </button>
            ))}
          </div>
          <span className="help">Pick any. The tightest length goal wins; each destination becomes an export.</span>
        </div>
        <div className="field">
          <span className="label">How do you want to start?</span>
          <div className="grid3" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))" }}>
            <button type="button" className={"tile" + (start === "empty" ? " on" : "")} onClick={() => setStart("empty")}>
              <span className="tt"><SquarePlus size={14} />Gather step by step</span>
              <span className="td">Suggestions, your cut bin, or new cuts from any source.</span>
            </button>
            <button type="button" className={"tile" + (start === "selection" ? " on" : "")} onClick={() => setStart("selection")} disabled={!picked.length}
                    style={!picked.length ? { opacity: .55, cursor: "default" } : undefined}>
              <span className="tt"><Scissors size={14} />{picked.length ? `With ${picked.length} ticked cut${picked.length > 1 ? "s" : ""}` : "With ticked cuts"}</span>
              <span className="td">{picked.length ? picked.join(" → ") : "Tick cuts in the cut bin first."}</span>
            </button>
            <button type="button" className={"tile" + (start === "search" ? " on" : "")} onClick={() => setStart("search")}>
              <span className="tt"><Sparkles size={14} />Draft from a theme</span>
              <span className="td">Whole-thought cuts for a theme, across your sources.</span>
            </button>
          </div>
          {start === "search" && (
            <input className={"input" + (tried && !theme.trim() ? " on" : "")} style={{ marginTop: 8 }} autoFocus placeholder='Theme to search for, e.g. free will, "hard problem"'
                   value={theme} onChange={(e) => setTheme(e.target.value)} onKeyDown={(e) => e.key === "Enter" && create()} />
          )}
        </div>
        <Disclosure id="newjourney.advanced" label="Advanced options">
          <div className="field" style={{ maxWidth: 260 }}>
            <label htmlFor="nj-lang">Language of the journey</label>
            <input id="nj-lang" className="input" value={language} onChange={(e) => setLanguage(e.target.value.trim())} />
            <span className="help">Other languages are added as translations later.</span>
          </div>
        </Disclosure>
      </div>
    </Dialog>
  );
}
