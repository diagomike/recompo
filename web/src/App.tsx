import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { Activity, Bot, ChevronsUpDown, Film, Home as HomeIcon, Keyboard, Layers, Lightbulb, ListChecks, Menu as MenuIcon, Monitor, Moon, Plus,
  Scissors, Search as SearchIcon, Share2, Sun, Upload, Users } from "lucide-react";
import { must, setProject, subscribe, verb, type Ev } from "./api";
import { ActionProvider, useActions, useHighlightScroll } from "./actions";
import { Dialog, Menu, TooltipLayer, useWidth } from "./ui";
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
import NewJourney from "./views/NewJourney";
import Follows from "./views/Follows";
import Topics from "./views/Topics";

type Route = { project: string | null; view: string; arg: string | null; params: URLSearchParams };
// Studio-level pages (the research wing): reachable without a project and from every project.
const STUDIO_VIEWS = ["follows", "topics"];

function parse(hash: string): Route {
  const [path, query] = hash.replace(/^#\/?/, "").split("?");
  const parts = path.split("/").filter(Boolean).map(decodeURIComponent);
  const params = new URLSearchParams(query || "");
  if (parts[0] === "p" && parts[1]) return { project: parts[1], view: parts[2] || "home", arg: parts[3] || null, params };
  if (parts[0] === "hub") return { project: null, view: "hub", arg: parts.slice(1).join("/") || null, params };
  if (STUDIO_VIEWS.includes(parts[0])) return { project: null, view: parts[0], arg: parts[1] || null, params };
  return { project: null, view: "start", arg: null, params };
}

type Ctx = {
  route: Route;
  go: (view: string, arg?: string | null, params?: Record<string, string | number | undefined>) => void;
  setParam: (key: string, value: string | null) => void;
  openProject: (name: string) => void;
  newJourney: () => void;
  version: number;
  lastEvent: Ev | null;
  bump: () => void;
};
const AppCtx = createContext<Ctx>(null!);
export const useApp = () => useContext(AppCtx);

export default function App() {
  return <ActionProvider><Shell /><TooltipLayer /></ActionProvider>;
}

const VIEWS = ["home", "sources", "cuts", "search", "journeys", "exports", "jobs", "activity", ...STUDIO_VIEWS];
const TITLES: Record<string, string> = {
  home: "Home", sources: "Sources", room: "Source room", cuts: "Cut bin", search: "Search", journeys: "Journeys",
  exports: "Exports", jobs: "Jobs", activity: "Activity", hub: "Community hub", start: "Projects", follows: "Follows", topics: "Topics",
};

function Shell() {
  const { setHighlight, toast } = useActions();
  const [help, setHelp] = useState(false);
  useHighlightScroll();
  const width = useWidth();
  const [hash, setHash] = useState(window.location.hash);
  const [version, setVersion] = useState(0);
  const [lastEvent, setLastEvent] = useState<Ev | null>(null);
  const [theme, setTheme] = useState<string>(() => {
    try { return localStorage.getItem("recomp.theme") || "system"; } catch { return "system"; }
  });
  // The agent drawer: docked on wide screens, a slide-over elsewhere; closed by default below 1440 px.
  const [agentOpen, setAgentOpen] = useState<boolean>(() => {
    try { const v = localStorage.getItem("recomp.agent"); if (v != null) return v === "1" && window.innerWidth >= 1440; } catch { /* ignore */ }
    return window.innerWidth >= 1440;
  });
  const toggleAgent = (v?: boolean) => {
    const next = v ?? !agentOpen;
    setAgentOpen(next);
    try { localStorage.setItem("recomp.agent", next ? "1" : "0"); } catch { /* ignore */ }
  };
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
    const qs = params ? new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined && v !== null).map(([k, v]) => [k, String(v)])).toString() : "";
    window.location.hash = (p ? `#/p/${encodeURIComponent(p)}/${view}${arg ? "/" + encodeURIComponent(arg) : ""}` : `#/${view}`) + (qs ? "?" + qs : "");
  }, []);
  const setParam = useCallback((key: string, value: string | null) => {
    const r = parse(window.location.hash);
    const next: Record<string, string> = {};
    r.params.forEach((v, k) => { next[k] = v; });
    if (value == null || value === "") delete next[key]; else next[key] = value;
    go(r.view, r.arg, next);
  }, [go]);
  const openProject = useCallback((name: string) => {
    window.location.hash = `#/p/${encodeURIComponent(name)}/home`;
  }, []);
  const newJourney = useCallback(() => setParam("new", "1"), [setParam]);
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
    else if (/^T\d+$/.test(ref)) go("topics", null, { t: ref });
    else if (/^[FI]\d+$/.test(ref)) go("follows", null, ref.startsWith("F") ? { tab: "following" } : {});
  };

  // Keyboard: g then h/s/c/f/j/e/b/a moves between views; n starts a journey; / focuses the filter; ? shows the keys.
  useEffect(() => {
    let g = 0;
    const on = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || !route.project) return;
      if (document.querySelector(".modal")) return;
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
        return;
      }
      if (e.key === "n" && route.view !== "room") { e.preventDefault(); newJourney(); }
      if (e.key === "." ) toggleAgent();
    };
    window.addEventListener("keydown", on);
    return () => window.removeEventListener("keydown", on);
  });

  const { data: notes } = useDataIn(version, route.project ? () => must<any>("ui.notes", { mark_seen: false }) : null, [route.project]);
  const { data: jobs } = useDataIn(version, route.project ? () => must<any>("job.list", { limit: 20 }) : null, [route.project]);
  const { data: follows } = useDataIn(version, () => must<any[]>("follow.list"), [route.project, route.view]);
  const inboxNew = (follows || []).reduce((n: number, x: any) => n + (x.inbox_new || 0), 0);
  const asks = (notes?.open_asks || []).length as number;
  const running = (jobs?.jobs || []).filter((j: any) => j.status === "running" || j.status === "queued").length as number;

  const ctx: Ctx = { route, go, setParam, openProject, newJourney, version, lastEvent, bump };
  const v = route.view;
  const isOn = (key: string) => v === key || (key === "sources" && v === "room");
  const nav: [string, string, JSX.Element, string][] = [
    ["home", "Home", <HomeIcon size={14} />, "g h"], ["journeys", "Journeys", <Layers size={14} />, "g j"],
    ["sources", "Sources", <Film size={14} />, "g s"], ["cuts", "Cut bin", <Scissors size={14} />, "g c"], ["search", "Search", <SearchIcon size={14} />, "g f"],
    ["exports", "Exports", <Upload size={14} />, "g e"],
  ];
  const themeIcon = theme === "dark" ? <Moon size={14} /> : theme === "light" ? <Sun size={14} /> : <Monitor size={14} />;
  const cycleTheme = () => setTheme(theme === "system" ? "dark" : theme === "dark" ? "light" : "system");
  const docked = agentOpen && width >= 1440 && v !== "room";
  const navButton = (key: string, label: string, icon: JSX.Element, keys?: string, badge?: number) => (
    <button key={key} className={"navitem" + (isOn(key) ? " on" : "")} onClick={() => go(key)} data-view={key}
            data-tip={width <= 1180 ? label : undefined} data-tip-key={width <= 1180 ? keys : undefined} aria-label={label}>
      {icon}<span className="lbl">{label}</span>{!!badge && <span className="badge">{badge}</span>}
    </button>
  );
  const title = TITLES[v] || v;

  return (
    <AppCtx.Provider value={ctx}>
      <div className={"app" + (route.project ? "" : " bare")}>
        {route.project && (
          <nav className="nav" aria-label="Main">
            <a className="brand" href="#/" data-tip={width <= 1180 ? "All projects" : undefined}><span className="logo">R</span><span className="word">Recomposer</span></a>
            <button className="projbtn" onClick={() => (window.location.hash = "#/")} data-tip="Switch project">
              <ChevronsUpDown size={14} className="faint" />
              <span className="ptext ellipsis"><span className="plabel">Project</span><br /><span className="pname">{route.project}</span></span>
            </button>
            <div className="navgroup">Make</div>
            {nav.slice(0, 2).map(([k, l, i, kk]) => navButton(k, l, i, kk))}
            <div className="navgroup">Material</div>
            {nav.slice(2, 5).map(([k, l, i, kk]) => navButton(k, l, i, kk))}
            <div className="navgroup">Deliver</div>
            {nav.slice(5).map(([k, l, i, kk]) => navButton(k, l, i, kk))}
            <div className="navgroup">Research</div>
            {navButton("follows", "Follows", <Users size={14} />, undefined, inboxNew)}
            {navButton("topics", "Topics", <Lightbulb size={14} />)}
            <div className="navfoot">
              {navButton("jobs", "Jobs", <ListChecks size={14} />, "g b", running)}
              {navButton("activity", "Activity", <Activity size={14} />, "g a")}
              <button className="navitem" onClick={() => (window.location.hash = "#/hub")} data-tip={width <= 1180 ? "Community hub" : undefined}><Share2 size={14} /><span className="lbl">Community hub</span></button>
            </div>
          </nav>
        )}
        <div className="col">
          <header className="topbar">
            {!route.project && <a className="brand" href="#/" style={{ padding: 0 }}><span className="logo">R</span><span>Recomposer</span></a>}
            {route.project && width <= 700 && (
              <button className="btn ghost small" onClick={() => (window.location.hash = "#/")} data-tip="Switch project"><ChevronsUpDown size={14} />{route.project}</button>
            )}
            {route.project && width > 700 && <div className="crumbs"><b>{title}</b></div>}
            <div className="spacer" />
            {route.project && v !== "start" && (
              <button className="btn primary" onClick={newJourney} data-tip="Start a guided journey" data-tip-key="n">
                <Plus size={14} /><span className="hide-sm">New journey</span>
              </button>
            )}
            {!route.project && <>
              <button className={"btn ghost" + (v === "follows" ? " on" : "")} onClick={() => (window.location.hash = "#/follows")}><Users size={14} />Follows{!!inboxNew && <span className="badge">{inboxNew}</span>}</button>
              <button className={"btn ghost" + (v === "topics" ? " on" : "")} onClick={() => (window.location.hash = "#/topics")}><Lightbulb size={14} />Topics</button>
              {v !== "hub" && <button className="btn ghost" onClick={() => (window.location.hash = "#/hub")}><Share2 size={14} /><span className="hide-sm">Community hub</span></button>}
            </>}
            <button className="btn ghost icon" onClick={cycleTheme} data-tip={`Theme: ${theme} (click to change)`} aria-label="Theme">{themeIcon}</button>
            {route.project && width > 700 && <button className="btn ghost icon" onClick={() => setHelp(true)} data-tip="Keyboard shortcuts" data-tip-key="?" aria-label="Keyboard shortcuts"><Keyboard size={14} /></button>}
            {route.project && (
              <button className={"btn iconbtn" + (agentOpen ? " on" : "")} onClick={() => toggleAgent()} aria-expanded={agentOpen}
                      data-tip={agentOpen ? "Hide the agent panel" : asks ? `The agent asks ${asks} question(s)` : "Agent: notes, questions and live activity"} data-tip-key=".">
                <Bot size={14} /><span className="hide-sm">Agent</span>{!!asks && <span className="badge">{asks}</span>}
              </button>
            )}
          </header>
          <div className={"workspace" + (docked ? " docked" : "")}>
            <main className="main" id="main" key={route.project || ""}>{/* a project change remounts every view */}
              {!route.project && v === "start" && <Start />}
              {v === "hub" && <Hub />}
              {v === "follows" && <Follows key={route.project || ""} />}
              {v === "topics" && <Topics key={route.project || ""} />}
              {route.project && v === "home" && <Home />}
              {route.project && v === "sources" && <Sources />}
              {route.project && v === "cuts" && <Cuts />}
              {route.project && v === "room" && route.arg && <Room key={route.project + "/" + route.arg} sourceRef={route.arg} />}
              {route.project && v === "search" && <SearchView />}
              {route.project && v === "journeys" && <Journeys />}
              {route.project && v === "exports" && <Exports />}
              {route.project && v === "jobs" && <Jobs />}
              {route.project && v === "activity" && <ActivityView />}
            </main>
            {route.project && agentOpen && (
              <>
                {!docked && <div className="scrim" onClick={() => toggleAgent(false)} />}
                <aside className={"drawer" + (docked ? "" : " float")} aria-label="Agent">
                  <AgentPanel onClose={() => toggleAgent(false)} />
                </aside>
              </>
            )}
          </div>
          {route.project && (
            <nav className="bottomnav" aria-label="Main">
              {nav.slice(0, 4).map(([k, l, i]) => (
                <button key={k} className={isOn(k) ? "on" : ""} onClick={() => go(k)}>{i}{l}</button>
              ))}
              <MoreNav go={go} running={running} />
            </nav>
          )}
        </div>
        {route.project && route.params.get("new") === "1" && <NewJourney onClose={() => setParam("new", null)} />}
        {help && (
          <Dialog title="Keyboard shortcuts" sub="Every button runs a command. Hover to see it; the robot hands it to the agent instead." onClose={() => setHelp(false)}>
            <div className="keys">
              <table><tbody>
                {[["n", "New journey"], ["g h · g j · g s", "Home, Journeys, Sources"], ["g c · g f · g e", "Cut bin, Search, Exports"], ["g b · g a", "Jobs, Activity"],
                  [".", "Show or hide the agent panel"], ["/", "Focus the filter or find box"], ["Ctrl+Z, Ctrl+Shift+Z", "Undo, redo (yours; the agent cannot undo your work)"],
                  ["1 – 6", "Journey studio: go to a step"], ["Enter", "Journey studio: the status bar's next action"],
                  ["Space", "Play / pause (source room)"], ["I / O", "Mark in / out"], ["C", "Cut the selection"], ["← / →", "Seek 2 s (Shift: 10 s)"],
                  ["Ctrl+F · F3", "Find in the source's transcript, next match"], ["Ctrl+H", "Find and replace in the transcript"],
                  ["Shift-click", "Extend a selection (lines, cuts)"], ["Double-click a line", "Edit it"], ["?", "This help"]].map(([k, d]) => (
                  <tr key={k}><td style={{ width: 200 }}><span className="kbd">{k}</span></td><td>{d}</td></tr>
                ))}
              </tbody></table>
            </div>
          </Dialog>
        )}
      </div>
    </AppCtx.Provider>
  );
}

