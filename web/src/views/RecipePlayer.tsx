import { useEffect, useRef, useState } from "react";
import { Pause, Play, SkipBack, SkipForward } from "lucide-react";
import { clock, fileUrl, mediaUrl } from "../api";
import YouTubePlayer, { type YTHandle } from "./YouTubePlayer";

// Plays a recipe straight from its sources, slot by slot, without rendering. Two players take turns: while one
// plays a slot, the other has the next slot loaded, seeked and paused; at the out point they swap, so the cut
// lands without a blank or a seek. Overlays and music are drawn approximately.
export default function RecipePlayer({ recipe, startSlot = 1, hasMedia = () => false, musicFiles = {} }: {
  recipe: any; startSlot?: number; hasMedia?: (sourceRef: string) => boolean; musicFiles?: Record<string, string>;
}) {
  const slots: any[] = recipe?.slots || [];
  const [i, setI] = useState(Math.max(0, Math.min(slots.length - 1, startSlot - 1)));
  const [act, setAct] = useState(0);                       // which of the two players is showing
  const [playing, setPlaying] = useState(false);
  const [local, setLocal] = useState(0);
  const videos = [useRef<HTMLVideoElement>(null), useRef<HTMLVideoElement>(null)];
  const yts = [useRef<YTHandle>(null), useRef<YTHandle>(null)];
  const held = useRef<(number | null)[]>([null, null]);    // the slot each player has loaded
  const advanced = useRef(false);                          // i changed by playing through, not by a jump
  const music = useRef<HTMLAudioElement>(null);
  const slot = slots[i];
  const isLinkSlot = (k: number) => { const s = slots[k]; const src = s && recipe.sources[s.source]; return !!src && src.kind === "link" && !hasMedia(s.source); };
  const isLink = !!slot && isLinkSlot(i);
  const anyLink = slots.some((_s, k) => isLinkSlot(k)), anyFile = slots.some((_s, k) => !isLinkSlot(k));
  const firstLink = slots.findIndex((_s, k) => isLinkSlot(k));
  const offsets = slots.reduce<number[]>((acc, _s, k) => { acc.push(k ? acc[k - 1] + (slots[k - 1].out - slots[k - 1].in) : 0); return acc; }, []);
  const outT = (offsets[i] || 0) + local;
  const total = slots.reduce((a, s) => a + (s.out - s.in), 0);

  // Load slot k into player b, at its in point; play it or hold it paused there.
  const prepare = (b: number, k: number, play: boolean) => {
    held.current[b] = k < slots.length ? k : null;
    if (k >= slots.length) return;
    const s = slots[k];
    if (isLinkSlot(k)) {
      const h = yts[b].current;
      if (play) h?.load(recipe.sources[s.source].id, s.in); else h?.cue(recipe.sources[s.source].id, s.in);
      return;
    }
    const v = videos[b].current;
    if (!v) return;
    const url = mediaUrl(s.source);
    const go = () => { v.currentTime = s.in; if (play) v.play().catch(() => {}); else v.pause(); };
    if (!v.src.includes(url)) { v.src = url; v.onloadedmetadata = go; v.load(); } else go();
  };
  const pauseAll = () => { for (const v of videos) v.current?.pause(); for (const y of yts) y.current?.pause(); };

  useEffect(() => { advanced.current = false; setI(Math.max(0, Math.min(slots.length - 1, startSlot - 1))); }, [startSlot, recipe?.hash]);

  // A jump (start, skip buttons, a new recipe): load it into the showing player and the next one into the other.
  useEffect(() => {
    if (!slot) return;
    if (advanced.current) { advanced.current = false; return; }
    pauseAll();
    prepare(act, i, playing);
    prepare(1 - act, i + 1, false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [i, recipe?.hash]);

  // Advance at each slot's out point: start the waiting player, then load the slot after next into the other.
  // An interval, not animation frames: those stop in a hidden tab while the video plays on past its out point.
  useEffect(() => {
    const tick = () => {
      if (slot) {
        const now = isLink ? yts[act].current?.time() ?? 0 : videos[act].current?.currentTime ?? 0;
        setLocal(Math.max(0, Math.min(slot.out - slot.in, now - slot.in)));
        if (playing && now >= slot.out - 0.04) {
          if (i + 1 < slots.length) {
            const nb = 1 - act;
            if (held.current[nb] !== i + 1) prepare(nb, i + 1, true);
            else if (isLinkSlot(i + 1)) yts[nb].current?.play();
            else videos[nb].current?.play().catch(() => {});
            if (isLink) yts[act].current?.pause(); else videos[act].current?.pause();
            const old = act;
            advanced.current = true;
            setAct(nb);
            setI(i + 1);
            prepare(old, i + 2, false);
          } else { setPlaying(false); pauseAll(); }
        }
      }
    };
    const iv = setInterval(tick, 20);
    return () => clearInterval(iv);
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
    if (isLink) { playing ? yts[act].current?.pause() : yts[act].current?.play(); }
    else { const v = videos[act].current; if (!v) return; playing ? v.pause() : v.play().catch(() => {}); }
    setPlaying(!playing);
  };
  const jump = (k: number) => { advanced.current = false; setI(Math.max(0, Math.min(slots.length - 1, k))); };

  const visible = Object.values(recipe?.overlays || {}).filter((o: any) =>
    o.slot ? o.slot === i + 1 && local >= o.at && local < o.at + (o.dur || 4) : outT >= o.at && outT < o.at + (o.dur || 4));

  if (!slots.length) return <div className="empty">No slots yet.</div>;
  const layer = (b: number, kind: "link" | "file") =>
    ({ position: "absolute" as const, inset: 0, opacity: b === act && (kind === "link") === isLink ? 1 : 0,
       pointerEvents: (b === act ? "auto" : "none") as "auto" | "none" });
  return (
    <div className="card" style={{ padding: 0, overflow: "hidden" }}>
      <div style={{ position: "relative", background: "#000", aspectRatio: "16 / 9" }}>
        {[0, 1].map((b) => (
          <div key={b}>
            {anyLink && <div style={layer(b, "link")}><YouTubePlayer ref={yts[b]} videoId={recipe.sources[slots[firstLink].source].id} start={slots[firstLink].in} /></div>}
            {anyFile && <video ref={videos[b]} preload="auto" style={{ ...layer(b, "file"), width: "100%", height: "100%", objectFit: "contain" }} onClick={toggle} />}
          </div>
        ))}
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
        <button className="btn small" onClick={() => jump(i - 1)}><SkipBack size={13} /></button>
        <button className="btn small" onClick={toggle}>{playing ? <Pause size={14} /> : <Play size={14} />}</button>
        <button className="btn small" onClick={() => jump(i + 1)}><SkipForward size={13} /></button>
        <span className="mono">{clock(outT)} / {clock(total)}</span>
        <span style={{ color: "var(--muted)" }}>slot {i + 1}/{slots.length} · {slot.source} {clock(slot.in + local)}</span>
        <div className="spacer" />
        <span style={{ fontSize: 11, color: "var(--faint)" }}>recipe player · next slot preloaded</span>
      </div>
    </div>
  );
}
