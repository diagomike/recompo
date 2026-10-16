import { useState } from "react";
import { ArrowRight, CheckCircle2, Circle, CircleDashed, Film, FolderOpen, Layers, Plus, Send, Sparkles } from "lucide-react";
import { must } from "../api";
import { useApp, useData } from "../App";
import { Act, useActions } from "../actions";
import { Disclosure, Menu } from "../ui";
import { JourneyTable } from "./Journeys";

// The project at a glance: journeys first (what you are making), then the setup steps still open, each with its
// next action. The agent reads the same list with `recomp project checklist`.
export default function Home() {
  const { go, newJourney } = useApp();
  const { run } = useActions();
  const { data, error } = useData(() => must<any>("project.checklist"));
  if (error) return <div className="page"><div className="err">{error}</div></div>;
  if (!data) return <div className="page">Loading…</div>;
  const steps = data.steps as any[];
  const open = steps.filter((s) => s.state !== "done");
  const done = steps.filter((s) => s.state === "done");
  const required = steps.filter((s) => !s.optional);
  const reqDone = required.filter((s) => s.state === "done").length;
  const hasSources = steps.find((s) => s.key === "sources")?.state === "done";
  const hasCuts = steps.find((s) => s.key === "cuts")?.state === "done";
  const journeys = data.journeys as any[];
  return (
    <div className="page">
      <div className="pagehead">
        <div className="titles">
          <div className="eyebrow">Project · {data.project.kind}</div>
          <h1 className="h1">{data.project.name}</h1>
          <p className="sub mono faint" style={{ fontSize: 13 }}>{data.project.path}</p>
        </div>
        <Menu label="Project actions" items={[
          { label: "Open the project folder", icon: <FolderOpen size={14} />, onSelect: () => run("project.reveal", { what: "root" }, { quiet: true }) },
          ...Object.keys(data.folders).map((k) => ({ label: `Open ${k}/`, icon: <FolderOpen size={14} />, onSelect: () => run("project.reveal", { what: k }, { quiet: true }) })),
          "sep",
          { label: "All projects", icon: <Layers size={14} />, onSelect: () => (window.location.hash = "#/") },
        ]} />
      </div>

      {!hasSources ? (
        <div className="hero">
          <div><h2>Start with your sources</h2>
            <p className="sub">Films, talks, podcasts or YouTube links. Files stay where they are; links bring captions first and video only when a journey needs it.</p></div>
          <div className="row"><button className="btn primary lg" onClick={() => go("sources", null, { browse: 1 })}><Film size={14} />Add sources</button></div>
        </div>
      ) : (
        <section className="section">
          <div className="sechead">
            <div className="grow"><h2 className="h2">Journeys</h2>
              <p className="sub">{journeys.length ? "Pick up where you left off, or start a new one." : "Your sources are ready: make something from them."}</p></div>
            {!!journeys.length && <button className="btn primary" onClick={newJourney}><Plus size={14} />New journey</button>}
          </div>
          {journeys.length ? <JourneyTable journeys={journeys} limit={6} /> : (
            <div className="hero">
              <div><h2>Make your first journey</h2>
                <p className="sub">Say what it is for and where it goes (Shorts, YouTube, the community hub). The studio walks you through gathering moments
                  from {hasCuts ? "your cuts and" : ""} your sources, putting them in order, the look, a check and the export.</p></div>
              <div className="row"><button className="btn primary lg" onClick={newJourney}><Sparkles size={14} />New journey</button></div>
            </div>
          )}
          {journeys.length > 6 && <div style={{ marginTop: 12 }}><button className="btn ghost" onClick={() => go("journeys")}>All {journeys.length} journeys<ArrowRight size={14} /></button></div>}
        </section>
      )}

      <section className="section">
        <div className="sechead">
          <div className="grow"><h2 className="h2">Project setup</h2>
            <p className="sub">{reqDone === required.length ? "Everything essential is in place." : `${reqDone} of ${required.length} essential steps done.`}</p></div>
          <div style={{ width: 200 }} className="bar"><i style={{ width: `${(reqDone / required.length) * 100}%` }} /></div>
        </div>
        <ol className="checklist">
          {open.map((s) => <StepRow key={s.key} s={s} next={s.key === data.next} />)}
        </ol>
        {!!done.length && (
          <div style={{ marginTop: 10 }}>
            <Disclosure id="home.done" label={`Finished steps`} count={done.length}>
              <ol className="checklist">{done.map((s) => <StepRow key={s.key} s={s} next={false} />)}</ol>
            </Disclosure>
          </div>
        )}
      </section>

      <section className="section">
        <Disclosure id="home.folders" label="Where everything lives">
          <div className="grid3">
            {Object.entries(data.folders).map(([k, f]: [string, any]) => (
              <div key={k} className="card pad-sm stack sm">
                <div className="row nowrap"><b className="grow">{k}/</b><span className="chip">{f.files} files · {f.mb >= 1000 ? (f.mb / 1000).toFixed(1) + " GB" : f.mb + " MB"}</span>
                  <Act verb="project.reveal" args={{ what: k }} small ghost quiet icon={<FolderOpen size={14} />} label={`Open ${k}/`}>{""}</Act></div>
                <div className="muted2">
                  {k === "sources" && "Media fetched for link sources, audio, thumbnails."}
                  {k === "recipes" && "One JSON recipe per journey: sources and timecodes, shareable without media."}
                  {k === "exports" && "<journey>/<profile>-<language>/: video, captions, description, credits, recipe."}
                </div>
                <div className="mono faint" style={{ fontSize: 12, overflowWrap: "anywhere" }}>{f.path}</div>
              </div>
            ))}
          </div>
        </Disclosure>
      </section>
    </div>
  );
}

