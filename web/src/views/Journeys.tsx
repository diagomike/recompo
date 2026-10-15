import { useMemo, useState } from "react";
import { CheckCircle2, GripVertical, Plus, Trash2, Type, Wand2, X } from "lucide-react";
import { clock, frameUrl, must, verb } from "../api";
import { useApp, useData } from "../App";
import RecipePlayer from "./RecipePlayer";

export default function Journeys() {
  const { route, go } = useApp();
  const { data: list } = useData(() => must<any[]>("journey.list"));
  const [title, setTitle] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const current = route.arg || list?.[0]?.ref || null;

  const create = async () => {
    if (!title.trim()) return;
    const env = await verb("journey.new", { title: title.trim() });
    if (!env.ok) setErr(env.error!.message);
    else { setTitle(""); go("journeys", env.refs![0]); }
  };

  return (
    <div className="page" style={{ maxWidth: "none" }}>
      <div className="jgrid">
        <div>
          <h1 className="h1">Journeys</h1>
          <p className="sub" style={{ fontSize: 12 }}>Authored sequences of cuts. Each is a recipe: sources and timecodes, shareable without the media.</p>
          <div className="row" style={{ marginBottom: 8 }}>
            <input className="input grow" placeholder="New journey title" value={title} onChange={(e) => setTitle(e.target.value)} onKeyDown={(e) => e.key === "Enter" && create()} />
            <button className="btn primary small" onClick={create}><Plus size={13} /></button>
          </div>
          {err && <div className="err">{err}</div>}
          {(list || []).map((j) => (
            <div key={j.ref} className="card" style={{ marginBottom: 6, cursor: "pointer", borderColor: j.ref === current ? "var(--accent)" : undefined }} onClick={() => go("journeys", j.ref)}>
              <div className="row"><b className="mono">{j.ref}</b><b className="grow">{j.title}</b><span className={"chip " + j.by}>{j.by}</span></div>
              <div style={{ color: "var(--muted)", fontSize: 12 }}>{j.slots} slots · {j.duration} · {j.sources.join(", ")}</div>
              {j.intent && <div style={{ fontSize: 12 }}>{j.intent}</div>}
            </div>
          ))}
          {list && !list.length && <div className="empty">No journeys yet. Name one above, or ask your agent to draft one.</div>}
        </div>
        <div>{current ? <Journey key={current} jref={current} slotParam={route.params.get("slot")} /> : null}</div>
      </div>
    </div>
  );
}

