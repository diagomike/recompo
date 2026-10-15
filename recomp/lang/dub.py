"""Dubbing a render plan into another language.

Each translated caption line is voiced (TTS), fitted into its window (sped up to 1.25× at most;
anything still longer is reported as an overflow), and placed on a dub track the length of the body.
``voiceover`` mixes the dub over the original, which is ducked under it; ``replace`` mixes the dub over
the original's separated background (music and effects without the voices).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ..core import config
from ..envelope import RecompError
from ..media import ff
from . import tts

MAX_SPEEDUP = 1.25
MAX_DELAY = 1.0
MAX_RATE_PCT = 35


def _key(*parts) -> str:
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False).encode()).hexdigest()[:16]


def build_dub(project, plan: dict, voice: str | None = None, log=print, progress=None) -> dict:
    lang = plan["lang"]
    lines = [c for c in plan["captions"] if c["text"].strip()]
    if not lines:
        raise RecompError("E_INVALID", f"no {lang} lines to voice",
                          hint=f"Translate first: `recomp lang translate <journey> --to {lang}`")
    backend, v = tts.voice_for(lang, voice)
    clips_dir = project.dir("cache", "dub", "clips")
    work = project.dir("cache", "dub", _key(plan["hash"], lang, v))
    body = plan["body_dur"]
    slot_ends = sorted(it["at"] + it["dur"] for it in plan["items"])
    if backend == "mms":  # one model load for every line
        tts.synth_batch([(l["text"], clips_dir / f"{_key(backend, v, l['text'])}.wav") for l in lines], lang, voice=voice)
    placed, overflow, sped, kept = [], [], 0, []
    prev_end = 0.0
    for k, line in enumerate(lines):
        # Voice-over placement: a line may start a little late (up to MAX_DELAY) to follow the one before,
        # and must finish before its own cut ends and before the next line would be pushed too late.
        start = max(line["start"], prev_end + 0.08)
        slot_end = next((e for e in slot_ends if e > line["start"] + 0.01), body) - 0.05
        nxt = lines[k + 1]["start"] + MAX_DELAY if k + 1 < len(lines) else body
        hard_end = min(slot_end, nxt, body)
        window = max(0.3, hard_end - start)
        clip = clips_dir / f"{_key(backend, v, line['text'])}.wav"
        dur = ff.probe(clip).duration if clip.exists() else tts.synth(line["text"], lang, clip, voice=voice)
        use, factor = clip, 1.0
        if dur > window and backend == "edge":
            # Ask the voice itself to speak faster first: it sounds natural where time-stretching does not.
            rate = min(MAX_RATE_PCT, int((dur / window - 1) * 100) + 6)
            fast_clip = clips_dir / f"{_key(backend, v, line['text'], rate)}.wav"
            fdur = ff.probe(fast_clip).duration if fast_clip.exists() else \
                tts.synth(line["text"], lang, fast_clip, voice=voice, rate_pct=rate)
            if fdur < dur:
                clip, dur, use = fast_clip, fdur, fast_clip
        if dur > window:
            factor = min(MAX_SPEEDUP, dur / window)
            fast = clips_dir / f"{clip.stem}_x{factor:.3f}.wav"
            if not fast.exists():
                ff.run_simple(["-i", str(clip), "-af", f"atempo={factor:.4f}", "-c:a", "pcm_s16le", str(fast)], timeout=60)
            use = fast
            sped += 1
            dur = dur / factor
            if dur > window + 0.3 and len(line["text"].split()) <= 3:
                # A short interjection that cannot fit: leave it in the original voice (audible under a voice-over).
                kept.append({"at": round(line["start"], 2), "text": line["text"][:80], "key": line.get("seg")})
                continue
            if dur > window + 0.3:
                overflow.append({"at": round(line["start"], 2), "text": line["text"][:80], "over_s": round(dur - window, 2),
                                 "key": line.get("seg")})
        placed.append({"file": str(use), "at": start, "dur": round(dur, 3), "factor": round(factor, 3),
                       "delay": round(start - line["start"], 2)})
        prev_end = start + dur
        if progress:
            progress(k / len(lines) * 0.4, f"voiced {k + 1}/{len(lines)}")
    dub = work / "dub.wav"
    # Mix in batches so the filter graph stays small, then sum the batches.
    batches = [placed[i:i + 40] for i in range(0, len(placed), 40)]
    parts = []
    for b, batch in enumerate(batches):
        args, fl = [], []
        for i, p in enumerate(batch):
            args += ["-i", p["file"]]
            ms = int(p["at"] * 1000)
            fl.append(f"[{i}:a]aresample=48000,adelay={ms}[d{i}]")
        fl.append("".join(f"[d{i}]" for i in range(len(batch))) +
                  f"amix=inputs={len(batch)}:normalize=0:duration=longest,apad=whole_dur={body:.3f},atrim=0:{body:.3f}[m]")
        part = work / f"part{b}.wav"
        ff.run_simple([*args, "-filter_complex", ";".join(fl), "-map", "[m]", "-ac", "1", "-ar", "48000", str(part)], timeout=600)
        parts.append(part)
    if len(parts) == 1:
        parts[0].replace(dub)
    else:
        args = []
        for p in parts:
            args += ["-i", str(p)]
        ff.run_simple([*args, "-filter_complex", "".join(f"[{i}:a]" for i in range(len(parts))) +
                       f"amix=inputs={len(parts)}:normalize=0[m]", "-map", "[m]", "-ac", "1", "-ar", "48000", str(dub)], timeout=600)
    info = {"file": str(dub), "lang": lang, "backend": backend, "voice": v, "lines": len(placed), "sped_up": sped, "kept_original": kept,
            "overflow": overflow, "text": " ".join(l["text"] for l in lines)}
    (work / "dub.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    return info


def background(project, body: Path, log=print) -> Path:
    """Separated background of the assembled body (for ``replace`` dubs), cached next to it."""
    from ..workers.worker_env import run_script
    out = body.parent / "sep"
    bg = out / "background.flac"
    if bg.exists():
        return bg
    wav = body.parent / "body_audio.wav"
    ff.run_simple(["-i", str(body), "-vn", "-ac", "2", "-ar", "44100", str(wav)], timeout=600)
    models = Path(config.get("worker.hf_home") or "").parent / "audio-separator"
    run_script("separate", ["--input", str(wav), "--outdir", str(out), "--models", str(models)])
    return bg


def apply_to_plan(project, db, plan: dict, exp: dict, ctx) -> dict:
    """Called by the export job for a dubbed language: voice the lines and attach the dub to the plan."""
    from ..render.plan import plan_hash
    info = build_dub(project, plan, voice=(ctx.params or {}).get("voice"), log=ctx.log, progress=ctx.progress)
    plan["dub"] = {k: info[k] for k in ("file", "lang", "backend", "voice", "lines", "sped_up", "overflow", "kept_original")}
    plan["dub"]["mode"] = plan["profile"].get("dub_mode", "voiceover")
    plan["_dub_text"] = info["text"]
    plan["hash"] = plan_hash(plan)
    ctx.log(f"dub: {info['lines']} lines, {info['sped_up']} sped up, {len(info['overflow'])} overflow ({info['backend']} {info['voice']})")
    return plan
