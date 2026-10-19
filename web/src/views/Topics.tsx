// Topics (P17): what is in the air, and what the creators we follow said about it. A topic's brief lists their
// passages; tick the ones that argue something and draft "What my creators think about X" in a project.
import { useState } from "react";
import { Lightbulb, Newspaper, Play, Plus, RefreshCw, Sparkles } from "lucide-react";
import { must } from "../api";
import { useApp, useData } from "../App";
import { Act, useActions } from "../actions";
import { useFilters } from "../filters";
import { Disclosure, Empty } from "../ui";

export default function Topics() {
  const [f, setF] = useFilters();
  const tab = f.t ? "brief" : f.tab || "topics";
  const { data: topics, reload } = useData(() => must<any[]>("topic.list"));
  return (
    <div className="page">
      <div className="pagehead">
        <div className="titles">
          <h1 className="h1">Topics</h1>
          <p className="sub">A topic from the news or from you → what the creators we follow said about it, now and before → a journey.
            The news is a prompt, never a scoreboard.</p>
        </div>
      </div>
      <div className="segmented" style={{ marginBottom: 14 }} role="tablist">
        <button className={tab === "topics" ? "on" : ""} onClick={() => { setF("t", null); setF("tab", null); }}>Your topics ({topics?.length ?? 0})</button>
        <button className={tab === "suggest" ? "on" : ""} onClick={() => { setF("t", null); setF("tab", "suggest"); }}>In the air</button>
        {f.t && <button className="on">{f.t} brief</button>}
      </div>
      {tab === "topics" && <TopicList topics={topics} onChange={reload} />}
      {tab === "suggest" && <Suggest onAdded={() => { reload(); setF("tab", null); }} />}
      {tab === "brief" && <Brief key={f.t} tref={f.t} onChange={reload} />}
    </div>
  );
}