function Journey({ jref, slotParam }: { jref: string; slotParam: string | null }) {
  const { go } = useApp();
  const { data: j, error } = useData(() => must<any>("journey.show", { journey: jref }), [jref]);
  const { data: rec } = useData(() => must<any>("recipe.show", { journey: jref }), [jref]);
  const { data: sources } = useData(() => must<any[]>("source.list"));
  const [drag, setDrag] = useState<number | null>(null);
  const [over, setOver] = useState<number | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [check, setCheck] = useState<any>(null);
  const [startSlot, setStartSlot] = useState(Number(slotParam || 1));
  const [picker, setPicker] = useState(false);
  const [ov, setOv] = useState(false);
  const media = useMemo(() => new Set((sources || []).filter((s) => s.kind === "file").map((s) => s.ref)), [sources]);

  const call = async (name: string, args: any) => {
    const env = await verb(name, args);
    setMsg(env.ok ? null : env.error!.message + (env.error!.hint ? " — " + env.error!.hint : ""));
    return env;
  };
  const drop = async (to: number) => {
    if (drag == null || drag === to) return;
    const order = j.slots.map((_: any, k: number) => k + 1);
    const [moved] = order.splice(drag, 1);
    order.splice(to, 0, moved);
    setDrag(null); setOver(null);
    await call("journey.reorder", { journey: jref, order });
  };

  if (error) return <div className="err">{error}</div>;
  if (!j) return <div>Loading…</div>;
  const musicFiles: Record<string, string> = {};
  for (const m of j.music) if (m.file) musicFiles[m.track] = m.file;
  return (
    <div>
      <div className="row" style={{ marginBottom: 6 }}>
        <h2 className="h1" style={{ margin: 0 }}>{j.ref} · {j.title}</h2>
        <span className="chip">{j.duration}</span><span className="chip">{j.slots.length} slots</span>
        <div className="spacer" />
        <button className="btn small" onClick={async () => setCheck((await call("journey.validate", { journey: jref })).data)}><CheckCircle2 size={13} />Check</button>
        <button className="btn small" onClick={() => go("exports", null, { journey: jref })}>Export…</button>
      </div>
      {j.intent && <p className="sub" style={{ margin: "0 0 8px" }}>{j.intent}</p>}
      {msg && <div className="err">{msg}</div>}
      {check && (
        <div className={check.ok ? "warn" : "err"} style={check.ok ? { color: "var(--accent)", background: "var(--accent-soft)" } : undefined}>
          {check.ok ? "Ready to export." : "Problems: " + check.problems.join("; ")} {check.notes.length ? " Notes: " + check.notes.join("; ") : ""}
          <button className="btn ghost small" onClick={() => setCheck(null)}><X size={12} /></button>
        </div>
      )}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: 12 }}>
        <div>
          {rec && <RecipePlayer recipe={rec} startSlot={startSlot} hasMedia={(r) => media.has(r)} musicFiles={musicFiles} />}
          <div className="card" style={{ marginTop: 8 }}>
            <div className="row" style={{ marginBottom: 4 }}>
              <b>Overlays</b><div className="spacer" />
              <button className="btn small" onClick={() => call("overlay.auto-lower-thirds", { journey: jref })}><Wand2 size={13} />Lower thirds</button>
              <button className="btn small" onClick={() => setOv(!ov)}><Type size={13} />Add</button>
            </div>
            {ov && <OverlayForm jref={jref} slots={j.slots.length} onDone={() => setOv(false)} />}
            {j.overlays.map((o: any) => (
              <div key={o.ref} className="row" style={{ fontSize: 12, borderTop: "1px solid var(--line)", padding: "3px 0" }}>
                <span className="mono">{o.ref}</span><span className="chip">{o.kind}</span><span className="mono">{o.slot || "journey"} @{o.at}s</span>
                <span className="grow" style={{ whiteSpace: "pre-line" }}>{o.text}</span>
                <button className="btn ghost small" onClick={() => call("overlay.remove", { ref: o.ref })}><Trash2 size={12} /></button>
              </div>
            ))}
            {!j.overlays.length && <div style={{ color: "var(--faint)", fontSize: 12 }}>None.</div>}
          </div>
          <div className="card" style={{ marginTop: 8 }}>
            <b>Music</b>
            {j.music.map((m: any) => <div key={m.ref} style={{ fontSize: 12 }}>{m.ref} “{m.title}” · {m.artist} · {m.licence} · {m.gain_db} dB</div>)}
            {!j.music.length && <div style={{ color: "var(--faint)", fontSize: 12 }}>No bed. Ask your agent: <code>recomp music search "…"</code></div>}
          </div>
        </div>
        <div>
          <div className="row" style={{ marginBottom: 6 }}>
            <b>Slots</b><span style={{ color: "var(--muted)", fontSize: 12 }}>drag to reorder · click to play from there</span>
            <div className="spacer" /><button className="btn small" onClick={() => setPicker(!picker)}><Plus size={13} />Add cuts</button>
          </div>
          {picker && <CutPicker jref={jref} />}
          {j.slots.map((s: any, k: number) => (
            <div key={s.slot}>
              {s.section && <div className="section">{s.section}</div>}
              <div className={"slot" + (drag === k ? " drag" : "") + (over === k ? " over" : "")} draggable
                   onDragStart={() => setDrag(k)} onDragOver={(e) => { e.preventDefault(); setOver(k); }} onDrop={() => drop(k)} onDragEnd={() => { setDrag(null); setOver(null); }}>
                <span className="n"><GripVertical size={12} />{k + 1}</span>
                {media.has(s.source) ? <img src={frameUrl(s.source, parseClock(s.span.split("–")[0]) + 0.5)} alt="" onClick={() => setStartSlot(k + 1)} />
                  : <div style={{ width: 92, height: 52, background: "var(--panel-2)", borderRadius: 3 }} onClick={() => setStartSlot(k + 1)} />}
                <div style={{ minWidth: 0, cursor: "pointer" }} onClick={() => setStartSlot(k + 1)}>
                  <div><b>{s.title}</b> <span className="mono" style={{ color: "var(--muted)" }}>{s.cut} · {s.source} {s.span} · {s.dur}s</span></div>
                  <div style={{ color: "var(--muted)", fontSize: 12, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{s.why || s.quote}</div>
                  {s.transition && <span className="chip">{s.transition.type} {s.transition.dur}s</span>}
                </div>
                <div className="row" style={{ gap: 2 }}>
                  <button className="btn ghost small" title="Section heading" onClick={() => { const h = prompt("Section heading (empty to clear)", s.section || ""); if (h !== null) call("journey.section", { journey: jref, heading: h, at: k + 1 }); }}>§</button>
                  <button className="btn ghost small" title="Remove from journey" onClick={() => call("journey.remove", { slot: s.slot })}><Trash2 size={12} /></button>
                </div>
              </div>
            </div>
          ))}
          {!j.slots.length && <div className="empty">Add cuts from the picker, or from a source room.</div>}
        </div>
      </div>
    </div>
  );
}

