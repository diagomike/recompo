"""The render engine: plan → cached slot renders → assembled body → captions/overlays, music, loudness,
endcard → packaged export (video, captions, description, credits, recipe, thumbnail).

Slot intermediates are cached by content (source, range, format), so reordering a journey only
re-assembles. Every intermediate has identical stream parameters, so hard cuts concatenate without
re-encoding.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import time
from pathlib import Path

from ..core import config
from ..core.timecode import clock, srt_clock
from ..envelope import RecompError
from ..media import ff
from . import ass
from .plan import slot_key

ISO3 = {"en": "eng", "am": "amh", "sw": "swa", "fr": "fra", "om": "orm", "so": "som", "es": "spa", "ar": "ara",
        "ti": "tir", "de": "deu", "it": "ita", "pt": "por", "zh": "zho", "hi": "hin"}


class Ctx:
    def __init__(self, progress=None, cancelled=None, log=None):
        self.progress = progress or (lambda f, m="": None)
        self.cancelled = cancelled or (lambda: False)
        self.log = log or (lambda m: None)


def _even(n: float) -> int:
    return int(n) // 2 * 2


def reframe_filter(item: dict, prof: dict) -> str:
    w, h = prof["width"], prof["height"]
    mode = prof["reframe"]
    if mode == "crop-center":
        return f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}"
    if mode == "crop-x":
        x = item.get("reframe_x")
        x = 0.5 if x is None else float(x)
        return f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}:(iw-{w})*{x:.3f}:(ih-{h})/2"
    if mode == "fit-blur":
        sw, sh = _even(w / 8), _even(h / 8)
        return (f"[0:v]split=2[bga][fga];[bga]scale={sw}:{sh}:force_original_aspect_ratio=increase,crop={sw}:{sh},"
                f"boxblur=8:2,eq=brightness=-0.10:saturation=0.85,scale={w}:{h}[bg];"
                f"[fga]scale={w}:{h}:force_original_aspect_ratio=decrease[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2")
    return f"[0:v]scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black"


def audio_filter(item: dict, dur: float) -> str:
    a = item.get("audio") or {}
    ch = a.get("channels") or 2
    pan = "pan=stereo|FL=FC+0.30*FL+0.30*BL|FR=FC+0.30*FR+0.30*BR" if ch >= 6 else \
          ("pan=stereo|FL=c0|FR=c0" if ch == 1 else "anull")
    return (f"{pan},aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
            f"afade=t=in:d=0.03,afade=t=out:st={max(0.0, dur - 0.03):.3f}:d=0.03,apad=whole_dur={dur:.3f}")


def render_slot(project, item: dict, prof: dict, c: Ctx) -> Path:
    cache = project.dir("cache", "render", "slots")
    out = cache / f"{slot_key(item, prof)}.mp4"
    if out.exists() and out.stat().st_size > 1000:
        os.utime(out)  # LRU for pruning
        return out
    src = item["path"]
    if not src or not Path(src).exists():
        raise RecompError("E_NOT_FOUND", f"{item['ref']}: no media file for {item['source']}")
    dur = item["dur"]
    has_audio = bool(item.get("audio"))
    frames = item.get("frames") or max(1, round(dur * prof["fps"]))
    args = ["-ss", f"{item['in']:.3f}", "-t", f"{dur + 1.0:.3f}", "-i", src]
    if not has_audio:
        args += ["-f", "lavfi", "-t", f"{dur + 1.0:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]
    # Exactly `frames` frames (padded by cloning the last one if the source runs short) and exactly
    # `dur` seconds of audio: slots then add up to the plan's length with no drift.
    vf = (reframe_filter(item, prof) + f",fps={prof['fps']},tpad=stop_mode=clone:stop_duration=1,"
          f"trim=end_frame={frames},setpts=PTS-STARTPTS,setsar=1,format=yuv420p[v]")
    af = (f"[0:a:0]{audio_filter(item, dur)},atrim=0:{dur:.4f},asetpts=PTS-STARTPTS[a]" if has_audio
          else f"[1:a]atrim=0:{dur:.4f},asetpts=PTS-STARTPTS[a]")
    args += ["-filter_complex", vf + ";" + af, "-map", "[v]", "-map", "[a]", "-frames:v", str(frames),
             "-c:v", prof["video_codec"], "-preset", prof["preset"], "-crf", str(prof["crf"]),
             "-g", str(prof["fps"] * 2), "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-b:a", prof["audio_bitrate"], "-ar", "48000", "-ac", "2",
             "-video_track_timescale", "90000", "-avoid_negative_ts", "make_zero", str(out.with_suffix(".part.mp4"))]
    ff.run(args, duration=dur, cancelled=c.cancelled)
    out.with_suffix(".part.mp4").replace(out)
    return out


def assemble(work: Path, items: list[dict], parts: list[Path], prof: dict, c: Ctx) -> Path:
    body = work / "body.mp4"
    has_tr = any((it.get("transition") or {}).get("type") in ("fade", "dip") for it in items[1:])
    if not has_tr:
        # Video: stream copy (every slot has exactly its frame count). Audio: decoded and trimmed to each
        # slot's exact length, so AAC padding cannot accumulate into drift over many slots.
        lst = work / "concat.txt"
        lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
        args = ["-f", "concat", "-safe", "0", "-i", str(lst)]
        fl = []
        for k, p in enumerate(parts):
            args += ["-i", str(p)]
            fl.append(f"[{k + 1}:a]atrim=0:{items[k]['dur']:.4f},asetpts=PTS-STARTPTS[a{k}]")
        fl.append("".join(f"[a{k}]" for k in range(len(parts))) + f"concat=n={len(parts)}:v=0:a=1[a]")
        args += ["-filter_complex", ";".join(fl), "-map", "0:v", "-map", "[a]", "-c:v", "copy",
                 "-c:a", "aac", "-b:a", prof["audio_bitrate"], "-ar", "48000", "-movflags", "+faststart", str(body)]
        ff.run(args, cancelled=c.cancelled)
        return body
    args = []
    for p in parts:
        args += ["-i", str(p)]
    fl = []
    v, a = "[0:v]", "[0:a]"
    t = items[0]["dur"]
    for k in range(1, len(parts)):
        tr = items[k].get("transition") or {}
        nv, na = f"[v{k}]", f"[a{k}]"
        if tr.get("type") in ("fade", "dip"):
            d = min(float(tr.get("dur", 0.5)), items[k]["dur"] / 2, items[k - 1]["dur"] / 2)
            kind = "fadeblack" if tr["type"] == "dip" else "fade"
            fl.append(f"{v}[{k}:v]xfade=transition={kind}:duration={d:.3f}:offset={t - d:.3f}{nv}")
            fl.append(f"{a}[{k}:a]acrossfade=d={d:.3f}{na}")
            t = t - d + items[k]["dur"]
        else:
            fl.append(f"{v}{a}[{k}:v][{k}:a]concat=n=2:v=1:a=1{nv}{na}")
            t += items[k]["dur"]
        v, a = nv, na
    args += ["-filter_complex", ";".join(fl), "-map", v, "-map", a, "-c:v", prof["video_codec"], "-preset", prof["preset"],
             "-crf", str(prof["crf"]), "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", prof["audio_bitrate"], "-ar", "48000",
             "-movflags", "+faststart", str(body)]
    ff.run(args, duration=t, cancelled=c.cancelled)
    return body


def endcard(work: Path, plan: dict, prof: dict, c: Ctx) -> Path | None:
    if not plan.get("endcard"):
        return None
    w, h, fps, dur = prof["width"], prof["height"], prof["fps"], plan["endcard"]["seconds"]
    url = (plan.get("links") or {}).get("hub")
    lines = []
    for cr in plan["credits"]:
        lines.append(cr["text"])
    link_text = f"Recipe: {url}" if url else f"Recomposer recipe {plan['recipe_hash'].split(':')[-1][:10]}"
    doc = ass.endcard_document(w, h, plan["title"], lines, dur, link_text)
    (work / "endcard.ass").write_text(doc, encoding="utf-8")
    out = work / "endcard.mp4"
    args = ["-f", "lavfi", "-i", f"color=c=0x0d1311:s={w}x{h}:r={fps}:d={dur:.3f}",
            "-f", "lavfi", "-t", f"{dur:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]
    vf = "[0:v]subtitles=endcard.ass:fontsdir=C\\\\:/Windows/Fonts" if os.name == "nt" else "[0:v]subtitles=endcard.ass"
    if url:
        import segno
        qr = work / "qr.png"
        segno.make(url, error="m").save(str(qr), scale=10, border=2, dark="#0d1311", light="#ffffff")
        size = _even(min(w, h) * 0.26)
        args += ["-i", str(qr)]
        vf += f"[base];[2:v]scale={size}:{size}[q];[base][q]overlay=W-w-{_even(w * 0.08)}:H-h-{_even(h * 0.10)}"
    vf += ",format=yuv420p[v]"
    args += ["-filter_complex", vf, "-map", "[v]", "-map", "1:a", "-t", f"{dur:.3f}", "-c:v", prof["video_codec"],
             "-preset", prof["preset"], "-crf", str(prof["crf"]), "-g", str(fps * 2), "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-b:a", prof["audio_bitrate"], "-ar", "48000", "-ac", "2",
             "-video_track_timescale", "90000", str(out)]
    ff.run(args, duration=dur, cancelled=c.cancelled, cwd=str(work))
    return out


def _music_graph(plan: dict, first_input: int, body_dur: float) -> tuple[list[str], list[str], str | None]:
    """Inputs and filter lines that produce [mus] (summed beds), or None without music."""
    inputs, fl, labels = [], [], []
    for k, m in enumerate(plan["music"]):
        idx = first_input + k
        inputs += ["-stream_loop", "-1", "-i", m["file"]]
        at = float(m.get("at") or 0)
        dur = float(m.get("dur") or max(1.0, body_dur - at))
        dur = min(dur, body_dur - at)
        fi, fo = float(m.get("fade_in", 1.5)), float(m.get("fade_out", 2.5))
        fl.append(f"[{idx}:a]atrim=start={float(m.get('track_in') or 0):.3f}:duration={dur:.3f},asetpts=PTS-STARTPTS,"
                  f"aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
                  f"afade=t=in:d={fi:.2f},afade=t=out:st={max(0, dur - fo):.3f}:d={fo:.2f},"
                  f"volume={float(m.get('gain_db', -16)):.1f}dB,adelay={int(at * 1000)}|{int(at * 1000)},"
                  f"apad=whole_dur={body_dur:.3f}[m{k}]")
        labels.append(f"[m{k}]")
    if not labels:
        return [], [], None
    if len(labels) > 1:
        fl.append("".join(labels) + f"amix=inputs={len(labels)}:normalize=0:duration=longest[mus]")
    else:
        fl[-1] = fl[-1][: -len(labels[0])] + "[mus]"
    return inputs, fl, "[mus]"


def _audio_chain(plan: dict, music_first: int, body_label: str = "[0:a]") -> tuple[list[str], list[str]]:
    """Filter lines turning body audio (+ music) into [mix]."""
    m_inputs, fl, mus = _music_graph(plan, music_first, plan["body_dur"])
    fl = list(fl)
    fl.append(f"{body_label}aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[dlg0]")
    if mus:
        duck = float(plan["music"][0].get("duck_db", -10))
        ratio = max(2.0, min(20.0, -duck / 1.5))
        fl.append("[dlg0]asplit=2[dlg][sc]")
        fl.append(f"{mus}[sc]sidechaincompress=threshold=0.015:ratio={ratio:.1f}:attack=15:release=450:makeup=1[ducked]")
        fl.append("[dlg][ducked]amix=inputs=2:normalize=0:duration=first[mix]")
    else:
        fl.append("[dlg0]anull[mix]")
    return m_inputs, fl


def measure_loudness(body: Path, plan: dict) -> dict:
    m_inputs, fl = _audio_chain(plan, 1)
    fl.append(f"[mix]loudnorm=I={plan['profile']['loudness']}:TP={plan['profile']['true_peak']}:LRA=11:print_format=json[out]")
    text = ff.run_simple(["-i", str(body), *m_inputs, "-filter_complex", ";".join(fl), "-map", "[out]", "-f", "null", "-"],
                         timeout=1800)
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", text, re.S)
    if not m:
        raise RecompError("E_TOOL", "loudness measurement failed")
    return json.loads(m.group(0))


def final(work: Path, body: Path, card: Path | None, plan: dict, prof: dict, out: Path, c: Ctx) -> Path:
    w, h = prof["width"], prof["height"]
    doc = ass.document(w, h, plan["captions"] if prof["captions"] == "burn" else [], prof["caption_style"], plan["overlays"])
    (work / "overlay.ass").write_text(doc, encoding="utf-8")
    meas = measure_loudness(body, plan)
    c.progress(0.8, "loudness measured")
    args = ["-i", str(body)]
    next_in = 1
    if card:
        args += ["-i", str(card)]
        next_in = 2
    m_inputs, afl = _audio_chain(plan, next_in)
    args += m_inputs
    fonts = ":fontsdir=C\\\\:/Windows/Fonts" if os.name == "nt" else ""
    fl = [f"[0:v]setpts=N/({prof['fps']}*TB),subtitles=overlay.ass{fonts}[vb]"] + afl
    ln = (f"loudnorm=I={prof['loudness']}:TP={prof['true_peak']}:LRA=11:measured_I={meas['input_i']}:"
          f"measured_TP={meas['input_tp']}:measured_LRA={meas['input_lra']}:measured_thresh={meas['input_thresh']}:"
          f"offset={meas['target_offset']}:linear=true,aresample=48000,"
          f"alimiter=limit={10 ** ((prof['true_peak'] - 0.6) / 20):.3f}:attack=2:release=60:level=false")
    fl.append(f"[mix]{ln}[mixn]")
    if card:
        fl.append("[vb][mixn][1:v][1:a]concat=n=2:v=1:a=1[v][a]")
        vmap, amap = "[v]", "[a]"
    else:
        vmap, amap = "[vb]", "[mixn]"
    lang3 = ISO3.get((plan.get("lang") or "en")[:2], "und")
    url = (plan.get("links") or {}).get("hub") or ""
    args += ["-filter_complex", ";".join(fl), "-map", vmap, "-map", amap, "-t", f"{plan['total']:.3f}",
             "-c:v", prof["video_codec"], "-preset", prof["preset"], "-crf", str(prof["crf"]), "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-b:a", prof["audio_bitrate"], "-ar", "48000", "-movflags", "+faststart",
             "-metadata", f"title={plan['title']}", "-metadata", f"comment=Recomposer recipe {plan['recipe_hash']} {url}".strip(),
             "-metadata:s:a:0", f"language={lang3}", str(out)]
    ff.run(args, duration=plan["total"], cancelled=c.cancelled, cwd=str(work),
           progress=lambda f, m: c.progress(0.8 + 0.2 * f, m))
    return out


def write_srt(captions: list[dict], path: Path) -> int:
    lines = []
    for k, cap in enumerate(captions, start=1):
        lines += [str(k), f"{srt_clock(cap['start'])} --> {srt_clock(cap['end'])}", cap["text"], ""]
    path.write_text("\n".join(lines), encoding="utf-8")
    return len(captions)


def description(plan: dict) -> str:
    rec = plan.get("_recipe") or {}
    out = [plan["title"], ""]
    if rec.get("intent"):
        out += [rec["intent"], ""]
    if rec.get("description"):
        out += [rec["description"], ""]
    src = [c for c in plan["credits"] if c["type"] == "source"]
    mus = [c for c in plan["credits"] if c["type"] == "music"]
    if src:
        out.append("Sources:")
        for c in src:
            moments = ", ".join(c.get("moments") or [])
            out.append(f"- {c['text']}" + (f" (moments {moments})" if moments else "") + (f" {c['url']}" if c.get("url") else ""))
        out.append("")
    if mus:
        out.append("Music:")
        for c in mus:
            out.append(f"- {c['text']}" + (f" {c['url']}" if c.get("url") else "") + (f" · licence {c['licence_url']}" if c.get("licence_url") else ""))
        out.append("")
    url = (plan.get("links") or {}).get("hub")
    out.append(f"Recipe (sources and timecodes): {url}" if url else f"Recomposer recipe {plan['recipe_hash']}")
    out.append("Made with Recomposer. Excerpts are used for commentary and are credited to their owners above.")
    tags = sorted({t for s in (rec.get("slots") or []) for t in (s.get("tags") or []) if t not in ("draft", "imported")})[:8]
    if tags:
        out += ["", " ".join("#" + re.sub(r"\W+", "", t) for t in tags)]
    return "\n".join(out) + "\n"


def render(project, plan: dict, out_dir: Path, c: Ctx | None = None) -> dict:
    c = c or Ctx()
    prof = plan["profile"]
    t0 = time.time()
    work = project.dir("cache", "render", "work", plan["hash"])
    parts = []
    hits = 0
    n = len(plan["items"])
    for k, item in enumerate(plan["items"]):
        if item.get("needs_fetch"):
            from ..ingest import links
            item["path"] = str(links.ensure_section(project, item, prof, log=c.log))
        before = time.time()
        parts.append(render_slot(project, item, prof, c))
        if time.time() - before < 0.05:
            hits += 1
        c.progress(0.6 * (k + 1) / n, f"slot {k + 1}/{n}")
        if c.cancelled():
            raise ff.Cancelled()
    body = assemble(work, plan["items"], parts, prof, c)
    c.progress(0.65, "assembled")
    card = endcard(work, plan, prof, c)
    c.progress(0.7, "endcard")
    out_dir.mkdir(parents=True, exist_ok=True)
    video = final(work, body, card, plan, prof, out_dir / "video.mp4.part.mp4", c)
    final_path = out_dir / "video.mp4"
    video.replace(final_path)
    write_srt(plan["captions"], out_dir / "captions.srt")
    shutil.copy(work / "overlay.ass", out_dir / "overlay.ass")
    (out_dir / "description.txt").write_text(description(plan), encoding="utf-8")
    (out_dir / "credits.json").write_text(json.dumps(plan["credits"], indent=2, ensure_ascii=False), encoding="utf-8")
    if plan.get("_recipe"):
        (out_dir / "recipe.json").write_text(json.dumps(plan["_recipe"], indent=2, ensure_ascii=False), encoding="utf-8")
    thumb_t = min(plan["body_dur"] * 0.3, plan["items"][0]["dur"] * 0.5 + 0.5)
    try:
        ff.run_simple(["-ss", f"{thumb_t:.2f}", "-i", str(final_path), "-frames:v", "1", "-q:v", "3",
                       str(out_dir / "thumb.jpg")], timeout=60)
    except RecompError:
        pass
    (out_dir / "plan.json").write_text(json.dumps({k: v for k, v in plan.items() if not k.startswith("_")},
                                                  indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    return {"video": str(final_path), "folder": str(out_dir), "seconds": round(time.time() - t0, 1),
            "slot_cache_hits": hits, "slots": n, "duration": plan["total"]}


def prune_cache(project, max_gb: float | None = None) -> dict:
    max_gb = max_gb if max_gb is not None else float(config.get("render.cache_max_gb") or 8)
    root = project.root / "cache" / "render"
    files = sorted((p for p in root.rglob("*") if p.is_file()), key=lambda p: p.stat().st_mtime)
    total = sum(p.stat().st_size for p in files)
    removed = 0
    while files and total > max_gb * 1e9:
        p = files.pop(0)
        total -= p.stat().st_size
        p.unlink()
        removed += 1
    return {"removed": removed, "remaining_gb": round(total / 1e9, 3)}
