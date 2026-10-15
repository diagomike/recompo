import { useState } from "react";
import { Search as SearchIcon } from "lucide-react";
import { must } from "../api";
import { useApp } from "../App";
import { Act } from "../actions";

export default function SearchView() {
  const { go, route } = useApp();
  const [q, setQ] = useState(route.params.get("q") || "");
  const [res, setRes] = useState<any>(null);
  const [sug, setSug] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const run = async () => {
    if (!q.trim()) return;
    setErr(null);
    try {
      setRes(await must("search", { query: q, limit: 40 }));
      setSug(await must("cut.suggest", { query: q, limit: 8 }));
    } catch (e: any) { setErr(e.message); }
  };
  return (
    <div className="page">
      <h1 className="h1">Search</h1>
      <p className="sub">Where is something said, across every source? Words or "exact phrases". Hits open in the source room; suggestions are whole thoughts ready to cut.</p>
      <div className="row" style={{ marginBottom: 12 }}>
        <SearchIcon size={16} />
        <input className="input grow" autoFocus value={q} placeholder='e.g. forgiveness, "free will", everlasting life' onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && run()} />
        <button className="btn primary" onClick={run}>Search</button>
      </div>
      {err && <div className="err">{err}</div>}
      {res && (
        <div className="jgrid" style={{ gridTemplateColumns: "1fr 1fr" }}>
          <div>
            <div className="sub"><b>{res.hits.length}</b> lines ({res.mode === "any" ? "any word" : "all words"}) · {Object.entries(res.by_source).map(([s, n]) => `${s}: ${n}`).join(" · ")}</div>
            {res.hits.map((h: any, i: number) => (
              <div key={i} className="card" style={{ marginBottom: 6, cursor: "pointer" }} onClick={() => go("room", h.source, { t: h.start })}>
                <div className="row"><b className="mono">{h.source}</b><span className="mono" style={{ color: "var(--muted)" }}>{h.at}</span>
                  {h.chapter && <span className="chip">{h.chapter.ref} {h.chapter.title}</span>}<span style={{ color: "var(--muted)" }}>{h.title}</span></div>
                <div style={{ marginTop: 4 }}>{h.context}</div>
              </div>
            ))}
          </div>
          <div>
            <div className="sub">Cut candidates</div>
            {sug?.candidates.map((c: any, i: number) => (
              <div key={i} className="card" style={{ marginBottom: 6 }}>
                <div className="row"><b className="mono">{c.source}</b><span className="mono" style={{ color: "var(--muted)" }}>{c.span} · {c.dur}s</span></div>
                <div style={{ margin: "4px 0" }}>{c.text}</div>
                <div className="row" style={{ gap: 4 }}>
                  <Act verb="cut.add" args={{ ref: c.source, from: String(c.start), to: String(c.end), title: c.text.split(/[.?!]/)[0].slice(0, 60), why: `search: ${q}` }} small primary>Cut this</Act>
                  <button className="btn small ghost" onClick={() => go("room", c.source, { t: c.start })}>Open</button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
