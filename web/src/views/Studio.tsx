// The journey studio: one journey, six guided steps — purpose → gather → order → look → check → export.
// Laid out like a document editor: a ribbon of step tabs (state from `recomp journey guide J1`, the same list the
// agent reads), a one-line step header with the step's commands, the work area, a preview pane that can be hidden,
// and a status bar with where you are and the one next action. Advanced options sit in menus, dialogs and
// collapsible sections.
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { AlertTriangle, ArrowDown, ArrowLeft, ArrowRight, ArrowUp, Check, CheckCircle2, ChevronRight, Clapperboard, Copy, Film, FolderOpen,
  GripVertical, Heading, Languages, Monitor, Music, PanelRightClose, PanelRightOpen, Play, Plus, Scissors, Search as SearchIcon, Share2,
  Sparkles, Trash2, Type, UserSquare2, Wand2, X, XCircle } from "lucide-react";
import { clock, fileUrl, frameUrl, must } from "../api";
import { useApp, useData } from "../App";
import { Act, useActions } from "../actions";
import { DESTINATIONS } from "../journeyMeta";
import { Dialog, Disclosure, Empty, Menu, SrcBadge, mmss } from "../ui";
import RecipePlayer from "./RecipePlayer";
import PublishButton from "./PublishButton";

type Guide = {
  journey: string; title: string; intent: string; formats: string[]; target: { min_s: number; max_s: number; hard_max_s: number | null } | null;
  duration_s: number; slots: number; sources: string[]; next: string | null; done: number; notes: string[];
  steps: { key: string; n: number; title: string; state: string; detail: string; hint: string; actions: any[]; agent: string; reviewed: boolean }[];
};

const RAIL: Record<string, string> = { purpose: "Purpose", gather: "Gather cuts", order: "Order", look: "Look", check: "Check", export: "Export & share" };

// The preview pane is a pane, not a page: shown or hidden, remembered in this browser.
function usePane(): [boolean, () => void] {
  const [open, setOpen] = useState<boolean>(() => { try { return localStorage.getItem("recomp.studio.pane") !== "0"; } catch { return true; } });
  return [open, () => { setOpen(!open); try { localStorage.setItem("recomp.studio.pane", open ? "0" : "1"); } catch { /* ignore */ } }];
}

