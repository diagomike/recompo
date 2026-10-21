import { forwardRef, useEffect, useImperativeHandle, useRef } from "react";

// Official YouTube IFrame player: link sources play without downloading anything.
export type YTHandle = {
  seek: (s: number, play?: boolean) => void;
  toggle: () => void;
  play: () => void;
  pause: () => void;
  time: () => number;
  playing: () => boolean;
  load: (id: string, start: number) => void;
  /** Load a video at a time without showing it play: muted until it buffers, then paused there (gapless swaps). */
  cue: (id: string, start: number) => void;
};

declare global {
  interface Window { YT?: any; onYouTubeIframeAPIReady?: () => void }
}

let apiPromise: Promise<any> | null = null;
function loadApi(): Promise<any> {
  if (window.YT?.Player) return Promise.resolve(window.YT);
  if (!apiPromise) {
    apiPromise = new Promise((resolve) => {
      const prev = window.onYouTubeIframeAPIReady;
      window.onYouTubeIframeAPIReady = () => { prev?.(); resolve(window.YT); };
      const s = document.createElement("script");
      s.src = "https://www.youtube.com/iframe_api";
      document.head.appendChild(s);
    });
  }
  return apiPromise;
}

const YouTubePlayer = forwardRef<YTHandle, { videoId: string; start?: number; autoplay?: boolean; onEnd?: () => void; height?: number }>(
  function YouTubePlayer({ videoId, start = 0, autoplay = false, onEnd, height = 360 }, ref) {
    const host = useRef<HTMLDivElement>(null);
    const player = useRef<any>(null);
    const ready = useRef(false);
    const pending = useRef<(() => void) | null>(null);  // a call made before the player was ready
    const pre = useRef<number | null>(null);            // cueing: pause at this time once it plays
    const whenReady = (f: () => void) => { if (ready.current) f(); else pending.current = f; };
    useEffect(() => {
      let live = true;
      loadApi().then((YT) => {
        if (!live || !host.current) return;
        player.current = new YT.Player(host.current, {
          videoId, height, width: "100%",
          playerVars: { start: Math.floor(start), autoplay: autoplay ? 1 : 0, rel: 0, modestbranding: 1, playsinline: 1 },
          events: {
            onReady: () => { ready.current = true; const f = pending.current; pending.current = null; f?.(); },
            onStateChange: (e: any) => {
              if (e.data === 1 && pre.current != null) {
                const p = player.current, t = pre.current;
                pre.current = null;
                p.pauseVideo(); p.seekTo(t, true); p.unMute();
                return;
              }
              if (e.data === 0) onEnd?.();
            },
          },
        });
      });
      return () => { live = false; try { player.current?.destroy(); } catch { /* ignore */ } };
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [videoId]);
    useImperativeHandle(ref, () => ({
      seek: (s, play) => { if (!ready.current) return; player.current.seekTo(s, true); if (play) player.current.playVideo(); },
      toggle: () => { if (!ready.current) return; player.current.getPlayerState() === 1 ? player.current.pauseVideo() : player.current.playVideo(); },
      play: () => whenReady(() => { if (pre.current != null) { pre.current = null; player.current.unMute(); } player.current.playVideo(); }),
      pause: () => ready.current && player.current.pauseVideo(),
      time: () => (ready.current ? player.current.getCurrentTime() || 0 : 0),
      playing: () => (ready.current ? player.current.getPlayerState() === 1 : false),
      load: (id, s) => whenReady(() => { pre.current = null; player.current.unMute(); player.current.loadVideoById({ videoId: id, startSeconds: s }); }),
      cue: (id, s) => whenReady(() => { pre.current = s; player.current.mute(); player.current.loadVideoById({ videoId: id, startSeconds: s }); }),
    }));
    return <div style={{ width: "100%", aspectRatio: "16 / 9" }}><div ref={host} /></div>;
  },
);
export default YouTubePlayer;
