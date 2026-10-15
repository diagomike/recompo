import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { Activity, Film, FolderOpen, Home as HomeIcon, Keyboard, Layers, ListChecks, Moon, Scissors, Search as SearchIcon, Share2, Sun, Upload } from "lucide-react";
import { must, setProject, subscribe, verb, type Ev } from "./api";
import { ActionProvider, useActions, useHighlightScroll } from "./actions";
import Start from "./views/Start";
import Home from "./views/Home";
import Cuts from "./views/Cuts";
import Sources from "./views/Sources";
import Room from "./views/Room";
import SearchView from "./views/Search";
import Jobs from "./views/Jobs";
import ActivityView from "./views/Activity";
import Journeys from "./views/Journeys";
import Exports from "./views/Exports";
import Hub from "./views/Hub";
import AgentPanel from "./views/AgentPanel";

type Route = { project: string | null; view: string; arg: string | null; params: URLSearchParams };

function parse(hash: string): Route {
  const [path, query] = hash.replace(/^#\/?/, "").split("?");
  const parts = path.split("/").filter(Boolean).map(decodeURIComponent);
  const params = new URLSearchParams(query || "");
  if (parts[0] === "p" && parts[1]) return { project: parts[1], view: parts[2] || "home", arg: parts[3] || null, params };
  if (parts[0] === "hub") return { project: null, view: "hub", arg: parts.slice(1).join("/") || null, params };
  return { project: null, view: "start", arg: null, params };
}

type Ctx = {
  route: Route;
  go: (view: string, arg?: string | null, params?: Record<string, string | number | undefined>) => void;
  openProject: (name: string) => void;
  version: number;
  lastEvent: Ev | null;
  bump: () => void;
};
const AppCtx = createContext<Ctx>(null!);
export const useApp = () => useContext(AppCtx);

export default function App() {
  return <ActionProvider><Shell /></ActionProvider>;
}

const VIEWS = ["home", "sources", "cuts", "search", "journeys", "exports", "jobs", "activity"];

function Shell() {
  const { setHighlight, toast } = useActions();
  const [help, setHelp] = useState(false);
  useHighlightScroll();
  const [hash, setHash] = useState(window.location.hash);
  const [version, setVersion] = useState(0);
  const [lastEvent, setLastEvent] = useState<Ev | null>(null);
  const [theme, setTheme] = useState<string>(() => {
    try { return localStorage.getItem("recomp.theme") || "system"; } catch { return "system"; }
  });
  const route = useMemo(() => parse(hash), [hash]);

  useEffect(() => {
    const on = () => setHash(window.location.hash);
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  useEffect(() => {
    if (theme === "system") document.documentElement.removeAttribute("data-theme");
    else document.documentElement.setAttribute("data-theme", theme);
    try { localStorage.setItem("recomp.theme", theme); } catch { /* ignore */ }
  }, [theme]);

  setProject(route.project);

  const go = useCallback((view: string, arg?: string | null, params?: Record<string, string | number | undefined>) => {
    const p = parse(window.location.hash).project;
    const qs = params ? "?" + new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined).map(([k, v]) => [k, String(v)])).toString() : "";
    window.location.hash = p ? `#/p/${encodeURIComponent(p)}/${view}${arg ? "/" + encodeURIComponent(arg) : ""}${qs}` : `#/${view}`;
  }, []);
  const openProject = useCallback((name: string) => {
    window.location.hash = `#/p/${encodeURIComponent(name)}/home`;
  }, []);
  const bump = useCallback(() => setVersion((v) => v + 1), []);

  // Live: every op, job and viewer-state event refreshes the views; the agent's `ui show` moves us.
  useEffect(() => {
    if (!route.project) return;
    let timer: number | undefined;
    const stop = subscribe((e) => {
      setLastEvent(e);
      if (e.kind === "ui" && e.data?.key === "focus" && e.data?.value?.by !== "user") {
        const f = e.data.value;
        navigateToRef(f.ref, f.at, f.play, f.filter);
        if (f.highlight) setHighlight(f.highlight);
        toast({ ok: true, title: `The agent opened ${f.ref}`, detail: f.highlight ? `and points at ${f.highlight}` : undefined });
      }
      // selection and focus are shared state, not data: they move views but need no reload
      if (e.kind !== "hello" && !(e.kind === "ui" && (e.data?.key === "selection" || e.data?.key === "focus"))) {
        window.clearTimeout(timer);
        timer = window.setTimeout(() => setVersion((v) => v + 1), 120);
      }
    });
    return () => { stop(); window.clearTimeout(timer); };
  }, [route.project]);

  const navigateToRef = (ref: string, at?: number | null, play?: boolean, filter?: Record<string, string>) => {
    if (ref === "translations") { go("exports", null, { ...(filter || {}), tab: "translations" }); return; }
    if (VIEWS.includes(ref)) { go(ref, null, filter || {}); return; }
    if (/^S\d+(\.c\d+|\.t\d+)?$/.test(ref) || /^C\d+$/.test(ref)) {
      const src = ref.startsWith("S") ? ref.split(".")[0] : null;
      if (src) go("room", src, { t: at ?? undefined, focus: ref, play: play ? 1 : undefined, ...(filter || {}) });
      else must("cut.show", { ref }).then((c: any) => go("room", c.source, { t: at ?? c.start, focus: ref, play: play ? 1 : undefined }));
    } else if (/^J\d+(#\d+)?$/.test(ref)) go("journeys", ref.split("#")[0], { slot: ref.split("#")[1], ...(filter || {}) });
    else if (/^X\d+$/.test(ref)) go("exports", ref);
    else if (/^job\d+$/.test(ref)) go("jobs");
  };

  // Keyboard: g then h/s/c/f/j/e/b/a moves between views; / focuses the filter; ? shows the keys; Ctrl+Z undoes.
  useEffect(() => {
    let g = 0;
    const on = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || !route.project) return;
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") {
        e.preventDefault();
        verb(e.shiftKey ? "op.redo" : "op.undo", {}).then((env) => toast(env.ok ? { ok: true, title: `${e.shiftKey ? "Redone" : "Undone"}: ${env.data.verb}` }
          : { ok: false, title: e.shiftKey ? "Redo" : "Undo", detail: env.error!.message + (env.error!.hint ? " — " + env.error!.hint : "") }));
        return;
      }
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      if (e.key === "?") { setHelp((h) => !h); return; }
      if (e.key === "/") {
        const el = document.querySelector("[data-filter]") as HTMLInputElement | null;
        if (el) { e.preventDefault(); el.focus(); }
        return;
      }
      if (e.key === "g") { g = Date.now(); return; }
      if (Date.now() - g < 1200) {
        const map: Record<string, string> = { h: "home", s: "sources", c: "cuts", f: "search", j: "journeys", e: "exports", b: "jobs", a: "activity" };
        if (map[e.key]) { go(map[e.key]); g = 0; }
      }
    };
    window.addEventListener("keydown", on);
    return () => window.removeEventListener("keydown", on);
  }, [route.project, go, toast]);

  const ctx: Ctx = { route, go, openProject, version, lastEvent, bump };
  const tabs: [string, string, JSX.Element][] = [
    ["home", "Home", <HomeIcon size={14} />],
    ["sources", "Sources", <Film size={14} />],
    ["cuts", "Cut bin", <Scissors size={14} />],
    ["search", "Search", <SearchIcon size={14} />],
    ["journeys", "Journeys", <Layers size={14} />],
    ["exports", "Exports", <Upload size={14} />],
    ["jobs", "Jobs", <ListChecks size={14} />],
    ["activity", "Activity", <Activity size={14} />],
  ];
  const v = route.view;
  return (
    <AppCtx.Provider value={ctx}>
      <div className="app">
        <div className="top">
          <a className="brand" href="#/"><span className="logo">R</span>Recomposer</a>
          {route.project && (
            <button className="btn ghost small" onClick={() => (window.location.hash = "#/")} title="Switch project">
              <FolderOpen size={14} /> {route.project}
            </button>
          )}
          {route.project && (
            <div className="tabs">
              {tabs.map(([key, label, icon]) => (
                <button key={key} className={"tab" + (v === key || (key === "sources" && v === "room") ? " on" : "")} onClick={() => go(key)} data-view={key}>
                  {icon}{label}
                </button>
              ))}
            </div>
          )}
          <div className="spacer" />
          <button className={"tab" + (v === "hub" ? " on" : "")} onClick={() => (window.location.hash = "#/hub")}><Share2 size={14} />Hub</button>
          {route.project && <button className="btn ghost small" title="Keyboard shortcuts (?)" onClick={() => setHelp(!help)}><Keyboard size={14} /></button>}
          <button className="btn ghost small" title="Theme" onClick={() => setTheme(theme === "dark" ? "light" : theme === "light" ? "system" : "dark")}>
            {theme === "dark" ? <Moon size={14} /> : <Sun size={14} />} {theme}
          </button>
        </div>
        <div className={"body" + (!route.project || v === "room" ? " nopanel" : "")}>
          <div className="main">
            {!route.project && v === "start" && <Start />}
            {v === "hub" && <Hub />}
            {route.project && v === "home" && <Home />}
            {route.project && v === "sources" && <Sources />}
            {route.project && v === "cuts" && <Cuts />}
            {route.project && v === "room" && route.arg && <Room key={route.arg} sourceRef={route.arg} />}
            {route.project && v === "search" && <SearchView />}
            {route.project && v === "journeys" && <Journeys />}
            {route.project && v === "exports" && <Exports />}
            {route.project && v === "jobs" && <Jobs />}
            {route.project && v === "activity" && <ActivityView />}
          </div>
          {route.project && v !== "room" && <aside className="side"><AgentPanel /></aside>}
        </div>
        {help && (
          <div className="modal" onClick={() => setHelp(false)}>
            <div className="card keys" onClick={(e) => e.stopPropagation()}>
              <b>Keyboard</b>
              <table><tbody>
                {[["g h / g s / g c / g f", "Home, Sources, Cut bin, Search"], ["g j / g e / g b / g a", "Journeys, Exports, Jobs, Activity"],
                  ["/", "Focus the filter or find box"], ["Ctrl+Z, Ctrl+Shift+Z", "Undo, redo (yours; the agent cannot undo your work)"],
                  ["Space", "Play / pause (source room)"], ["I / O", "Mark in / out"], ["C", "Cut the selection"], ["← / →", "Seek 2 s (Shift: 10 s)"],
                  ["Shift-click", "Extend a selection (lines, cuts)"], ["Double-click a line", "Edit it"], ["?", "This help"]].map(([k, d]) => (
                  <tr key={k}><td><span className="kbd">{k}</span></td><td>{d}</td></tr>
                ))}
              </tbody></table>
              <p className="muted2">Every button runs a command. Hover to see it; the robot hands it to the agent instead.</p>
            </div>
          </div>
        )}
      </div>
    </AppCtx.Provider>
  );
}

export function useData<T>(load: () => Promise<T>, deps: any[] = []): { data: T | null; error: string | null; reload: () => void } {
  const { version } = useApp();
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [n, setN] = useState(0);
  useEffect(() => {
    let live = true;
    load().then((d) => live && (setData(d), setError(null))).catch((e) => live && setError(String(e.message || e)));
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [version, n, ...deps]);
  return { data, error, reload: () => setN((x) => x + 1) };
}