function MoreNav({ go, running }: { go: (v: string) => void; running: number }) {
  return (
    <span style={{ display: "grid", placeItems: "center", position: "relative" }}>
      <Menu label="More" align="end" trigger={<><MenuIcon size={14} /></>} items={[
        { label: "Search", icon: <SearchIcon size={14} />, onSelect: () => go("search") },
        { label: "Exports", icon: <Upload size={14} />, onSelect: () => go("exports") },
        { label: `Jobs${running ? ` (${running} running)` : ""}`, icon: <ListChecks size={14} />, onSelect: () => go("jobs") },
        { label: "Activity", icon: <Activity size={14} />, onSelect: () => go("activity") },
        "sep",
        { label: "Follows", icon: <Users size={14} />, onSelect: () => go("follows") },
        { label: "Topics", icon: <Lightbulb size={14} />, onSelect: () => go("topics") },
        { label: "Community hub", icon: <Share2 size={14} />, onSelect: () => (window.location.hash = "#/hub") },
        { label: "All projects", icon: <ChevronsUpDown size={14} />, onSelect: () => (window.location.hash = "#/") },
      ]} />
    </span>
  );
}

function useDataIn<T>(version: number, load: (() => Promise<T>) | null, deps: any[] = []): { data: T | null } {
  const [data, setData] = useState<T | null>(null);
  useEffect(() => {
    if (!load) { setData(null); return; }
    let live = true;
    load().then((d) => live && setData(d)).catch(() => {});
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [version, ...deps]);
  return { data };
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
