// The journey studio: one journey, six guided steps — purpose → gather → order → look → check → export.
// The rail shows what is done and what is next (from `recomp journey guide J1`, the same list the agent reads);
// each step has one obvious primary action at the bottom, and its advanced options folded away.
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { AlertTriangle, ArrowDown, ArrowLeft, ArrowRight, ArrowUp, Check, CheckCircle2, Clapperboard, Copy, Film, FolderOpen,
  GripVertical, Heading, Languages, Music, PartyPopper, Play, Plus, Scissors, Search as SearchIcon, Share2, Sparkles, Trash2,
  Type, UserSquare2, Wand2, X, XCircle } from "lucide-react";
import { clock, fileUrl, frameUrl, must } from "../api";
import { useApp, useData } from "../App";
import { Act, useActions } from "../actions";
import { DESTINATIONS, STEP_HELP } from "../journeyMeta";
import { Dialog, Disclosure, Empty, Menu, SrcBadge, mmss, useWidth } from "../ui";
import RecipePlayer from "./RecipePlayer";

type Guide = {
  journey: string; title: string; intent: string; formats: string[]; target: { min_s: number; max_s: number; hard_max_s: number | null } | null;
  duration_s: number; slots: number; sources: string[]; next: string | null; done: number; notes: string[];
  steps: { key: string; n: number; title: string; state: string; detail: string; hint: string; actions: any[]; agent: string; reviewed: boolean }[];
};

export default function Studio({ jref }: { jref: string }) {
  const { route, go, setParam } = useApp();
  const { data: g, error } = useData(() => must<Guide>("journey.guide", { journey: jref }), [jref]);
  const { data: j } = useData(() => must<any>("journey.show", { journey: jref }), [jref]);
  const { data: sources } = useData(() => must<any[]>("source.list"));
  const width = useWidth();
  const step = route.params.get("step") || g?.next || "purpose";
  const setStep = (s: string) => setParam("step", s);
  const media = useMemo(() => new Set((sources || []).filter((s) => s.has_media).map((s) => s.ref)), [sources]);
  const titles = useMemo(() => Object.fromEntries((sources || []).map((s) => [s.ref, s.title])), [sources]) as Record<string, string>;

  if (error) return <div className="page"><div className="err">{error}</div><button className="btn" onClick={() => go("journeys")}>All journeys</button></div>;
  if (!g || !j) return <div className="page">Loading…</div>;
  const cur = g.steps.find((s) => s.key === step) || g.steps[0];
  const idx = g.steps.indexOf(cur);
  const nextKey = g.steps[idx + 1]?.key;
  const ctx: StepCtx = { jref, g, j, media, titles, sources: sources || [], setStep, nextKey, cur: cur.key };

  return (
    <div className="studio">
      <div className="studiohead">
        <div className="grow" style={{ minWidth: 260 }}>
          <div className="eyebrow">
            <a href="#" onClick={(e) => { e.preventDefault(); go("journeys"); }} className="row tight" style={{ color: "inherit" }}><ArrowLeft size={14} />Journeys</a>
            <span className="faint">/ {j.ref}</span>
          </div>
          <h1 className="h1">{j.title}</h1>
          <div className="row tight">
            {g.formats.map((f) => <span key={f} className="chip info">{DESTINATIONS.find((d) => d.key === f)?.label || f}</span>)}
            {!g.formats.length && <a href="#" className="chip warn" onClick={(e) => { e.preventDefault(); setStep("purpose"); }}>Where does it go?</a>}
            <span className="chip">{g.slots} cut{g.slots === 1 ? "" : "s"} · {mmss(g.duration_s)}</span>
            {g.sources.map((s) => <span key={s} data-tip={titles[s]}><SrcBadge ref_={s} /></span>)}
          </div>
        </div>
        <JourneyMenu j={j} />
      </div>
      <div className="rail" role="tablist" aria-label="Steps">
        {g.steps.map((s) => (
          <button key={s.key} role="tab" aria-selected={s.key === cur.key}
                  className={"railstep " + s.state + (s.key === cur.key ? " on" : "") + (s.key === g.next ? " next" : "")}
                  onClick={() => setStep(s.key)} data-tip={width <= 1180 ? `${s.title}: ${s.detail}` : s.detail}>
            <span className="num">{s.state === "done" ? <Check size={16} /> : s.state === "problem" ? "!" : s.n}</span>
            <span className="rt">{RAIL[s.key] || s.title}</span>
            <span className="rd">{s.state === "done" ? "Done" : s.key === g.next ? "Next" : STEP_HELP[s.key]?.verb}</span>
          </button>
        ))}
      </div>
      <div className="stagewrap">
        {cur.key === "purpose" && <PurposeStep c={ctx} />}
        {cur.key === "gather" && <GatherStep c={ctx} />}
        {cur.key === "order" && <OrderStep c={ctx} />}
        {cur.key === "look" && <LookStep c={ctx} />}
        {cur.key === "check" && <CheckStep c={ctx} />}
        {cur.key === "export" && <ExportStep c={ctx} />}
      </div>
    </div>
  );
}

const RAIL: Record<string, string> = { purpose: "Purpose", gather: "Gather", order: "Order", look: "Look", check: "Check", export: "Export" };

type StepCtx = {
  jref: string; g: Guide; j: any; media: Set<string>; titles: Record<string, string>; sources: any[];
  setStep: (s: string) => void; nextKey?: string; cur: string;
};

function StepHead({ c, k, children }: { c: StepCtx; k: string; children?: ReactNode }) {
  const s = c.g.steps.find((x) => x.key === k)!;
  const { ask } = useActions();
  return (
    <div className="stephead">
      <div className="grow" style={{ minWidth: 240 }}>
        <div className="snum">Step {s.n} of 6</div>
        <h2 className="h2">{s.title}</h2>
        <p className="sub">{s.hint}</p>
      </div>
      <div className="row tight">
        {children}
        {s.agent && s.state !== "done" && (
          <button className="btn ghost" onClick={() => ask(s.agent, [c.jref])} data-tip="Leave this for the agent: it sees the request in `recomp ui notes`"
                  data-tip-cmd={`“${s.agent}”`}><Sparkles size={16} />Ask the agent</button>
        )}
      </div>
    </div>
  );
}

function StepFoot({ c, what, primary, back = true }: { c: StepCtx; what?: ReactNode; primary?: ReactNode; back?: boolean }) {
  const prev = c.g.steps[c.g.steps.findIndex((s) => s.key === c.cur) - 1];
  return (
    <div className="stepfoot">
      {back && prev && <button className="btn ghost" onClick={() => c.setStep(prev.key)}><ArrowLeft size={16} />{prev.title}</button>}
      <div className="what">{what}</div>
      {primary}
    </div>
  );
}

