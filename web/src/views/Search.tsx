import { useEffect, useState } from "react";
import { Layers, Play, Scissors, Search as SearchIcon } from "lucide-react";
import { must } from "../api";
import { useApp, useData } from "../App";
import { Act, useActions } from "../actions";
import { Empty, Menu, SrcBadge, useWidth } from "../ui";

// Where is something said, across every source? Lines open in the source room; suggestions are whole thoughts
// that become cuts in one click (or go straight into a journey).
export default function SearchView() {
  const { go, route, setParam } = useApp();
  const { run } = useActions();
  const q0 = route.params.get("q") || "";
  const [q, setQ] = useState(q0);
  const [res, setRes] = useState<any>(null);
  const [sug, setSug] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const { data: journeys } = useData(() => must<any[]>("journey.list"));
  const { data: sources } = useData(() => must<any[]>("source.list"));
  const titles = Object.fromEntries((sources || []).map((s) => [s.ref, s.title])) as Record<string, string>;
  const wide = useWidth() > 1100;
  useEffect(() => {
    if (!q0.trim()) { setRes(null); setSug(null); return; }
    setErr(null); setBusy(true);
    Promise.all([must("search", { query: q0, limit: 40 }), must("cut.suggest", { query: q0, limit: 8 })])
      .then(([r, s]) => { setRes(r); setSug(s); }).catch((e) => setErr(e.message)).finally(() => setBusy(false));
  }, [q0]);
  const cutArgs = (c: any, journey?: string) => ({ ref: c.source, from: String(c.start), to: String(c.end), title: c.text.split(/(?<=[.?!])\s/)[0].slice(0, 60), why: `search: ${q0}`, ...(journey ? { journey } : {}) });
  return (
    <div className="page">
      <div className="pagehead">
        <div className="titles">
          <h1 className="h1">Search</h1>
          <p className="sub">Where is something said, across every source? Words or “exact phrases”. Suggestions are whole thoughts ready to cut.</p>
        </div>
      </div>
      <form className="filterbar" onSubmit={(e) => { e.preventDefault(); setParam("q", q.trim() || null); }}>
        <div className="search" style={{ maxWidth: "none" }}><SearchIcon size={14} />
          <input className="input" autoFocus value={q} data-filter="q" placeholder='e.g. forgiveness, "free will", everlasting life' onChange={(e) => setQ(e.target.value)} /></div>
        <button className="btn primary" type="submit" disabled={busy}>{busy ? "Searching…" : "Search"}</button>
        {res && <span className="muted2 nowrap">{res.hits.length} lines · {sug?.candidates.length || 0} moments</span>}
      </form>
      {err && <div className="err">{err}</div>}
      {!q0 && <Empty icon={<SearchIcon size={16} />} title="Search every transcript at once">Type a word, a theme, or a phrase in quotes. Results show where it is said, and suggest whole moments to cut.</Empty>}
      {res && (
        <div style={{ display: "grid", gridTemplateColumns: wide ? "minmax(0, 1fr) minmax(0, 1fr)" : "minmax(0, 1fr)", gap: 12, alignItems: "start" }}>
          <section className="panel">
            <div className="phead"><span className="h3 grow">Moments to cut</span><span className="muted2">whole thoughts, at sentence and pause boundaries</span></div>
            {!sug?.candidates.length && <div className="pbody muted2">No suggestions. Try other words, or open a line.</div>}
            <div className="reslist" style={{ border: 0 }}>
            {sug?.candidates.map((c: any, i: number) => (
              <div key={i} className="res">
                <div style={{ minWidth: 0 }}>
                  <div className="srcmini"><SrcBadge ref_={c.source} /><span className="ellipsis">{titles[c.source]}</span><span className="nowrap">· {Math.round(c.dur)}s</span></div>
                  <div className="quote clamp">“{c.text}”</div>
                </div>
                <div className="row tight nowrap">
                  <button className="btn small ghost icon" aria-label="Open in source" data-tip="Open in the source room" onClick={() => go("room", c.source, { t: c.start })}><Play size={13} /></button>
                  {!!journeys?.length && <Menu small label="Cut it into a journey" trigger={<><Layers size={13} />Into…</>} items={[
                    { header: "Cut it and add it to" },
                    ...(journeys || []).map((j) => ({ label: `${j.ref} · ${j.title}`,
                      onSelect: async () => { const e = await run("cut.add", cutArgs(c, j.ref), { label: `Cut into ${j.ref}` }); if (e.ok) go("journeys", j.ref, { step: "gather" }); } })),
                  ]} />}
                  <Act verb="cut.add" args={cutArgs(c)} small primary icon={<Scissors size={13} />} title="Cut it into the cut bin">Cut</Act>
                </div>
              </div>
            ))}
            </div>
          </section>
          <section className="panel">
            <div className="phead"><span className="h3 grow">{res.hits.length} lines</span>
              <span className="muted2">{res.mode === "any" ? "any of the words" : "all the words"} · {Object.entries(res.by_source).map(([s, n]) => `${s}: ${n}`).join(" · ")}</span></div>
            <div className="reslist" style={{ border: 0 }}>
            {res.hits.map((h: any, i: number) => (
              <div key={i} className="res" style={{ cursor: "pointer", gridTemplateColumns: "minmax(0, 1fr)" }} onClick={() => go("room", h.source, { t: h.start, tq: q0 })}>
                <div style={{ minWidth: 0 }}>
                  <div className="srcmini"><SrcBadge ref_={h.source} /><span className="mono faint">{String(h.at).replace(/^00:/, "")}</span>
                    {h.chapter && <span className="chip">{h.chapter.title}</span>}<span className="ellipsis">{h.title}</span></div>
                  <div>{h.context}</div>
                </div>
              </div>
            ))}
            </div>
          </section>
        </div>
      )}
      {res && <p className="muted2" style={{ marginTop: 10 }}>Cuts you make here land in the <a href="#" onClick={(e) => { e.preventDefault(); go("cuts"); }}>cut bin</a>; “Into…” cuts straight into a journey.</p>}
    </div>
  );
}
