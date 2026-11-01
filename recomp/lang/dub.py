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
    lines = []
    for c in plan["captions"]:
        if not c["text"].strip():
            continue
        if c.get("parts"):  # the LLM dubber's phrases: voiced one per speech frame, at the speaker's own pauses
            lines += [{"start": p["start"], "text": p["text"], "seg": c.get("seg")} for p in c["parts"] if p["text"].strip()]
        else:
            lines.append(c)
    if not lines:
        raise RecompError("E_INVALID", f"no {lang} lines to voice",
                          hint=f"Translate first: `recomp lang translate <journey> --to {lang}`")
    backend, v = ("clone", "omnivoice") if voice == "clone" else tts.voice_for(lang, voice)
    clips_dir = project.dir("cache", "dub", "clips")
    work = project.dir("cache", "dub", _key(plan["hash"], lang, v))
    body = plan["body_dur"]
    slot_ends = sorted(it["at"] + it["dur"] for it in plan["items"])
    if backend == "mms":  # one model load for every line
        tts.synth_batch([(l["text"], clips_dir / f"{_key(backend, v, l['text'])}.wav") for l in lines], lang, voice=voice)
    cloned = clone_lines(project, plan, lines, slot_ends, body, clips_dir, log) if backend == "clone" else {}
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
        if backend == "clone" and k not in cloned:  # no reference for this line: the language's own voice
            fb_backend, fb_v = tts.voice_for(lang)
            clip = clips_dir / f"{_key(fb_backend, fb_v, line['text'])}.wav"
            dur = ff.probe(clip).duration if clip.exists() else tts.synth(line["text"], lang, clip)
        else:
            clip = cloned[k] if backend == "clone" else clips_dir / f"{_key(backend, v, line['text'])}.wav"
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
    if backend == "clone":
        v = f"omnivoice (cloned {len(cloned)}/{len(lines)} lines)"
    info = {"file": str(dub), "lang": lang, "backend": backend, "voice": v, "lines": len(placed), "sped_up": sped, "kept_original": kept,
            "overflow": overflow, "text": " ".join(l["text"] for l in lines)}
    (work / "dub.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    return info


def _reference(db, seg_id, work: Path, paths: dict[str, str]) -> tuple[Path, str] | None:
    """The original speaker's audio for a dubbed line: its own segment, widened with neighbouring lines of the same
    speaker to 4–10 s, and their original text (a cloning prompt). None without a segment or a local file."""
    seg = db.one('SELECT s.idx, s.start, s."end", s.text, s.speaker, s.transcript_id, src.ref FROM segment s '
                 "JOIN transcript t ON t.id=s.transcript_id JOIN source src ON src.id=t.source_id WHERE s.id=?", (seg_id,))
    if seg is None or not paths.get(seg["ref"]):
        return None
    rows = [dict(r) for r in db.all('SELECT idx, start, "end", text, speaker FROM segment WHERE transcript_id=? AND idx BETWEEN ? AND ? '
                                    "ORDER BY idx", (seg["transcript_id"], seg["idx"] - 4, seg["idx"] + 4))]
    me = next(i for i, r in enumerate(rows) if r["idx"] == seg["idx"])
    a, b = me, me
    same = lambda r: (r["speaker"] or None) == (seg["speaker"] or None)  # noqa: E731
    while rows[b]["end"] - rows[a]["start"] < 4.0:
        grow_b = b + 1 < len(rows) and same(rows[b + 1]) and rows[b + 1]["end"] - rows[a]["start"] <= 10.0
        grow_a = a > 0 and same(rows[a - 1]) and rows[b]["end"] - rows[a - 1]["start"] <= 10.0
        if not (grow_a or grow_b):
            break
        if grow_b:
            b += 1
        else:
            a -= 1
    st, en = rows[a]["start"], min(rows[b]["end"], rows[a]["start"] + 10.0)
    ref = work / f"ref_{_key(paths[seg['ref']], round(st, 2), round(en, 2))}.wav"
    if not ref.exists():
        ff.run_simple(["-ss", f"{st:.3f}", "-t", f"{en - st:.3f}", "-i", paths[seg["ref"]], "-vn", "-ac", "1", "-ar", "24000",
                       "-c:a", "pcm_s16le", str(ref)], timeout=120)
    return ref, " ".join(r["text"] for r in rows[a:b + 1])


def clone_lines(project, plan: dict, lines: list[dict], slot_ends: list[float], body: float, clips_dir: Path, log) -> dict[int, Path]:
    """Voice the lines in their original speakers' voices (OmniVoice, workers/scripts/tts_clone.py), each fitted to
    the time it has where it can be. {line index: clip}; lines without a reference are left out (another voice)."""
    from ..workers.worker_env import run_script
    db = project.db
    paths = {it["source"]: it["path"] for it in plan["items"] if it.get("path") and Path(it["path"]).exists()}
    work = project.dir("cache", "dub", "refs")
    todo, out = [], {}
    for k, line in enumerate(lines):
        ref = _reference(db, line.get("seg"), work, paths) if line.get("seg") is not None else None
        if ref is None:
            continue
        slot_end = next((e for e in slot_ends if e > line["start"] + 0.01), body) - 0.05
        nxt = lines[k + 1]["start"] + MAX_DELAY if k + 1 < len(lines) else body
        window = round(max(0.5, min(slot_end, nxt, body) - line["start"]), 2)
        clip = clips_dir / f"{_key('clone', plan['lang'], line['text'], ref[0].name, window)}.wav"
        out[k] = clip
        if not clip.exists():
            todo.append({"text": line["text"], "ref_audio": str(ref[0]), "ref_text": ref[1], "max_dur": window, "out": str(clip)})
    if todo:
        job = work / f"clone_{_key(plan['hash'], plan['lang'], len(todo))}.json"
        job.write_text(json.dumps({"language": plan["lang"], "items": todo}, ensure_ascii=False), encoding="utf-8")
        log(f"dub: cloning {len(todo)} line(s) with OmniVoice (CPU, a while)")
        run_script("tts_clone", ["--input", str(job), "--model", config.get("tts.clone_model") or "k2-fsa/OmniVoice"])
    return {k: c for k, c in out.items() if c.exists()}


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
    if info["backend"] == "clone":  # say so wherever the video goes (D-09: credit everything; no passing off)
        plan["credits"] = list(plan["credits"]) + [{"type": "voice", "ref": "dub", "url": None,
            "text": f"{info['lang']} voices: AI voices cloned from the original speakers (OmniVoice); not their recordings"}]
    plan["_dub_text"] = info["text"]
    plan["hash"] = plan_hash(plan)
    ctx.log(f"dub: {info['lines']} lines, {info['sped_up']} sped up, {len(info['overflow'])} overflow ({info['backend']} {info['voice']})")
    return plan
