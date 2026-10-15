// Every action in the viewer is a verb call. Buttons show the command they run (the same one the agent
// would type), report the result with an Undo, and can be handed to the agent instead of run here.
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { Bot, Check, Undo2, X } from "lucide-react";
import { verb, type Envelope } from "./api";

type Toast = { id: number; ok: boolean; title: string; cli?: string; detail?: string; undo?: boolean; refs?: string[] };
type RunOpts = { label?: string; quiet?: boolean; undoable?: boolean };
type Ctx = {
  run: (name: string, args?: Record<string, any>, opts?: RunOpts) => Promise<Envelope>;
  hand: (name: string, args: Record<string, any>, label: string) => Promise<void>;
  ask: (text: string, refs?: string[]) => Promise<void>;
  toast: (t: Omit<Toast, "id">) => void;
  highlight: string | null;
  setHighlight: (v: string | null) => void;
};
const ActionCtx = createContext<Ctx>(null!);
export const useActions = () => useContext(ActionCtx);

const READ_ONLY = /\.(list|show|status|lines|read|outline|browse|checklist|selection|notes)$|^search$|^context$/;

export function ActionProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [highlight, setHighlightState] = useState<string | null>(null);
  const seq = useRef(0);
  const toast = useCallback((t: Omit<Toast, "id">) => {
    const id = ++seq.current;
    setToasts((xs) => [...xs.slice(-3), { ...t, id }]);
    window.setTimeout(() => setToasts((xs) => xs.filter((x) => x.id !== id)), t.ok ? 6000 : 12000);
  }, []);
  const setHighlight = useCallback((v: string | null) => {
    setHighlightState(v);
    if (v) window.setTimeout(() => setHighlightState((cur) => (cur === v ? null : cur)), 8000);
  }, []);
  const run = useCallback(async (name: string, args: Record<string, any> = {}, opts: RunOpts = {}) => {
    const env = await verb(name, args);
    const cli = (env as any).cli as string | undefined;
    if (!env.ok) {
      toast({ ok: false, title: opts.label || name, cli, detail: `${env.error!.message}${env.error!.hint ? " — " + env.error!.hint : ""}` });
    } else if (!opts.quiet) {
      const write = !READ_ONLY.test(name);
      toast({ ok: true, title: opts.label || name, cli, refs: env.refs, undo: write && !env.job && opts.undoable !== false && !!env.op,
              detail: env.warnings?.length ? env.warnings.join(" ") : env.job ? `Queued as ${env.job}` : undefined });
    }
    return env;
  }, [toast]);
  const hand = useCallback(async (name: string, args: Record<string, any>, label: string) => {
    const env = await verb("ui.note", { text: `Please do this for me: ${label}`, verb: name, args });
    toast(env.ok ? { ok: true, title: "Handed to the agent", cli: env.data?.request?.cli, detail: "It sees this in `recomp ui notes` (and `context`)." }
                 : { ok: false, title: "Could not hand it over", detail: env.error?.message });
  }, [toast]);
  const ask = useCallback(async (text: string, refs: string[] = []) => {
    const env = await verb("ui.note", { text, refs });
    toast(env.ok ? { ok: true, title: "Sent to the agent", detail: text } : { ok: false, title: "Could not send", detail: env.error?.message });
  }, [toast]);
  return (
    <ActionCtx.Provider value={{ run, hand, ask, toast, highlight, setHighlight }}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={"toast " + (t.ok ? "ok" : "bad")}>
            <div className="thead">
              <span className="ticon">{t.ok ? <Check size={15} /> : <X size={15} />}</span>
              <b className="grow">{t.title}{t.refs?.length ? " → " + t.refs.slice(0, 4).join(", ") : ""}</b>
              {t.undo && <button className="btn small" onClick={async () => { const e = await verb("op.undo", {}); toast(e.ok ? { ok: true, title: `Undone: ${e.data.verb}` } : { ok: false, title: "Undo", detail: e.error!.message + (e.error!.hint ? " — " + e.error!.hint : "") }); setToasts((xs) => xs.filter((x) => x.id !== t.id)); }}><Undo2 size={14} />Undo</button>}
              <button className="btn ghost small icon" aria-label="Dismiss" onClick={() => setToasts((xs) => xs.filter((x) => x.id !== t.id))}><X size={14} /></button>
            </div>
            {t.detail && <div className="tdetail">{t.detail}</div>}
            {t.cli && <code className="tcli">{t.cli}</code>}
          </div>
        ))}
      </div>
    </ActionCtx.Provider>
  );
}

