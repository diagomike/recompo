import { useEffect, useRef, useState } from "react";
import { Pause, Play, SkipBack, SkipForward } from "lucide-react";
import { clock, fileUrl, mediaUrl } from "../api";
import YouTubePlayer, { type YTHandle } from "./YouTubePlayer";

// Plays a recipe straight from its sources, slot by slot, without rendering. Seams are approximate
// (one element, the browser seeks between slots); overlays and music are drawn approximately too.
export default function RecipePlayer({ recipe, startSlot = 1, hasMedia = () => false, musicFiles = {} }: {
  recipe: any; startSlot?: number; hasMedia?: (sourceRef: string) => boolean; musicFiles?: Record<string, string>;
}) {
  const slots: any[] = recipe?.slots || [];
  const [i, setI] = useState(Math.max(0, Math.min(slots.length - 1, startSlot - 1)));
  const [playing, setPlaying] = useState(false);
  const [local, setLocal] = useState(0);
  const video = useRef<HTMLVideoElement>(null);
  const yt = useRef<YTHandle>(null);
  const music = useRef<HTMLAudioElement>(null);
  const slot = slots[i];
  const src = slot ? recipe.sources[slot.source] : null;
  const isLink = !!src && src.kind === "link" && !hasMedia(slot.source);
  const offsets = slots.reduce<number[]>((acc, _s, k) => { acc.push(k ? acc[k - 1] + (slots[k - 1].out - slots[k - 1].in) : 0); return acc; }, []);
  const outT = (offsets[i] || 0) + local;
  const total = slots.reduce((a, s) => a + (s.out - s.in), 0);

  useEffect(() => { setI(Math.max(0, Math.min(slots.length - 1, startSlot - 1))); }, [startSlot, recipe?.hash]);

  // Load the current slot.
  useEffect(() => {
    if (!slot) return;
    if (isLink) { yt.current?.load(src.id, slot.in); return; }
    const v = video.current;
    if (!v) return;
    const url = mediaUrl(slot.source);
    const go = () => { v.currentTime = slot.in; if (playing) v.play().catch(() => {}); };
    if (!v.src.includes(url)) { v.src = url; v.onloadedmetadata = go; } else go();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [i, recipe?.hash]);

  // Advance at each slot's out point.
  useEffect(() => {
    let raf = 0;
    const tick = () => {
      if (slot) {
        const now = isLink ? yt.current?.time() ?? 0 : video.current?.currentTime ?? 0;
        setLocal(Math.max(0, now - slot.in));
        if (playing && now >= slot.out - 0.04) {
          if (i + 1 < slots.length) setI(i + 1);
          else { setPlaying(false); video.current?.pause(); yt.current?.pause(); }
        }
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  });

  // Music bed: one track under everything, ducked while a slot plays (approximate: constant duck).
  const bed = recipe?.music?.[0];
  useEffect(() => {
    const a = music.current;
    if (!a || !bed) return;
    a.volume = Math.min(1, Math.pow(10, (bed.gain_db + bed.duck_db) / 20) * 1.8);
    if (playing) { a.currentTime = (bed.track_in || 0) + outT; a.play().catch(() => {}); } else a.pause();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing, bed?.track]);

  const toggle = () => {
    if (isLink) { playing ? yt.current?.pause() : yt.current?.play(); }
    else { const v = video.current; if (!v) return; playing ? v.pause() : v.play().catch(() => {}); }
    setPlaying(!playing);
  };

  const visible = Object.values(recipe?.overlays || {}).filter((o: any) =>
    o.slot ? o.slot === i + 1 && local >= o.at && local < o.at + (o.dur || 4) : outT >= o.at && outT < o.at + (o.dur || 4));

  if (!slots.length) return <div className="empty">No slots yet.</div>;
  return (
    <div className="card" style={{ padding: 0, overflow: "hidden" }}>
      <div style={{ position: "relative", background: "#000", aspectRatio: "16 / 9" }}>
        {isLink ? <YouTubePlayer ref={yt} videoId={src.id} start={slot.in} />
          : <video ref={video} style={{ width: "100%", height: "100%", objectFit: "contain" }} onClick={toggle} />}
        {visible.map((o: any, k) => (
          <div key={k} style={{
            position: "absolute", left: "6%", right: "6%",
            ...(o.kind === "title" || o.kind === "quote" || o.kind === "section" ? { top: "38%", textAlign: "center", fontSize: o.kind === "quote" ? 20 : 26 } : { bottom: "12%", fontSize: 15 }),
            color: "#fff", textShadow: "0 1px 3px #000, 0 0 12px #000", whiteSpace: "pre-line", fontWeight: o.kind === "title" ? 700 : 500,
            pointerEvents: "none",
          }}>{o.kind === "quote" ? `“${o.text}”` : o.text}</div>
        ))}
        {bed && musicFiles[bed.track] && <audio ref={music} src={fileUrl(musicFiles[bed.track])} />}
      </div>
      <div className="ctrl" style={{ borderBottom: 0 }}>
        <button className="btn small" onClick={() => setI(Math.max(0, i - 1))}><SkipBack size={13} /></button>
        <button className="btn small" onClick={toggle}>{playing ? <Pause size={14} /> : <Play size={14} />}</button>
        <button className="btn small" onClick={() => setI(Math.min(slots.length - 1, i + 1))}><SkipForward size={13} /></button>
        <span className="mono">{clock(outT)} / {clock(total)}</span>
        <span style={{ color: "var(--muted)" }}>slot {i + 1}/{slots.length} · {slot.source} {clock(slot.in + local)}</span>
        <div className="spacer" />
        <span style={{ fontSize: 11, color: "var(--faint)" }}>recipe player · approximate seams</span>
      </div>
    </div>
  );
}