function StepRow({ s, next }: { s: any; next: boolean }) {
  const { go } = useApp();
  const { ask } = useActions();
  const [asking, setAsking] = useState(false);
  const [draft, setDraft] = useState(s.agent);
  const expanded = s.state !== "done" || next;
  const open = (a: any) => {
    const params = Object.fromEntries(Object.entries(a.params || {}).filter(([k2]) => k2 !== "ref")) as any;
    go(a.view, a.params?.ref ?? null, params);
  };
  return (
    <li className={"step " + s.state + (next ? " next" : "")}>
      <span className="sicon">
        {s.state === "done" ? <CheckCircle2 size={14} /> : s.state === "partial" ? <CircleDashed size={14} /> : <Circle size={14} />}
      </span>
      <div className="stack sm">
        <div className="row tight">
          <b>{s.title}</b>
          {next && <span className="chip running">Next</span>}
          {s.optional && s.state !== "done" && <span className="chip">Optional</span>}
          <span className="sdetail">{s.detail}</span>
        </div>
        {expanded && (!!s.actions.length || s.agent) && (
          <div className="row tight">
            {s.actions.map((a: any, k: number) => a.verb
              ? <Act key={a.label} verb={a.verb} args={a.args} small primary={next && k === 0} agent>{a.label}</Act>
              : <button key={a.label} className={"btn small" + (next && k === 0 ? " primary" : "")} onClick={() => open(a)}>{a.label}</button>)}
            {s.agent && s.state !== "done" && !asking && (
              <button className="btn ghost small" data-tip="Leave this for the agent: it sees it in `recomp ui notes`" onClick={() => setAsking(true)}><Sparkles size={14} />Ask the agent…</button>
            )}
            {asking && (
              <span className="row nowrap grow" style={{ minWidth: 260 }}>
                <input className="input small grow" autoFocus value={draft} onChange={(e) => setDraft(e.target.value)}
                       onKeyDown={(e) => { if (e.key === "Enter" && draft.trim()) { ask(draft.trim()); setAsking(false); } if (e.key === "Escape") setAsking(false); }} />
                <button className="btn small" disabled={!draft.trim()} onClick={() => { ask(draft.trim()); setAsking(false); }}><Send size={14} />Send</button>
              </span>
            )}
          </div>
        )}
      </div>
    </li>
  );
}