const cliCache = new Map<string, string>();
export async function cliFor(name: string, args: Record<string, any>): Promise<string> {
  const key = name + JSON.stringify(args);
  if (cliCache.has(key)) return cliCache.get(key)!;
  try {
    const r = await fetch("/api/cli", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ verb: name, args }) });
    const { cli } = await r.json();
    cliCache.set(key, cli);
    return cli;
  } catch { return `recomp ${name.replace(".", " ")}`; }
}

type ActProps = {
  verb: string; args?: Record<string, any>; label?: string; icon?: ReactNode; children?: ReactNode;
  primary?: boolean; small?: boolean; lg?: boolean; ghost?: boolean; disabled?: boolean; confirm?: string; quiet?: boolean;
  agent?: boolean; onDone?: (env: Envelope) => void; title?: string; className?: string; kbd?: string;
};

// The words of a button's children, for its toast and the agent hand-off.
function textOf(n: ReactNode): string {
  if (typeof n === "string" || typeof n === "number") return String(n);
  if (Array.isArray(n)) return n.map(textOf).join("").trim();
  return "";
}

// A button that runs one verb. Hover shows the command; the robot hands the same action to the agent.
export function Act(p: ActProps) {
  const { run, hand, highlight } = useActions();
  const [busy, setBusy] = useState(false);
  const [tip, setTip] = useState<string>("");
  const [armed, setArmed] = useState(false);
  const args = p.args || {};
  const label = p.label || textOf(p.children) || p.verb;
  const go = async () => {
    if (p.disabled || busy) return;
    if (p.confirm && !armed) {  // two clicks instead of a blocking dialog
      setArmed(true);
      window.setTimeout(() => setArmed(false), 4000);
      return;
    }
    setArmed(false);
    setBusy(true);
    const env = await run(p.verb, args, { label, quiet: p.quiet });
    setBusy(false);
    if (env.ok) p.onDone?.(env);
  };
  const iconOnly = !!p.icon && (p.children === "" || (p.children == null && !p.label));
  const cls = ["btn", p.primary ? "primary" : "", p.small ? "small" : "", p.lg ? "lg" : "", iconOnly && !armed ? "icon" : "", p.ghost && !armed ? "ghost" : "", armed ? "armed" : "",
               highlight === p.verb ? "pulse" : "", p.className || ""].join(" ");
  return (
    <span className="act-wrap">
      <button className={cls} data-verb={p.verb} disabled={p.disabled || busy} onClick={go} aria-label={iconOnly ? label : undefined}
              onMouseEnter={() => !tip && cliFor(p.verb, args).then(setTip)} onFocus={() => !tip && cliFor(p.verb, args).then(setTip)}
              data-tip={(armed && p.confirm ? p.confirm : p.title || (iconOnly ? label : "Runs this command")) || undefined}
              data-tip-cmd={tip || `recomp ${p.verb.replace(".", " ")}`} data-tip-key={p.kbd}>
        {p.icon}{armed ? "Click again to confirm" : iconOnly ? null : (p.children ?? p.label)}{busy ? "…" : ""}
      </button>
      {p.agent && (
        <button className="btn ghost small icon agent-hand" disabled={p.disabled} aria-label="Hand this to the agent"
                data-tip="Hand this to the agent instead: it gets the same command" data-tip-cmd={tip || p.verb}
                onMouseEnter={() => !tip && cliFor(p.verb, args).then(setTip)} onClick={() => hand(p.verb, args, label)}>
          <Bot size={15} />
        </button>
      )}
    </span>
  );
}

// Pulse the matching buttons when the agent points at one (`recomp ui show … --highlight export.run`).
export function useHighlightScroll() {
  const { highlight } = useActions();
  useEffect(() => {
    if (!highlight) return;
    const t = window.setTimeout(() => {
      const el = document.querySelector(`[data-verb="${highlight}"]`) as HTMLElement | null;
      el?.scrollIntoView({ block: "center", behavior: "smooth" });
    }, 300);
    return () => window.clearTimeout(t);
  }, [highlight]);
}