function TopicList({ topics, onChange }: { topics: any[] | null; onChange: () => void }) {
  const [, setF] = useFilters();
  const [title, setTitle] = useState("");
  const [terms, setTerms] = useState("");
  const termList = terms.split(",").map((x) => x.trim()).filter(Boolean);
  return (
    <>
      <div className="cmdrow boxed">
        <div className="cmdgroup grow">
          <Lightbulb size={14} className="faint" />
          <input className="input grow" placeholder="A topic in your words, e.g. AI models are getting good" value={title} onChange={(e) => setTitle(e.target.value)} />
          <input className="input" style={{ width: 300 }} placeholder="Terms people say: AI, AGI, superintelligence, copy itself" value={terms} onChange={(e) => setTerms(e.target.value)} />
        </div>
        <div className="cmdgroup">
          <Act verb="topic.add" args={{ title: title.trim(), terms: termList }} primary icon={<Plus size={14} />} disabled={!title.trim()}
               onDone={(env) => { setTitle(""); setTerms(""); onChange(); setF("t", env.data.ref); }}>Add topic</Act>
        </div>
      </div>
      {topics && !topics.length && <Empty icon={<Lightbulb size={14} />} title="No topics yet">Name one above, or pick one from <b>In the air</b>.</Empty>}
      {!!topics?.length && (
        <table className="table">
          <thead><tr><th>Topic</th><th>Terms</th><th>Brief</th><th>Journeys</th><th></th></tr></thead>
          <tbody>
            {topics.map((t) => (
              <tr key={t.ref} className="click" onClick={() => setF("t", t.ref)}>
                <td><span className="mono faint">{t.ref}</span> <b>{t.title}</b></td>
                <td className="muted2 ellipsis" style={{ maxWidth: 320 }}>{t.terms.join(", ")}</td>
                <td className="muted2">{t.scanned ? `${t.passages} passages · ${t.creators} creators · ${t.scanned}` : "not scanned"}</td>
                <td className="mono muted2">{(t.journeys || []).map((j: any) => `${j.project} ${j.journey}`).join(", ")}</td>
                <td className="nowrap" style={{ textAlign: "right" }} onClick={(e) => e.stopPropagation()}>
                  <Act verb="topic.scan" args={{ ref: t.ref }} small primary={!t.scanned} agent icon={<RefreshCw size={12} />} onDone={() => { onChange(); setF("t", t.ref); }}
                       title="Find what each followed creator said; fetch missing transcripts; write the brief">Scan</Act>
                  <Act verb="topic.remove" args={{ ref: t.ref }} small ghost confirm="Remove this topic and its brief" onDone={onChange}>Remove</Act>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}

const SECTIONS = ["top", "technology", "science", "world", "business", "health", "entertainment"];

function Suggest({ onAdded }: { onAdded: () => void }) {
  const { run } = useActions();
  const [f, setF] = useFilters();
  const section = f.section || "top";
  const [q, setQ] = useState(f.q || "");
  const [items, setItems] = useState<any[] | null>(null);
  const [busy, setBusy] = useState(false);
  const load = async () => {
    setBusy(true);
    const env = await run("topic.suggest", { section, query: q.trim() || undefined }, { quiet: true, label: "What is in the air" });
    setBusy(false);
    if (env.ok) setItems(env.data.suggestions);
  };
  return (
    <>
      <div className="cmdrow boxed">
        <div className="cmdgroup">
          <Newspaper size={14} className="faint" />
          <select className="input" value={section} onChange={(e) => setF("section", e.target.value === "top" ? null : e.target.value)} aria-label="News section">
            {SECTIONS.map((s) => <option key={s} value={s}>{s === "top" ? "Top stories" : s[0].toUpperCase() + s.slice(1)}</option>)}
          </select>
        </div>
        <div className="cmdgroup grow">
          <input className="input grow" placeholder="…or search this week's news" value={q} onChange={(e) => setQ(e.target.value)}
                 onKeyDown={(e) => e.key === "Enter" && load()} />
          <button className="btn primary" onClick={load} disabled={busy} data-tip="Runs this command"
                  data-tip-cmd={`recomp topic suggest${q ? ` --query "${q}"` : section !== "top" ? ` --section ${section}` : ""}`}>{busy ? "Reading…" : "Show"}</button>
        </div>
      </div>
      {!items && <Empty icon={<Newspaper size={14} />} title="Headlines as prompts">Each one shows which of the creators you follow have talked about it (from the library).</Empty>}
      {items && !items.length && <Empty icon={<Newspaper size={14} />} title="Nothing came back">Try another section.</Empty>}
      {!!items?.length && (
        <table className="table">
          <thead><tr><th>#</th><th>Prompt</th><th>Who has talked about it</th><th></th></tr></thead>
          <tbody>
            {items.map((s) => (
              <tr key={s.n}>
                <td className="mono faint">{s.n}</td>
                <td><span className="chip">{s.from}</span> {s.link ? <a href={s.link} target="_blank" rel="noreferrer">{s.title}</a> : s.title}
                  <div className="muted2">{[s.source, s.date].filter(Boolean).join(" · ")} · terms: {s.terms.join(", ")}</div></td>
                <td>{Object.entries(s.voices).map(([k, v]) => <span key={k} className="chip done" style={{ marginRight: 4 }}>{k} · {String(v)}</span>)}</td>
                <td style={{ textAlign: "right" }}>
                  <Act verb="topic.add" args={{ title: String(s.n) }} small primary={!!Object.keys(s.voices).length} icon={<Plus size={12} />} onDone={onAdded}>Make it a topic</Act>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}

function Brief({ tref, onChange }: { tref: string; onChange: () => void }) {
  const { route } = useApp();
  const { data: b, error, reload } = useData(() => must<any>("topic.brief", { ref: tref }), [tref]);
  const { data: projects } = useData(() => must<any>("project.list"));
  const [picked, setPicked] = useState<string[]>([]);
  if (error) {
    return <Empty icon={<Sparkles size={14} />} title={`${tref} has no brief yet`}
                  actions={<Act verb="topic.scan" args={{ ref: tref }} primary agent icon={<RefreshCw size={14} />} onDone={() => { reload(); onChange(); }}>Scan now</Act>}>
      Scanning finds what each followed creator said about it and fetches missing transcripts the cheap way.</Empty>;
  }
  if (!b) return null;
  const toggle = (id: string) => setPicked(picked.includes(id) ? picked.filter((x) => x !== id) : [...picked, id]);
  const s = b.summary;
  return (
    <>
      <div className="cmdrow boxed">
        <div className="cmdgroup grow">
          <b>{b.title}</b>
          <span className="muted2">{s.passages} passages · {s.episodes} episodes · {s.creators} creators{s.oldest ? ` · ${s.oldest} → ${s.newest}` : ""} · terms: {b.terms.join(", ")}</span>
        </div>
        <div className="cmdgroup">
          <Act verb="topic.scan" args={{ ref: tref }} small agent icon={<RefreshCw size={12} />} onDone={() => { reload(); onChange(); }}>Scan again</Act>
        </div>
      </div>
      {!!b.news?.length && (
        <Disclosure id="topics.news" label="In the news this week" count={b.news.length}>
          <ul className="plain">{b.news.map((n: any, k: number) => <li key={k}><a href={n.link} target="_blank" rel="noreferrer">{n.title}</a> <span className="muted2">{n.source} · {n.date}</span></li>)}</ul>
        </Disclosure>
      )}
      {b.creators.map((c: any) => (
        <section key={c.follow} className="briefcreator">
          <h2 className="h3">{c.name} <span className="muted2">{c.follow}{c.fetched ? ` · ${c.fetched} transcript(s) fetched` : ""}</span></h2>
          {!c.episodes.length && <div className="muted2">Nothing on this topic in the transcripts we have.</div>}
          {c.episodes.map((e: any) => (
            <div key={e.where} className="briefep">
              <div className="row tight"><b className="ellipsis grow">{e.title}</b><span className="mono muted2">{e.published || ""} · {e.where}</span>
                {e.timing !== "video" && <span className="chip running" data-tip="Times follow the podcast; drafting aligns them to the video when it can">podcast timing</span>}</div>
              {e.passages.map((p: any) => (
                <label key={p.id} className={"passage" + (picked.includes(p.id) ? " on" : "")}>
                  <input type="checkbox" checked={picked.includes(p.id)} onChange={() => toggle(p.id)} />
                  <span className="mono">{p.id}</span>
                  <span className="grow">
                    <span className="row tight">
                      {p.link && <a className="btn small ghost" href={p.link} target="_blank" rel="noreferrer" onClick={(ev) => ev.stopPropagation()}><Play size={12} />{p.at}</a>}
                      {!!p.speakers.length && <span className="muted2">{p.speakers.join(", ")}</span>}
                      <span className="faint">score {p.score} · {p.terms.join(", ")}</span>
                    </span>
                    <span className="ptext">{p.text}</span>
                  </span>
                </label>
              ))}
            </div>
          ))}
          {!!c.missing.length && (
            <Disclosure id={`topics.missing.${c.follow}`} label="Not read" count={c.missing.length}>
              <ul className="plain">{c.missing.map((m: any, k: number) => <li key={k}><span>{m.title}</span> <span className="muted2">— {m.why}</span></li>)}</ul>
            </Disclosure>
          )}
        </section>
      ))}
      <div className="actionbar live" style={{ position: "sticky", bottom: 0, top: "auto", marginTop: 12 }}>
        <span className="grow">{picked.length ? `${picked.length} passage(s): ${picked.join(", ")}` : "Tick the passages that argue something (or draft from the best two per creator)."}</span>
        {route.project ? (
          <Act verb="journey.from-topic" args={{ topic: tref, passages: picked }} primary agent icon={<Sparkles size={14} />}
               onDone={(env) => (window.location.hash = `#/p/${encodeURIComponent(route.project!)}/journeys/${env.data.journey}`)}
               title={`Cuts with why and who speaks, a section per creator, in ${route.project}`}>Draft journey in {route.project}</Act>
        ) : (
          <select className="input" defaultValue="" aria-label="Draft in project"
                  onChange={(e) => e.target.value && (window.location.hash = `#/p/${encodeURIComponent(e.target.value)}/topics?t=${tref}`)}>
            <option value="">Draft in a project…</option>
            {(projects?.projects || []).filter((p: any) => p.exists).map((p: any) => <option key={p.name} value={p.name}>{p.name}</option>)}
          </select>
        )}
      </div>
    </>
  );
}
