// One filter bar for every list. Filters live in the URL (#/p/x/cuts?source=S1&tag=fear), so a view can be
// bookmarked, and the agent opens the same view with `recomp ui show cuts --filter "source=S1&tag=fear"`.
import { useEffect, useRef, useState } from "react";
import { Filter, X } from "lucide-react";
import { useApp } from "./App";

export type FilterField =
  | { key: string; label: string; type: "text"; placeholder?: string; width?: number }
  | { key: string; label: string; type: "select"; options: (string | [string, string])[] }
  | { key: string; label: string; type: "number"; placeholder?: string; width?: number }
  | { key: string; label: string; type: "check" };

export function useFilters(): [Record<string, string>, (k: string, v: string | null) => void] {
  const { route, go } = useApp();
  const values: Record<string, string> = {};
  route.params.forEach((v, k) => { values[k] = v; });
  const set = (k: string, v: string | null) => {
    const next: Record<string, string> = {};
    new URLSearchParams(window.location.hash.split("?")[1] || "").forEach((val, key) => { next[key] = val; });
    if (v === null || v === "") delete next[k]; else next[k] = v;
    go(route.view, route.arg, next);
  };
  return [values, set];
}

export function FilterBar({ fields, count, extra, keep = [] }: { fields: FilterField[]; count?: number; extra?: React.ReactNode; keep?: string[] }) {
  const [values, set] = useFilters();
  const active = fields.filter((f) => values[f.key]);
  const { route, go } = useApp();
  const clearAll = () => {
    const keys = fields.map((f) => f.key);
    const next: Record<string, string> = {};
    route.params.forEach((v, k) => { if (!keys.includes(k) || keep.includes(k)) next[k] = v; });
    go(route.view, route.arg, next);
  };
  return (
    <div className="filterbar">
      <Filter size={14} style={{ color: "var(--faint)" }} />
      {fields.map((f) => <FilterInput key={f.key} f={f} value={values[f.key] || ""} set={(v) => set(f.key, v)} />)}
      {!!active.length && <button className="btn ghost small" onClick={clearAll} title="Clear filters"><X size={12} />Clear</button>}
      <div className="spacer" />
      {extra}
      {count != null && <span className="chip">{count} shown</span>}
    </div>
  );
}

function FilterInput({ f, value, set }: { f: FilterField; value: string; set: (v: string | null) => void }) {
  const [draft, setDraft] = useState(value);
  const timer = useRef<number>();
  useEffect(() => setDraft(value), [value]);
  if (f.type === "select") {
    return (
      <select className={"input" + (value ? " on" : "")} value={value} onChange={(e) => set(e.target.value || null)} aria-label={f.label}>
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
      <label className={"chip" + (value ? " done" : "")} style={{ cursor: "pointer" }}>
        <input type="checkbox" checked={!!value} onChange={(e) => set(e.target.checked ? "1" : null)} /> {f.label}
      </label>
    );
  }
  return (
    <input className={"input" + (value ? " on" : "")} data-filter={f.key} style={{ width: f.width || (f.type === "number" ? 70 : 180) }}
           placeholder={f.placeholder || f.label} value={draft} type={f.type === "number" ? "number" : "text"} aria-label={f.label}
           onChange={(e) => {
             setDraft(e.target.value);
             window.clearTimeout(timer.current);
             const v = e.target.value;
             timer.current = window.setTimeout(() => set(v || null), 300);
           }} />
  );
}

export const textMatch = (q: string | undefined, ...fields: (string | null | undefined)[]) =>
  !q || fields.some((x) => (x || "").toLowerCase().includes(q.toLowerCase()));
