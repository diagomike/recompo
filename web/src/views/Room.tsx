import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowLeft, BookmarkPlus, ExternalLink, Film, Focus, Keyboard, Layers, Maximize2, Pause, Pencil, Play, Scissors, Search as SearchIcon, Trash2, X, ZoomIn, ZoomOut } from "lucide-react";
import { clock, frameUrl, mediaUrl, peaksUrl, room, thumbUrl, verb } from "../api";
import { useApp } from "../App";
import { Act, useActions } from "../actions";
import { Dialog, Disclosure, Menu, SrcBadge } from "../ui";
import YouTubePlayer, { type YTHandle } from "./YouTubePlayer";
import TranscriptPane from "./TranscriptPane";

type Seg = { idx: number; start: number; end: number; text: string; speaker: string | null; words: [number, number, string][] | null };
type Span = { ref: string; start: number; end: number; title: string; by: string; why?: string; summary?: string; tags?: string[] };
type RoomData = {
  source: any; transcript: any; segments: Seg[]; chapters: Span[]; cuts: Span[]; shots: number[];
  turns: any[]; thumbs: any; peaks: any; voices?: Record<string, { name: string | null }>; people?: any[]; transcripts?: any[];
};

// Panel sizes the user dragged, remembered in this browser.
function useLayout(): [{ playerH: number; paneW: number }, (k: "playerH" | "paneW", v: number) => void] {
  const [lay, setLay] = useState(() => {
    try { return { playerH: 0, paneW: 0, ...JSON.parse(localStorage.getItem("recomp.room.layout") || "{}") }; } catch { return { playerH: 0, paneW: 0 }; }
  });
  const set = (k: "playerH" | "paneW", v: number) => setLay((cur: any) => {
    const next = { ...cur, [k]: Math.round(v) };
    try { localStorage.setItem("recomp.room.layout", JSON.stringify(next)); } catch { /* ignore */ }
    return next;
  });
  return [lay, set];
}

function Splitter({ dir, onDrag }: { dir: "col" | "row"; onDrag: (delta: number) => void }) {
  const start = (e: React.MouseEvent) => {
    e.preventDefault();
    let last = dir === "col" ? e.clientX : e.clientY;
    const move = (ev: MouseEvent) => { const cur = dir === "col" ? ev.clientX : ev.clientY; onDrag(cur - last); last = cur; };
    const up = () => { window.removeEventListener("mousemove", move); window.removeEventListener("mouseup", up); document.body.style.cursor = ""; };
    document.body.style.cursor = dir === "col" ? "col-resize" : "row-resize";
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
  };
  return <div className={"splitter " + dir} onMouseDown={start} title="Drag to resize" />;
}