export default function Studio({ jref }: { jref: string }) {
  const { route, go, setParam } = useApp();
  const { data: g, error } = useData(() => must<Guide>("journey.guide", { journey: jref }), [jref]);
  const { data: j } = useData(() => must<any>("journey.show", { journey: jref }), [jref]);
  const { data: sources } = useData(() => must<any[]>("source.list"));
  const [pane, togglePane] = usePane();
  const step = route.params.get("step") || g?.next || "purpose";
  const setStep = (s: string) => setParam("step", s);
  const media = useMemo(() => new Set((sources || []).filter((s) => s.has_media).map((s) => s.ref)), [sources]);
  const titles = useMemo(() => Object.fromEntries((sources || []).map((s) => [s.ref, s.title])), [sources]) as Record<string, string>;

  // Keys: 1–6 switch steps; Enter runs the status bar's primary action. Not while typing, in a dialog or a menu,
  // and not when a button or link has the focus (Enter already presses that one).
  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement | null;
      const tag = el?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || el?.isContentEditable) return;
      if (e.ctrlKey || e.metaKey || e.altKey || document.querySelector(".modal, .menu")) return;
      if (/^[1-6]$/.test(e.key) && g) {
        const st = g.steps[Number(e.key) - 1];
        if (st) { e.preventDefault(); setStep(st.key); }
      } else if (e.key === "Enter" && !e.shiftKey && tag !== "BUTTON" && tag !== "A") {
        const btn = document.querySelector(".stepfoot button.primary:not(:disabled)") as HTMLButtonElement | null;
        if (btn) { e.preventDefault(); btn.click(); }
      }
    };
    window.addEventListener("keydown", on);
    return () => window.removeEventListener("keydown", on);
  });

  if (error) return <div className="page"><div className="err">{error}</div><button className="btn" onClick={() => go("journeys")}>All journeys</button></div>;
  if (!g || !j) return <div className="page">Loading…</div>;
  const cur = g.steps.find((s) => s.key === step) || g.steps[0];
  const idx = g.steps.indexOf(cur);
  const nextKey = g.steps[idx + 1]?.key;
  const ctx: StepCtx = { jref, g, j, media, titles, sources: sources || [], setStep, nextKey, cur: cur.key, pane };
  const hasPane = ["gather", "order", "look", "check"].includes(cur.key);

  return (
    <div className="studio">
      <div className="studiohead">
        <a href="#" className="btn ghost small quiet" onClick={(e) => { e.preventDefault(); go("journeys"); }} data-tip="All journeys"><ArrowLeft size={14} />Journeys</a>
        <span className="faint">/</span>
        <span className="mono faint">{j.ref}</span>
        <h1 className="h1 ellipsis" style={{ maxWidth: "40ch" }}>{j.title}</h1>
        <div className="row tight">
          {g.formats.map((f) => <span key={f} className="chip info">{DESTINATIONS.find((d) => d.key === f)?.label || f}</span>)}
          {!g.formats.length && <a href="#" className="chip warn" onClick={(e) => { e.preventDefault(); setStep("purpose"); }}>Where does it go?</a>}
          <span className="chip">{g.slots} cut{g.slots === 1 ? "" : "s"} · {mmss(g.duration_s)}</span>
          {g.sources.map((s) => <span key={s} data-tip={titles[s]}><SrcBadge ref_={s} /></span>)}
        </div>
        <div className="spacer" />
        {hasPane && <button className={"btn small hide-sm" + (pane ? " on" : "")} onClick={togglePane} data-tip={pane ? "Hide the preview pane" : "Show the preview pane"}>
          {pane ? <PanelRightClose size={14} /> : <PanelRightOpen size={14} />}Preview pane</button>}
        <JourneyMenu j={j} />
      </div>
      <div className="rail" role="tablist" aria-label="Steps">
        {g.steps.map((s, k) => (
          <span key={s.key} className="row nowrap" style={{ gap: 0 }}>
            {k > 0 && <ChevronRight size={12} className="faint" />}
            <button role="tab" aria-selected={s.key === cur.key}
                    className={"railstep " + s.state + (s.key === cur.key ? " on" : "") + (s.key === g.next ? " next" : "")}
                    onClick={() => setStep(s.key)} data-tip={`${s.title}: ${s.detail}${s.key === g.next ? " (next)" : ""}`} data-tip-key={String(k + 1)}>
              <span className="num">{s.state === "done" ? <Check size={11} /> : s.state === "problem" ? "!" : s.n}</span>
              <span className="rt">{RAIL[s.key] || s.title}</span>
            </button>
          </span>
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

type StepCtx = {
  jref: string; g: Guide; j: any; media: Set<string>; titles: Record<string, string>; sources: any[];
  setStep: (s: string) => void; nextKey?: string; cur: string; pane: boolean;
};

// One line: which step, what it is for, and the step's commands on the right.
function StepHead({ c, k, children }: { c: StepCtx; k: string; children?: ReactNode }) {
  const s = c.g.steps.find((x) => x.key === k)!;
  const { ask } = useActions();
  return (
    <div className="stephead">
      <span className="snum">Step {s.n} of 6</span>
      <b className="nowrap">{s.title}</b>
      <span className="muted2 grow" style={{ minWidth: 200 }}>{s.hint}</span>
      <div className="row tight">
        {children}
        {s.agent && s.state !== "done" && (
          <button className="btn small ghost" onClick={() => ask(s.agent, [c.jref])} data-tip="Leave this for the agent: it sees the request in `recomp ui notes`"
                  data-tip-cmd={`“${s.agent}”`}><Sparkles size={14} />Ask the agent</button>
        )}
      </div>
    </div>
  );
}

// The status bar: back, what is true now, and the one next action.
function StepFoot({ c, what, primary, back = true }: { c: StepCtx; what?: ReactNode; primary?: ReactNode; back?: boolean }) {
  const prev = c.g.steps[c.g.steps.findIndex((s) => s.key === c.cur) - 1];
  return (
    <div className="stepfoot">
      {back && prev && <button className="btn small ghost" onClick={() => c.setStep(prev.key)}><ArrowLeft size={14} />{RAIL[prev.key]}</button>}
      <div className="what">{what}</div>
      {primary}
    </div>
  );
}

function NextButton({ c, label }: { c: StepCtx; label?: string }) {
  if (!c.nextKey) return null;
  return <button className="btn primary" onClick={() => c.setStep(c.nextKey!)} data-tip={`Go to step ${c.g.steps.findIndex((s) => s.key === c.nextKey) + 1}`} data-tip-key="Enter">
    {label || `Next: ${RAIL[c.nextKey]}`}<ArrowRight size={14} /></button>;
}

// The journey's length against the destination's sweet spot.
function LengthMeter({ dur, target }: { dur: number; target: Guide["target"] }) {
  const scale = Math.max(target ? target.max_s * 1.35 : 120, dur * 1.08, 1);
  const pct = (x: number) => `${Math.min(100, (x / scale) * 100)}%`;
  const over = !!target && dur > target.max_s;
  const under = !!target && dur < target.min_s;
  return (
    <div className="stack sm">
      <div className="row nowrap"><span className="muted2 grow">Length <b style={{ color: "var(--text)" }}>{mmss(dur)}</b></span>
        {target && <span className={"chip " + (over ? "warn" : under ? "" : "ok")} data-tip="The length that suits every destination chosen">
          {over ? "too long" : under ? "short" : "in range"} · aim {mmss(target.min_s)}–{mmss(target.max_s)}</span>}
      </div>
      <div className="meter" aria-hidden>
        {target && <span className="zone" style={{ left: pct(target.min_s), width: `calc(${pct(target.max_s)} - ${pct(target.min_s)})` }} />}
        <i className={over ? "over" : ""} style={{ width: pct(dur) }} />
      </div>
    </div>
  );
}

function Thumb({ c, source, t, w = 160 }: { c: StepCtx; source: string; t: number; w?: number }) {
  return c.media.has(source) ? <img src={frameUrl(source, t, w)} alt="" loading="lazy" onError={(e) => ((e.target as HTMLImageElement).style.visibility = "hidden")} />
    : <div className="noimg" style={{ display: "grid", placeItems: "center", color: "var(--faint)" }}><Film size={14} /></div>;
}

const secs = (hms: string) => String(hms || "0").split(":").reduce((a, x) => a * 60 + parseFloat(x), 0);
const startOf = (span: string) => secs(span.split("–")[0]);
const short = (hms: string) => String(hms || "").replace(/^00:/, "").replace(/\.\d+$/, "");

function Stage({ c, side, children }: { c: StepCtx; side?: ReactNode; children: ReactNode }) {
  const show = !!side && c.pane;
  return (
    <div className={"stage" + (show ? "" : " noside")}>
      <div className="stagemain">{children}</div>
      {show && <aside className="stageside">{side}</aside>}
    </div>
  );
}

// ── 1. Purpose ────────────────────────────────────────────────────────────────────────────
function PurposeStep({ c }: { c: StepCtx }) {
  const [title, setTitle] = useState(c.j.title);
  const [intent, setIntent] = useState(c.j.intent);
  const [formats, setFormats] = useState<string[]>(c.g.formats);
  const dirty = title !== c.j.title || intent !== c.j.intent || formats.join() !== c.g.formats.join();
  const args = { journey: c.jref, title: title.trim(), intent: intent.trim(), formats };
  return (
    <>
      <Stage c={c}>
        <StepHead c={c} k="purpose" />
        <div className="panel" style={{ maxWidth: 820 }}>
          <div className="pbody stack">
            <div className="field"><label htmlFor="p-title">Name</label>
              <input id="p-title" className="input" value={title} onChange={(e) => setTitle(e.target.value)} /></div>
            <div className="field"><label htmlFor="p-intent">What is it for?</label>
              <textarea id="p-intent" className="input" rows={2} value={intent} placeholder="The idea, question or feeling people should leave with."
                        onChange={(e) => setIntent(e.target.value)} />
              <span className="help">Shapes the cut suggestions and the export description.</span></div>
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
              <span className="help">The tightest length goal wins; each destination becomes an export.</span>
            </div>
          </div>
        </div>
      </Stage>
      <StepFoot c={c} back={false} what={dirty ? "Unsaved changes" : "Saved. You can come back and change this any time."}
                primary={dirty ? <Act kbd="Enter" verb="journey.edit" args={args} primary disabled={!title.trim()} onDone={() => c.setStep("gather")}>Save and gather cuts<ArrowRight size={14} /></Act>
                  : <NextButton c={c} />} />
    </>
  );
}

// ── 2. Gather ─────────────────────────────────────────────────────────────────────────────
function GatherStep({ c }: { c: StepCtx }) {
  const { route, setParam } = useApp();
  const from = route.params.get("from") || "suggest";
  return (
    <>
      <Stage c={c} side={<Tray c={c} />}>
        <StepHead c={c} k="gather">
          <div className="segmented" role="tablist" aria-label="Where cuts come from">
            <button className={from === "suggest" ? "on" : ""} onClick={() => setParam("from", "suggest")} data-tip="Whole-thought moments for the journey's intent, from every source"><Sparkles size={14} />Suggested</button>
            <button className={from === "bin" ? "on" : ""} onClick={() => setParam("from", "bin")} data-tip="Cuts you (or the agent) already made"><Scissors size={14} />Cut bin</button>
            <button className={from === "sources" ? "on" : ""} onClick={() => setParam("from", "sources")} data-tip="Open a source and cut your own moment"><Film size={14} />From a source</button>
          </div>
        </StepHead>
        {from === "suggest" && <Suggestions c={c} />}
        {from === "bin" && <BinPicker c={c} />}
        {from === "sources" && <SourcePicker c={c} />}
      </Stage>
      <StepFoot c={c} what={c.g.slots ? `${c.g.slots} cut${c.g.slots > 1 ? "s" : ""} from ${c.g.sources.length} source${c.g.sources.length > 1 ? "s" : ""} · ${mmss(c.g.duration_s)}${c.g.slots < 2 ? " · add at least one more" : ""}` : "No cuts yet: add moments from any source."}
                primary={<button className="btn primary" disabled={!c.g.slots} onClick={() => c.setStep("order")} data-tip="Go to step 3" data-tip-key="Enter">Next: Order<ArrowRight size={14} /></button>} />
    </>
  );
}

function Tray({ c }: { c: StepCtx }) {
  return (
    <div className="panel">
      <div className="phead"><span className="h3 grow">In this journey</span><span className="chip">{c.j.slots.length}</span></div>
      <div className="pbody stack sm">
        <LengthMeter dur={c.g.duration_s} target={c.g.target} />
        {!c.j.slots.length && <span className="muted2">Cuts you add show up here, in order.</span>}
      </div>
      {!!c.j.slots.length && (
        <div className="slotlist" style={{ border: 0, borderTop: "1px solid var(--line)", borderRadius: 0 }}>
          {c.j.slots.map((s: any, k: number) => (
            <div key={s.slot}>
              <div className="slot compact">
                <span className="n">{k + 1}</span>
                <Thumb c={c} source={s.source} t={startOf(s.span) + 0.5} w={120} />
                <div style={{ minWidth: 0 }}>
                  <div className="ellipsis" style={{ fontWeight: 600 }}>{s.title}</div>
                  <div className="srcmini"><SrcBadge ref_={s.source} /><span>{Math.round(s.dur)}s</span></div>
                </div>
                <Act verb="journey.remove" args={{ slot: s.slot }} small ghost icon={<X size={13} />} label={`Remove ${s.title}`}>{""}</Act>
              </div>
            </div>
          ))}
        </div>
      )}
      {c.g.sources.length === 1 && c.j.slots.length > 1 && <div className="pbody muted2" style={{ borderTop: "1px solid var(--line)" }}>All from one source. Journeys shine when voices meet: try “From a source”.</div>}
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
      <form className="filterbar" style={{ margin: 0 }} onSubmit={(e) => { e.preventDefault(); setQuery(q); }}>
        <div className="search" style={{ maxWidth: "none" }}><SearchIcon size={14} /><input className="input" value={q} onChange={(e) => setQ(e.target.value)} data-filter="q"
               placeholder='What should the moments be about? Words or "a phrase"' /></div>
        <button className="btn" type="submit" data-tip="Find whole-thought moments across every source" data-tip-cmd={`recomp cut suggest "${q}"`}>Suggest</button>
        {data && <span className="muted2 nowrap">{data.candidates.length} moments</span>}
      </form>
      {error && <div className="err">{error}</div>}
      {!data && <div className="muted2">Looking across your sources…</div>}
      {data && !data.candidates.length && (
        <Empty icon={<SearchIcon size={16} />} title={`Nothing found for “${query}”`}>
          Try fewer or different words, a phrase someone would actually say, or pick from the cut bin.
        </Empty>
      )}
      {!!data?.candidates.length && (
        <div className="reslist">
          {data.candidates.map((cand: any, k: number) => {
            const key = `${cand.source}@${cand.start}`;
            const isIn = added.includes(key) || inJourney(cand);
            const t = cand.text.split(/(?<=[.?!])\s/)[0].slice(0, 70);
            return (
              <div key={k} className={"res" + (isIn ? " in" : "")}>
                <div style={{ minWidth: 0 }}>
                  <div className="srcmini"><SrcBadge ref_={cand.source} /><span className="ellipsis">{c.titles[cand.source]}</span>
                    <span className="mono faint nowrap">{cand.span.replace(/^00:/, "").replace(/–00:/, "–")}</span><span className="nowrap">· {Math.round(cand.dur)}s</span></div>
                  <Quote text={cand.text} />
                </div>
                <div className="row tight nowrap">
                  <button className="btn small ghost icon" onClick={() => go("room", cand.source, { t: cand.start, j: c.jref })} aria-label="Open in source"
                          data-tip="Open the source here to adjust the edges before cutting"><Play size={13} /></button>
                  {isIn ? <span className="chip ok"><Check size={11} />in journey</span>
                    : <Act verb="cut.add" small primary icon={<Plus size={13} />} onDone={() => setAdded([...added, key])}
                           args={{ ref: cand.source, from: String(cand.start), to: String(cand.end), title: t, why: `${c.j.ref}: ${c.j.intent || c.j.title}`.slice(0, 140), journey: c.jref }}
                           title="Make this a cut and add it to the journey">Add</Act>}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function Quote({ text }: { text: string }) {
  const [more, setMore] = useState(false);
  const long = text.length > 220;
  return (
    <div style={{ marginTop: 2 }}>
      <span className={"quote" + (long && !more ? " clamp" : "")} style={{ display: long && !more ? "-webkit-box" : "inline" }}>“{text}”</span>
      {long && <button className="btn ghost small quiet" style={{ height: 18, padding: "0 4px" }} onClick={() => setMore(!more)}>{more ? "less" : "more"}</button>}
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
  useEffect(() => { const t = setTimeout(() => draft !== q && setParam("cq", draft || null), 300); return () => clearTimeout(t); }, [draft]);
  return (
    <div className="stack">
      <div className="filterbar" style={{ margin: 0 }}>
        <div className="search"><SearchIcon size={14} /><input className="input" placeholder="Filter the cut bin" value={draft} onChange={(e) => setDraft(e.target.value)} data-filter="cq" /></div>
        <select className={"input" + (src ? " on" : "")} value={src} onChange={(e) => setParam("csrc", e.target.value || null)} aria-label="Source">
          <option value="">Every source</option>
          {c.sources.map((s) => <option key={s.ref} value={s.ref}>{s.ref} · {String(s.title).slice(0, 40)}</option>)}
        </select>
        <label className="check muted2"><input type="checkbox" checked={showAll} onChange={(e) => setParam("call", e.target.checked ? "1" : null)} />include cuts already in it</label>
        <div className="spacer" />
        {!!sel.length && <><span className="muted2">{sel.length} ticked: {sel.join(" → ")}</span>
          <Act verb="journey.add" args={{ journey: c.jref, cuts: sel }} small primary icon={<Plus size={13} />} onDone={() => setSel([])}>Add {sel.length}</Act>
          <button className="btn small ghost" onClick={() => setSel([])}>Clear</button></>}
        {!sel.length && cuts && <span className="muted2">{list.length} cuts · tick several to add them in that order</span>}
      </div>
      {cuts && !list.length && (
        <Empty icon={<Scissors size={16} />} title={(cuts.length ? "Every matching cut is already in this journey" : q || src ? "No cuts match" : "The cut bin is empty")}>
          {cuts.length ? "Cut new moments from a source, or use the suggestions." : "Use “Suggested” to find moments by theme, or “From a source” to cut your own."}
        </Empty>
      )}
      {!!list.length && (
        <div className="reslist">
          {list.map((x) => {
            const on = sel.includes(x.ref);
            return (
              <div key={x.ref} className={"res thumbed" + (inJ.has(x.ref) ? " in" : on ? " sel" : "")}>
                <Thumb c={c} source={x.source} t={x.start + Math.min(1, x.dur / 2)} />
                <div style={{ minWidth: 0 }}>
                  <div className="row nowrap tight">
                    {!inJ.has(x.ref) && <input type="checkbox" checked={on} aria-label={`Tick ${x.ref}`} onChange={() => setSel(on ? sel.filter((r) => r !== x.ref) : [...sel, x.ref])} />}
                    <span className="mono faint">{x.ref}</span><b className="ellipsis">{x.title || "(untitled)"}</b>{on && <span className="ord">{sel.indexOf(x.ref) + 1}</span>}
                  </div>
                  <div className="srcmini"><SrcBadge ref_={x.source} /><span className="ellipsis">{x.source_title}</span><span className="nowrap mono faint">{clock(x.start, 0).replace(/^00:/, "")}</span><span className="nowrap">· {Math.round(x.dur)}s</span></div>
                  {(x.why || x.quote) && <div className="muted2 ellipsis">{x.why || x.quote}</div>}
                </div>
                {inJ.has(x.ref) ? <span className="chip ok"><Check size={11} />in journey</span>
                  : <Act verb="journey.add" args={{ journey: c.jref, cuts: [x.ref] }} small icon={<Plus size={13} />}>Add</Act>}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function SourcePicker({ c }: { c: StepCtx }) {
  const { go } = useApp();
  if (!c.sources.length) return <Empty icon={<Film size={16} />} title="No sources yet" actions={<button className="btn primary" onClick={() => go("sources", null, { add: 1 })}>Add sources</button>}>Add films, talks or links first.</Empty>;
  return (
    <div className="stack">
      <div className="callout"><Scissors size={14} /><div>Open a source, select a range (drag across the lanes, or click a line and shift-click another) and press <span className="kbd">C</span>.
        While you gather for {c.jref}, every cut you make there <b>goes straight into this journey</b>; “Back to {c.jref}” returns here.</div></div>
      <table className="table">
        <thead><tr><th style={{ width: 96 }}></th><th>Source</th><th>Length</th><th>Transcript</th><th>Cuts</th><th></th></tr></thead>
        <tbody>
          {c.sources.map((s) => (
            <tr key={s.ref} className="click" onClick={() => go("room", s.ref, { j: c.jref })}>
              <td>{s.has_media ? <img className="thumb" src={frameUrl(s.ref, Math.min(60, secs(s.duration) / 3), 160)} alt="" loading="lazy" /> : <div className="thumb" />}</td>
              <td><div className="row nowrap tight"><SrcBadge ref_={s.ref} /><b className="ellipsis">{s.title}</b>{s.kind === "link" && <span className="chip">link</span>}</div></td>
              <td className="mono nowrap">{short(s.duration)}</td>
              <td>{s.transcript ? <span className="chip ok">{s.transcript.origin}</span> : <span className="chip warn">none yet</span>}</td>
              <td>{s.cuts || 0}</td>
              <td style={{ textAlign: "right" }}><span className="btn small primary"><Scissors size={13} />Open and cut</span></td>
            </tr>
          ))}
        </tbody>
      </table>
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
  const headingForm = (k: number) => (
    <form className="row nowrap sectionhead" style={{ padding: "4px 8px" }} onSubmit={async (e) => { e.preventDefault(); await run("journey.section", { journey: c.jref, heading: heading!.text, at: k + 1 }, { label: "Section" }); setHeading(null); }}>
      <Heading size={14} />
      <input className="input small grow" autoFocus placeholder="Section heading (empty removes it)" value={heading!.text} onChange={(e) => setHeading({ at: k + 1, text: e.target.value })}
             onKeyDown={(e) => e.key === "Escape" && setHeading(null)} />
      <button className="btn small primary" type="submit">Set</button><button className="btn small ghost" type="button" onClick={() => setHeading(null)}>Cancel</button>
    </form>
  );
  return (
    <>
      <Stage c={c} side={<PlayerPane c={c} startSlot={startSlot} />}>
        <StepHead c={c} k="order">
          <span className="muted2">Drag ⠿ or use ↑ ↓ · ⋯ for sections, trims, fades</span>
        </StepHead>
        {!slots.length && <Empty icon={<Scissors size={16} />} title="Nothing to order yet" actions={<button className="btn primary" onClick={() => c.setStep("gather")}>Gather cuts</button>}>Add cuts first.</Empty>}
        {!!slots.length && (
          <div className="slotlist">
            {slots.map((sl, k) => (
              <div key={sl.slot}>
                {heading?.at === k + 1 ? headingForm(k) : sl.section ? (
                  <div className="sectionhead"><Heading size={13} /><span className="grow">{sl.section}</span>
                    <button className="btn small ghost" onClick={() => setHeading({ at: k + 1, text: sl.section })}>Rename</button></div>
                ) : k > 0 && (
                  <div className="between"><button className="btn small" onClick={() => setHeading({ at: k + 1, text: "" })}><Plus size={12} />Section here</button></div>
                )}
                <div className={"slot" + (drag === k ? " drag" : "") + (over === k ? " over" : "") + (startSlot === k + 1 ? " playing" : "")} draggable
                     onDragStart={() => setDrag(k)} onDragOver={(e) => { e.preventDefault(); if (drag != null) setOver(k); }}
                     onDrop={() => drop(k)} onDragEnd={() => { setDrag(null); setOver(null); }}>
                  <span className="n" data-tip="Drag to reorder"><GripVertical size={13} />{k + 1}</span>
                  <span style={{ cursor: "pointer" }} onClick={() => setStartSlot(k + 1)} data-tip="Play from here"><Thumb c={c} source={sl.source} t={startOf(sl.span) + 0.5} /></span>
                  <div style={{ minWidth: 0, cursor: "pointer" }} onClick={() => setStartSlot(k + 1)}>
                    <div className="row nowrap tight"><span className="st ellipsis">{sl.title}</span>
                      <span className="chip">{Math.round(sl.dur)}s</span>
                      {sl.trimmed && <span className="chip info">trimmed</span>}
                      {sl.transition && sl.transition.type !== "cut" && <span className="chip">{sl.transition.type} {sl.transition.dur}s</span>}
                    </div>
                    <div className="srcmini"><SrcBadge ref_={sl.source} /><span className="ellipsis">{c.titles[sl.source]}</span><span className="mono faint nowrap">{sl.span.replace(/00:/g, "")}</span></div>
                    <div className="sl ellipsis">{sl.why || sl.quote}</div>
                  </div>
                  <div className="row tight nowrap">
                    <Act verb="journey.move" args={{ slot: sl.slot, to: k }} small ghost icon={<ArrowUp size={14} />} label="Move up" disabled={k === 0}>{""}</Act>
                    <Act verb="journey.move" args={{ slot: sl.slot, to: k + 2 }} small ghost icon={<ArrowDown size={14} />} label="Move down" disabled={k === slots.length - 1}>{""}</Act>
                    <Menu small label="More for this cut" items={[
                      { label: "Play from here", icon: <Play size={14} />, onSelect: () => setStartSlot(k + 1) },
                      { label: sl.section ? "Rename section" : "Start a section here", icon: <Heading size={14} />, onSelect: () => setHeading({ at: k + 1, text: sl.section || "" }) },
                      { label: "Trim the edges…", icon: <Scissors size={14} />, desc: "For this journey only; the cut stays", onSelect: () => setTrim(sl) },
                      { label: sl.transition?.type === "fade" ? "Hard cut into it" : "Fade into it", icon: <Wand2 size={14} />,
                        onSelect: () => run("journey.transition", { slot: sl.slot, type: sl.transition?.type === "fade" ? "cut" : "fade", dur: 0.5 }, { label: "Transition" }) },
                      { label: "Open in its source", icon: <Film size={14} />, onSelect: () => go("room", sl.source, { focus: sl.cut, j: c.jref }) },
                      "sep",
                      { label: "Remove from journey", icon: <Trash2 size={14} />, danger: true, desc: "The cut stays in the cut bin", onSelect: () => run("journey.remove", { slot: sl.slot }, { label: `Remove ${sl.title}` }) },
                    ]} />
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
        <div><button className="btn small ghost" onClick={() => c.setStep("gather")}><Plus size={13} />Add more cuts</button></div>
      </Stage>
      <StepFoot c={c} what={s.state === "done" ? "Order confirmed. Changing it is always fine." : "Play it through in the preview pane. When it reads well, confirm the order."}
                primary={s.state === "done" ? <NextButton c={c} /> :
                  <Act kbd="Enter" verb="journey.review" args={{ journey: c.jref, step:"order" }} primary disabled={slots.length < 2} onDone={() => c.setStep("look")}>Order looks right<ArrowRight size={14} /></Act>} />
      {trim && <TrimDialog slot={trim} onClose={() => setTrim(null)} />}
    </>
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

function PlayerPane({ c, startSlot = 1 }: { c: StepCtx; startSlot?: number }) {
  const { data: rec } = useData(() => must<any>("recipe.show", { journey: c.jref }), [c.jref]);
  const musicFiles: Record<string, string> = {};
  for (const m of c.j.music) if (m.file) musicFiles[m.track] = m.file;
  return (
    <div className="panel">
      <div className="phead"><Monitor size={14} /><span className="h3 grow">Preview</span><span className="muted2">plays from the sources</span></div>
      {rec && c.j.slots.length ? <RecipePlayer recipe={rec} startSlot={startSlot} hasMedia={(r) => c.media.has(r)} musicFiles={musicFiles} />
        : <div className="pbody muted2">The player appears once the journey has cuts.</div>}
      <div className="pbody" style={{ borderTop: "1px solid var(--line)" }}><LengthMeter dur={c.g.duration_s} target={c.g.target} /></div>
    </div>
  );
}

// ── 4. Look: a property sheet — title card, who is speaking, music; more text under a disclosure ──
function LookStep({ c }: { c: StepCtx }) {
  const ov = c.j.overlays as any[];
  const titleOv = ov.find((o) => o.kind === "title");
  const lowers = ov.filter((o) => o.kind === "lower_third");
  const others = ov.filter((o) => o.kind !== "title" && o.kind !== "lower_third");
  const [titleText, setTitleText] = useState(c.j.title);
  const s = c.g.steps.find((x) => x.key === "look")!;
  return (
    <>
      <Stage c={c} side={<PlayerPane c={c} />}>
        <StepHead c={c} k="look" />
        <div className="panel">
          <div className={"lookrow" + (titleOv ? " done" : "")}>
            <span className="licon">{titleOv ? <CheckCircle2 size={15} /> : <Type size={15} />}</span>
            <div><div className="lt">Title card</div><div className="ld">The first three seconds: use the hook, not just the name.</div></div>
            {titleOv ? (
              <div className="row nowrap"><b className="grow ellipsis">“{titleOv.text}”</b>
                <Act verb="overlay.remove" args={{ ref: titleOv.ref }} small ghost icon={<Trash2 size={13} />} label="Remove the title card">{""}</Act></div>
            ) : (
              <div className="row nowrap">
                <input className="input grow" value={titleText} onChange={(e) => setTitleText(e.target.value)} placeholder="Title text" />
                <Act verb="overlay.add" args={{ target: c.jref, kind: "title", text: titleText, at: "0" }} small primary disabled={!titleText.trim()} icon={<Plus size={13} />}>Add</Act>
              </div>
            )}
          </div>
          <div className={"lookrow" + (lowers.length ? " done" : "")}>
            <span className="licon">{lowers.length ? <CheckCircle2 size={15} /> : <UserSquare2 size={15} />}</span>
            <div><div className="lt">Who is speaking</div><div className="ld">Lower thirds credit each speaker and source: essential when cuts come from different sources.</div></div>
            <div className="stack sm">
              <div className="row">
                {!!lowers.length && <span className="chip ok">{lowers.length} lower third{lowers.length > 1 ? "s" : ""}</span>}
                <Act verb="overlay.auto-lower-thirds" args={{ journey: c.jref }} small primary={!lowers.length} agent icon={<Wand2 size={13} />}>{lowers.length ? "Redo" : "Credit every speaker and source"}</Act>
              </div>
              {!!lowers.length && (
                <Disclosure id="look.lowers" label="Edit them">
                  <table className="table"><tbody>
                    {lowers.map((o) => (
                      <tr key={o.ref}><td className="mono faint" style={{ width: 50 }}>{o.slot}</td><td style={{ whiteSpace: "pre-line" }}>{o.text}</td>
                        <td style={{ width: 30 }}><Act verb="overlay.remove" args={{ ref: o.ref }} small ghost icon={<Trash2 size={13} />} label={`Remove ${o.ref}`}>{""}</Act></td></tr>
                    ))}
                  </tbody></table>
                </Disclosure>
              )}
            </div>
          </div>
          <MusicRow c={c} />
        </div>
        <Disclosure id="look.more" label="More text on screen (quotes, captions, endcard text)" count={others.length}>
          <div className="panel"><div className="pbody stack">
            {!!others.length && <table className="table"><tbody>
              {others.map((o) => (
                <tr key={o.ref}><td><span className="chip">{o.kind}</span></td><td className="mono faint nowrap">{o.slot || "journey"} @{o.at}s</td>
                  <td style={{ whiteSpace: "pre-line" }}>{o.text}</td>
                  <td style={{ width: 30 }}><Act verb="overlay.remove" args={{ ref: o.ref }} small ghost icon={<Trash2 size={13} />} label={`Remove ${o.ref}`}>{""}</Act></td></tr>
              ))}
            </tbody></table>}
            <OverlayForm jref={c.jref} slots={c.j.slots.length} />
          </div></div>
        </Disclosure>
      </Stage>
      <StepFoot c={c} what={s.detail}
                primary={s.state === "done" ? <NextButton c={c} /> :
                  <Act kbd="Enter" verb="journey.review" args={{ journey: c.jref, step:"look" }} primary onDone={() => c.setStep("check")}>Looks good<ArrowRight size={14} /></Act>} />
    </>
  );
}

function MusicRow({ c }: { c: StepCtx }) {
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
    <div className={"lookrow" + (bed ? " done" : "")}>
      <span className="licon">{bed ? <CheckCircle2 size={15} /> : <Music size={15} />}</span>
      <div><div className="lt">Music bed</div><div className="ld">A quiet track under everything, ducked while people speak. Open licences only (CC0, CC BY).</div></div>
      {bed ? (
        <div className="stack sm">
          <div className="row nowrap"><span className="grow ellipsis"><b>{bed.title}</b> · {bed.artist} <span className="chip">{bed.licence}</span></span>
            <Act verb="music.bed-remove" args={{ ref: bed.ref }} small ghost icon={<Trash2 size={13} />} label="Remove the music">{""}</Act></div>
          <Disclosure id="look.musiclevel" label="Level and ducking">
            <div className="row">
              <span className="muted2">Level (dB)</span>
              <input className="input small" style={{ width: 70 }} type="number" placeholder={String(bed.gain_db)} value={gain} onChange={(e) => setGain(e.target.value)} />
              <Act verb="music.bed-edit" args={{ ref: bed.ref, gain: Number(gain) }} small disabled={gain === ""} onDone={() => setGain("")}>Set</Act>
              <span className="muted2">ducks {bed.duck_db} dB under speech</span>
            </div>
          </Disclosure>
        </div>
      ) : (
        <div className="stack sm">
          {!!lib?.length && (
            <div className="row tight"><span className="muted2">Library:</span>
              {lib.slice(0, 4).map((t) => <Act key={t.ref} verb="music.bed-add" args={{ journey: c.jref, track: t.ref }} small title={`${t.artist} · ${t.licence}`} icon={<Plus size={12} />}>{String(t.title).slice(0, 28)}</Act>)}
            </div>
          )}
          <form className="row nowrap" onSubmit={(e) => { e.preventDefault(); search(); }}>
            <input className="input grow" placeholder="Mood or instrument, e.g. calm piano" value={q} onChange={(e) => setQ(e.target.value)} />
            <button className="btn" type="submit" disabled={!q.trim() || searching} data-tip="Searches open-licensed music (Openverse)" data-tip-cmd={`recomp music search "${q}"`}>
              <SearchIcon size={13} />{searching ? "Searching…" : "Find music"}</button>
          </form>
          {res && !res.length && <div className="muted2">Nothing found (or no network). Try another mood.</div>}
          {!!res?.length && (
            <table className="table"><tbody>
              {res.map((r) => (
                <tr key={r.n}><td className="ellipsis" style={{ maxWidth: 260 }}><b>{r.title}</b> · {r.artist}</td><td><span className="chip">{r.licence}</span></td>
                  <td className="mono faint">{r.duration ? mmss(r.duration) : ""}</td>
                  <td className="nowrap" style={{ textAlign: "right" }}>{r.page_url && <a className="btn small ghost" href={r.page_url} target="_blank" rel="noreferrer">Listen</a>}
                    <button className="btn small" onClick={() => use(r.n)} data-tip="Download it with its licence and lay it under the journey" data-tip-cmd={`recomp music get ${r.n}; recomp music bed-add ${c.jref} M…`}><Plus size={12} />Use</button></td></tr>
              ))}
            </tbody></table>
          )}
        </div>
      )}
    </div>
  );
}

function OverlayForm({ jref, slots }: { jref: string; slots: number }) {
  const [kind, setKind] = useState("quote");
  const [target, setTarget] = useState("journey");
  const [text, setText] = useState("");
  const [at, setAt] = useState("0");
  return (
    <div className="row">
      <select className="input" value={kind} onChange={(e) => setKind(e.target.value)} aria-label="Kind">{["quote", "text", "section", "lower_third", "title", "endcard"].map((k) => <option key={k}>{k}</option>)}</select>
      <select className="input" value={target} onChange={(e) => setTarget(e.target.value)} aria-label="Where">
        <option value="journey">whole journey</option>{Array.from({ length: slots }, (_, k) => <option key={k} value={k + 1}>cut {k + 1}</option>)}
      </select>
      <span className="muted2">at</span><input className="input" style={{ width: 56 }} value={at} onChange={(e) => setAt(e.target.value)} aria-label="Seconds in" /><span className="muted2">s</span>
      <input className="input grow" style={{ minWidth: 200 }} placeholder="Text (\n for a new line)" value={text} onChange={(e) => setText(e.target.value)} />
      <Act verb="overlay.add" args={{ target: target === "journey" ? jref : `${jref}#${target}`, kind, text, at }} disabled={!text.trim()} onDone={() => setText("")} icon={<Plus size={13} />}>Add</Act>
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
    <>
      <Stage c={c} side={<PlayerPane c={c} />}>
        <StepHead c={c} k="check" />
        <div className="panel">
          <div className="phead"><span className="h3 grow">Validation</span>
            {v && <span className={"chip " + (v.ok ? "ok" : "problem")}>{v.ok ? "ready to export" : `${v.problems.length} to fix`}</span>}
            <Act verb="journey.validate" args={{ journey: c.jref }} small ghost quiet>Re-check</Act></div>
          <div className="pbody">
            {!v && <div className="muted2">Checking…</div>}
            {v && <>
              {v.problems.map((p: string) => <div key={p} className="checkline"><XCircle size={14} color="var(--red)" /><span>{p}</span></div>)}
              {v.notes.map((p: string) => <div key={p} className="checkline"><AlertTriangle size={14} color="var(--amber)" /><span>{p}</span></div>)}
              {v.ok && <div className="checkline"><CheckCircle2 size={14} color="var(--accent)" /><span>Every source is reachable, every cut is long enough, the recipe is complete ({v.duration.replace(/^00:/, "")}).</span></div>}
            </>}
          </div>
        </div>
        <div className="panel">
          <div className="phead"><span className="h3 grow">Preview render</span>
            {profiles.length > 1 && <select className="input small" value={profile} onChange={(e) => setProfile(e.target.value)} aria-label="Format">{profiles.map((p) => <option key={p}>{p}</option>)}</select>}
            <Act verb="preview" args={{ target: c.jref, profile }} small primary={!latest} icon={<Clapperboard size={13} />} disabled={!c.j.slots.length}>{latest ? "Preview again" : "Make a preview"}</Act>
          </div>
          <div className="pbody">
            {!latest && <span className="muted2">A fast, small render with captions, overlays and music: what the real export will look like. Optional, about a minute.</span>}
            {latest && <ExportRow x={latest} open />}
          </div>
        </div>
      </Stage>
      <StepFoot c={c} what={v && !v.ok ? "Fix the problems above, then come back." : s.state === "done" ? "Checked." : "A preview is optional but worth a minute."}
                primary={s.state === "done" ? <NextButton c={c} /> :
                  <Act kbd="Enter" verb="journey.review" args={{ journey: c.jref, step:"check" }} primary disabled={!v?.ok} onDone={() => c.setStep("export")}>Ready to export<ArrowRight size={14} /></Act>} />
    </>
  );
}

// One export as a row; done ones open to the video and the ready-to-paste description.
function ExportRow({ x, open }: { x: any; open?: boolean }) {
  const { go } = useApp();
  const [show, setShow] = useState(!!open);
  const { data: d } = useData(() => (x.status === "done" && show ? must<any>("export.show", { ref: x.ref }) : Promise.resolve(null)), [x.ref, x.status, show]);
  const [copied, setCopied] = useState(false);
  const vertical = x.profile === "shorts";
  const st = x.status === "done" ? "ok" : x.status === "failed" ? "problem" : "running";
  return (
    <div className="stack sm">
      <div className="row nowrap">
        <span className={"chip " + st}>{x.status}</span>
        <span className="mono faint">{x.ref}</span>
        <b className="grow ellipsis">{x.preview ? "preview · " : ""}{x.profile} · {x.lang}</b>
        {x.status === "done" && <button className="btn small" onClick={() => setShow(!show)}>{show ? "Hide" : <><Play size={12} />Watch</>}</button>}
        <Act verb="project.reveal" args={{ what: x.ref }} small ghost quiet icon={<FolderOpen size={13} />} label="Open the folder">{""}</Act>
        <button className="btn small ghost" onClick={() => go("exports", x.ref)}>Details</button>
      </div>
      {x.status !== "done" && x.status !== "failed" && <div className="bar"><i style={{ width: `${Math.round((x.progress || 0) * 100)}%` }} /></div>}
      {x.error && <div className="err">{x.error}</div>}
      {!!x.problems?.length && <div className="warn">Checks: {x.problems.map((p: any) => p.check).join(", ")}</div>}
      {show && d?.video && <video controls src={fileUrl(d.video)} style={vertical ? { height: "min(56vh, 480px)", maxWidth: "100%", display: "block", background: "#000" }
                                                                                    : { width: "100%", maxWidth: 720, background: "#000" }} />}
      {show && !x.preview && d?.description && (
        <Disclosure id="export.desc" label="Description with credits (ready to paste)">
          <div className="row"><div className="spacer" /><button className="btn small" onClick={() => { navigator.clipboard.writeText(d.description); setCopied(true); setTimeout(() => setCopied(false), 1500); }}><Copy size={12} />{copied ? "Copied" : "Copy"}</button></div>
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
  const mainProfs = (profs || []).filter((p) => dest.includes(p.name) || (!dest.length && p.name === "landscape"));
  const others = (profs || []).filter((p) => !["preview", "clip"].includes(p.name) && !mainProfs.includes(p));
  const n = chosen.length * Math.max(1, langList.length);
  const tile = (p: any) => (
    <button key={p.name} type="button" className={"tile" + (chosen.includes(p.name) ? " on" : "")} aria-pressed={chosen.includes(p.name)}
            onClick={() => setChosen(chosen.includes(p.name) ? chosen.filter((x) => x !== p.name) : [...chosen, p.name])}>
      <span className="tt"><input type="checkbox" readOnly checked={chosen.includes(p.name)} tabIndex={-1} />{DESTINATIONS.find((d) => d.profile === p.name)?.label || p.name}<span className="chip">{p.size}</span></span>
      <span className="td">{p.description}</span>
    </button>
  );
  return (
    <>
      <Stage c={c}>
        {!!done.length && (
          <div className="celebrate">
            <CheckCircle2 size={16} color="var(--accent)" />
            <span className="grow"><b>{c.j.title} is ready.</b> {done.length} video{done.length > 1 ? "s" : ""} with captions and a description crediting every source. Upload them yourself{hubWanted && !onHub ? "; share the recipe on the hub below" : ""}.</span>
            <Act verb="project.reveal" args={{ what: "exports" }} small icon={<FolderOpen size={13} />} quiet>Exports folder</Act>
            <button className="btn small" onClick={() => go("exports", null, { tab: "translations", journey: c.jref })}><Languages size={13} />Translate it</button>
            <button className="btn small primary" onClick={newJourney}><Plus size={13} />New journey</button>
          </div>
        )}
        <StepHead c={c} k="export" />
        <div className="panel">
          <div className="phead"><span className="h3 grow">Render</span><span className="muted2">runs in the background; keep working</span></div>
          <div className="pbody stack">
            <div className="grid2">{mainProfs.map(tile)}</div>
            <div className="row" style={{ gap: 16 }}>
              {!!others.length && <Disclosure id="export.more" label="More formats" count={others.filter((p) => chosen.includes(p.name)).length || undefined}><div className="grid2">{others.map(tile)}</div></Disclosure>}
            </div>
            <Disclosure id="export.langs" label="Languages" count={langList.length || undefined}>
              <div className="row">
                <input className="input" style={{ width: 280 }} placeholder={`${c.j.language} (default); more: ${c.j.language},fr,sw`} value={langs} onChange={(e) => setLangs(e.target.value)} />
                <span className="muted2">Other languages are dubbed from their translations. <a href="#" onClick={(e) => { e.preventDefault(); go("exports", null, { tab: "translations", journey: c.jref }); }}>Prepare translations</a></span>
              </div>
            </Disclosure>
          </div>
        </div>
        <div className="panel">
          <div className="phead"><span className="h3 grow">Exports of this journey</span><span className="chip">{finals.length}</span></div>
          <div className="pbody stack">
            {!finals.length && <span className="muted2">None yet. Exports land in exports/{c.jref}-…/&lt;format&gt;-&lt;language&gt;/ with captions, description and recipe.</span>}
            {finals.slice(0, 10).map((x, k) => <div key={x.ref} style={k ? { borderTop: "1px solid var(--line)", paddingTop: 6 } : undefined}><ExportRow x={x} /></div>)}
          </div>
        </div>
        <div className="panel">
          <div className="phead"><Share2 size={14} /><span className="h3 grow">Share with the community</span>{onHub && <span className="chip ok">on the hub</span>}</div>
          <div className="pbody row">
            <span className="muted2 grow" style={{ minWidth: 260 }}>Publishes the recipe (sources, timecodes, text and credits, never the media) to the hub, where others play it from the original videos and remix it.</span>
            {onHub ? <><a className="btn small" href={`#/hub/r/${String(c.j.links.hub).split("/r/")[1]}`}>View it</a><PublishButton journey={c.jref} label="Publish a new version" /></>
              : <PublishButton journey={c.jref} label="Publish the recipe" primary={hubWanted && !!done.length} />}
          </div>
        </div>
      </Stage>
      <StepFoot c={c} what={done.length ? "Done. Change anything and export again: unchanged parts come from the cache." : `${n} video${n === 1 ? "" : "s"}: ${chosen.join(", ") || "pick a format"}${langList.length ? ` × ${langList.join(", ")}` : ""}`}
                primary={<Act kbd="Enter" verb="export.run" args={{ journey: c.jref, profiles: chosen, langs: langList }} primary agent disabled={!chosen.length || !c.j.slots.length} icon={<Clapperboard size={14} />}>
                  {`Export ${n} video${n === 1 ? "" : "s"}`}</Act>} />
    </>
  );
}

function JourneyMenu({ j }: { j: any }) {
  const { run } = useActions();
  const { go } = useApp();
  const [confirm, setConfirm] = useState(false);
  return (
    <>
      <Menu small label="Journey actions" items={[
        { header: j.ref },
        { label: "Duplicate to try a variation", icon: <Copy size={14} />, onSelect: async () => { const e = await run("journey.duplicate", { journey: j.ref }, { label: "Duplicate" }); if (e.ok) go("journeys", e.refs![0]); } },
        { label: "Export the recipe file", desc: "JSON in the recipes folder", icon: <FolderOpen size={14} />, onSelect: () => run("recipe.export", { journey: j.ref }, { label: "Recipe file" }) },
        { label: "Open the recipes folder", icon: <FolderOpen size={14} />, onSelect: () => run("project.reveal", { what: "recipes" }, { quiet: true }) },
        "sep",
        { label: "Delete journey…", icon: <Trash2 size={14} />, danger: true, desc: "Its cuts stay; undo brings it back", onSelect: () => setConfirm(true) },
      ]} />
      {confirm && (
        <Dialog title={`Delete “${j.title}”?`} sub="The journey goes; its cuts stay in the cut bin. Undo (Ctrl+Z) brings it back." onClose={() => setConfirm(false)}
                footer={<><div className="spacer" /><button className="btn" onClick={() => setConfirm(false)}>Keep it</button>
                  <Act verb="journey.delete" args={{ journey: j.ref }} className="danger" onDone={() => { setConfirm(false); go("journeys"); }}>Delete</Act></>}>
          <p className="muted2" style={{ margin: 0 }}>{j.slots.length} cuts · {j.duration}</p>
        </Dialog>
      )}
    </>
  );
}

