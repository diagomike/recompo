import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronDown, Clapperboard, Layers, Plus, Scissors, Search as SearchIcon, Tag, Trash2, X } from "lucide-react";
import { clock, frameUrl, must, verb } from "../api";
import { useApp, useData } from "../App";
import { Act, useActions } from "../actions";
import { FilterBar, useFilters } from "../filters";
import { Empty, Menu, SrcBadge, useWidth } from "../ui";

// The cut bin: every cut from every source, filtered, multi-selected, and sent into journeys.
// The selection is shared with the agent (`recomp ui selection`), and the agent can tick cuts for you
// (`recomp ui select --refs C3,C7`).
export default function Cuts() {
  const { go, lastEvent, newJourney } = useApp();
  const narrow = useWidth() < 760;
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
  const [tag, setTag] = useState("");
  const [tagging, setTagging] = useState(false);
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
    <div className="page">
      <div className="pagehead">
        <div className="titles">
          <h1 className="h1">Cut bin</h1>
          <p className="sub">Every moment you have cut, from every source. Tick cuts in the order you want them, then add them to a journey.
            Double-click a title or a “why” to edit it.</p>
        </div>
        <button className="btn" onClick={() => go("search")}><SearchIcon size={14} />Find moments to cut</button>
      </div>
      <FilterBar count={list.length} noun={list.length === 1 ? "cut" : "cuts"} fields={[
        { key: "q", label: "Text", type: "text", placeholder: "Search titles, why, quotes" },
        { key: "source", label: "Source", type: "select", options: (sources || []).map((s) => [s.ref, `${s.ref} ${String(s.title).slice(0, 40)}`] as [string, string]) },
        { key: "tag", label: "Tag", type: "select", options: tags },
        ...(people.length ? [{ key: "person", label: "Person", type: "select" as const, options: people }] : []),
        { key: "journey", label: "In journey", type: "select", options: (journeys || []).map((j) => [j.ref, `${j.ref} ${j.title}`] as [string, string]) },
        { key: "by", label: "By", type: "select", options: [["user", "you"], ["agent", "agent"], ["machine", "machine"]] },
        { key: "min", label: "Min s", type: "number" },
        { key: "max", label: "Max s", type: "number" },
        { key: "unused", label: "Not in a journey", type: "check" },
      ]} />

      <div className={"actionbar" + (sel.length ? " live" : "")}>
        {sel.length ? <b>{sel.length} selected · {clock(total, 0).replace(/^00:/, "")}</b> : <span className="muted2">Tick cuts to add them to a journey. Shift-click selects a range.</span>}
        {!!sel.length && <span className="hint">{ordered.join(" → ")}</span>}
        <div className="spacer" />
        {!!sel.length && (
          <>
            <Menu label="Add to a journey" trigger={<><Layers size={14} />Add to journey<ChevronDown size={14} /></>} items={[
              ...(journeys || []).map((j) => ({ label: `${j.ref} · ${j.title}`, desc: `${j.slots} cuts · ${String(j.duration).replace(/^00:/, "").replace(/\.\d$/, "")}`,
                onSelect: async () => { const env = await run("journey.add", { journey: j.ref, cuts: ordered }, { label: `Add to ${j.ref}` }); if (env.ok) share([]); } })),
              ...((journeys || []).length ? ["sep" as const] : []),
              { label: "New journey with these…", icon: <Plus size={14} />, desc: "Name it, say what it is for and where it goes", onSelect: () => newJourney() },
            ]} />
            {tagging ? (
              <span className="row nowrap tight">
                <input className="input small" style={{ width: 140 }} autoFocus placeholder="tag" value={tag} onChange={(e) => setTag(e.target.value)}
                       onKeyDown={(e) => e.key === "Escape" && setTagging(false)} />
                <Act verb="cut.tag" args={{ refs: ordered, add: tag ? [tag] : [] }} small disabled={!tag} icon={<Tag size={14} />} onDone={() => { setTag(""); setTagging(false); }}>Tag</Act>
              </span>
            ) : <button className="btn" onClick={() => setTagging(true)}><Tag size={14} />Tag</button>}
            <Menu label="More for the selection" items={[
              { label: "Export each as a clip", icon: <Clapperboard size={14} />, desc: "One video per cut, with its own credits", onSelect: () => run("export.cuts", { cuts: ordered, profile: "clip" }, { label: "Export as clips" }) },
              ...(sel.length === 1 ? [{ label: `Delete ${sel[0]}`, icon: <Trash2 size={14} />, danger: true, desc: "Undo brings it back", onSelect: async () => { const env = await run("cut.remove", { ref: sel[0] }, { label: `Delete ${sel[0]}` }); if (env.ok) share([]); } }] : []),
              "sep",
              { label: "Clear the selection", icon: <X size={14} />, onSelect: () => share([]) },
            ]} />
          </>
        )}
      </div>

      {error && <div className="err">{error}</div>}
      {cuts && !all?.length && (
        <Empty icon={<Scissors size={14} />} title="No cuts yet"
               actions={<><button className="btn primary" onClick={() => go("search")}><SearchIcon size={14} />Search for a theme</button><button className="btn" onClick={() => go("sources")}>Open a source</button></>}>
          Search for a theme and cut from the suggestions, or open a source, drag across the lanes (or click a line and shift-click another) and press C.
        </Empty>
      )}
      {!!all?.length && !list.length && <Empty title="No cuts match these filters">Clear a filter or two to see more.</Empty>}
      {!!list.length && narrow && (
        <div className="reslist">
          {list.map((c, k) => {
            const on = sel.includes(c.ref);
            return (
              <div key={c.ref} className={"res thumbed" + (on ? " sel" : "")} onClick={(e) => toggle(k, e)} style={{ cursor: "pointer" }}>
                {media.has(c.source) ? <img src={frameUrl(c.source, c.start + Math.min(1, c.dur / 2), 160)} alt="" loading="lazy" /> : <div className="noimg" />}
                <div style={{ minWidth: 0 }}>
                  <div className="row nowrap tight"><input type="checkbox" checked={on} readOnly aria-label={`Select ${c.ref}`} /><b className="ellipsis">{c.title || "(untitled)"}</b>
                    {on && <span className="ord">{ordered.indexOf(c.ref) + 1}</span>}</div>
                  <div className="srcmini" style={{ marginTop: 4 }}><SrcBadge ref_={c.source} /><span className="ellipsis">{c.source_title}</span><span className="nowrap">· {Math.round(c.dur)}s</span></div>
                  {(c.why || c.quote) && <div className="muted2 ellipsis">{c.why || c.quote}</div>}
                </div>
                <div className="row tight">{(c.journeys || []).map((j: string) => <span key={j} className="chip info">{j}</span>)}</div>
              </div>
            );
          })}
        </div>
      )}
      {!!list.length && !narrow && (
        <table className="table cuts">
          <thead><tr><th style={{ width: 28 }}><input type="checkbox" aria-label="Select all shown" checked={list.every((c) => sel.includes(c.ref))}
            onChange={(e) => share(e.target.checked ? Array.from(new Set([...sel, ...list.map((c) => c.ref)])) : sel.filter((r) => !list.some((c) => c.ref === r)))} /></th>
            <th style={{ width: 128 }}></th><th>Cut</th><th>Source</th><th>Length</th><th>Tags</th><th>Journeys</th></tr></thead>
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
                          {c.by !== "user" && <span className={"chip " + c.by}>{c.by}</span>}</div>
                        <div className="muted2 editable" title="Double-click to say why it matters" onDoubleClick={(e) => { e.stopPropagation(); setEditing({ ref: c.ref, field: "why", text: c.why || "" }); }}>{c.why || <i>{c.quote}</i>}</div>
                      </>
                    )}
                  </td>
                  <td><a href="#" className="srcmini" style={{ color: "inherit" }} data-tip="Open this cut in its source"
                         onClick={(e) => { e.preventDefault(); e.stopPropagation(); go("room", c.source, { focus: c.ref }); }}>
                    <SrcBadge ref_={c.source} /><span className="ellipsis" style={{ maxWidth: 180 }}>{String(c.source_title || "")}</span></a></td>
                  <td className="nowrap"><span className="mono faint">{clock(c.start, 0).replace(/^00:/, "")}</span> · {Math.round(c.dur)}s</td>
                  <td><div className="row tight">{(c.tags || []).map((t: string) => <span key={t} className="chip">{t}</span>)}</div></td>
                  <td><div className="row tight">{(c.journeys || []).map((j: string) => <a key={j} href="#" className="chip info" onClick={(e) => { e.preventDefault(); e.stopPropagation(); go("journeys", j); }}>{j}</a>)}</div></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}
