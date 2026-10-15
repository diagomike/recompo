import { useEffect, useMemo, useRef, useState } from "react";
import { Clapperboard, Layers, Plus, Scissors, Tag, Trash2 } from "lucide-react";
import { clock, frameUrl, must, verb } from "../api";
import { useApp, useData } from "../App";
import { Act, useActions } from "../actions";
import { FilterBar, useFilters } from "../filters";

// The cut bin: every cut from every source, filtered, multi-selected, and sent into journeys.
// The selection is shared with the agent (`recomp ui selection`), and the agent can tick cuts for you
// (`recomp ui select --refs C3,C7`).
export default function Cuts() {
  const { go, lastEvent } = useApp();
  const { run } = useActions();
  const [f] = useFilters();
  const args: Record<string, any> = {};
  if (f.q) args.match = f.q;
  for (const k of ["source", "tag", "person", "journey", "by"]) if (f[k]) args[k] = f[k];
  if (f.min) args.min = Number(f.min);
  if (f.max) args.max = Number(f.max);
  if (f.unused) args.unused = true;
  const { data: cuts, error } = useData(() => must<any[]>("cut.list", { ...args, limit: 1000 }), [JSON.stringify(args)]);
  const { data: all } = useData(() => must<any[]>("cut.list", { limit: 1000 }));
  const { data: sources } = useData(() => must<any[]>("source.list"));
  const { data: journeys } = useData(() => must<any[]>("journey.list"));
  const [sel, setSel] = useState<string[]>([]);
  const [target, setTarget] = useState<string>("");
  const [tag, setTag] = useState("");
  const [jtitle, setJtitle] = useState("");
  const [editing, setEditing] = useState<{ ref: string; field: "title" | "why"; text: string } | null>(null);
  const saveEdit = async () => {
    if (!editing) return;
    const e = editing;
    setEditing(null);
    await run("cut.edit", { ref: e.ref, [e.field]: e.text.trim() }, { label: `Edit ${e.ref}` });
  };
  const anchor = useRef<number | null>(null);

  // The agent's selection (ui select --refs …) ticks cuts here.
  useEffect(() => {
    must<any>("ui.selection").then((s) => { if (s?.refs?.length && s.by !== "user") setSel(s.refs.filter((r: string) => /^C\d+$/.test(r))); }).catch(() => {});
  }, []);
  useEffect(() => {
    const v = lastEvent?.data?.value;
    if (lastEvent?.kind === "ui" && lastEvent.data?.key === "selection" && v?.by !== "user" && v?.refs) setSel(v.refs.filter((r: string) => /^C\d+$/.test(r)));
  }, [lastEvent]);
  const share = (refs: string[]) => {
    setSel(refs);
    verb("ui.select", { refs });
  };

  const tags = useMemo(() => Array.from(new Set((all || []).flatMap((c) => c.tags || []))).sort(), [all]);
  const people = useMemo(() => Array.from(new Set((all || []).flatMap((c) => c.people || []))).sort(), [all]);
  const media = useMemo(() => new Set((sources || []).filter((s) => s.has_media).map((s) => s.ref)), [sources]);
  const list = cuts || [];
  const total = list.reduce((a, c) => a + (sel.includes(c.ref) ? c.dur : 0), 0);
  const jsel = target || journeys?.[0]?.ref || "";

  const toggle = (k: number, e: React.MouseEvent | React.ChangeEvent) => {
    const ref = list[k].ref;
    if ((e as React.MouseEvent).shiftKey && anchor.current != null) {
      const [a, b] = [Math.min(anchor.current, k), Math.max(anchor.current, k)];
      share(Array.from(new Set([...sel, ...list.slice(a, b + 1).map((c) => c.ref)])));
    } else {
      anchor.current = k;
      share(sel.includes(ref) ? sel.filter((x) => x !== ref) : [...sel, ref]);
    }
  };
  // Keep the order the user ticked them in: that is the order they go into a journey.
  const ordered = sel.filter((r) => list.some((c) => c.ref === r) || (all || []).some((c) => c.ref === r));

  return (
    <div className="page" style={{ maxWidth: "none" }}>
      <h1 className="h1">Cut bin</h1>
      <p className="sub">Every cut from every source. Tick cuts (in the order you want them), then add them to a journey or start a new one. Mix
        sources freely: a journey can hold cuts from any number of films, talks and episodes. Double-click a title or a “why” to edit it.</p>
      <FilterBar count={list.length} fields={[
        { key: "q", label: "Text", type: "text", placeholder: "title, why, quote" },
        { key: "source", label: "Source", type: "select", options: (sources || []).map((s) => [s.ref, `${s.ref} ${String(s.title).slice(0, 40)}`] as [string, string]) },
        { key: "tag", label: "Tag", type: "select", options: tags },
        ...(people.length ? [{ key: "person", label: "Person", type: "select" as const, options: people }] : []),
        { key: "journey", label: "In journey", type: "select", options: (journeys || []).map((j) => [j.ref, `${j.ref} ${j.title}`] as [string, string]) },
        { key: "by", label: "By", type: "select", options: ["user", "agent", "machine"] },
        { key: "min", label: "Min s", type: "number" },
        { key: "max", label: "Max s", type: "number" },
        { key: "unused", label: "Not in a journey", type: "check" },
      ]} />

      <div className={"actionbar" + (sel.length ? " live" : "")}>
        <b>{sel.length ? `${sel.length} selected · ${clock(total, 0)}` : "Nothing selected"}</b>
        <span className="hint">{sel.length ? ordered.join(" → ") : "tick cuts; shift-click selects a range"}</span>
        <div className="spacer" />
        {!!sel.length && (
          <>
            <select className="input" value={jsel} onChange={(e) => setTarget(e.target.value)} aria-label="Journey">
              {(journeys || []).map((j) => <option key={j.ref} value={j.ref}>{j.ref} · {j.title}</option>)}
            </select>
            <Act verb="journey.add" args={{ journey: jsel, cuts: ordered }} small primary agent disabled={!jsel} icon={<Plus size={13} />}
                 onDone={() => share([])}>Add to {jsel || "journey"}</Act>
            <span className="act-wrap">
              <input className="input" style={{ width: 170 }} placeholder="New journey title" value={jtitle} onChange={(e) => setJtitle(e.target.value)}
                     onKeyDown={async (e) => { if (e.key === "Enter" && jtitle.trim()) { const env = await run("journey.new", { title: jtitle.trim(), cuts: ordered }, { label: "New journey" }); if (env.ok) { share([]); setJtitle(""); go("journeys", env.refs![0]); } } }} />
              <Act verb="journey.new" args={{ title: jtitle.trim(), cuts: ordered }} small disabled={!jtitle.trim()} icon={<Layers size={13} />}
                   onDone={(env) => { share([]); setJtitle(""); go("journeys", env.refs![0]); }}>New journey from selection</Act>
            </span>
            <span className="act-wrap">
              <input className="input" style={{ width: 110 }} placeholder="tag" value={tag} onChange={(e) => setTag(e.target.value)} />
              <Act verb="cut.tag" args={{ refs: ordered, add: tag ? [tag] : [] }} small disabled={!tag} icon={<Tag size={12} />} onDone={() => setTag("")}>Tag</Act>
            </span>
            <Act verb="export.cuts" args={{ cuts: ordered, profile: "clip" }} small agent icon={<Clapperboard size={12} />}>Export as clips</Act>
            {sel.length === 1 && <Act verb="cut.remove" args={{ ref: sel[0] }} small ghost confirm={`Delete ${sel[0]}? (undo brings it back)`} icon={<Trash2 size={12} />} onDone={() => share([])}>Delete</Act>}
            <button className="btn ghost small" onClick={() => share([])}>Clear</button>
          </>
        )}
      </div>

      {error && <div className="err">{error}</div>}
      {cuts && !all?.length && (
        <div className="empty">
          <Scissors size={16} /> No cuts yet. Open a source, drag across the lanes (or click a line and shift-click another) and press <span className="kbd">C</span>.
          Or search for a theme and cut from the suggestions.
          <div className="row" style={{ justifyContent: "center", marginTop: 8 }}>
            <button className="btn small" onClick={() => go("sources")}>Open sources</button>
            <button className="btn small" onClick={() => go("search")}>Search</button>
          </div>
        </div>
      )}
      {!!all?.length && !list.length && <div className="empty">No cuts match these filters.</div>}
      {!!list.length && (
        <table className="table cuts">
          <thead><tr><th style={{ width: 28 }}><input type="checkbox" aria-label="Select all shown" checked={list.every((c) => sel.includes(c.ref))}
            onChange={(e) => share(e.target.checked ? Array.from(new Set([...sel, ...list.map((c) => c.ref)])) : sel.filter((r) => !list.some((c) => c.ref === r)))} /></th>
            <th style={{ width: 96 }}></th><th>Cut</th><th>Source</th><th>Span</th><th>Tags</th><th>In</th></tr></thead>
          <tbody>
            {list.map((c, k) => {
              const on = sel.includes(c.ref);
              return (
                <tr key={c.ref} className={"click" + (on ? " on" : "")} draggable
                    onDragStart={(e) => { const refs = on ? ordered : [c.ref]; e.dataTransfer.setData("text/x-cuts", JSON.stringify(refs)); e.dataTransfer.setData("text/plain", refs.join(" ")); }}
                    onClick={(e) => toggle(k, e)}>
                  <td><input type="checkbox" checked={on} onChange={(e) => toggle(k, e)} onClick={(e) => e.stopPropagation()} aria-label={`Select ${c.ref}`} />
                    {on && <span className="ord">{ordered.indexOf(c.ref) + 1}</span>}</td>
                  <td>{media.has(c.source) ? <img className="thumb" src={frameUrl(c.source, c.start + Math.min(1, c.dur / 2), 160)} alt="" loading="lazy"
                         onError={(e) => ((e.target as HTMLImageElement).style.visibility = "hidden")} /> : <div className="thumb" />}</td>
                  <td onClick={(e) => editing?.ref === c.ref && e.stopPropagation()}>
                    {editing && editing.ref === c.ref ? (
                      <input className="input small" style={{ width: "100%" }} autoFocus value={editing.text} placeholder={editing.field}
                             onChange={(e) => setEditing({ ...editing, text: e.target.value })} onBlur={saveEdit}
                             onKeyDown={(e) => { if (e.key === "Enter") saveEdit(); if (e.key === "Escape") setEditing(null); }} />
                    ) : (
                      <>
                        <div><span className="mono">{c.ref}</span>{" "}
                          <b className="editable" title="Double-click to rename" onDoubleClick={(e) => { e.stopPropagation(); setEditing({ ref: c.ref, field: "title", text: c.title || "" }); }}>{c.title || "(untitled)"}</b>{" "}
                          <span className={"chip " + c.by}>{c.by}</span></div>
                        <div className="muted2 editable" title="Double-click to say why it matters" onDoubleClick={(e) => { e.stopPropagation(); setEditing({ ref: c.ref, field: "why", text: c.why || "" }); }}>{c.why || <i>{c.quote}</i>}</div>
                      </>
                    )}
                  </td>
                  <td><a href="#" onClick={(e) => { e.preventDefault(); e.stopPropagation(); go("room", c.source, { focus: c.ref }); }}>
                    <span className="mono">{c.source}</span></a> <span className="muted2">{String(c.source_title || "").slice(0, 48)}</span></td>
                  <td className="mono nowrap">{clock(c.start, 0)} · {Math.round(c.dur)}s</td>
                  <td>{(c.tags || []).map((t: string) => <span key={t} className="chip">{t}</span>)}</td>
                  <td>{(c.journeys || []).map((j: string) => <a key={j} href="#" className="chip" onClick={(e) => { e.preventDefault(); e.stopPropagation(); go("journeys", j); }}>{j}</a>)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}