export default function Room({ sourceRef }: { sourceRef: string }) {
  const { route, version, go } = useApp();
  const jref = route.params.get("j");  // gathering for a journey: new cuts go straight into it
  const [data, setData] = useState<RoomData | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [t, setT] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [sel, setSel] = useState<{ a: number; b: number } | null>(null);
  const [view, setView] = useState<[number, number]>([0, 0]);
  const [peaks, setPeaks] = useState<Uint8Array | null>(null);
  const [form, setForm] = useState<null | { kind: "cut" | "chapter"; edit?: Span }>(null);
  const { run } = useActions();
  const [focusRef, setFocusRef] = useState<string | null>(route.params.get("focus"));
  const [hits, setHits] = useState<number[]>([]);
  const [lay, setLay] = useLayout();
  const playerH = lay.playerH || Math.round(window.innerHeight * 0.42);
  const paneW = lay.paneW || 420;
  const video = useRef<HTMLVideoElement>(null);
  const yt = useRef<YTHandle>(null);
  const dur = data?.source?.duration || 0;

  useEffect(() => {
    room(sourceRef).then((d) => { setData(d); setErr(null); }).catch((e) => setErr(String(e.message || e)));
  }, [sourceRef, version]);
  useEffect(() => {
    fetch(peaksUrl(sourceRef)).then((r) => (r.ok ? r.arrayBuffer() : null)).then((b) => b && setPeaks(new Uint8Array(b))).catch(() => {});
  }, [sourceRef, data?.peaks?.bins]);
  useEffect(() => { if (dur && view[1] === 0) setView([0, dur]); }, [dur]);

  const useYT = data && !data.source.has_media && data.source.platform === "youtube";
  const seek = useCallback((s: number, play?: boolean) => {
    if (useYT) yt.current?.seek(s, play);
    else if (video.current) { video.current.currentTime = s; if (play) video.current.play(); }
    setT(s);
  }, [useYT]);
  const toggle = () => {
    if (useYT) { yt.current?.toggle(); return; }
    const v = video.current; if (!v) return; v.paused ? v.play() : v.pause();
  };

  // Initial focus from the URL (the agent's `ui show`, search hits).
  const lastNav = useRef("");
  useEffect(() => {
    if (!data) return;
    const key = route.params.toString();
    if (key === lastNav.current) return;
    lastNav.current = key;
    const ft = route.params.get("t");
    const fr = route.params.get("focus");
    setFocusRef(fr);
    const span = fr && (data.cuts.find((c) => c.ref === fr) || data.chapters.find((c) => c.ref === fr));
    if (span) { setSel({ a: span.start, b: span.end }); zoomTo(span.start, span.end); }
    const at = ft != null ? Number(ft) : span ? span.start : null;
    if (at != null) setTimeout(() => seek(at, route.params.get("play") === "1"), 50);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, route.params]);

  // Playhead.
  useEffect(() => {
    let raf = 0;
    const tick = () => {
      const v = video.current;
      if (v && !useYT) { setT(v.currentTime); setPlaying(!v.paused); }
      if (useYT && yt.current) { setT(yt.current.time()); setPlaying(yt.current.playing()); }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [useYT]);

  // Share the selection with the agent (`recomp ui selection`).
  useEffect(() => {
    const h = setTimeout(() => {
      verb("ui.select", { source: sourceRef, start: sel ? String(sel.a) : null, end: sel ? String(sel.b) : null,
        refs: focusRef ? [focusRef] : [], t: String(Math.round(t * 10) / 10) });
    }, 450);
    return () => clearTimeout(h);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sel?.a, sel?.b, focusRef, sourceRef]);

  const zoomTo = (a: number, b: number) => {
    const pad = Math.max(2, (b - a) * 0.4);
    setView([Math.max(0, a - pad), Math.min(dur || b + pad, b + pad)]);
  };

  const markIn = () => setSel((s) => ({ a: t, b: s && s.b > t ? s.b : Math.min(dur, t + 10) }));
  const markOut = () => setSel((s) => ({ a: s && s.a < t ? s.a : Math.max(0, t - 10), b: t }));

  // Keyboard: space play, I/O set in/out, C cut, Esc clear. Not while a dialog or menu is open.
  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      if (document.querySelector(".modal, .menu") || e.ctrlKey || e.metaKey || e.altKey) return;
      if (e.key === " ") { e.preventDefault(); toggle(); }
      else if (e.key === "i" || e.key === "I") markIn();
      else if (e.key === "o" || e.key === "O") markOut();
      else if ((e.key === "c" || e.key === "C") && sel) { e.preventDefault(); setForm({ kind: "cut" }); }  // the key must not land in the title field
      else if (e.key === "Escape") setSel(null);
      else if (e.key === "ArrowLeft") seek(Math.max(0, t - (e.shiftKey ? 10 : 2)));
      else if (e.key === "ArrowRight") seek(Math.min(dur, t + (e.shiftKey ? 10 : 2)));
    };
    window.addEventListener("keydown", on);
    return () => window.removeEventListener("keydown", on);
  });

  if (err) return <div className="page"><div className="err">{err}</div></div>;
  if (!data) return <div className="page">Loading…</div>;
  const src = data.source;
  const missing = [...(!data.peaks ? ["audio", "peaks"] : []), ...(!data.thumbs ? ["thumbs"] : [])];
  const zoomBy = (f: number) => { const c = (view[0] + view[1]) / 2, w = ((view[1] - view[0]) / 2) * f; setView([Math.max(0, c - w), Math.min(dur, c + w)]); };
  const pick = (s: Span) => { setFocusRef(s.ref); setSel({ a: s.start, b: s.end }); zoomTo(s.start, s.end); seek(s.start); };
  const findInSource = () => { const el = document.querySelector('[data-filter="tq"]') as HTMLInputElement | null; el?.focus(); el?.select(); };

  return (
    <div className="roomwrap" style={{ gridTemplateRows: (jref ? "auto " : "") + "auto minmax(0, 1fr)" }}>
    {jref && (
      <div className="roombanner">
        <Scissors size={15} />
        <span className="grow">Gathering for <b>{jref}</b>: select a range and press <span className="kbd">C</span>. Cuts you make here go straight into the journey.</span>
        <button className="btn small primary" onClick={() => go("journeys", jref, { step: "gather" })}><ArrowLeft size={14} />Back to {jref}</button>
      </div>
    )}
    <div className="roomhead">
      <SrcBadge ref_={src.ref} />
      <h1 className="h1 ellipsis">{src.title}{src.year ? ` (${src.year})` : ""}</h1>
      <span className="row tight nowrap hide-sm">
        <span className="chip">{clock(dur, 0).replace(/^00:/, "")}</span>
        {src.kind === "link" && <span className="chip" data-tip={src.has_media ? "A link; its media is fetched for frames and waveform" : "A link: it plays from the platform"}>link</span>}
        {data.transcript ? <span className="chip ok" data-tip="The transcript in use">{data.transcript.origin} · {data.transcript.language}</span> : <span className="chip warn">no transcript</span>}
      </span>
      <div className="spacer" />
      <Menu small label="Source actions" items={[
        { header: src.ref },
        ...(src.has_media && missing.length ? [{ label: "Build the filmstrip and waveform", icon: <Film size={14} />, desc: "Runs in the background; the lanes fill in",
            onSelect: () => run("source.process", { ref: sourceRef, jobs: missing }, { label: "Build lanes" }) }] : []),
        ...(String(src.uri || "").startsWith("http") ? [{ label: "Open the original", icon: <ExternalLink size={14} />, desc: src.platform || undefined, onSelect: () => window.open(src.uri, "_blank", "noreferrer") }] : []),
        { label: "Its cuts in the cut bin", icon: <Scissors size={14} />, onSelect: () => go("cuts", null, { source: sourceRef }) },
        { label: "Reset panel sizes", icon: <Maximize2 size={14} />, onSelect: () => { setLay("playerH", 0); setLay("paneW", 0); } },
        "sep",
        { label: "Keyboard shortcuts", icon: <Keyboard size={14} />, desc: "Space, I/O, C, ←/→, Ctrl+F", onSelect: () => window.dispatchEvent(new KeyboardEvent("keydown", { key: "?" })) },
      ]} />
    </div>
    <div className="room" style={window.innerWidth > 900 ? { gridTemplateColumns: `minmax(380px, 1fr) 6px ${paneW}px` } : undefined}>
      <div className="left">
        <div className="player" style={{ height: playerH }}>
          {useYT ? <YouTubePlayer ref={yt} videoId={src.platform_id} />
            : src.has_media ? <video ref={video} src={mediaUrl(sourceRef)} preload="metadata" onClick={toggle}
                                     poster={frameUrl(sourceRef, Math.min(60, (src.duration || 10) / 3), 640)} />
              : <div style={{ color: "#bbb", padding: 40 }}>No local media for this source yet.</div>}
        </div>
        <Splitter dir="row" onDrag={(d) => setLay("playerH", Math.max(120, Math.min(window.innerHeight * 0.75, playerH + d)))} />
        <div className="cmdrow" role="toolbar" aria-label="Source room commands">
          <div className="cmdgroup" role="group" aria-label="Play and select">
            <button className="btn small icon" onClick={toggle} aria-label={playing ? "Pause" : "Play"} data-tip={playing ? "Pause" : "Play"} data-tip-key="Space">
              {playing ? <Pause size={14} /> : <Play size={14} />}</button>
            <span className="tc" data-tip={`Playhead, of ${clock(dur, 0)}`}>{clock(t)}</span>
            <button className="btn small ghost" onClick={markIn} data-tip="Mark in at the playhead" data-tip-key="I">In</button>
            <button className="btn small ghost" onClick={markOut} data-tip="Mark out at the playhead" data-tip-key="O">Out</button>
            {sel ? (
              <span className="selchip" data-tip={`The selection, ${clock(sel.a).replace(/^00:/, "")}–${clock(sel.b).replace(/^00:/, "")}; the agent sees it too`} data-tip-cmd="recomp ui selection">
                <span className="selrange">{clock(sel.a).replace(/^00:/, "")}–{clock(sel.b).replace(/^00:/, "")} · </span>{(sel.b - sel.a).toFixed(1)}s
                <button className="btn ghost small icon" onClick={() => setSel(null)} aria-label="Clear the selection" data-tip="Clear the selection" data-tip-key="Esc"><X size={12} /></button>
              </span>
            ) : <span className="muted2 nowrap hide-sm" data-tip="Drag across the lanes, click a line, or use I and O">No selection</span>}
          </div>
          <div className="cmdgroup" role="group" aria-label="Cut and chapter">
            <button className={"btn small" + (sel ? " primary" : "")} disabled={!sel} onClick={() => setForm({ kind: "cut" })}
                    data-tip={jref ? `Cut the selection into ${jref}` : "Cut the selection"} data-tip-cmd={sel ? `recomp cut add ${sourceRef} --from ${sel.a.toFixed(2)} --to ${sel.b.toFixed(2)}` : undefined} data-tip-key="C">
              <Scissors size={13} />Cut</button>
            <button className="btn small" disabled={!sel} onClick={() => setForm({ kind: "chapter" })} data-tip="Make a chapter from the selection"
                    data-tip-cmd={sel ? `recomp chapter add ${sourceRef} --start ${sel.a.toFixed(2)} --end ${sel.b.toFixed(2)}` : undefined}><BookmarkPlus size={13} />Chapter</button>
          </div>
          <div className="cmdgroup" role="group" aria-label="Zoom">
            <button className="btn small ghost icon" onClick={() => zoomBy(2 / 3)} aria-label="Zoom in" data-tip="Zoom in" data-tip-key="wheel"><ZoomIn size={14} /></button>
            <button className="btn small ghost icon" onClick={() => zoomBy(1.5)} aria-label="Zoom out" data-tip="Zoom out" data-tip-key="wheel"><ZoomOut size={14} /></button>
            <button className="btn small ghost icon" onClick={() => sel && zoomTo(sel.a, sel.b)} disabled={!sel} aria-label="Zoom to the selection" data-tip="Zoom to the selection"><Focus size={14} /></button>
            <button className="btn small ghost icon" onClick={() => setView([0, dur])} aria-label="Whole source" data-tip="Show the whole source"><Maximize2 size={14} /></button>
          </div>
          <div className="cmdgroup" role="group" aria-label="Find">
            <button className="btn small ghost icon" onClick={findInSource} disabled={!data.transcript} aria-label="Find in this source" data-tip="Find in this source's transcript" data-tip-key="Ctrl+F"><SearchIcon size={14} /></button>
          </div>
        </div>
        <div>
          {src.has_media && missing.length > 0 && (
            <div className="lanehint">
              <span>{!data.thumbs && !data.peaks ? "No filmstrip or waveform yet" : !data.thumbs ? "No filmstrip yet" : "No waveform yet"} for this source.</span>
              <Act verb="source.process" args={{ ref: sourceRef, jobs: missing }}
                   small agent title="Runs in the background; the lanes fill in when it is done">Build them</Act>
            </div>
          )}
          <Lanes data={data} peaks={peaks} t={t} view={view} setView={setView} sel={sel} setSel={setSel} seek={seek}
                 focusRef={focusRef} setFocusRef={setFocusRef} hits={hits} />
        </div>
        <div className="below">
          <Lists data={data} focusRef={focusRef} jref={jref} onPick={pick} play={(s) => { pick(s); seek(s.start, true); }}
                 onEdit={(s, kind) => setForm({ kind, edit: s })} onCutFrom={(s) => { pick(s); setForm({ kind: "cut" }); }} />
        </div>
      </div>
      <Splitter dir="col" onDrag={(d) => setLay("paneW", Math.max(280, Math.min(window.innerWidth * 0.6, paneW - d)))} />
      <TranscriptPane data={data} t={t} sel={sel} seek={seek} setSel={setSel} panel={route.params.get("panel")}
                      query={route.params.get("tq")} onHits={setHits} />
    </div>
    {form && (form.edit || sel) && (
      <SpanDialog kind={form.kind} sourceRef={sourceRef} sel={form.edit ? { a: form.edit.start, b: form.edit.end } : sel!} jref={jref} edit={form.edit}
                  onDone={(ref) => { setForm(null); if (ref) setFocusRef(ref); }} />
    )}
    </div>
  );
}

