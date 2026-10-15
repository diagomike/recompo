"""Briefing, health checks, configuration and setup."""

from __future__ import annotations

import importlib.metadata as md
import shutil
import subprocess
import time
from pathlib import Path

from pydantic import BaseModel, Field

from .. import __version__
from ..core import config
from ..core.timecode import clock
from ..envelope import RecompError, Result
from ..registry import Ctx, NoInput, verb
from . import agentkit
from .ui import get_state


def _count(db, table: str, where: str = "", params=()) -> int:
    return db.scalar(f"SELECT COUNT(*) FROM {table} {where}", params) or 0


STAGES = ("probe", "audio", "shots", "peaks", "transcript", "index", "chapters")


def source_brief(db, s: dict) -> dict:
    status = s.get("status") or {}
    tr = db.one("SELECT ref, origin, language FROM transcript WHERE source_id=? AND is_primary=1", (s["id"],))
    return {
        "ref": s["ref"], "title": s["title"], "kind": s["kind"],
        "duration": clock(s.get("duration")) if s.get("duration") else None,
        "stages": {k: status.get(k, "pending") for k in STAGES if k in status or k in ("transcript", "chapters")},
        "transcript": dict(tr) if tr else None,
        "chapters": _count(db, "chapter", "WHERE source_id=?", (s["id"],)),
        "cuts": _count(db, "cut", "WHERE source_id=?", (s["id"],)),
    }


@verb("context", NoInput, examples=["recomp context"])
def context(ctx: Ctx, inp: NoInput):
    """One-call briefing: the project, every source's pipeline status, journeys, jobs, the user's selection and notes, and suggested next steps."""
    db = ctx.db
    sources = db.rows("source", "ORDER BY created_at")
    journeys = []
    for j in db.rows("journey", "ORDER BY created_at"):
        n = _count(db, "slot", "WHERE journey_id=?", (j["id"],))
        dur = db.scalar(
            "SELECT SUM(COALESCE(s.trim_out, c.\"end\") - COALESCE(s.trim_in, c.start)) "
            "FROM slot s JOIN cut c ON c.id=s.cut_id WHERE s.journey_id=?", (j["id"],)) or 0
        journeys.append({"ref": j["ref"], "title": j["title"], "slots": n, "duration": clock(dur),
                         "status": j["status"]})
    jobs = [{"ref": r["ref"], "type": r["type"], "status": r["status"], "progress": round(r["progress"], 2),
             "message": r["message"], "target": r["target"]}
            for r in db.all("SELECT * FROM job WHERE status IN ('queued','running') "
                            "OR (status='failed' AND finished_at > ?) ORDER BY created_at",
                            (time.time() - 3600,))]
    asks = get_state(db, "asks", [])
    notes = [n for n in get_state(db, "notes", []) if not n.get("seen")]
    counts = {t: _count(db, t) for t in ("source", "transcript", "chapter", "cut", "journey", "export",
                                         "music_track", "person")}
    briefs = [source_brief(db, s) for s in sources[:60]]
    nxt: list[str] = []
    if not sources:
        nxt.append('recomp source add "<file, folder, glob or link>"')
    for b in briefs:
        if not b["transcript"]:
            nxt.append(f"recomp transcript asr {b['ref']}   # or import/fetch-captions; no transcript yet")
        elif b["chapters"] == 0:
            nxt.append(f"recomp transcript outline {b['ref']}   # then write chapters")
    if counts["cut"] and not journeys:
        nxt.append('recomp journey new "<title>" --intent "<what it is for>"')
    if notes:
        nxt.insert(0, "recomp ui notes   # the user left you notes")
    return Result(data={
        "project": ctx.project.summary(),
        "counts": counts,
        "sources": briefs,
        "more_sources": max(0, len(sources) - 60),
        "journeys": journeys,
        "jobs": jobs,
        "selection": get_state(db, "selection"),
        "open_asks": [a for a in asks if a.get("answer") is None],
        "unread_notes": len(notes),
        "recent_ops": [{"actor": r["actor"], "verb": r["verb"], "refs": r["refs"], "ago_s": round(time.time() - r["time"])}
                       for r in db.rows("op", "WHERE state='done' ORDER BY seq DESC LIMIT 5")],
    }, next=nxt[:6])


