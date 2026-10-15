import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Pause, Play, Scissors, BookmarkPlus, ZoomIn, ZoomOut, Maximize2, X } from "lucide-react";
import { clock, mediaUrl, peaksUrl, room, thumbUrl, verb } from "../api";
import { useApp } from "../App";
import YouTubePlayer, { type YTHandle } from "./YouTubePlayer";

type Seg = { idx: number; start: number; end: number; text: string; speaker: string | null; words: [number, number, string][] | null };
type Span = { ref: string; start: number; end: number; title: string; by: string; why?: string; summary?: string; tags?: string[] };
type RoomData = {
  source: any; transcript: any; segments: Seg[]; chapters: Span[]; cuts: Span[]; shots: number[];
  turns: any[]; thumbs: any; peaks: any;
};

const LANE = { ruler: 16, film: 40, wave: 44, shots: 8, speakers: 8, chapters: 20, cuts: 20 };
const H = Object.values(LANE).reduce((a, b) => a + b, 0) + 6;

export default function Room({ sourceRef }: { sourceRef: string }) {
  const { route, version } = useApp();
  const [data, setData] = useState<RoomData | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [t, setT] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [sel, setSel] = useState<{ a: number; b: number } | null>(null);
  const [view, setView] = useState<[number, number]>([0, 0]);
  const [peaks, setPeaks] = useState<Uint8Array | null>(null);
  const [form, setForm] = useState<null | "cut" | "chapter">(null);
  const [focusRef, setFocusRef] = useState<string | null>(route.params.get("focus"));
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

  // Keyboard: space play, I/O set in/out, C cut, Esc clear.
  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      if (e.key === " ") { e.preventDefault(); toggle(); }
      else if (e.key === "i" || e.key === "I") setSel((s) => ({ a: t, b: s && s.b > t ? s.b : Math.min(dur, t + 10) }));
      else if (e.key === "o" || e.key === "O") setSel((s) => ({ a: s && s.a < t ? s.a : Math.max(0, t - 10), b: t }));
      else if ((e.key === "c" || e.key === "C") && sel) setForm("cut");
      else if (e.key === "Escape") { setSel(null); setForm(null); }
      else if (e.key === "ArrowLeft") seek(Math.max(0, t - (e.shiftKey ? 10 : 2)));
      else if (e.key === "ArrowRight") seek(Math.min(dur, t + (e.shiftKey ? 10 : 2)));
    };
    window.addEventListener("keydown", on);
    return () => window.removeEventListener("keydown", on);
  });

  if (err) return <div className="page"><div className="err">{err}</div></div>;
  if (!data) return <div className="page">Loading…</div>;
  const src = data.source;

  return (
    <div className="room">
      <div className="left">
        <div className="player">
          {useYT ? <YouTubePlayer ref={yt} videoId={src.platform_id} />
            : src.has_media ? <video ref={video} src={mediaUrl(sourceRef)} preload="metadata" onClick={toggle} />
              : <div style={{ color: "#bbb", padding: 40 }}>No local media for this source yet.</div>}
        </div>
        <div className="ctrl">
          <button className="btn small" onClick={toggle}>{playing ? <Pause size={14} /> : <Play size={14} />}</button>
          <span className="mono">{clock(t)} / {clock(dur, 0)}</span>
          <b style={{ marginLeft: 8 }}>{src.ref} · {src.title}{src.year ? ` (${src.year})` : ""}</b>
          <div className="spacer" />
          {sel && <span className="chip" style={{ color: "var(--blue)" }}>{clock(sel.a)}–{clock(sel.b)} · {(sel.b - sel.a).toFixed(1)}s</span>}
          <button className="btn small" disabled={!sel} onClick={() => setForm("cut")} title="Cut the selection (C)"><Scissors size={13} />Cut</button>
          <button className="btn small" disabled={!sel} onClick={() => setForm("chapter")} title="Chapter from the selection"><BookmarkPlus size={13} />Chapter</button>
          <button className="btn small ghost" onClick={() => { const c = (view[0] + view[1]) / 2, w = (view[1] - view[0]) / 3; setView([Math.max(0, c - w), Math.min(dur, c + w)]); }}><ZoomIn size={14} /></button>
          <button className="btn small ghost" onClick={() => { const c = (view[0] + view[1]) / 2, w = (view[1] - view[0]) * 1.5; setView([Math.max(0, c - w), Math.min(dur, c + w)]); }}><ZoomOut size={14} /></button>
          <button className="btn small ghost" onClick={() => setView([0, dur])}><Maximize2 size={14} /></button>
        </div>
        <div>
          <Lanes data={data} peaks={peaks} t={t} view={view} setView={setView} sel={sel} setSel={setSel} seek={seek}
                 focusRef={focusRef} setFocusRef={setFocusRef} />
          {form && sel && <SpanForm kind={form} sourceRef={sourceRef} sel={sel} onDone={(ref) => { setForm(null); if (ref) setFocusRef(ref); }} />}
        </div>
        <div className="below">
          <Lists data={data} focusRef={focusRef} onPick={(s) => { setFocusRef(s.ref); setSel({ a: s.start, b: s.end }); zoomTo(s.start, s.end); seek(s.start); }} />
          <p style={{ color: "var(--faint)", fontSize: 11, marginTop: 8 }}>
            <span className="kbd">Space</span> play · <span className="kbd">I</span>/<span className="kbd">O</span> in/out · drag on the lanes to select ·
            <span className="kbd">C</span> cut · <span className="kbd">Shift</span>-click a line to extend · wheel zooms. Your selection is visible to the agent (<code>recomp ui selection</code>).
          </p>
        </div>
      </div>
      <Transcript data={data} t={t} sel={sel} seek={seek} setSel={setSel} />
    </div>
  );
}