type LaneDef = { key: string; h: number; label: string };

// Only the lanes a source has: link sources without fetched media get a speech lane (from the transcript)
// instead of empty frame and waveform strips. Chapters and cuts get room for their labels.
function laneDefs(data: RoomData, peaks: Uint8Array | null): LaneDef[] {
  const out: LaneDef[] = [{ key: "overview", h: 16, label: "whole source" }, { key: "ruler", h: 16, label: "" }];
  if (data.thumbs?.sheets?.length) out.push({ key: "film", h: 40, label: "frames" });
  if (peaks && data.peaks) out.push({ key: "wave", h: 40, label: "audio" });
  else if (data.segments.length) out.push({ key: "speech", h: 16, label: "speech" });
  if (data.shots.length) out.push({ key: "shots", h: 8, label: "shots" });
  if (data.turns.length) out.push({ key: "speakers", h: 12, label: "speakers" });
  out.push({ key: "chapters", h: 28, label: "chapters" }, { key: "cuts", h: 28, label: "cuts" });
  return out;
}

const PALETTE = ["#2b62b8", "#c2410c", "#7c3aed", "#0f766e", "#b45309", "#be185d"];

function Lanes(p: {
  data: RoomData; peaks: Uint8Array | null; t: number; view: [number, number]; setView: (v: [number, number]) => void;
  sel: { a: number; b: number } | null; setSel: (s: { a: number; b: number } | null) => void; seek: (t: number) => void;
  focusRef: string | null; setFocusRef: (r: string | null) => void; hits: number[];
}) {
  const ref = useRef<HTMLCanvasElement>(null);
  const wrap = useRef<HTMLDivElement>(null);
  const [w, setW] = useState(800);
  const drag = useRef<{ x: number; t: number; lane: string } | null>(null);
  const sprites = useRef<Record<string, HTMLImageElement>>({});
  const [, setLoaded] = useState(0);
  const [tip, setTip] = useState<{ x: number; y: number; text: string } | null>(null);
  const { data, peaks, t, view, sel } = p;
  const dur = data.source.duration || 1;
  const [v0, v1] = view[1] > view[0] ? view : [0, dur];
  const lanes = laneDefs(data, peaks);
  const H = lanes.reduce((a, l) => a + l.h, 0) + 4;
  const top: Record<string, number> = {};
  lanes.reduce((y, l) => { top[l.key] = y; return y + l.h; }, 0);
  const voiceName = (l: string) => data.voices?.[l]?.name || l;
  const speakerKeys: string[] = [];
  for (const tr of data.turns) { const k = voiceName(tr.label); if (!speakerKeys.includes(k)) speakerKeys.push(k); }

  useEffect(() => {
    const ro = new ResizeObserver(() => wrap.current && setW(wrap.current.clientWidth));
    if (wrap.current) ro.observe(wrap.current);
    return () => ro.disconnect();
  }, []);
  useEffect(() => {
    for (const name of data.thumbs?.sheets || []) {
      if (sprites.current[name]) continue;
      const img = new Image();
      img.onload = () => setLoaded((n) => n + 1);
      img.src = thumbUrl(data.source.ref, name);
      sprites.current[name] = img;
    }
  }, [data.thumbs, data.source.ref]);

  const x2t = (x: number) => v0 + (x / w) * (v1 - v0);
  const t2x = (s: number) => ((s - v0) / (v1 - v0)) * w;
  const o2x = (s: number) => (s / dur) * w;  // overview: the whole source

  useEffect(() => {
    const c = ref.current;
    if (!c) return;
    const dpr = window.devicePixelRatio || 1;
    c.width = w * dpr; c.height = H * dpr;
    const g = c.getContext("2d")!;
    g.scale(dpr, dpr);
    const css = getComputedStyle(document.documentElement);
    const col = (n: string) => css.getPropertyValue(n).trim();
    g.fillStyle = col("--panel"); g.fillRect(0, 0, w, H);
    const font = (px: number) => `${px}px ` + col("--sans");
    for (const l of lanes) {
      const y = top[l.key], h = l.h;
      if (l.key === "overview") {
        g.fillStyle = col("--panel-2"); g.fillRect(0, y, w, h);
        g.globalAlpha = 0.45; g.fillStyle = col("--violet");
        for (const c of data.chapters) g.fillRect(o2x(c.start), y + 3, Math.max(1, o2x(c.end) - o2x(c.start) - 1), h - 6);
        g.globalAlpha = 1; g.fillStyle = col("--accent");
        for (const c of data.cuts) g.fillRect(o2x(c.start), y + 1, Math.max(2, o2x(c.end) - o2x(c.start)), h - 2);
        g.fillStyle = col("--amber");
        for (const hh of p.hits) g.fillRect(o2x(hh), y, 1, h);
        g.strokeStyle = col("--blue"); g.lineWidth = 1.5;
        g.strokeRect(o2x(v0) + 0.5, y + 0.5, Math.max(3, o2x(v1) - o2x(v0)) - 1, h - 1);
        g.fillStyle = col("--red"); g.fillRect(o2x(t), y, 1.5, h);
      } else if (l.key === "ruler") {
        const span = v1 - v0;
        const step = [1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 900, 1800].find((s) => span / s < w / 70) || 3600;
        g.fillStyle = col("--faint"); g.font = "10px " + col("--mono");
        for (let s = Math.ceil(v0 / step) * step; s <= v1; s += step) { const x = t2x(s); g.fillRect(x, y + 10, 1, 6); g.fillText(clock(s, 0), x + 3, y + 10); }
      } else if (l.key === "film") {
        const th = data.thumbs;
        const first = sprites.current[th.sheets[0]];
        const tw = th.width, tH = first?.naturalHeight ? first.naturalHeight / th.rows : 22;
        const cellW = tw * (h / tH);
        for (let x = 0; x < w; x += cellW) {
          const k = Math.max(0, Math.floor(x2t(x + cellW / 2) / th.every));
          const sheet = sprites.current[th.sheets[Math.floor(k / (th.cols * th.rows))]];
          const kk = k % (th.cols * th.rows);
          if (sheet?.complete && sheet.naturalWidth) g.drawImage(sheet, (kk % th.cols) * tw, Math.floor(kk / th.cols) * tH, tw, tH, x, y, cellW, h);
        }
      } else if (l.key === "wave") {
        const ps = data.peaks.per_second;
        g.fillStyle = col("--wave");
        const mid = y + h / 2;
        for (let x = 0; x < w; x++) {
          const a = Math.floor(x2t(x) * ps), b = Math.max(a + 1, Math.floor(x2t(x + 1) * ps));
          let m = 0;
          for (let k = a; k < b && k < peaks!.length; k++) if (peaks![k] > m) m = peaks![k];
          const hh = (m / 255) * (h / 2 - 1);
          g.fillRect(x, mid - hh, 1, hh * 2 || 1);
        }
      } else if (l.key === "speech") {
        for (const s of data.segments) {
          if (s.end < v0 || s.start > v1) continue;
          g.fillStyle = s.speaker ? PALETTE[Math.max(0, speakerKeys.indexOf(voiceName(s.speaker))) % PALETTE.length] : col("--wave");
          g.fillRect(t2x(s.start), y + 3, Math.max(1, t2x(s.end) - t2x(s.start) - 0.5), h - 6);
        }
      } else if (l.key === "shots") {
        g.fillStyle = col("--faint");
        for (const s of data.shots) { if (s < v0 || s > v1) continue; g.fillRect(t2x(s), y + 1, 1, h - 2); }
      } else if (l.key === "speakers") {
        for (const tr of data.turns) {
          if (tr.end < v0 || tr.start > v1) continue;
          g.fillStyle = PALETTE[speakerKeys.indexOf(voiceName(tr.label)) % PALETTE.length];
          g.fillRect(t2x(tr.start), y + 2, Math.max(1, t2x(tr.end) - t2x(tr.start)), h - 4);
        }
      } else if (l.key === "chapters" || l.key === "cuts") {
        const items = l.key === "chapters" ? data.chapters : data.cuts;
        const color = l.key === "chapters" ? col("--violet") : col("--accent");
        for (const it of items) {
          if (it.end < v0 || it.start > v1) continue;
          const x = t2x(it.start), x2 = t2x(it.end), bw = Math.max(4, x2 - x - 1);
          g.fillStyle = color; g.globalAlpha = it.ref === p.focusRef ? 1 : 0.6;
          g.fillRect(x, y + 3, bw, h - 6);
          g.globalAlpha = 1;
          if (bw > 26) {
            g.save(); g.beginPath(); g.rect(x, y, bw - 2, h); g.clip();
            g.fillStyle = "#fff"; g.font = font(11); g.fillText(`${it.ref.replace(/^S\d+\./, "")} ${it.title}`, x + 4, y + h / 2 + 4);
            g.restore();
          }
        }
      }
      if (l.label && l.key !== "overview") {  // lane name, faint, at the right edge
        g.fillStyle = col("--faint"); g.globalAlpha = 0.7; g.font = font(9);
        const tw2 = g.measureText(l.label).width;
        g.fillText(l.label, w - tw2 - 4, y + 10); g.globalAlpha = 1;
      }
    }
    const bodyTop = top["ruler"];
    if (sel) { g.fillStyle = col("--sel"); g.fillRect(t2x(sel.a), bodyTop, t2x(sel.b) - t2x(sel.a), H - bodyTop); }
    g.fillStyle = col("--amber");
    const dense = p.hits.filter((hh) => hh >= v0 && hh <= v1).length > 30;  // many hits: marks on the ruler, faint lines below
    for (const hh of p.hits) {
      if (hh < v0 || hh > v1) continue;
      const x = t2x(hh);
      g.globalAlpha = 1; g.fillRect(x - 1, bodyTop, dense ? 2 : 3, 16);
      g.globalAlpha = dense ? 0.22 : 0.8; g.fillRect(x, bodyTop + 16, 1, H - bodyTop - 16);
    }
    g.globalAlpha = 1;
    g.fillStyle = col("--red"); g.fillRect(t2x(t), bodyTop, 1.5, H - bodyTop);
  });

  const laneAt = (y: number) => lanes.find((l) => y >= top[l.key] && y < top[l.key] + l.h)?.key || null;
  const hit = (x: number, y: number): Span | null => {
    const s = x2t(x), lane = laneAt(y);
    const near = (items: Span[]) => items.find((c) => c.start <= s && s < c.end) ||
      items.find((c) => Math.abs(t2x(c.start) - x) < 4) || null;  // thin bars are easy to hit
    if (lane === "chapters") return near(data.chapters);
    if (lane === "cuts") return near(data.cuts);
    return null;
  };
  const describe = (x: number, y: number): string | null => {
    const lane = laneAt(y);
    if (lane === "overview") return `${clock((x / w) * dur, 0)} · click or drag to move the view`;
    const h = hit(x, y);
    if (h) return `${h.ref} ${h.title || ""} · ${clock(h.start, 0)}–${clock(h.end, 0)} (${Math.round(h.end - h.start)}s)${h.why ? " — " + h.why : ""}`;
    const s = x2t(x);
    if (lane === "speakers") { const tr = data.turns.find((r) => r.start <= s && s < r.end); return tr ? `${voiceName(tr.label)} · ${clock(s, 0)}` : null; }
    if (lane === "speech") { const sg = data.segments.find((r) => r.start <= s && s < r.end); return sg ? `${clock(sg.start, 0)} ${sg.speaker ? voiceName(sg.speaker) + ": " : ""}${sg.text.slice(0, 90)}` : null; }
    return clock(s, 1);
  };
  const recenter = (x: number) => {
    const span = v1 - v0, c = (x / w) * dur;
    const a = Math.max(0, Math.min(dur - span, c - span / 2));
    p.setView([a, a + span]);
  };

  return (
    <div className="lanes" ref={wrap}
         onWheel={(e) => {
           const rect = (e.currentTarget as HTMLDivElement).getBoundingClientRect();
           const at = x2t(e.clientX - rect.left);
           if (e.shiftKey) { const d = (v1 - v0) * 0.15 * Math.sign(e.deltaY); p.setView([Math.max(0, v0 + d), Math.min(dur, v1 + d)]); return; }
           const f = e.deltaY > 0 ? 1.25 : 0.8;
           p.setView([Math.max(0, at - (at - v0) * f), Math.min(dur, at + (v1 - at) * f)]);
         }}
         onMouseDown={(e) => {
           const r = e.currentTarget.getBoundingClientRect(); const x = e.clientX - r.left, y = e.clientY - r.top;
           const lane = laneAt(y) || "";
           drag.current = { x, t: x2t(x), lane };
           if (lane === "overview") recenter(x);
         }}
         onMouseMove={(e) => {
           const r = e.currentTarget.getBoundingClientRect(); const x = e.clientX - r.left, y = e.clientY - r.top;
           const d = describe(x, y);
           setTip(d ? { x, y, text: d } : null);
           if (!drag.current) return;
           if (drag.current.lane === "overview") { recenter(x); return; }
           if (Math.abs(x - drag.current.x) > 4) { const a = drag.current.t, b = x2t(x); p.setSel({ a: Math.min(a, b), b: Math.max(a, b) }); }
         }}
         onMouseUp={(e) => {
           const r = e.currentTarget.getBoundingClientRect(); const x = e.clientX - r.left; const y = e.clientY - r.top;
           if (drag.current && drag.current.lane !== "overview" && Math.abs(x - drag.current.x) <= 4) {
             const h = hit(x, y);
             if (h) { p.setFocusRef(h.ref); p.setSel({ a: h.start, b: h.end }); p.seek(h.start); }
             else p.seek(x2t(x));
           }
           drag.current = null;
         }}
         onMouseLeave={() => { drag.current = null; setTip(null); }}>
      <canvas ref={ref} style={{ height: H }} />
      {tip && <div className="lanetip" style={{ left: Math.min(tip.x + 12, w - 260), top: tip.y + 14 }}>{tip.text}</div>}
    </div>
  );
}