function NextButton({ c, label }: { c: StepCtx; label?: string }) {
  if (!c.nextKey) return null;
  const t = c.g.steps.find((s) => s.key === c.nextKey)!.title;
  return <button className="btn primary lg" onClick={() => c.setStep(c.nextKey!)}>{label || `Next: ${t}`}<ArrowRight size={18} /></button>;
}

// A bar of the journey's length against the destination's sweet spot.
function LengthMeter({ dur, target }: { dur: number; target: Guide["target"] }) {
  const scale = Math.max(target ? target.max_s * 1.35 : 120, dur * 1.08, 1);
  const pct = (x: number) => `${Math.min(100, (x / scale) * 100)}%`;
  const over = !!target && dur > target.max_s;
  const under = !!target && dur < target.min_s;
  return (
    <div className="stack sm">
      <div className="row nowrap"><b className="grow">{mmss(dur)}</b>
        {target && <span className={"chip " + (over ? "warn" : under ? "" : "ok")}>{over ? "Too long" : under ? "Short" : "In range"} · aim {mmss(target.min_s)}–{mmss(target.max_s)}</span>}
      </div>
      <div className="meter" aria-hidden>
        {target && <span className="zone" style={{ left: pct(target.min_s), width: `calc(${pct(target.max_s)} - ${pct(target.min_s)})` }} />}
        <i className={over ? "over" : ""} style={{ width: pct(dur) }} />
      </div>
    </div>
  );
}

function Thumb({ c, source, t, w = 200, className }: { c: StepCtx; source: string; t: number; w?: number; className?: string }) {
  return c.media.has(source) ? <img className={className} src={frameUrl(source, t, w)} alt="" loading="lazy" onError={(e) => ((e.target as HTMLImageElement).style.visibility = "hidden")} />
    : <div className={"noimg " + (className || "")} style={{ display: "grid", placeItems: "center", color: "var(--faint)" }}><Film size={18} /></div>;
}

const secs = (hms: string) => String(hms || "0").split(":").reduce((a, x) => a * 60 + parseFloat(x), 0);
const startOf = (span: string) => secs(span.split("–")[0]);
const short = (hms: string) => String(hms || "").replace(/^00:/, "").replace(/\.\d+$/, "");

