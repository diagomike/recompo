import { useState } from "react";
import { CheckCircle2, Circle, CircleDashed, FolderOpen, Send } from "lucide-react";
import { must } from "../api";
import { useApp, useData } from "../App";
import { Act, useActions } from "../actions";

// The project at a glance: where the work stands, step by step, with the next action for each step.
// The agent reads the same list with `recomp project checklist`.
export default function Home() {
  const { go } = useApp();
  const { ask } = useActions();
  const [asking, setAsking] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const { data, error } = useData(() => must<any>("project.checklist"));
  if (error) return <div className="page"><div className="err">{error}</div></div>;
  if (!data) return <div className="page">Loading…</div>;
  const nextKey = data.next;
  return (
    <div className="page" style={{ maxWidth: 1100 }}>
      <div className="row" style={{ marginBottom: 2 }}>
        <h1 className="h1" style={{ margin: 0 }}>{data.project.name}</h1>
        <span className="chip">{data.project.kind}</span>
        <div className="spacer" />
        <Act verb="project.reveal" args={{ what: "root" }} small icon={<FolderOpen size={13} />}>Open project folder</Act>
      </div>
      <p className="sub mono" style={{ fontSize: 12 }}>{data.project.path}</p>

      <div className="homegrid">
        <div>
          <h2 className="h2">Where this project stands</h2>
          <ol className="checklist">
            {data.steps.map((s: any, k: number) => (
              <li key={s.key} className={"step " + s.state + (s.key === nextKey ? " next" : "")}>
                <span className="sicon">
                  {s.state === "done" ? <CheckCircle2 size={16} /> : s.state === "partial" ? <CircleDashed size={16} /> : <Circle size={16} />}
                </span>
                <div className="sbody">
                  <div className="row" style={{ gap: 6 }}>
                    <b>{k + 1}. {s.title}</b>
                    {s.key === nextKey && <span className="chip running">next</span>}
                    <span className="sdetail">{s.detail}</span>
                  </div>
                  {(!!s.actions.length || s.agent) && (
                    <div className="row" style={{ gap: 4, marginTop: 4 }}>
                      {s.actions.map((a: any) => a.verb
                        ? <Act key={a.label} verb={a.verb} args={a.args} small agent>{a.label}</Act>
                        : <button key={a.label} className="btn small" onClick={() => go(a.view === "room" ? "room" : a.view, a.params?.ref ?? null,
                            Object.fromEntries(Object.entries(a.params || {}).filter(([k2]) => k2 !== "ref")) as any)}>{a.label}</button>)}
                      {s.agent && s.state !== "done" && asking !== s.key && (
                        <button className="btn ghost small" title="Leave this request for the agent (it sees it in `recomp ui notes`)"
                                onClick={() => { setAsking(s.key); setDraft(s.agent); }}>Ask the agent…</button>
                      )}
                      {asking === s.key && (
                        <span className="act-wrap grow">
                          <input className="input small grow" autoFocus value={draft} onChange={(e) => setDraft(e.target.value)}
                                 onKeyDown={(e) => { if (e.key === "Enter" && draft.trim()) { ask(draft.trim()); setAsking(null); } if (e.key === "Escape") setAsking(null); }} />
                          <button className="btn small" disabled={!draft.trim()} onClick={() => { ask(draft.trim()); setAsking(null); }}><Send size={12} />Send</button>
                        </span>
                      )}
                    </div>
                  )}
                </div>
              </li>
            ))}
          </ol>
        </div>
        <div>
          <h2 className="h2">Folders</h2>
          <p className="sub" style={{ fontSize: 12 }}>Everything lives in the project folder: your media stays where it is; the
            project keeps fetched media, recipes (journeys as JSON) and every export.</p>
          {Object.entries(data.folders).map(([k, f]: [string, any]) => (
            <div key={k} className="card folder">
              <div className="row">
                <b>{k}/</b>
                <span className="chip">{f.files} files · {f.mb >= 1000 ? (f.mb / 1000).toFixed(1) + " GB" : f.mb + " MB"}</span>
                <div className="spacer" />
                <Act verb="project.reveal" args={{ what: k }} small ghost quiet icon={<FolderOpen size={12} />}>Open</Act>
              </div>
              <div className="mono" style={{ color: "var(--faint)", fontSize: 11, overflowWrap: "anywhere" }}>{f.path}</div>
              <div style={{ color: "var(--muted)", fontSize: 12 }}>
                {k === "sources" && "Media fetched for link sources, audio, thumbnails."}
                {k === "recipes" && "One JSON recipe per journey: sources and timecodes, shareable without media."}
                {k === "exports" && "<journey>/<profile>-<language>/: video, captions, description, credits, recipe."}
              </div>
            </div>
          ))}
          <div className="guide" style={{ marginTop: 10 }}>
            <b>Working with an agent.</b> Every button here runs a command the agent can run too: hover a button to see it, or press the
            robot next to it to hand the action to the agent. The agent can open views, filter lists and point at buttons for you.
          </div>
        </div>
      </div>
    </div>
  );
}