// Cuts and chapters of this source as a flat list: click a row to select its range; the rest is in its ⋯ menu.
function Lists({ data, focusRef, jref, onPick, play, onEdit, onCutFrom }: {
  data: RoomData; focusRef: string | null; jref: string | null; onPick: (s: Span) => void; play: (s: Span) => void;
  onEdit: (s: Span, kind: "cut" | "chapter") => void; onCutFrom: (s: Span) => void;
}) {
  const [tab, setTab] = useState<"cuts" | "chapters">(data.cuts.length || !data.chapters.length ? "cuts" : "chapters");
  const [del, setDel] = useState<Span | null>(null);
  const { run } = useActions();
  const { go } = useApp();
  const items = tab === "cuts" ? data.cuts : data.chapters;
  const kind = tab === "cuts" ? "cut" : "chapter";
  return (
    <div>
      <div className="row nowrap cutlistbar" style={{ marginBottom: 4 }}>
        <div className="segmented" role="tablist" aria-label="Cuts or chapters" style={{ flexWrap: "nowrap", flex: "none" }}>
          <button role="tab" aria-selected={tab === "cuts"} className={tab === "cuts" ? "on" : ""} onClick={() => setTab("cuts")}><Scissors size={13} />Cuts {data.cuts.length}</button>
          <button role="tab" aria-selected={tab === "chapters"} className={tab === "chapters" ? "on" : ""} onClick={() => setTab("chapters")}><BookmarkPlus size={13} />Chapters {data.chapters.length}</button>
        </div>
        <span className="muted2 ellipsis hide-sm">Click a row to select it · ⋯ for more</span>
      </div>
      {!items.length && <div className="muted2" style={{ padding: "6px 2px" }}>{tab === "cuts" ? "No cuts yet: select a range and press C." : "No chapters yet: select a range and choose Chapter."}</div>}
      {!!items.length && (
        <div className="spanlist">
          {items.map((s) => (
            <div key={s.ref} className={"spanrow" + (s.ref === focusRef ? " on" : "")} onClick={() => onPick(s)}>
              <span className="mono faint">{s.ref.replace(/^S\d+\./, "")}</span>
              <div style={{ minWidth: 0 }}>
                <div className="row nowrap tight"><b className="ellipsis">{s.title || "(untitled)"}</b><span className={"chip " + s.by}>{s.by}</span>
                  {(s.tags || []).slice(0, 3).map((tg) => <span key={tg} className="chip hide-sm">{tg}</span>)}</div>
                {(s.why || s.summary) && <div className="sw ellipsis">{s.why || s.summary}</div>}
              </div>
              <span className="mono faint nowrap">{clock(s.start, 0).replace(/^00:/, "")} · {(s.end - s.start).toFixed(0)}s</span>
              <span onClick={(e) => e.stopPropagation()}>
                <Menu small label={`More for ${s.ref}`} items={[
                  { label: "Play from here", icon: <Play size={14} />, onSelect: () => play(s) },
                  { label: "Edit title and notes…", icon: <Pencil size={14} />, onSelect: () => onEdit(s, kind) },
                  ...(kind === "cut" && jref ? [{ label: `Add to ${jref}`, icon: <Layers size={14} />, onSelect: () => run("journey.add", { journey: jref, cuts: [s.ref] }, { label: `Add ${s.ref} to ${jref}` }) }] : []),
                  ...(kind === "cut" ? [{ label: "Show in the cut bin", icon: <Scissors size={14} />, onSelect: () => go("cuts", null, { q: s.title || s.ref }) }]
                    : [{ label: "Cut this chapter…", icon: <Scissors size={14} />, desc: "A cut with the chapter's range", onSelect: () => onCutFrom(s) }]),
                  "sep",
                  { label: `Delete ${s.ref}…`, icon: <Trash2 size={14} />, danger: true, desc: kind === "cut" ? "Refused while a journey uses it" : "Undo brings it back", onSelect: () => setDel(s) },
                ]} />
              </span>
            </div>
          ))}
        </div>
      )}
      {del && (
        <Dialog title={`Delete ${del.ref} “${del.title || "untitled"}”?`} sub={kind === "cut" ? "A cut a journey uses cannot be deleted; remove it from the journey first. Undo (Ctrl+Z) brings it back." : "Undo (Ctrl+Z) brings it back."}
                onClose={() => setDel(null)}
                footer={<><div className="spacer" /><button className="btn" onClick={() => setDel(null)}>Keep it</button>
                  <Act verb={kind === "cut" ? "cut.remove" : "chapter.remove"} args={{ ref: del.ref }} label={`Delete ${del.ref}`} className="danger" onDone={() => setDel(null)}>Delete</Act></>}>
          <p className="muted2" style={{ margin: 0 }}>{clock(del.start, 0)}–{clock(del.end, 0)} · {(del.end - del.start).toFixed(0)}s</p>
        </Dialog>
      )}
    </div>
  );
}