// ── 1. Purpose ────────────────────────────────────────────────────────────────────────────
function PurposeStep({ c }: { c: StepCtx }) {
  const [title, setTitle] = useState(c.j.title);
  const [intent, setIntent] = useState(c.j.intent);
  const [formats, setFormats] = useState<string[]>(c.g.formats);
  const dirty = title !== c.j.title || intent !== c.j.intent || formats.join() !== c.g.formats.join();
  const args = { journey: c.jref, title: title.trim(), intent: intent.trim(), formats };
  return (
    <div className="stage noside">
      <div className="stagemain" style={{ maxWidth: 860 }}>
        <StepHead c={c} k="purpose" />
        <div className="card stack lg">
          <div className="field"><label htmlFor="p-title">Name</label>
            <input id="p-title" className="input lg" value={title} onChange={(e) => setTitle(e.target.value)} /></div>
          <div className="field"><label htmlFor="p-intent">What is it for?</label>
            <textarea id="p-intent" className="input" rows={2} value={intent} placeholder="The idea, question or feeling people should leave with."
                      onChange={(e) => setIntent(e.target.value)} /></div>
          <div className="field"><span className="label">Where will people see it?</span>
            <div className="grid2">
              {DESTINATIONS.map((d) => (
                <button key={d.key} type="button" className={"tile" + (formats.includes(d.key) ? " on" : "")} aria-pressed={formats.includes(d.key)}
                        onClick={() => setFormats(formats.includes(d.key) ? formats.filter((x) => x !== d.key) : [...formats, d.key])}>
                  <span className="tt"><input type="checkbox" readOnly checked={formats.includes(d.key)} tabIndex={-1} />{d.label}</span>
                  <span className="td">{d.note}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
        <StepFoot c={c} back={false} what={dirty ? "Unsaved changes" : "Saved. You can come back and change this any time."}
                  primary={dirty ? <Act verb="journey.edit" args={args} primary lg disabled={!title.trim()} onDone={() => c.setStep("gather")}>Save and gather cuts<ArrowRight size={18} /></Act>
                    : <NextButton c={c} />} />
      </div>
    </div>
  );
}

// ── 2. Gather ─────────────────────────────────────────────────────────────────────────────
function GatherStep({ c }: { c: StepCtx }) {
  const { route, setParam } = useApp();
  const from = route.params.get("from") || "suggest";
  return (
    <div className="stage">
      <div className="stagemain">
        <StepHead c={c} k="gather" />
        <div className="segmented" role="tablist">
          <button className={from === "suggest" ? "on" : ""} onClick={() => setParam("from", "suggest")}><Sparkles size={16} />Suggested</button>
          <button className={from === "bin" ? "on" : ""} onClick={() => setParam("from", "bin")}><Scissors size={16} />Your cuts</button>
          <button className={from === "sources" ? "on" : ""} onClick={() => setParam("from", "sources")}><Film size={16} />Cut from a source</button>
        </div>
        {from === "suggest" && <Suggestions c={c} />}
        {from === "bin" && <BinPicker c={c} />}
        {from === "sources" && <SourcePicker c={c} />}
        <StepFoot c={c} what={c.g.slots ? `${c.g.slots} cut${c.g.slots > 1 ? "s" : ""} from ${c.g.sources.length} source${c.g.sources.length > 1 ? "s" : ""} · ${mmss(c.g.duration_s)}` : "Add at least two cuts to tell something."}
                  primary={<button className="btn primary lg" disabled={!c.g.slots} onClick={() => c.setStep("order")}>Next: Order<ArrowRight size={18} /></button>} />
      </div>
      <aside className="stageside"><Tray c={c} /></aside>
    </div>
  );
}

function Tray({ c }: { c: StepCtx }) {
  return (
    <div className="card stack">
      <div className="row nowrap"><b className="grow">In this journey</b><span className="chip">{c.j.slots.length}</span></div>
      <LengthMeter dur={c.g.duration_s} target={c.g.target} />
      {!c.j.slots.length && <p className="muted2" style={{ margin: 0 }}>Cuts you add show up here, in order.</p>}
      <div className="stack sm">
        {c.j.slots.map((s: any, k: number) => (
          <div key={s.slot} className="slot compact">
            <span className="n">{k + 1}</span>
            <Thumb c={c} source={s.source} t={startOf(s.span) + 0.5} w={120} />
            <div style={{ minWidth: 0 }}>
              <div className="st ellipsis" style={{ fontSize: 14 }}>{s.title}</div>
              <div className="srcmini"><SrcBadge ref_={s.source} /><span className="ellipsis">{Math.round(s.dur)}s</span></div>
            </div>
            <Act verb="journey.remove" args={{ slot: s.slot }} small ghost icon={<X size={15} />} label={`Remove ${s.title}`}>{""}</Act>
          </div>
        ))}
      </div>
      {c.g.sources.length === 1 && c.j.slots.length > 1 && <p className="muted2" style={{ margin: 0 }}>All from one source. Journeys shine when voices meet: try “Cut from a source”.</p>}
    </div>
  );
}

function Suggestions({ c }: { c: StepCtx }) {
  const [q, setQ] = useState(c.j.intent || c.j.title);
  const [query, setQuery] = useState(q);
  const [added, setAdded] = useState<string[]>([]);
  const { data, error } = useData(() => (query.trim() ? must<any>("cut.suggest", { query, limit: 10 }) : Promise.resolve({ candidates: [] })), [query]);
  const { go } = useApp();
  const inJourney = (cand: any) => c.j.slots.some((s: any) => s.source === cand.source && Math.abs(startOf(s.span) - cand.start) < 2);
  return (
    <div className="stack">
      <form className="row nowrap" onSubmit={(e) => { e.preventDefault(); setQuery(q); }}>
        <div className="filterbar" style={{ margin: 0, flex: 1 }}>
          <div className="search" style={{ maxWidth: "none" }}><SearchIcon size={16} /><input className="input lg" value={q} onChange={(e) => setQ(e.target.value)} data-filter="q"
                 placeholder='What should the moments be about? Words or "a phrase"' /></div>
        </div>
        <button className="btn lg" type="submit" data-tip="Find whole-thought moments across every source" data-tip-cmd={`recomp cut suggest "${q}"`}>Suggest</button>
      </form>
      {error && <div className="err">{error}</div>}
      {!data && <div className="muted2">Looking across your sources…</div>}
      {data && !data.candidates.length && (
        <Empty icon={<SearchIcon size={22} />} title={`Nothing found for “${query}”`}>
          Try fewer or different words, a phrase someone would actually say, or pick from your cuts.
        </Empty>
      )}
      {data?.candidates.map((cand: any, k: number) => {
        const key = `${cand.source}@${cand.start}`;
        const isIn = added.includes(key) || inJourney(cand);
        const t = cand.text.split(/(?<=[.?!])\s/)[0].slice(0, 70);
        return (
          <div key={k} className={"card candidate" + (isIn ? " sel" : "")}>
            <div className="row nowrap">
              <SrcBadge ref_={cand.source} />
              <span className="ellipsis grow muted2">{c.titles[cand.source]}</span>
              <span className="chip">{cand.span.replace(/^00:/, "").replace(/–00:/, "–")} · {Math.round(cand.dur)}s</span>
            </div>
            <Quote text={cand.text} />
            <div className="row tight">
              {isIn ? <span className="chip ok"><Check size={14} />In the journey</span>
                : <Act verb="cut.add" small primary icon={<Plus size={15} />} onDone={() => setAdded([...added, key])}
                       args={{ ref: cand.source, from: String(cand.start), to: String(cand.end), title: t, why: `${c.j.ref}: ${c.j.intent || c.j.title}`.slice(0, 140), journey: c.jref }}
                       title="Make this a cut and add it to the journey">Add to journey</Act>}
              <button className="btn small ghost" onClick={() => go("room", cand.source, { t: cand.start, j: c.jref })} data-tip="Open the source here to adjust the edges before cutting"><Play size={15} />Open in source</button>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function Quote({ text }: { text: string }) {
  const [more, setMore] = useState(false);
  const long = text.length > 260;
  return (
    <div>
      <div className={"quote" + (long && !more ? " clamp" : "")}>“{text}”</div>
      {long && <button className="btn ghost small quiet" style={{ paddingLeft: 0 }} onClick={() => setMore(!more)}>{more ? "Less" : "Read all"}</button>}
    </div>
  );
}

function BinPicker({ c }: { c: StepCtx }) {
  const { route, setParam } = useApp();
  const q = route.params.get("cq") || "";
  const src = route.params.get("csrc") || "";
  const showAll = route.params.get("call") === "1";
  const [draft, setDraft] = useState(q);
  const { data: cuts } = useData(() => must<any[]>("cut.list", { ...(q ? { match: q } : {}), ...(src ? { source: src } : {}), limit: 500 }), [q, src]);
  const [sel, setSel] = useState<string[]>([]);
  const inJ = new Set(c.j.slots.map((s: any) => s.cut));
  const list = (cuts || []).filter((x) => showAll || !inJ.has(x.ref));
  const usedSrc = Array.from(new Set((cuts || []).map((x) => x.source)));
  useEffect(() => { const t = setTimeout(() => draft !== q && setParam("cq", draft || null), 300); return () => clearTimeout(t); }, [draft]);
  return (
    <div className="stack">
      <div className="filterbar" style={{ margin: 0 }}>
        <div className="search"><SearchIcon size={16} /><input className="input" placeholder="Filter your cuts" value={draft} onChange={(e) => setDraft(e.target.value)} data-filter="cq" /></div>
        <select className={"input" + (src ? " on" : "")} value={src} onChange={(e) => setParam("csrc", e.target.value || null)} aria-label="Source">
          <option value="">Every source</option>
          {c.sources.map((s) => <option key={s.ref} value={s.ref}>{s.ref} · {String(s.title).slice(0, 40)}</option>)}
        </select>
        <label className="check muted2"><input type="checkbox" checked={showAll} onChange={(e) => setParam("call", e.target.checked ? "1" : null)} />Show cuts already in it</label>
      </div>
      {!!sel.length && (
        <div className="actionbar live">
          <b>{sel.length} ticked</b><span className="hint">{sel.join(" → ")}</span><div className="spacer" />
          <Act verb="journey.add" args={{ journey: c.jref, cuts: sel }} primary icon={<Plus size={16} />} onDone={() => setSel([])}>Add {sel.length} to the journey</Act>
          <button className="btn ghost" onClick={() => setSel([])}>Clear</button>
        </div>
      )}
      {cuts && !list.length && (
        <Empty icon={<Scissors size={22} />} title={(cuts.length ? "Every matching cut is already in this journey" : q || src ? "No cuts match" : "No cuts yet")}>
          {cuts.length ? "Cut new moments from a source, or ask for suggestions." : "Use “Suggested” to find moments by theme, or “Cut from a source” to make your own."}
        </Empty>
      )}
      {usedSrc.length > 1 && !src && !!list.length && <div className="muted2">{list.length} cuts from {usedSrc.length} sources. Tick several to add them in that order.</div>}
      {list.map((x) => {
        const on = sel.includes(x.ref);
        return (
          <div key={x.ref} className={"card cutcard" + (inJ.has(x.ref) ? " in" : on ? " sel" : "")}>
            <Thumb c={c} source={x.source} t={x.start + Math.min(1, x.dur / 2)} w={224} />
            <div style={{ minWidth: 0 }}>
              <div className="row nowrap tight">
                {!inJ.has(x.ref) && <input type="checkbox" checked={on} aria-label={`Tick ${x.ref}`} onChange={() => setSel(on ? sel.filter((r) => r !== x.ref) : [...sel, x.ref])} />}
                <b className="ellipsis">{x.title || "(untitled)"}</b>{on && <span className="ord">{sel.indexOf(x.ref) + 1}</span>}
              </div>
              <div className="srcmini" style={{ marginTop: 4 }}><SrcBadge ref_={x.source} /><span className="ellipsis">{x.source_title}</span><span className="nowrap">· {clock(x.start, 0).replace(/^00:/, "")} · {Math.round(x.dur)}s</span></div>
              {(x.why || x.quote) && <div className="muted2 ellipsis" style={{ marginTop: 2 }}>{x.why || x.quote}</div>}
            </div>
            {inJ.has(x.ref) ? <span className="chip ok"><Check size={14} />In it</span>
              : <Act verb="journey.add" args={{ journey: c.jref, cuts: [x.ref] }} small icon={<Plus size={15} />}>Add</Act>}
          </div>
        );
      })}
    </div>
  );
}

function SourcePicker({ c }: { c: StepCtx }) {
  const { go } = useApp();
  if (!c.sources.length) return <Empty icon={<Film size={22} />} title="No sources yet" actions={<button className="btn primary" onClick={() => go("sources")}>Add sources</button>}>Add films, talks or links first.</Empty>;
  return (
    <div className="stack">
      <div className="callout"><Scissors size={18} /><div>Open a source, select a range (drag across the lanes, or click a line and shift-click another) and press <span className="kbd">C</span>.
        While you gather for {c.jref}, every cut you make there <b>goes straight into this journey</b>.</div></div>
      <div className="grid3">
        {c.sources.map((s) => (
          <button key={s.ref} className="card click" style={{ textAlign: "left", display: "grid", gap: 10, padding: 0, overflow: "hidden" }} onClick={() => go("room", s.ref, { j: c.jref })}>
            {s.has_media ? <img src={frameUrl(s.ref, Math.min(60, secs(s.duration) / 3), 480)} alt="" style={{ width: "100%", aspectRatio: "16/9", objectFit: "cover", display: "block", background: "var(--panel-3)" }} />
              : <div style={{ aspectRatio: "16/9", background: "var(--panel-3)", display: "grid", placeItems: "center", color: "var(--faint)" }}><Film size={28} /></div>}
            <div style={{ padding: "0 16px 16px" }}>
              <div className="row nowrap tight"><SrcBadge ref_={s.ref} /><b className="ellipsis">{s.title}</b></div>
              <div className="muted2" style={{ marginTop: 4 }}>{short(s.duration)} · {s.cuts || 0} cut{s.cuts === 1 ? "" : "s"}{s.transcript ? "" : " · no transcript yet"}</div>
              <div className="row tight" style={{ marginTop: 10 }}><span className="btn small primary"><Scissors size={15} />Open and cut</span></div>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

// ── 3. Order ──────────────────────────────────────────────────────────────────────────────
function OrderStep({ c }: { c: StepCtx }) {
  const { run } = useActions();
  const { go, route } = useApp();
  const [drag, setDrag] = useState<number | null>(null);
  const [over, setOver] = useState<number | null>(null);
  const [startSlot, setStartSlot] = useState(Number(route.params.get("slot") || 1));
  const [heading, setHeading] = useState<{ at: number; text: string } | null>(null);
  const [trim, setTrim] = useState<any>(null);
  const slots = c.j.slots as any[];
  const drop = async (to: number) => {
    if (drag == null || drag === to) return;
    const order = slots.map((_, k) => k + 1);
    const [moved] = order.splice(drag, 1);
    order.splice(to, 0, moved);
    setDrag(null); setOver(null);
    await run("journey.reorder", { journey: c.jref, order }, { label: "Reorder" });
  };
  const s = c.g.steps.find((x) => x.key === "order")!;
  return (
    <div className="stage">
      <div className="stagemain">
        <StepHead c={c} k="order" />
        {!slots.length && <Empty icon={<Scissors size={22} />} title="Nothing to order yet" actions={<button className="btn primary" onClick={() => c.setStep("gather")}>Gather cuts</button>}>Add cuts first.</Empty>}
        <div className="slotlist">
          {slots.map((sl, k) => (
            <div key={sl.slot}>
              {heading?.at === k + 1 ? (
                <form className="row nowrap" style={{ margin: "8px 0" }} onSubmit={async (e) => { e.preventDefault(); await run("journey.section", { journey: c.jref, heading: heading.text, at: k + 1 }, { label: "Section" }); setHeading(null); }}>
                  <Heading size={18} className="faint" />
                  <input className="input grow" autoFocus placeholder="Section heading (empty removes it)" value={heading.text} onChange={(e) => setHeading({ at: k + 1, text: e.target.value })}
                         onKeyDown={(e) => e.key === "Escape" && setHeading(null)} />
                  <button className="btn primary" type="submit">Set</button><button className="btn ghost" type="button" onClick={() => setHeading(null)}>Cancel</button>
                </form>
              ) : sl.section ? (
                <div className="sectionhead"><button className="btn ghost small" style={{ color: "inherit", fontWeight: 700, paddingLeft: 0 }} data-tip="Rename or remove this section"
                     onClick={() => setHeading({ at: k + 1, text: sl.section })}>{sl.section}</button></div>
              ) : k > 0 && (
                <div className="between"><button className="btn ghost small quiet" onClick={() => setHeading({ at: k + 1, text: "" })}><Plus size={14} />Section here</button></div>
              )}
              <div className={"slot" + (drag === k ? " drag" : "") + (over === k ? " over" : "") + (startSlot === k + 1 ? " playing" : "")} draggable
                   onDragStart={() => setDrag(k)} onDragOver={(e) => { e.preventDefault(); if (drag != null) setOver(k); }}
                   onDrop={() => drop(k)} onDragEnd={() => { setDrag(null); setOver(null); }}>
                <span className="n" data-tip="Drag to reorder"><GripVertical size={16} />{k + 1}</span>
                <button className="btn ghost" style={{ padding: 0, height: "auto", border: 0 }} onClick={() => setStartSlot(k + 1)} data-tip="Play from here">
                  <Thumb c={c} source={sl.source} t={startOf(sl.span) + 0.5} />
                </button>
                <div style={{ minWidth: 0, cursor: "pointer" }} onClick={() => setStartSlot(k + 1)}>
                  <div className="st">{sl.title}</div>
                  <div className="srcmini"><SrcBadge ref_={sl.source} /><span className="ellipsis">{c.titles[sl.source]}</span></div>
                  <div className="sl ellipsis">{sl.why || sl.quote}</div>
                  <div className="row tight" style={{ marginTop: 4 }}>
                    <span className="chip">{Math.round(sl.dur)}s</span>
                    {sl.trimmed && <span className="chip info">trimmed</span>}
                    {sl.transition && <span className="chip">{sl.transition.type} {sl.transition.dur}s</span>}
                  </div>
                </div>
                <div className="row tight nowrap">
                  <Act verb="journey.move" args={{ slot: sl.slot, to: k }} small ghost icon={<ArrowUp size={16} />} label="Move up" disabled={k === 0}>{""}</Act>
                  <Act verb="journey.move" args={{ slot: sl.slot, to: k + 2 }} small ghost icon={<ArrowDown size={16} />} label="Move down" disabled={k === slots.length - 1}>{""}</Act>
                  <Menu small label="More for this cut" items={[
                    { label: "Play from here", icon: <Play size={16} />, onSelect: () => setStartSlot(k + 1) },
                    { label: sl.section ? "Rename section" : "Start a section here", icon: <Heading size={16} />, onSelect: () => setHeading({ at: k + 1, text: sl.section || "" }) },
                    { label: "Trim the edges…", icon: <Scissors size={16} />, desc: "Tighten in and out for this journey only", onSelect: () => setTrim(sl) },
                    { label: sl.transition?.type === "fade" ? "Hard cut into it" : "Fade into it", icon: <Wand2 size={16} />,
                      onSelect: () => run("journey.transition", { slot: sl.slot, type: sl.transition?.type === "fade" ? "cut" : "fade", dur: 0.5 }, { label: "Transition" }) },
                    { label: "Open in its source", icon: <Film size={16} />, onSelect: () => go("room", sl.source, { focus: sl.cut, j: c.jref }) },
                    "sep",
                    { label: "Remove from journey", icon: <Trash2 size={16} />, danger: true, desc: "The cut stays in your cut bin", onSelect: () => run("journey.remove", { slot: sl.slot }, { label: `Remove ${sl.title}` }) },
                  ]} />
                </div>
              </div>
            </div>
          ))}
        </div>
        <StepFoot c={c} what={s.state === "done" ? "Order confirmed. Changing it is always fine." : "Play it through on the right. When it reads well, confirm."}
                  primary={s.state === "done" ? <NextButton c={c} /> :
                    <Act verb="journey.review" args={{ journey: c.jref, step: "order" }} primary lg disabled={slots.length < 2} onDone={() => c.setStep("look")}>Order looks right<ArrowRight size={18} /></Act>} />
      </div>
      <aside className="stageside"><PlayerCard c={c} startSlot={startSlot} /></aside>
      {trim && <TrimDialog slot={trim} onClose={() => setTrim(null)} />}
    </div>
  );
}

function TrimDialog({ slot, onClose }: { slot: any; onClose: () => void }) {
  const [a, setA] = useState("");
  const [b, setB] = useState("");
  return (
    <Dialog title={`Trim “${slot.title}”`} sub="Seconds to move each edge, for this journey only (the cut itself stays). +1.5 starts later; −2 ends earlier."
            onClose={onClose} footer={<>
              <Act verb="journey.trim-slot" args={{ slot: slot.slot, start: "reset", end: "reset" }} ghost onDone={onClose}>Reset</Act>
              <div className="spacer" /><button className="btn" onClick={onClose}>Cancel</button>
              <Act verb="journey.trim-slot" args={{ slot: slot.slot, ...(a ? { start: a } : {}), ...(b ? { end: b } : {}) }} primary disabled={!a && !b} onDone={onClose}>Apply</Act>
            </>}>
      <div className="grid2">
        <div className="field"><label>Start</label><input className="input" placeholder="+1.5" value={a} onChange={(e) => setA(e.target.value)} /></div>
        <div className="field"><label>End</label><input className="input" placeholder="-2" value={b} onChange={(e) => setB(e.target.value)} /></div>
      </div>
      <p className="muted2">Now: {slot.span} ({slot.dur}s)</p>
    </Dialog>
  );
}

function PlayerCard({ c, startSlot = 1 }: { c: StepCtx; startSlot?: number }) {
  const { data: rec } = useData(() => must<any>("recipe.show", { journey: c.jref }), [c.jref]);
  const musicFiles: Record<string, string> = {};
  for (const m of c.j.music) if (m.file) musicFiles[m.track] = m.file;
  return (
    <div className="stack">
      {rec && c.j.slots.length ? <RecipePlayer recipe={rec} startSlot={startSlot} hasMedia={(r) => c.media.has(r)} musicFiles={musicFiles} />
        : <div className="card muted2">The player appears once the journey has cuts.</div>}
      <div className="card pad-sm"><LengthMeter dur={c.g.duration_s} target={c.g.target} /></div>
    </div>
  );
}

// ── 4. Look ───────────────────────────────────────────────────────────────────────────────
function LookStep({ c }: { c: StepCtx }) {
  const ov = c.j.overlays as any[];
  const titleOv = ov.find((o) => o.kind === "title");
  const lowers = ov.filter((o) => o.kind === "lower_third");
  const others = ov.filter((o) => o.kind !== "title" && o.kind !== "lower_third");
  const [titleText, setTitleText] = useState(c.j.title);
  const s = c.g.steps.find((x) => x.key === "look")!;
  return (
    <div className="stage">
      <div className="stagemain">
        <StepHead c={c} k="look" />
        <div className={"card lookcard" + (titleOv ? " done" : "")}>
          <span className="licon"><Type size={22} /></span>
          <div className="stack">
            <div><h3 className="h3">Title card</h3><p className="muted2" style={{ margin: 0 }}>Opens the journey for three seconds. Use the hook, not just the name.</p></div>
            {titleOv ? (
              <div className="row"><span className="chip ok"><Check size={14} />On</span><b className="grow">“{titleOv.text}”</b>
                <Act verb="overlay.remove" args={{ ref: titleOv.ref }} small ghost icon={<Trash2 size={15} />} label="Remove the title card">{""}</Act></div>
            ) : (
              <div className="row nowrap">
                <input className="input grow" value={titleText} onChange={(e) => setTitleText(e.target.value)} placeholder="Title text" />
                <Act verb="overlay.add" args={{ target: c.jref, kind: "title", text: titleText, at: "0" }} primary disabled={!titleText.trim()} icon={<Plus size={16} />}>Add</Act>
              </div>
            )}
          </div>
        </div>
        <div className={"card lookcard" + (lowers.length ? " done" : "")}>
          <span className="licon"><UserSquare2 size={22} /></span>
          <div className="stack">
            <div><h3 className="h3">Who is speaking</h3><p className="muted2" style={{ margin: 0 }}>Lower thirds credit each speaker and where the moment comes from: essential when cuts come from different sources.</p></div>
            <div className="row">
              {lowers.length ? <span className="chip ok"><Check size={14} />{lowers.length} lower third{lowers.length > 1 ? "s" : ""}</span> : null}
              <Act verb="overlay.auto-lower-thirds" args={{ journey: c.jref }} primary={!lowers.length} agent icon={<Wand2 size={16} />}>{lowers.length ? "Redo them" : "Credit every speaker and source"}</Act>
            </div>
            {!!lowers.length && (
              <Disclosure id="look.lowers" label="Show them">
                <div className="stack sm">
                  {lowers.map((o) => (
                    <div key={o.ref} className="row nowrap" style={{ borderTop: "1px solid var(--line)", paddingTop: 8 }}>
                      <span className="chip">{o.slot}</span><span className="grow" style={{ whiteSpace: "pre-line" }}>{o.text}</span>
                      <Act verb="overlay.remove" args={{ ref: o.ref }} small ghost icon={<Trash2 size={15} />} label={`Remove ${o.ref}`}>{""}</Act>
                    </div>
                  ))}
                </div>
              </Disclosure>
            )}
          </div>
        </div>
        <MusicCard c={c} />
        <Disclosure id="look.more" label="More text on screen (quotes, captions, endcard text)" count={others.length}>
          <div className="card stack">
            {others.map((o) => (
              <div key={o.ref} className="row nowrap"><span className="chip">{o.kind}</span><span className="chip">{o.slot || "journey"} @{o.at}s</span>
                <span className="grow" style={{ whiteSpace: "pre-line" }}>{o.text}</span>
                <Act verb="overlay.remove" args={{ ref: o.ref }} small ghost icon={<Trash2 size={15} />} label={`Remove ${o.ref}`}>{""}</Act></div>
            ))}
            <OverlayForm jref={c.jref} slots={c.j.slots.length} />
          </div>
        </Disclosure>
        <StepFoot c={c} what={s.detail}
                  primary={s.state === "done" ? <NextButton c={c} /> :
                    <Act verb="journey.review" args={{ journey: c.jref, step: "look" }} primary lg onDone={() => c.setStep("check")}>Looks good<ArrowRight size={18} /></Act>} />
      </div>
      <aside className="stageside"><PlayerCard c={c} /></aside>
    </div>
  );
}

function MusicCard({ c }: { c: StepCtx }) {
  const { run } = useActions();
  const bed = c.j.music[0];
  const { data: lib } = useData(() => must<any[]>("music.list"));
  const [q, setQ] = useState("");
  const [res, setRes] = useState<any[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [gain, setGain] = useState<string>("");
  const search = async () => {
    if (!q.trim()) return;
    setSearching(true);
    const env = await run("music.search", { query: q.trim(), limit: 8 }, { quiet: true, label: "Music search" });
    setSearching(false);
    setRes(env.ok ? env.data : []);
  };
  const use = async (n: number) => {
    const got = await run("music.get", { pick: String(n) }, { label: "Fetch track" });
    if (got.ok) await run("music.bed-add", { journey: c.jref, track: got.refs![0] }, { label: "Music bed" });
  };
  return (
    <div className={"card lookcard" + (bed ? " done" : "")}>
      <span className="licon"><Music size={22} /></span>
      <div className="stack">
        <div><h3 className="h3">Music bed</h3><p className="muted2" style={{ margin: 0 }}>A quiet track under everything, ducked automatically while people speak. Open licences only (CC0, CC BY).</p></div>
        {bed ? (
          <>
            <div className="row nowrap"><span className="chip ok"><Check size={14} />On</span>
              <span className="grow ellipsis"><b>{bed.title}</b> · {bed.artist} <span className="chip">{bed.licence}</span></span>
              <Act verb="music.bed-remove" args={{ ref: bed.ref }} small ghost icon={<Trash2 size={15} />} label="Remove the music">{""}</Act></div>
            <Disclosure id="look.musiclevel" label="Level and ducking">
              <div className="row">
                <label className="muted2">Level (dB)</label>
                <input className="input small" style={{ width: 90 }} type="number" placeholder={String(bed.gain_db)} value={gain} onChange={(e) => setGain(e.target.value)} />
                <Act verb="music.bed-edit" args={{ ref: bed.ref, gain: Number(gain) }} small disabled={gain === ""} onDone={() => setGain("")}>Set</Act>
                <span className="muted2">Ducks {bed.duck_db} dB under speech.</span>
              </div>
            </Disclosure>
          </>
        ) : (
          <>
            {!!lib?.length && (
              <div className="stack sm">
                <span className="muted2">From your library</span>
                {lib.slice(0, 4).map((t) => (
                  <div key={t.ref} className="row nowrap"><span className="grow ellipsis"><b>{t.title}</b> · {t.artist} <span className="chip">{t.licence}</span></span>
                    <Act verb="music.bed-add" args={{ journey: c.jref, track: t.ref }} small icon={<Plus size={15} />}>Use</Act></div>
                ))}
              </div>
            )}
            <form className="row nowrap" onSubmit={(e) => { e.preventDefault(); search(); }}>
              <input className="input grow" placeholder="Mood or instrument, e.g. calm piano" value={q} onChange={(e) => setQ(e.target.value)} />
              <button className="btn" type="submit" disabled={!q.trim() || searching} data-tip="Searches open-licensed music (Openverse)" data-tip-cmd={`recomp music search "${q}"`}>
                <SearchIcon size={16} />{searching ? "Searching…" : "Find music"}</button>
            </form>
            {res && !res.length && <div className="muted2">Nothing found (or no network). Try another mood.</div>}
            {res?.map((r) => (
              <div key={r.n} className="row nowrap" style={{ borderTop: "1px solid var(--line)", paddingTop: 8 }}>
                <span className="grow ellipsis"><b>{r.title}</b> · {r.artist} <span className="chip">{r.licence}</span> <span className="faint">{r.duration ? mmss(r.duration) : ""}</span></span>
                {r.page_url && <a className="btn small ghost" href={r.page_url} target="_blank" rel="noreferrer" data-tip="Listen on the provider's page">Listen</a>}
                <button className="btn small" onClick={() => use(r.n)} data-tip="Download it with its licence and lay it under the journey" data-tip-cmd={`recomp music get ${r.n} && recomp music bed-add ${c.jref} M…`}><Plus size={15} />Use</button>
              </div>
            ))}
          </>
        )}
      </div>
    </div>
  );
}

function OverlayForm({ jref, slots }: { jref: string; slots: number }) {
  const [kind, setKind] = useState("quote");
  const [target, setTarget] = useState("journey");
  const [text, setText] = useState("");
  const [at, setAt] = useState("0");
  return (
    <div className="stack sm">
      <div className="row">
        <select className="input" value={kind} onChange={(e) => setKind(e.target.value)} aria-label="Kind">{["quote", "text", "section", "lower_third", "title", "endcard"].map((k) => <option key={k}>{k}</option>)}</select>
        <select className="input" value={target} onChange={(e) => setTarget(e.target.value)} aria-label="Where">
          <option value="journey">over the whole journey</option>{Array.from({ length: slots }, (_, k) => <option key={k} value={k + 1}>on cut {k + 1}</option>)}
        </select>
        <label className="muted2">at</label><input className="input" style={{ width: 80 }} value={at} onChange={(e) => setAt(e.target.value)} aria-label="Seconds in" /><span className="muted2">s</span>
      </div>
      <div className="row nowrap">
        <input className="input grow" placeholder="Text (\n for a new line)" value={text} onChange={(e) => setText(e.target.value)} />
        <Act verb="overlay.add" args={{ target: target === "journey" ? jref : `${jref}#${target}`, kind, text, at }} disabled={!text.trim()} onDone={() => setText("")} icon={<Plus size={16} />}>Add</Act>
      </div>
    </div>
  );
}

// ── 5. Check ──────────────────────────────────────────────────────────────────────────────
function CheckStep({ c }: { c: StepCtx }) {
  const { data: v } = useData(() => must<any>("journey.validate", { journey: c.jref }), [c.jref]);
  const { data: exps } = useData(() => must<any[]>("export.status", { of: c.jref, limit: 30 }), [c.jref]);
  const profiles = c.g.formats.map((f) => DESTINATIONS.find((d) => d.key === f)?.profile).filter(Boolean) as string[];
  const [profile, setProfile] = useState(profiles[0] || "landscape");
  const latest = (exps || []).find((x) => x.preview);
  const s = c.g.steps.find((x) => x.key === "check")!;
  return (
    <div className="stage">
      <div className="stagemain">
        <StepHead c={c} k="check" />
        <div className="card">
          <div className="cardhead"><h3 className="h3 grow" style={{ margin: 0 }}>Validation</h3>
            {v && <span className={"chip " + (v.ok ? "ok" : "problem")}>{v.ok ? "Ready to export" : `${v.problems.length} to fix`}</span>}</div>
          {!v && <div className="muted2">Checking…</div>}
          {v && (
            <div>
              {v.problems.map((p: string) => <div key={p} className="checkline"><XCircle size={18} color="var(--red)" /><span>{p}</span></div>)}
              {v.notes.map((p: string) => <div key={p} className="checkline"><AlertTriangle size={18} color="var(--amber)" /><span>{p}</span></div>)}
              {v.ok && <div className="checkline"><CheckCircle2 size={18} color="var(--accent)" /><span>Every source is reachable, every cut is long enough, the recipe is complete ({v.duration.replace(/^00:/, "")}).</span></div>}
            </div>
          )}
        </div>
        <div className="card stack">
          <div className="cardhead" style={{ marginBottom: 0 }}>
            <div className="grow"><h3 className="h3">Preview</h3><p className="muted2" style={{ margin: 0 }}>A fast, small render with captions, overlays and music: what the real export will look like.</p></div>
            {profiles.length > 1 && <select className="input" value={profile} onChange={(e) => setProfile(e.target.value)} aria-label="Format">{profiles.map((p) => <option key={p}>{p}</option>)}</select>}
            <Act verb="preview" args={{ target: c.jref, profile }} primary={!latest} icon={<Clapperboard size={16} />} disabled={!c.j.slots.length}>{latest ? "Preview again" : "Make a preview"}</Act>
          </div>
          {latest && <ExportCard x={latest} compact />}
        </div>
        <StepFoot c={c} what={v && !v.ok ? "Fix the problems above, then come back." : s.state === "done" ? "Checked." : "A preview is optional but worth a minute."}
                  primary={s.state === "done" ? <NextButton c={c} /> :
                    <Act verb="journey.review" args={{ journey: c.jref, step: "check" }} primary lg disabled={!v?.ok} onDone={() => c.setStep("export")}>Ready to export<ArrowRight size={18} /></Act>} />
      </div>
      <aside className="stageside"><PlayerCard c={c} /></aside>
    </div>
  );
}

function ExportCard({ x, compact }: { x: any; compact?: boolean }) {
  const { go } = useApp();
  const { data: d } = useData(() => (x.status === "done" ? must<any>("export.show", { ref: x.ref }) : Promise.resolve(null)), [x.ref, x.status]);
  const [copied, setCopied] = useState(false);
  const vertical = x.profile === "shorts" || (d?.checks || []).some((ch: any) => ch.check === "frame size" && /^(\d+)x(\d+)$/.test(ch.detail) && +ch.detail.split("x")[1] > +ch.detail.split("x")[0]);
  const st = x.status === "done" ? "ok" : x.status === "failed" ? "problem" : "running";
  return (
    <div className={compact ? "stack" : "card stack"}>
      <div className="row nowrap">
        <span className={"chip " + st}>{x.status}</span>
        <b className="grow ellipsis">{x.preview ? "Preview · " : ""}{x.profile} · {x.lang}</b>
        {!compact && <Act verb="project.reveal" args={{ what: x.ref }} small ghost quiet icon={<FolderOpen size={15} />} label="Open the folder">{""}</Act>}
        <button className="btn small ghost" onClick={() => go("exports", x.ref)}>Details</button>
      </div>
      {x.status !== "done" && x.status !== "failed" && <div className="bar"><i style={{ width: `${Math.round((x.progress || 0) * 100)}%` }} /></div>}
      {x.error && <div className="err">{x.error}</div>}
      {!!x.problems?.length && <div className="warn">Checks: {x.problems.map((p: any) => p.check).join(", ")}</div>}
      {d?.video && <video controls src={fileUrl(d.video)} style={vertical ? { height: "min(64vh, 560px)", maxWidth: "100%", display: "block", margin: "0 auto", background: "#000", borderRadius: 12 }
                                                                   : { width: "100%", maxHeight: 420, background: "#000", borderRadius: 12 }} />}
      {!compact && d?.description && (
        <Disclosure id="export.desc" label="Description with credits (ready to paste)">
          <div className="row"><div className="spacer" /><button className="btn small" onClick={() => { navigator.clipboard.writeText(d.description); setCopied(true); setTimeout(() => setCopied(false), 1500); }}><Copy size={14} />{copied ? "Copied" : "Copy"}</button></div>
          <pre className="desc">{d.description}</pre>
        </Disclosure>
      )}
    </div>
  );
}

// ── 6. Export & share ─────────────────────────────────────────────────────────────────────
function ExportStep({ c }: { c: StepCtx }) {
  const { go, newJourney } = useApp();
  const { data: profs } = useData(() => must<any[]>("profile.list"));
  const { data: exps } = useData(() => must<any[]>("export.status", { of: c.jref, limit: 40 }), [c.jref]);
  const dest = c.g.formats.map((f) => DESTINATIONS.find((d) => d.key === f)?.profile).filter(Boolean) as string[];
  const [chosen, setChosen] = useState<string[]>(dest.length ? dest : ["landscape"]);
  const [langs, setLangs] = useState("");
  const langList = langs ? langs.split(/[,\s]+/).map((x) => x.trim()).filter(Boolean) : [];
  const finals = (exps || []).filter((x) => !x.preview);
  const done = finals.filter((x) => x.status === "done");
  const hubWanted = c.g.formats.includes("hub");
  const onHub = !!c.j.links?.hub;
  const others = (profs || []).filter((p) => !["preview", "clip"].includes(p.name) && !dest.includes(p.name));
  const n = chosen.length * Math.max(1, langList.length);
  const tile = (p: any) => (
    <button key={p.name} type="button" className={"tile" + (chosen.includes(p.name) ? " on" : "")} aria-pressed={chosen.includes(p.name)}
            onClick={() => setChosen(chosen.includes(p.name) ? chosen.filter((x) => x !== p.name) : [...chosen, p.name])}>
      <span className="tt"><input type="checkbox" readOnly checked={chosen.includes(p.name)} tabIndex={-1} />{DESTINATIONS.find((d) => d.profile === p.name)?.label || p.name}<span className="chip">{p.size}</span></span>
      <span className="td">{p.description}</span>
    </button>
  );
  return (
    <div className="stage noside">
      <div className="stagemain" style={{ maxWidth: 1000 }}>
        {!!done.length && (
          <div className="celebrate stack">
            <div style={{ display: "grid", placeItems: "center" }}><span className="eicon" style={{ width: 56, height: 56, borderRadius: 16, display: "grid", placeItems: "center", background: "var(--accent)", color: "var(--accent-ink)" }}><PartyPopper size={26} /></span></div>
            <h2 className="h2">{c.j.title} is ready</h2>
            <p className="sub" style={{ margin: "0 auto" }}>{done.length} video{done.length > 1 ? "s" : ""} rendered with captions and a description that credits every source. Upload them yourself{hubWanted && !onHub ? ", and share the recipe with the community below" : ""}.</p>
            <div className="row" style={{ justifyContent: "center" }}>
              <Act verb="project.reveal" args={{ what: "exports" }} icon={<FolderOpen size={16} />} quiet>Open the exports folder</Act>
              <button className="btn" onClick={() => go("exports", null, { tab: "translations", journey: c.jref })}><Languages size={16} />Translate it</button>
              <button className="btn primary" onClick={newJourney}><Plus size={16} />Start another journey</button>
            </div>
          </div>
        )}
        <StepHead c={c} k="export" />
        <div className="card stack">
          <span className="label">Formats</span>
          <div className="grid2">{(profs || []).filter((p) => dest.includes(p.name) || (!dest.length && p.name === "landscape")).map(tile)}</div>
          {!!others.length && <Disclosure id="export.more" label="More formats">{<div className="grid2">{others.map(tile)}</div>}</Disclosure>}
          <Disclosure id="export.langs" label="Languages" count={langList.length || undefined}>
            <div className="stack sm">
              <input className="input" style={{ maxWidth: 360 }} placeholder={`${c.j.language} (default) — add more, e.g. ${c.j.language},fr,sw`} value={langs} onChange={(e) => setLangs(e.target.value)} />
              <span className="muted2">Other languages are dubbed from their translations. <a href="#" onClick={(e) => { e.preventDefault(); go("exports", null, { tab: "translations", journey: c.jref }); }}>Prepare translations</a> first.</span>
            </div>
          </Disclosure>
          <div className="row">
            <Act verb="export.run" args={{ journey: c.jref, profiles: chosen, langs: langList }} primary lg agent disabled={!chosen.length || !c.j.slots.length} icon={<Clapperboard size={18} />}>
              {`Export ${n} video${n === 1 ? "" : "s"}`}</Act>
            <span className="muted2">Renders run in the background; you can keep working.</span>
          </div>
        </div>
        {!!finals.length && (
          <div className="stack">
            <h3 className="h3">Exports of this journey</h3>
            {finals.slice(0, 8).map((x) => <ExportCard key={x.ref} x={x} />)}
          </div>
        )}
        <div className={"card lookcard" + (onHub ? " done" : "")}>
          <span className="licon"><Share2 size={22} /></span>
          <div className="stack">
            <div><h3 className="h3">Share with the community</h3>
              <p className="muted2" style={{ margin: 0 }}>Publishing shares the recipe — sources, timecodes, text and credits, never the media — on the hub, where others play it from the original videos and remix it.</p></div>
            <div className="row">
              {onHub ? <><span className="chip ok"><Check size={14} />On the hub</span><a className="btn small" href={`#/hub/r/${String(c.j.links.hub).split("/r/")[1]}`}>View it</a>
                <Act verb="hub.publish" args={{ journey: c.jref }} small>Publish a new version</Act></>
                : <Act verb="hub.publish" args={{ journey: c.jref }} primary={hubWanted} icon={<Share2 size={16} />} title="Publish the recipe to the configured hub">Publish the recipe</Act>}
            </div>
          </div>
        </div>
        <StepFoot c={c} what={done.length ? "Done. Change anything and export again: unchanged parts come from the cache." : "Pick formats and export."} />
      </div>
    </div>
  );
}

function JourneyMenu({ j }: { j: any }) {
  const { run } = useActions();
  const { go } = useApp();
  const [confirm, setConfirm] = useState(false);
  return (
    <>
      <Menu label="Journey actions" items={[
        { header: j.ref },
        { label: "Duplicate to try a variation", icon: <Copy size={16} />, onSelect: async () => { const e = await run("journey.duplicate", { journey: j.ref }, { label: "Duplicate" }); if (e.ok) go("journeys", e.refs![0]); } },
        { label: "Export the recipe file", desc: "JSON in the recipes folder", icon: <FolderOpen size={16} />, onSelect: () => run("recipe.export", { journey: j.ref }, { label: "Recipe file" }) },
        { label: "Open the recipes folder", icon: <FolderOpen size={16} />, onSelect: () => run("project.reveal", { what: "recipes" }, { quiet: true }) },
        "sep",
        { label: "Delete journey…", icon: <Trash2 size={16} />, danger: true, desc: "Its cuts stay; undo brings it back", onSelect: () => setConfirm(true) },
      ]} />
      {confirm && (
        <Dialog title={`Delete “${j.title}”?`} sub="The journey goes; its cuts stay in your cut bin. Undo (Ctrl+Z) brings it back." onClose={() => setConfirm(false)}
                footer={<><div className="spacer" /><button className="btn" onClick={() => setConfirm(false)}>Keep it</button>
                  <Act verb="journey.delete" args={{ journey: j.ref }} className="danger" onDone={() => { setConfirm(false); go("journeys"); }}>Delete</Act></>}>
          <p className="muted2" style={{ margin: 0 }}>{j.slots.length} cuts · {j.duration}</p>
        </Dialog>
      )}
    </>
  );
}
