import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { Activity, Film, FolderOpen, Layers, ListChecks, Moon, Search as SearchIcon, Share2, Sun, Upload } from "lucide-react";
import { must, setProject, subscribe, type Ev } from "./api";
import Start from "./views/Start";
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
  if (parts[0] === "p" && parts[1]) return { project: parts[1], view: parts[2] || "sources", arg: parts[3] || null, params };
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
    window.location.hash = `#/p/${encodeURIComponent(name)}/sources`;
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
        navigateToRef(f.ref, f.at, f.play);
      }
      if (e.kind !== "hello") {
        window.clearTimeout(timer);
        timer = window.setTimeout(() => setVersion((v) => v + 1), 120);
      }
    });
    return () => { stop(); window.clearTimeout(timer); };
  }, [route.project]);

  const navigateToRef = (ref: string, at?: number | null, play?: boolean) => {
    if (/^S\d+(\.c\d+|\.t\d+)?$/.test(ref) || /^C\d+$/.test(ref)) {
      const src = ref.startsWith("S") ? ref.split(".")[0] : null;
      if (src) go("room", src, { t: at ?? undefined, focus: ref, play: play ? 1 : undefined });
      else must("cut.show", { ref }).then((c: any) => go("room", c.source, { t: at ?? c.start, focus: ref, play: play ? 1 : undefined }));
    } else if (/^J\d+(#\d+)?$/.test(ref)) go("journeys", ref.split("#")[0], { slot: ref.split("#")[1] });
    else if (/^X\d+$/.test(ref)) go("exports", ref);
    else if (/^job\d+$/.test(ref)) go("jobs");
  };

  const ctx: Ctx = { route, go, openProject, version, lastEvent, bump };
  const tabs: [string, string, JSX.Element][] = [
    ["sources", "Sources", <Film size={14} />],
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
                <button key={key} className={"tab" + (v === key || (key === "sources" && v === "room") ? " on" : "")} onClick={() => go(key)}>
                  {icon}{label}
                </button>
              ))}
            </div>
          )}
          <div className="spacer" />
          <button className={"tab" + (v === "hub" ? " on" : "")} onClick={() => (window.location.hash = "#/hub")}><Share2 size={14} />Hub</button>
          <button className="btn ghost small" title="Theme" onClick={() => setTheme(theme === "dark" ? "light" : theme === "light" ? "system" : "dark")}>
            {theme === "dark" ? <Moon size={14} /> : <Sun size={14} />} {theme}
          </button>
        </div>
        <div className={"body" + (!route.project || v === "room" ? " nopanel" : "")}>
          <div className="main">
            {!route.project && v === "start" && <Start />}
            {v === "hub" && <Hub />}
            {route.project && v === "sources" && <Sources />}
            {route.project && v === "room" && route.arg && <Room key={route.arg} sourceRef={route.arg} />}
            {route.project && v === "search" && <SearchView />}
            {route.project && v === "journeys" && <Journeys />}
            {route.project && v === "exports" && <Exports />}
            {route.project && v === "jobs" && <Jobs />}
            {route.project && v === "activity" && <ActivityView />}
          </div>
          {route.project && v !== "room" && <aside className="side"><AgentPanel /></aside>}
        </div>
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