// New cut, new chapter, or editing one: a dialog, so the lanes and the lists stay where they were.
function SpanDialog({ kind, sourceRef, sel, onDone, jref, edit }: {
  kind: "cut" | "chapter"; sourceRef: string; sel: { a: number; b: number }; onDone: (ref?: string) => void; jref: string | null; edit?: Span;
}) {
  const [title, setTitle] = useState(edit?.title || "");
  const [why, setWhy] = useState((kind === "cut" ? edit?.why : edit?.summary) || "");
  const [tags, setTags] = useState((edit?.tags || []).join(", "));
  const [snap, setSnap] = useState("words+shots");
  const [intoJ, setIntoJ] = useState(true);
  const { run } = useActions();
  const tagList = tags ? tags.split(",").map((x) => x.trim()).filter(Boolean) : [];
  const into = kind === "cut" && !edit && !!jref && intoJ;
  const save = async () => {
    const env = edit
      ? await run(kind === "cut" ? "cut.edit" : "chapter.edit", { ref: edit.ref, title, ...(kind === "cut" ? { why } : { summary: why }), tags: tagList }, { label: `Edit ${edit.ref}` })
      : kind === "cut"
        ? await run("cut.add", { ref: sourceRef, from: String(sel.a), to: String(sel.b), title, why, tags: tagList, snap, ...(into ? { journey: jref } : {}) },
                    { label: into ? `New cut into ${jref}` : "New cut" })
        : await run("chapter.add", { ref: sourceRef, start: String(sel.a), end: String(sel.b), title, summary: why, tags: tagList }, { label: "New chapter" });
    if (env.ok) onDone(edit ? edit.ref : env.refs?.[0]);
  };
  const cmd = edit ? `recomp ${kind} edit ${edit.ref}` : kind === "cut" ? `recomp cut add ${sourceRef} --from ${sel.a.toFixed(2)} --to ${sel.b.toFixed(2)}${into ? ` --journey ${jref}` : ""}`
    : `recomp chapter add ${sourceRef} --start ${sel.a.toFixed(2)} --end ${sel.b.toFixed(2)}`;
  return (
    <Dialog title={edit ? `Edit ${edit.ref}` : kind === "cut" ? (into ? `New cut into ${jref}` : "New cut") : "New chapter"}
            sub={<span className="mono">{clock(sel.a)}–{clock(sel.b)} · {(sel.b - sel.a).toFixed(1)}s</span>} onClose={() => onDone()}
            icon={kind === "cut" ? <Scissors size={16} /> : <BookmarkPlus size={16} />}
            footer={<>
              {kind === "cut" && !edit && jref && <label className="check muted2"><input type="checkbox" checked={intoJ} onChange={(e) => setIntoJ(e.target.checked)} />Add to {jref}</label>}
              <div className="spacer" />
              <button className="btn" onClick={() => onDone()}>Cancel</button>
              <button className="btn primary" onClick={save} data-tip="Saves it (Enter)" data-tip-cmd={cmd}>{edit ? "Save" : kind === "cut" ? "Save cut" : "Save chapter"}</button>
            </>}>
      <form className="stack" onSubmit={(e) => { e.preventDefault(); save(); }}>
        <div className="field"><label htmlFor="sp-title">Title</label>
          <input id="sp-title" className="input" value={title} onChange={(e) => setTitle(e.target.value)} placeholder={kind === "cut" ? "What happens, in a few words" : "Chapter title"} /></div>
        <div className="field"><label htmlFor="sp-why">{kind === "cut" ? "Why it matters" : "Summary"}</label>
          <input id="sp-why" className="input" value={why} onChange={(e) => setWhy(e.target.value)} placeholder={kind === "cut" ? "Helps you (and the agent) find and order it later" : "Optional"} /></div>
        <Disclosure id={"room.span.more." + kind} label={kind === "cut" && !edit ? "Tags and edge snapping" : "Tags"} count={tagList.length || undefined}>
          <div className="stack sm">
            <div className="field"><label htmlFor="sp-tags">Tags</label>
              <input id="sp-tags" className="input" value={tags} onChange={(e) => setTags(e.target.value)} placeholder="comma separated, e.g. fear, turning point" /></div>
            {kind === "cut" && !edit && (
              <div className="field"><label htmlFor="sp-snap">Snap the edges to</label>
                <select id="sp-snap" className="input" value={snap} onChange={(e) => setSnap(e.target.value)} style={{ maxWidth: 260 }}>
                  <option value="words+shots">word ends and shot changes</option><option value="words">word ends</option><option value="shots">shot changes</option><option value="none">nothing (exact)</option>
                </select>
                <span className="help">Snapping keeps cuts from clipping a word or landing a frame before a shot change.</span></div>
            )}
          </div>
        </Disclosure>
        <button type="submit" hidden />
      </form>
    </Dialog>
  );
}
