"""Links (YouTube and anything yt-dlp reads): metadata first, captions next, bytes last.

* A channel or playlist link returns a **pick list** (nothing is added); ``--pick`` adds entries.
* A video link adds a ``link`` source with metadata, creator chapters and caption availability, then
  queues a ``captions`` job. If captions are refused (HTTP 429, bot checks), the agent can fall back
  to ``transcript asr`` which fetches audio only.
* Renders fetch only the ranges a journey uses (``ensure_section``), cut exactly at the edges.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

from ..core import config, refs
from ..core.timecode import clock, parse
from ..envelope import RecompError, Result
from ..workers import jobs

YT_ID = re.compile(r"(?:v=|youtu\.be/|shorts/|embed/|live/)([A-Za-z0-9_-]{11})")


class _Quiet:
    def debug(self, msg):
        pass

    def info(self, msg):
        pass

    def warning(self, msg):
        pass

    def error(self, msg):
        pass


def _ydl(extra: dict | None = None):
    import yt_dlp
    import shutil
    opts = {"quiet": True, "no_warnings": True, "logger": _Quiet(), "noprogress": True,
            "extractor_retries": int(config.get("network.yt_retries") or 3), "retries": 5,
            "socket_timeout": 30, "skip_download": True}
    # YouTube extraction needs a JavaScript runtime; Node is on this machine, deno usually is not.
    if shutil.which("node"):
        opts["js_runtimes"] = {"node": {}}
    # Browser cookies only when the *user* configured them: `recomp config set network.cookies_from_browser chrome`.
    browser = config.get("network.cookies_from_browser")
    if browser:
        opts["cookiesfrombrowser"] = (browser,)
    opts.update(extra or {})
    return yt_dlp.YoutubeDL(opts)


def classify_error(exc: Exception) -> RecompError:
    text = str(exc)
    if "429" in text or "Too Many Requests" in text:
        return RecompError("E_EXTERNAL", "the site is rate-limiting this machine (HTTP 429)",
                           hint="Wait a few minutes and retry; for transcripts use `recomp transcript asr <S>` (audio only).")
    if "Sign in to confirm" in text or "bot" in text.lower():
        return RecompError("E_EXTERNAL", "the site asks to confirm this is not a bot",
                           hint="Stop here and ask the user (browser cookies are their decision).")
    if "Private video" in text or "unavailable" in text.lower():
        return RecompError("E_NOT_FOUND", f"video unavailable: {text[:160]}")
    return RecompError("E_NETWORK", f"yt-dlp: {text[:300]}")


def extract(url: str, flat: bool = False, limit: int | None = None) -> dict:
    opts = {"extract_flat": "in_playlist"} if flat else {}
    if limit:
        opts["playlistend"] = limit
    try:
        with _ydl(opts) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception as exc:  # noqa: BLE001
        raise classify_error(exc) from exc


def _entry(e: dict, n: int) -> dict:
    dur = e.get("duration")
    return {"n": n, "id": e.get("id"), "title": e.get("title"), "duration": clock(dur, 0) if dur else None,
            "duration_s": dur, "views": e.get("view_count"), "date": e.get("upload_date"),
            "url": e.get("url") if (e.get("url") or "").startswith("http") else f"https://www.youtube.com/watch?v={e.get('id')}"}


def add(ctx, inp) -> Result:
    from ..verbs.ui import get_state, set_state
    db = ctx.db
    if inp.pick:
        pl = get_state(db, "pick_list") or {}
        entries = pl.get("entries") or []
        chosen = []
        for p in inp.pick:
            hit = next((e for e in entries if str(e["n"]) == str(p) or e["id"] == p), None)
            if hit is None:
                raise RecompError("E_NOT_FOUND", f"{p} is not in the last pick list",
                                  hint="List again: `recomp source add <channel or playlist link> --limit 30`")
            chosen.append(hit)
        added, warnings = [], []
        for e in chosen:
            try:
                r = add_video(ctx, e["url"], inp)
            except RecompError as exc:
                if exc.code != "E_EXTERNAL":
                    raise
                # Blocked for full metadata: add from the list's metadata now, complete it later.
                r = add_video(ctx, e["url"], inp, info={"id": e["id"], "title": e["title"], "duration": e["duration_s"],
                                                       "channel": pl.get("channel"), "webpage_url": e["url"],
                                                       "extractor_key": "youtube", "view_count": e.get("views"),
                                                       "_partial": True})
                warnings.append(f"{r.data['added'][0]['ref'] if r.data['added'] else e['id']}: added from the list only "
                                f"({exc.message}); `recomp source refresh <ref>` completes chapters and caption info later")
            added += r.data["added"]
            warnings += r.warnings
        return Result(data={"added": added, "skipped": [], "jobs": [], "runner": jobs.kick(ctx.project)},
                      refs=[a["ref"] for a in added], warnings=warnings)
    url = inp.target.strip()
    if YT_ID.search(url) and "list=" not in url:
        return add_video(ctx, url, inp)
    info = extract(url, flat=True, limit=inp.limit or 30)
    if info.get("_type") not in ("playlist", "multi_video") and not info.get("entries"):
        return add_video(ctx, url, inp, info=None)
    entries = [e for e in (info.get("entries") or []) if e]
    out = [_entry(e, k) for k, e in enumerate(entries, start=1)]
    if inp.match:
        rx = re.compile(inp.match, re.I)
        out = [e for e in out if rx.search(e["title"] or "")]
    if inp.since:
        secs = parse(inp.since.replace("d", "")) if inp.since.endswith("d") else None
        if secs is not None:
            cutoff = time.strftime("%Y%m%d", time.gmtime(time.time() - float(secs) * 86400))
            out = [e for e in out if not e["date"] or e["date"] >= cutoff]
    set_state(db, "pick_list", {"url": url, "title": info.get("title"), "channel": info.get("channel") or info.get("uploader"),
                                "entries": out})
    total = sum(e["duration_s"] or 0 for e in out)
    return Result(data={"list": info.get("title"), "channel": info.get("channel") or info.get("uploader"),
                        "entries": out, "total": clock(total, 0)},
                  next=["recomp source add --pick 1,3,5   # adds those entries (metadata + captions first)"])


def add_video(ctx, url: str, inp, info: dict | None = None) -> Result:
    db = ctx.db
    m = YT_ID.search(url)
    if m:
        existing = db.rows("source", "WHERE platform='youtube' AND platform_id=?", (m.group(1),))
        if existing:
            return Result(data={"added": [], "skipped": [{"url": url, "ref": existing[0]["ref"], "why": "already in the project"}],
                                "jobs": [], "runner": None})
    info = info or extract(url)
    platform = (info.get("extractor_key") or info.get("extractor") or "web").lower().replace("tab", "")
    if platform.startswith("youtube"):
        platform = "youtube"
    vid = info.get("id")
    title = inp.title or info.get("title") or vid
    channel = info.get("channel") or info.get("uploader") or ""
    year = int(info["upload_date"][:4]) if info.get("upload_date") else None
    langs_manual = sorted((info.get("subtitles") or {}).keys())
    langs_auto = sorted(k for k in (info.get("automatic_captions") or {}).keys() if k.endswith("-orig") or len(k) <= 3)
    chapters = [{"start": c.get("start_time"), "end": c.get("end_time"), "title": c.get("title", "")}
                for c in info.get("chapters") or []]
    lang = inp.language or info.get("language") or next((k[:-5] for k in langs_auto if k.endswith("-orig")), None) or \
        (ctx.project.meta.get("languages") or ["en"])[0]
    webpage = info.get("webpage_url") or url
    with ctx.op(f"add link {vid}") as tx:
        src = tx.insert("source", {
            "kind": "link", "uri": webpage, "platform": platform, "platform_id": vid, "title": title,
            "creator": inp.creator or channel, "year": year, "language": lang, "duration": info.get("duration"),
            "rights": {"kind": "link", "owner": channel, "url": webpage,
                       "notice": f"\"{title}\", {channel}" + (f" ({platform.title()}, {year})" if year else ""),
                       "licence": info.get("license") or "platform standard licence"},
            "status": {"probe": "metadata-partial" if info.get("_partial") else "metadata"},
            "meta": {"chapters": chapters, "captions": {"manual": langs_manual, "auto": langs_auto},
                     "upload_date": info.get("upload_date"), "views": info.get("view_count"),
                     "thumbnail": info.get("thumbnail"), "description": (info.get("description") or "")[:3000],
                     "channel_url": info.get("channel_url"), "tags": (info.get("tags") or [])[:20]}})
    folder = ctx.project.dir("sources", src["ref"])
    slim = {k: info.get(k) for k in ("id", "title", "channel", "uploader", "upload_date", "duration", "webpage_url",
                                     "chapters", "language", "view_count", "categories", "tags", "description")}
    (folder / "info.json").write_text(json.dumps(slim, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    queued = []
    if getattr(inp, "subtitles", True) and not info.get("_partial"):
        j = jobs.enqueue(db, "captions", target=src["ref"], source_id=src["id"], params={"language": lang})
        queued.append(j["ref"])
    nxt = [f"recomp job wait {queued[0]} --timeout 60" if queued else f"recomp transcript fetch-captions {src['ref']}"]
    if chapters:
        nxt.append(f"recomp chapter seed {src['ref']}   # {len(chapters)} creator chapters")
    return Result(data={"added": [{"ref": src["ref"], "title": title, "creator": channel, "duration": clock(info.get('duration'), 0),
                                   "kind": "link", "creator_chapters": len(chapters),
                                   "captions": {"manual": langs_manual[:6], "auto": langs_auto[:6]}, "transcripts": []}],
                        "skipped": [], "jobs": queued, "runner": jobs.kick(ctx.project) if queued else None},
                  refs=[src["ref"]], next=nxt)


def refresh(ctx, src: dict, captions: bool = True) -> dict:
    """Fetch full metadata for a link source added from a list (chapters, caption languages, dates)."""
    info = extract(src["uri"])
    langs_manual = sorted((info.get("subtitles") or {}).keys())
    langs_auto = sorted(k for k in (info.get("automatic_captions") or {}).keys() if k.endswith("-orig") or len(k) <= 3)
    chapters = [{"start": c.get("start_time"), "end": c.get("end_time"), "title": c.get("title", "")}
                for c in info.get("chapters") or []]
    meta = dict(src.get("meta") or {})
    meta.update({"chapters": chapters, "captions": {"manual": langs_manual, "auto": langs_auto},
                 "upload_date": info.get("upload_date"), "views": info.get("view_count"),
                 "description": (info.get("description") or "")[:3000], "tags": (info.get("tags") or [])[:20]})
    status = dict(src.get("status") or {})
    status["probe"] = "metadata"
    year = int(info["upload_date"][:4]) if info.get("upload_date") else src.get("year")
    with ctx.op(f"refresh {src['ref']}") as tx:
        tx.update("source", src["id"], {"meta": meta, "year": year, "status": status,
                                        "language": src.get("language") or info.get("language")}, log=False)
    queued = None
    if captions and not ctx.db.one("SELECT 1 FROM transcript WHERE source_id=?", (src["id"],)):
        queued = jobs.enqueue(ctx.db, "captions", target=src["ref"], source_id=src["id"],
                              params={"language": src.get("language")})["ref"]
        jobs.kick(ctx.project)
    return {"ref": src["ref"], "creator_chapters": len(chapters), "captions": {"manual": langs_manual[:6], "auto": langs_auto[:6]},
            "job": queued}


# ---- jobs -------------------------------------------------------------------------------------

def pick_caption_lang(meta: dict, lang: str | None) -> tuple[str | None, bool]:
    caps = meta.get("captions") or {}
    manual, auto = caps.get("manual") or [], caps.get("auto") or []
    want = (lang or "en").split("-")[0]
    for m in manual:
        if m.split("-")[0] == want:
            return m, False
    for a in auto:
        if a == f"{want}-orig":
            return a, True
    for a in auto:
        if a.split("-")[0] == want:
            return a, True
    if manual:
        return manual[0], False
    return None, True


def fetch_captions(project, src: dict, lang: str | None, log=print) -> Path:
    meta = src.get("meta") or {}
    code, is_auto = pick_caption_lang(meta, lang)
    if code is None:
        raise RecompError("E_NOT_FOUND", f"{src['ref']} has no captions", hint=f"`recomp transcript asr {src['ref']}`")
    folder = project.dir("sources", src["ref"])
    opts = {"skip_download": True, "writesubtitles": not is_auto, "writeautomaticsub": is_auto,
            "subtitleslangs": [code], "subtitlesformat": "json3/vtt/best",
            "outtmpl": str(folder / "captions.%(ext)s"),
            "sleep_interval_subtitles": int(config.get("network.yt_sleep_subtitles") or 2)}
    last = None
    for attempt in range(int(config.get("network.yt_retries") or 3)):
        try:
            with _ydl(opts) as ydl:
                ydl.download([src["uri"]])
            files = sorted(folder.glob("captions*.json3")) + sorted(folder.glob("captions*.vtt"))
            if files:
                return files[0]
            raise RecompError("E_EXTERNAL", "no caption file was written")
        except RecompError:
            raise
        except Exception as exc:  # noqa: BLE001
            last = classify_error(exc)
            log(f"captions attempt {attempt + 1}: {last.message}")
            if last.code != "E_EXTERNAL" or "bot" in last.message:
                break
            time.sleep(20 * (attempt + 1))
    raise last or RecompError("E_EXTERNAL", "captions failed")


def fetch_audio(project, src: dict, progress=None, log=print) -> Path:
    folder = project.dir("sources", src["ref"])
    for old in folder.glob("audio_full.*"):
        if old.suffix not in (".part", ".ytdl"):
            return old
    hook = None
    if progress:
        def hook(d):
            if d.get("status") == "downloading" and d.get("total_bytes"):
                progress(min(0.99, d.get("downloaded_bytes", 0) / d["total_bytes"]), f"{d.get('downloaded_bytes', 0) // 1_000_000} MB")
    opts = {"skip_download": False, "format": "bestaudio[ext=webm]/bestaudio/best", "outtmpl": str(folder / "audio_full.%(ext)s"),
            "progress_hooks": [hook] if hook else []}
    try:
        with _ydl(opts) as ydl:
            ydl.download([src["uri"]])
    except Exception as exc:  # noqa: BLE001
        raise classify_error(exc) from exc
    files = [p for p in folder.glob("audio_full.*") if p.suffix not in (".part", ".ytdl")]
    if not files:
        raise RecompError("E_EXTERNAL", "audio download produced no file")
    return files[0]


def fetch_video(project, src: dict, height: int = 720, log=print, progress=None) -> Path:
    """The whole video at ≤ height (H.264 + AAC), once per source. Talks at 720p are small (≈1 MB/min);
    reading sections through ffmpeg instead streams from the start of the file and is far slower here."""
    folder = project.dir("sources", src["ref"])
    out = folder / f"video_{height}.mp4"
    if out.exists():
        return out
    hook = None
    if progress:
        def hook(d):
            if d.get("status") == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate")
                if total:
                    progress(min(0.99, d.get("downloaded_bytes", 0) / total), f"{d.get('downloaded_bytes', 0) // 1_000_000} MB")
    opts = {"skip_download": False,
            "format": f"bv*[height<={height}][vcodec^=avc1]+ba[ext=m4a]/bv*[height<={height}][ext=mp4]+ba/b[height<={height}]/b",
            "merge_output_format": "mp4", "outtmpl": str(folder / f"video_{height}.%(ext)s"),
            "concurrent_fragment_downloads": 4, "progress_hooks": [hook] if hook else []}
    try:
        with _ydl(opts) as ydl:
            ydl.download([src["uri"]])
    except Exception as exc:  # noqa: BLE001
        raise classify_error(exc) from exc
    if not out.exists():
        cands = [p for p in folder.glob(f"video_{height}.*") if p.suffix not in (".part", ".ytdl")]
        if not cands:
            raise RecompError("E_EXTERNAL", "video download produced no file")
        cands[0].rename(out)
    db = project.db
    db.conn.execute("INSERT OR REPLACE INTO asset(id, source_id, role, path, info, created_at) VALUES(?,?,?,?,?,?)",
                    (f"video-{src['ref']}-{height}", src["id"], "video", str(out), json.dumps({"height": height}), time.time()))
    log(f"video {src['ref']} ≤{height}p → {out.name} ({out.stat().st_size // 1_000_000} MB)")
    return out


def ensure_section(project, item: dict, prof: dict, log=print) -> str:
    """Media for one slot of a link source. Default (network.link_video = full): the whole video at ≤720p,
    downloaded once per source. With ``sections``: only [in − 1.5 s, out + 1.5 s], cut exactly."""
    db = project.db
    src = db.by_ref("source", item["source"])
    if (config.get("network.link_video") or "full") == "full":
        path = fetch_video(project, src, int(config.get("network.link_video_height") or 720), log=log)
        from ..media import ff
        info = ff.probe(path).to_dict()
        item["video"], item["audio"] = info["video"], info["audio"]
        item["fingerprint"] = f"video:{src['ref']}:{path.stat().st_size}"
        return str(path)
    pad = 1.5
    a = max(0.0, item["in"] - pad)
    b = item["out"] + pad
    target_h = 1080 if max(prof["width"], prof["height"]) >= 1280 else 720
    folder = project.dir("sources", src["ref"], "sections")
    name = f"{a:.2f}_{b:.2f}_{target_h}.mp4"
    out = folder / name
    if not out.exists():
        from yt_dlp.utils import download_range_func
        opts = {"skip_download": False,
                "format": f"bv*[height<={target_h}][ext=mp4]+ba[ext=m4a]/bv*[height<={target_h}]+ba/b[height<={target_h}]/b",
                "merge_output_format": "mp4", "outtmpl": str(folder / (name[:-4] + ".%(ext)s")),
                "download_ranges": download_range_func(None, [(a, b)]), "force_keyframes_at_cuts": True}
        try:
            with _ydl(opts) as ydl:
                ydl.download([src["uri"]])
        except Exception as exc:  # noqa: BLE001
            raise classify_error(exc) from exc
        if not out.exists():
            cands = sorted(folder.glob(name[:-4] + ".*"))
            if not cands:
                raise RecompError("E_EXTERNAL", "section download produced no file")
            cands[0].rename(out)
        db.conn.execute("INSERT INTO asset(id, source_id, role, path, range_start, range_end, info, created_at) "
                        "VALUES(?,?,?,?,?,?,?,?)", (f"sec-{src['ref']}-{a:.2f}", src["id"], "section", str(out), a, b,
                                                    json.dumps({"height": target_h}), time.time()))
        log(f"section {src['ref']} {clock(a)}–{clock(b)} → {out.name} ({out.stat().st_size // 1000} kB)")
    from ..media import ff
    info = ff.probe(out)
    item["in"] = round(item["in"] - a, 3)
    item["out"] = round(item["in"] + item["dur"], 3)
    item["video"] = info.to_dict()["video"]
    item["audio"] = info.to_dict()["audio"]
    item["fingerprint"] = f"section:{src['ref']}:{a:.2f}:{b:.2f}:{target_h}"
    return str(out)