function Lanes(p: {
  data: RoomData; peaks: Uint8Array | null; t: number; view: [number, number]; setView: (v: [number, number]) => void;
  sel: { a: number; b: number } | null; setSel: (s: { a: number; b: number } | null) => void; seek: (t: number) => void;
  focusRef: string | null; setFocusRef: (r: string | null) => void;
}) {
  const ref = useRef<HTMLCanvasElement>(null);
  const wrap = useRef<HTMLDivElement>(null);
  const [w, setW] = useState(800);
  const drag = useRef<{ x: number; t: number } | null>(null);
  const sprites = useRef<Record<string, HTMLImageElement>>({});
  const [, setLoaded] = useState(0);
  const { data, peaks, t, view, sel } = p;
  const dur = data.source.duration || 1;
  const [v0, v1] = view[1] > view[0] ? view : [0, dur];

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
    let y = 0;
    // ruler
    const span = v1 - v0;
    const step = [1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 900, 1800].find((s) => span / s < w / 70) || 3600;
    g.fillStyle = col("--faint"); g.font = "10px " + col("--mono"); g.strokeStyle = col("--line");
    for (let s = Math.ceil(v0 / step) * step; s <= v1; s += step) {
      const x = t2x(s); g.fillRect(x, y + 10, 1, 6); g.fillText(clock(s, 0), x + 3, y + 10);
    }
    y += LANE.ruler;
    // filmstrip
    const th = data.thumbs;
    if (th?.sheets?.length) {
      const first = sprites.current[th.sheets[0]];
      const tw = th.width, tH = first?.naturalHeight ? first.naturalHeight / th.rows : 22;
      const scale = LANE.film / tH, cellW = tw * scale;
      for (let x = 0; x < w; x += cellW) {
        const s = x2t(x + cellW / 2);
        const k = Math.max(0, Math.floor(s / th.every));
        const sheet = sprites.current[th.sheets[Math.floor(k / (th.cols * th.rows))]];
        const kk = k % (th.cols * th.rows);
        if (sheet?.complete && sheet.naturalWidth) g.drawImage(sheet, (kk % th.cols) * tw, Math.floor(kk / th.cols) * tH, tw, tH, x, y, cellW, LANE.film);
      }
    }
    y += LANE.film;
    // waveform
    if (peaks && data.peaks) {
      const ps = data.peaks.per_second;
      g.fillStyle = col("--wave");
      const mid = y + LANE.wave / 2;
      for (let x = 0; x < w; x++) {
        const a = Math.floor(x2t(x) * ps), b = Math.max(a + 1, Math.floor(x2t(x + 1) * ps));
        let m = 0;
        for (let k = a; k < b && k < peaks.length; k++) if (peaks[k] > m) m = peaks[k];
        const hgt = (m / 255) * (LANE.wave / 2 - 1);
        g.fillRect(x, mid - hgt, 1, hgt * 2 || 1);
      }
    }
    y += LANE.wave;
    // shots
    g.fillStyle = col("--faint");
    for (const s of data.shots) { if (s < v0 || s > v1) continue; g.fillRect(t2x(s), y + 1, 1, LANE.shots - 2); }
    y += LANE.shots;
    // speakers: one colour per voice label
    const palette = ["#2b62b8", "#c2410c", "#7c3aed", "#0f766e", "#b45309", "#be185d"];
    const labels: string[] = [];
    for (const tr of data.turns) {
      if (!labels.includes(tr.label)) labels.push(tr.label);
      if (tr.end < v0 || tr.start > v1) continue;
      g.fillStyle = palette[labels.indexOf(tr.label) % palette.length];
      g.fillRect(t2x(tr.start), y + 1, Math.max(1, t2x(tr.end) - t2x(tr.start)), LANE.speakers - 2);
    }
    y += LANE.speakers;
    const bars = (items: Span[], color: string, yy: number, h: number) => {
      for (const it of items) {
        if (it.end < v0 || it.start > v1) continue;
        const x = t2x(it.start), x2 = t2x(it.end);
        g.fillStyle = color; g.globalAlpha = it.ref === p.focusRef ? 0.95 : 0.55;
        g.fillRect(x, yy + 2, Math.max(2, x2 - x - 1), h - 4);
        g.globalAlpha = 1; g.fillStyle = "#fff"; g.font = "10px " + col("--sans");
        if (x2 - x > 30) { g.save(); g.beginPath(); g.rect(x, yy, x2 - x - 2, h); g.clip(); g.fillText(`${it.ref} ${it.title}`, x + 3, yy + h - 6); g.restore(); }
      }
    };
    bars(data.chapters, col("--violet"), y, LANE.chapters); y += LANE.chapters;
    bars(data.cuts, col("--accent"), y, LANE.cuts); y += LANE.cuts;
    if (sel) { g.fillStyle = col("--sel"); g.fillRect(t2x(sel.a), 0, t2x(sel.b) - t2x(sel.a), H); }
    g.fillStyle = col("--red"); g.fillRect(t2x(t), 0, 1.5, H);
  });

  const hit = (x: number, y: number): Span | null => {
    const s = x2t(x);
    const chapY = LANE.ruler + LANE.film + LANE.wave + LANE.shots + LANE.speakers;
    if (y >= chapY && y < chapY + LANE.chapters) return data.chapters.find((c) => c.start <= s && s < c.end) || null;
    if (y >= chapY + LANE.chapters && y < chapY + LANE.chapters + LANE.cuts) return data.cuts.find((c) => c.start <= s && s < c.end) || null;
    return null;
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
         onMouseDown={(e) => { const r = e.currentTarget.getBoundingClientRect(); drag.current = { x: e.clientX - r.left, t: x2t(e.clientX - r.left) }; }}
         onMouseMove={(e) => {
           if (!drag.current) return;
           const r = e.currentTarget.getBoundingClientRect(); const x = e.clientX - r.left;
           if (Math.abs(x - drag.current.x) > 4) { const a = drag.current.t, b = x2t(x); p.setSel({ a: Math.min(a, b), b: Math.max(a, b) }); }
         }}
         onMouseUp={(e) => {
           const r = e.currentTarget.getBoundingClientRect(); const x = e.clientX - r.left; const y = e.clientY - r.top;
           if (drag.current && Math.abs(x - drag.current.x) <= 4) {
             const h = hit(x, y);
             if (h) { p.setFocusRef(h.ref); p.setSel({ a: h.start, b: h.end }); p.seek(h.start); }
             else p.seek(x2t(x));
           }
           drag.current = null;
         }}
         onMouseLeave={() => (drag.current = null)}>
      <canvas ref={ref} style={{ height: H }} />
    </div>
  );
}