def _run(cmd: list[str], timeout: int = 20) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")
        return p.returncode, (p.stdout or p.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return -1, str(exc)


class DoctorIn(BaseModel):
    net: bool = Field(False, description="Also check network endpoints (Openverse, YouTube, edge-tts)")
    worker: bool = Field(True, description="Check the worker python and its packages")


@verb("doctor", DoctorIn, needs_project=False, examples=["recomp doctor", "recomp doctor --net"])
def doctor(ctx: Ctx, inp: DoctorIn):
    """Check the tools, worker environment, models, disk and (optionally) network this app needs."""
    checks: list[dict] = []

    def add(name, ok, detail="", fix=""):
        item = {"check": name, "ok": bool(ok), "detail": detail}
        if not ok and fix:
            item["fix"] = fix
        checks.append(item)

    for tool in ("ffmpeg", "ffprobe"):
        path = shutil.which(tool)
        code, out = _run([tool, "-version"]) if path else (-1, "")
        add(tool, code == 0, out.splitlines()[0] if out else "", "winget install --id Gyan.FFmpeg -e")
    fonts = Path(r"C:\Windows\Fonts")
    for font in ("arial.ttf", "ebrima.ttf", "georgia.ttf"):
        add(f"font {font}", (fonts / font).exists() or not fonts.exists(), str(fonts / font))
    for pkg in ("yt-dlp", "edge-tts", "fastapi", "mcp", "segno", "curl_cffi"):
        try:
            add(f"python package {pkg}", True, md.version(pkg))
        except md.PackageNotFoundError:
            add(f"python package {pkg}", False, "", "pip install -e .")
    if inp.worker:
        wpy = Path(config.get("worker.python"))
        add("worker python", wpy.exists(), str(wpy), "recomp config set worker.python <path to a python with faster-whisper>")
        if wpy.exists():
            code, out = _run([str(wpy), "-c",
                              "import importlib.util as u;print(','.join(m for m in ('faster_whisper','pyannote.audio','transformers','torch') if u.find_spec(m.split('.')[0])))"], 60)
            have = set(out.split(",")) if code == 0 else set()
            add("worker faster_whisper", "faster_whisper" in have, out)
            add("worker pyannote (speakers)", "pyannote.audio" in have or "pyannote" in out, out)
        hf = Path(config.get("worker.hf_home")) / "hub"
        model = config.get("worker.asr_model").replace("/", "--")
        add("ASR model cached", (hf / f"models--{model}").exists(), str(hf / f"models--{model}"),
            "The first ASR job downloads it (about 1.6 GB).")
    root = Path(config.get("projects_root"))
    anchor = Path(root.anchor or ".")
    try:
        free_gb = shutil.disk_usage(anchor).free / 1e9
        add("disk free (projects root)", free_gb > 10, f"{free_gb:.1f} GB on {anchor}", "Free space or move projects_root")
    except OSError as exc:
        add("disk free (projects root)", False, str(exc))
    add("node (viewer build)", shutil.which("node") is not None, shutil.which("node") or "")
    if inp.net:
        import httpx
        for name, url in (("openverse", "https://api.openverse.org/v1/audio/?q=piano&page_size=1"),
                          ("youtube", "https://www.youtube.com/robots.txt"),
                          ("edge-tts host", "https://speech.platform.bing.com/")):
            try:
                r = httpx.get(url, timeout=10)
                add(f"net {name}", r.status_code < 500, f"HTTP {r.status_code}")
            except httpx.HTTPError as exc:
                add(f"net {name}", False, str(exc)[:120], "The sandbox may block this host; allow it when prompted")
    bad = [c for c in checks if not c["ok"]]
    return {"version": __version__, "ok": not bad, "problems": len(bad), "checks": checks}


class ConfigGetIn(BaseModel):
    key: str | None = Field(None, description="Dotted key, e.g. worker.python (omit for everything)",
                            json_schema_extra={"pos": 0})


@verb("config.get", ConfigGetIn, needs_project=False)
def config_get(ctx: Ctx, inp: ConfigGetIn):
    """Studio settings (projects root, worker python, hub URL, TTS voices…)."""
    return config.get(inp.key) if inp.key else {"home": str(config.home()), **config.load()}


class ConfigSetIn(BaseModel):
    key: str = Field(..., json_schema_extra={"pos": 0})
    value: str = Field(..., description="Value (JSON accepted: numbers, true/false, objects)",
                       json_schema_extra={"pos": 1})


@verb("config.set", ConfigSetIn, effect="write", needs_project=False,
      examples=[r"recomp config set worker.python D:\LangBridgeLocal\.venv\Scripts\python.exe"])
def config_set(ctx: Ctx, inp: ConfigSetIn):
    """Change a studio setting."""
    import json
    try:
        value = json.loads(inp.value)
    except json.JSONDecodeError:
        value = inp.value
    if "." not in inp.key and inp.key not in config.DEFAULTS:
        raise RecompError("E_INVALID", f"unknown setting {inp.key!r}")
    config.set_value(inp.key, value)
    return {inp.key: config.get(inp.key)}


class ShimIn(BaseModel):
    bin_dir: str = Field(str(Path.home() / "bin"), description="Folder on PATH for the launchers")


@verb("setup.shim", ShimIn, effect="write", needs_project=False)
def setup_shim(ctx: Ctx, inp: ShimIn):
    """Write `recomp` launchers (sh and .cmd) into a folder on PATH so agents can call `recomp` anywhere."""
    return {"written": agentkit.write_shims(Path(inp.bin_dir)), "exe": agentkit.recomp_exe()}


@verb("version", NoInput, needs_project=False)
def version(ctx: Ctx, inp: NoInput):
    """Version and where things are."""
    return {"version": __version__, "exe": agentkit.recomp_exe(), "home": str(config.home()),
            "repo": str(agentkit.REPO)}