function parseClock(c: string): number {
  return c.split(":").reduce((a, x) => a * 60 + parseFloat(x), 0);
}

function CutPicker({ jref }: { jref: string }) {
  const [q, setQ] = useState("");
  const { data } = useData(() => must<any[]>("cut.list", q ? { match: q } : {}), [q]);
  return (
    <div className="card" style={{ marginBottom: 8, maxHeight: 280, overflow: "auto" }}>
      <input className="input" style={{ width: "100%", marginBottom: 6 }} placeholder="Filter cuts (title, why, quote)" value={q} onChange={(e) => setQ(e.target.value)} />
      {(data || []).map((c) => (
        <div key={c.ref} className="row" style={{ fontSize: 12, borderTop: "1px solid var(--line)", padding: "3px 0" }}>
          <button className="btn small" onClick={() => verb("journey.add", { journey: jref, cuts: [c.ref] })}><Plus size={12} /></button>
          <span className="mono">{c.ref}</span><b>{c.title}</b><span className="mono" style={{ color: "var(--muted)" }}>{c.source} {clock(c.start, 0)} · {c.dur}s</span>
          <span style={{ color: "var(--muted)" }} className="grow">{c.why}</span>
        </div>
      ))}
    </div>
  );
}

function OverlayForm({ jref, slots, onDone }: { jref: string; slots: number; onDone: () => void }) {
  const [kind, setKind] = useState("title");
  const [target, setTarget] = useState("journey");
  const [text, setText] = useState("");
  const [at, setAt] = useState("0");
  const [msg, setMsg] = useState<string | null>(null);
  const save = async () => {
    const env = await verb("overlay.add", { target: target === "journey" ? jref : `${jref}#${target}`, kind, text, at });
    if (!env.ok) setMsg(env.error!.message); else onDone();
  };
  return (
    <div style={{ marginBottom: 6 }}>
      <div className="row">
        <select className="input" value={kind} onChange={(e) => setKind(e.target.value)}>{["title", "lower_third", "quote", "text", "section", "endcard"].map((k) => <option key={k}>{k}</option>)}</select>
        <select className="input" value={target} onChange={(e) => setTarget(e.target.value)}>
          <option value="journey">whole journey</option>{Array.from({ length: slots }, (_, k) => <option key={k} value={k + 1}>slot {k + 1}</option>)}
        </select>
        <input className="input" style={{ width: 60 }} value={at} onChange={(e) => setAt(e.target.value)} title="seconds in" />
      </div>
      <div className="row" style={{ marginTop: 4 }}>
        <input className="input grow" placeholder="Text (\n for a new line)" value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => e.key === "Enter" && save()} />
        <button className="btn primary small" onClick={save}>Add</button>
      </div>
      {msg && <div className="err">{msg}</div>}
    </div>
  );
}