function Transcript({ data, t, sel, seek, setSel }: { data: RoomData; t: number; sel: { a: number; b: number } | null; seek: (t: number, play?: boolean) => void; setSel: (s: { a: number; b: number } | null) => void }) {
  const box = useRef<HTMLDivElement>(null);
  const userScroll = useRef(0);
  const anchor = useRef<number | null>(null);
  const cur = useMemo(() => {
    let lo = 0, hi = data.segments.length - 1, ans = -1;
    while (lo <= hi) { const m = (lo + hi) >> 1; if (data.segments[m].start <= t) { ans = m; lo = m + 1; } else hi = m - 1; }
    return ans;
  }, [t, data.segments]);
  useEffect(() => {
    if (Date.now() - userScroll.current < 4000 || cur < 0) return;
    const el = box.current?.querySelector(`[data-i="${cur}"]`) as HTMLElement | null;
    if (el && box.current) {
      const top = el.offsetTop - box.current.clientHeight / 3;
      if (Math.abs(box.current.scrollTop - top) > box.current.clientHeight / 3) box.current.scrollTop = top;
    }
  }, [cur]);
  const chapStarts = new Map<number, Span>();
  for (const c of data.chapters) {
    const i = data.segments.findIndex((s) => s.end > c.start);
    if (i >= 0 && !chapStarts.has(i)) chapStarts.set(i, c);
  }
  if (!data.transcript) return <div className="transcript"><div className="empty" style={{ margin: 12 }}>No transcript yet. Ask your agent: <code>recomp transcript asr {data.source.ref}</code></div></div>;
  return (
    <div className="transcript" ref={box} onWheel={() => (userScroll.current = Date.now())}>
      <div style={{ padding: "0 10px 6px", color: "var(--muted)", fontSize: 12 }}>
        {data.transcript.ref} · {data.transcript.origin} · {data.transcript.language}{data.transcript.has_words ? " · word timing" : ""} · {data.segments.length} lines
      </div>
      {data.segments.map((s, i) => {
        const c = chapStarts.get(i);
        const inSel = sel && s.end > sel.a && s.start < sel.b;
        return (
          <div key={s.idx}>
            {c && <div className="chaphead">{c.ref} {c.title}<span className="s">{clock(c.start, 0)}</span></div>}
            <div className={"seg" + (i === cur ? " now" : "") + (inSel ? " sel" : "")} data-i={i}
                 onClick={(e) => {
                   if (e.shiftKey && anchor.current != null) {
                     const a = Math.min(anchor.current, s.start), b = Math.max(data.segments.find((x) => x.start === anchor.current)?.end || s.end, s.end);
                     setSel({ a, b });
                   } else { anchor.current = s.start; setSel({ a: s.start, b: s.end }); seek(s.start); }
                 }}>
              <span className="t">#{s.idx} {clock(s.start, 0)}</span>
              <span>
                {s.speaker && <b style={{ color: "var(--blue)" }}>{s.speaker}: </b>}
                {i === cur && s.words ? s.words.map((w, k) => <span key={k} className={"w" + (t >= w[0] && t < w[1] ? " now" : "")}>{w[2]} </span>) : s.text}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function Lists({ data, focusRef, onPick }: { data: RoomData; focusRef: string | null; onPick: (s: Span) => void }) {
  const [tab, setTab] = useState<"cuts" | "chapters">(data.cuts.length ? "cuts" : "chapters");
  const items = tab === "cuts" ? data.cuts : data.chapters;
  return (
    <div className="cutlist">
      <div className="row" style={{ marginBottom: 4 }}>
        <button className={"tab" + (tab === "cuts" ? " on" : "")} onClick={() => setTab("cuts")}>Cuts ({data.cuts.length})</button>
        <button className={"tab" + (tab === "chapters" ? " on" : "")} onClick={() => setTab("chapters")}>Chapters ({data.chapters.length})</button>
      </div>
      {!items.length && <div style={{ color: "var(--muted)", fontSize: 12 }}>None yet.</div>}
      {items.map((s) => (
        <div key={s.ref} className="cutrow" style={s.ref === focusRef ? { background: "var(--accent-soft)" } : undefined}>
          <a className="mono" href="#" onClick={(e) => { e.preventDefault(); onPick(s); }}>{s.ref}</a>
          <div>
            <b>{s.title}</b> <span className={"chip " + s.by}>{s.by}</span>
            <div style={{ color: "var(--muted)" }}>{s.why || s.summary}</div>
            {!!s.tags?.length && <div className="row" style={{ gap: 3 }}>{s.tags.map((tg) => <span key={tg} className="chip">{tg}</span>)}</div>}
          </div>
          <span className="mono" style={{ color: "var(--faint)" }}>{clock(s.start, 0)} · {(s.end - s.start).toFixed(0)}s</span>
        </div>
      ))}
    </div>
  );
}

function SpanForm({ kind, sourceRef, sel, onDone }: { kind: "cut" | "chapter"; sourceRef: string; sel: { a: number; b: number }; onDone: (ref?: string) => void }) {
  const [title, setTitle] = useState("");
  const [why, setWhy] = useState("");
  const [tags, setTags] = useState("");
  const [snap, setSnap] = useState("words+shots");
  const [msg, setMsg] = useState<string | null>(null);
  const save = async () => {
    const env = kind === "cut"
      ? await verb("cut.add", { ref: sourceRef, from: String(sel.a), to: String(sel.b), title, why, tags: tags ? tags.split(",").map((x) => x.trim()) : [], snap })
      : await verb("chapter.add", { ref: sourceRef, start: String(sel.a), end: String(sel.b), title, summary: why, tags: tags ? tags.split(",").map((x) => x.trim()) : [] });
    if (!env.ok) setMsg(env.error!.message);
    else onDone(env.refs?.[0]);
  };
  return (
    <div className="card" style={{ margin: 8 }}>
      <div className="row" style={{ marginBottom: 6 }}>
        <b>{kind === "cut" ? "New cut" : "New chapter"}</b><span className="mono" style={{ color: "var(--muted)" }}>{clock(sel.a)}–{clock(sel.b)}</span>
        <div className="spacer" /><button className="btn ghost small" onClick={() => onDone()}><X size={14} /></button>
      </div>
      <div className="row">
        <input autoFocus className="input grow" placeholder="Title" value={title} onChange={(e) => setTitle(e.target.value)} />
        {kind === "cut" && (
          <select className="input" value={snap} onChange={(e) => setSnap(e.target.value)}>
            {["words+shots", "words", "shots", "none"].map((s) => <option key={s}>{s}</option>)}
          </select>
        )}
      </div>
      <div className="row" style={{ marginTop: 6 }}>
        <input className="input grow" placeholder={kind === "cut" ? "Why it matters" : "Summary"} value={why} onChange={(e) => setWhy(e.target.value)} onKeyDown={(e) => e.key === "Enter" && save()} />
        <input className="input" placeholder="tags, comma separated" value={tags} onChange={(e) => setTags(e.target.value)} />
        <button className="btn primary" onClick={save}>Save</button>
      </div>
      {msg && <div className="err">{msg}</div>}
    </div>
  );
}



