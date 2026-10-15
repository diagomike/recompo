// One filter bar for every list. Filters live in the URL (#/p/x/cuts?source=S1&tag=fear), so a view can be
// bookmarked, and the agent opens the same view with `recomp ui show cuts --filter "source=S1&tag=fear"`.
// The first fields stay visible; the rest fold under "More filters" (opened by itself when one of them is set).
import { useEffect, useRef, useState } from "react";
import { Search, SlidersHorizontal, X } from "lucide-react";
import { useApp } from "./App";

export type FilterField =
  | { key: string; label: string; type: "text"; placeholder?: string; width?: number }
  | { key: string; label: string; type: "select"; options: (string | [string, string])[] }
  | { key: string; label: string; type: "number"; placeholder?: string; width?: number }
  | { key: string; label: string; type: "check" };

export function useFilters(): [Record<string, string>, (k: string, v: string | null) => void] {
  const { route, setParam } = useApp();
  const values: Record<string, string> = {};
  route.params.forEach((v, k) => { values[k] = v; });
  return [values, setParam];
}

export function FilterBar({ fields, count, extra, keep = [], primary = 2, noun = "shown" }: {
  fields: FilterField[]; count?: number; extra?: React.ReactNode; keep?: string[]; primary?: number; noun?: string;
}) {
  const [values, set] = useFilters();
  const active = fields.filter((f) => values[f.key]);
  const { route, go } = useApp();
  const rest = fields.slice(primary);
  const restActive = rest.filter((f) => values[f.key]).length;
  const [more, setMore] = useState(restActive > 0);
  const clearAll = () => {
    const keys = fields.map((f) => f.key);
    const next: Record<string, string> = {};
    route.params.forEach((v, k) => { if (!keys.includes(k) || keep.includes(k)) next[k] = v; });
    go(route.view, route.arg, next);
  };
  return (
    <div className="filterbar">
      {fields.slice(0, primary).map((f) => <FilterInput key={f.key} f={f} value={values[f.key] || ""} set={(v) => set(f.key, v)} />)}
      {!!rest.length && (
        <button className={"btn" + (more || restActive ? " on" : "")} onClick={() => setMore(!more)} aria-expanded={more}>
          <SlidersHorizontal size={14} />More filters{restActive ? <span className="chip info" style={{ lineHeight: "20px" }}>{restActive}</span> : null}
        </button>
      )}
      {!!active.length && <button className="btn ghost" onClick={clearAll} data-tip="Clear every filter"><X size={14} />Clear</button>}
      <div className="spacer" />
      {extra}
      {count != null && <span className="muted2 nowrap">{count} {noun}</span>}
      {more && !!rest.length && (
        <div className="filtermore">
          {rest.map((f) => <FilterInput key={f.key} f={f} value={values[f.key] || ""} set={(v) => set(f.key, v)} />)}
        </div>
      )}
    </div>
  );
}

function FilterInput({ f, value, set }: { f: FilterField; value: string; set: (v: string | null) => void }) {
  const [draft, setDraft] = useState(value);
  const timer = useRef<number>();
  useEffect(() => setDraft(value), [value]);
  if (f.type === "select") {
    return (
      <select className={"input" + (value ? " on" : "")} value={value} onChange={(e) => set(e.target.value || null)} aria-label={f.label} style={{ maxWidth: 260 }}>
        <option value="">{f.label}: any</option>
        {f.options.map((o) => {
          const [v, l] = Array.isArray(o) ? o : [o, o];
          return <option key={v} value={v}>{f.label}: {l}</option>;
        })}
      </select>
    );
  }
  if (f.type === "check") {
    return (
      <label className={"btn" + (value ? " on" : "")} style={{ cursor: "pointer" }}>
        <input type="checkbox" checked={!!value} onChange={(e) => set(e.target.checked ? "1" : null)} /> {f.label}
      </label>
    );
  }
  const input = (
    <input className={"input" + (value ? " on" : "")} data-filter={f.key} style={f.type === "number" ? { width: f.width || 110 } : f.width ? { width: f.width } : undefined}
           placeholder={f.placeholder || f.label} value={draft} type={f.type === "number" ? "number" : "text"} aria-label={f.label}
           onChange={(e) => {
             setDraft(e.target.value);
             window.clearTimeout(timer.current);
             const v = e.target.value;
             timer.current = window.setTimeout(() => set(v || null), 300);
           }} />
  );
  return f.type === "text" && !f.width ? <div className="search"><Search size={14} />{input}</div> : input;
}

export const textMatch = (q: string | undefined, ...fields: (string | null | undefined)[]) =>
  !q || fields.some((x) => (x || "").toLowerCase().includes(q.toLowerCase()));
