"""The project as a workspace: a guided checklist of where the work stands, its folders, and a file browser
for adding media without typing paths. The viewer's home page is drawn from these verbs, so the agent sees
exactly what the user sees."""

from __future__ import annotations

import os
import string
import subprocess
import sys
from pathlib import Path

from pydantic import BaseModel, Field

from ..core import refs
from ..envelope import RecompError
from ..media import ff
from ..registry import Ctx, NoInput, verb


def _n(db, sql: str, params: tuple = ()) -> int:
    return int(db.scalar(sql, params) or 0)


def _act(label: str, verb_: str | None = None, args: dict | None = None, view: str | None = None,
         params: dict | None = None) -> dict:
    """One next action: a verb the viewer (or the agent) runs, or a view the viewer opens."""
    out: dict = {"label": label}
    if verb_:
        out["verb"], out["args"] = verb_, args or {}
    if view:
        out["view"] = view
        if params:
            out["params"] = params
    return out


def checklist(db, project) -> list[dict]:
    srcs = db.rows("source", "ORDER BY created_at")
    total = len(srcs)
    steps: list[dict] = []

    def step(key, title, state, detail, actions=(), agent="", optional=False):
        steps.append({"key": key, "title": title, "state": state, "detail": detail, "actions": list(actions),
                      "agent": agent, "optional": optional})

    step("sources", "Add sources", "done" if total else "todo",
         f"{total} source(s)" if total else "Films, talks, podcasts: files, folders or links.",
         [_act("Browse for files", view="sources", params={"browse": 1}), _act("Open sources", view="sources")],
         "Add the films in <folder> to this project" if not total else "")

    no_tr = [s for s in srcs if not db.one("SELECT 1 FROM transcript WHERE source_id=?", (s["id"],))]
    acts = []
    for s in no_tr[:3]:
        if s["kind"] == "link":
            acts.append(_act(f"Captions for {s['ref']}", "transcript.fetch-captions", {"ref": s["ref"]}))
        else:
            acts.append(_act(f"Transcribe {s['ref']} (ASR)", "transcript.asr", {"ref": s["ref"]}))
    step("transcripts", "Transcripts", "todo" if total and len(no_tr) == total else "partial" if no_tr else
         ("done" if total else "todo"),
         f"{total - len(no_tr)}/{total} sources have one" if total else "Each source needs one to be searched and cut.",
         acts, f"Get transcripts for {', '.join(s['ref'] for s in no_tr[:5])}" if no_tr else "")

    named = _n(db, "SELECT COUNT(DISTINCT t.source_id) FROM segment s JOIN transcript t ON t.id=s.transcript_id "
                   "WHERE t.is_primary=1 AND s.person_id IS NOT NULL")
    marked = [s for s in srcs if not db.one("SELECT 1 FROM segment g JOIN transcript t ON t.id=g.transcript_id "
                                            "WHERE t.source_id=? AND t.is_primary=1 AND g.person_id IS NOT NULL LIMIT 1",
                                            (s["id"],)) and db.one("SELECT 1 FROM segment g JOIN transcript t ON t.id=g.transcript_id "
                                        "WHERE t.source_id=? AND t.is_primary=1 AND g.text LIKE '%>>%' LIMIT 1", (s["id"],))]
    acts = [_act(f"Name speakers in {s['ref']} from >> marks", view="room", params={"ref": s["ref"], "panel": "speakers"})
            for s in marked[:2]]
    step("speakers", "Speakers (optional)", "done" if named else "todo",
         f"{named}/{total} sources have named speakers" if total else "Who speaks when.",
         acts, "Name the speakers in my sources (use `speaker assign`, diarise only if needed)", optional=True)

    no_ch = [s for s in srcs if not db.one("SELECT 1 FROM chapter WHERE source_id=?", (s["id"],))]
    acts = [_act(f"Creator chapters for {s['ref']}", "chapter.seed", {"ref": s["ref"]})
            for s in no_ch[:2] if s["kind"] == "link"]
    step("chapters", "Chapters", "done" if total and not no_ch else "partial" if total and len(no_ch) < total else "todo",
         f"{total - len(no_ch)}/{total} sources have chapters" if total else "Scenes or topics, to find your way around.",
         acts, f"Write chapters for {', '.join(s['ref'] for s in no_ch[:5])}" if no_ch else "", optional=True)

    cuts = _n(db, "SELECT COUNT(*) FROM cut")
    cut_srcs = _n(db, "SELECT COUNT(DISTINCT source_id) FROM cut")
    step("cuts", "Cuts", "done" if cuts else "todo",
         f"{cuts} cut(s) from {cut_srcs} source(s)" if cuts else "Select a range in a source room and press C, or search.",
         [_act("Open the cut bin", view="cuts"), _act("Search", view="search")],
         "Suggest cuts about <theme> across my sources")

    js = db.rows("journey", "ORDER BY created_at")
    filled = [j for j in js if db.one("SELECT 1 FROM slot WHERE journey_id=?", (j["id"],))]
    open_js = [j for j in js if not db.one("SELECT 1 FROM export WHERE journey_id=? AND status='done' "
                                           "AND COALESCE(folder, '') NOT LIKE '%preview-%'", (j["id"],))]
    acts = [_act("Start a journey", view="journeys", params={"new": 1})]
    if open_js:
        acts.insert(0, _act(f"Continue {open_js[-1]['ref']}", view="journeys", params={"ref": open_js[-1]["ref"]}))
    step("journeys", "Journeys", "done" if filled else "partial" if js else "todo",
         f"{len(filled)} journey(s) with cuts" + (f", {len(js) - len(filled)} empty" if len(js) > len(filled) else "")
         if js else "Name it, say what it is for and where it goes: the journey studio guides you from there.",
         acts, "Build a journey from my cuts about <theme>")

    langs = _n(db, "SELECT COUNT(DISTINCT lang) FROM translation")
    step("languages", "Languages (optional)", "done" if langs else "todo",
         f"{langs} language(s) translated" if langs else "Translate a journey, then export it dubbed.",
         [_act("Translations", view="exports", params={"tab": "translations"})] if filled else [],
         "Translate J1 into Amharic and Swahili", optional=True)

    done = _n(db, "SELECT COUNT(*) FROM export WHERE status='done' AND COALESCE(folder, '') NOT LIKE '%preview-%'")
    step("exports", "Exports", "done" if done else "todo",
         f"{done} export(s) done" if done else "Render a journey in your formats and languages.",
         [_act(f"Export {filled[0]['ref']}", view="journeys", params={"ref": filled[0]["ref"], "step": "export"})]
         if filled else [],
         "Export J1 as shorts and landscape")
    return steps


def _folder(path: Path) -> dict:
    files = [p for p in path.rglob("*") if p.is_file()] if path.exists() else []
    return {"path": str(path), "files": len(files), "mb": round(sum(p.stat().st_size for p in files) / 1e6, 1)}


@verb("project.checklist", NoInput, examples=["recomp project checklist"])
def project_checklist(ctx: Ctx, inp: NoInput):
    """Where the project stands, step by step (sources → transcripts → speakers → chapters → cuts → journeys →
    languages → exports), each with its next actions. The viewer's home page shows the same list."""
    from .journey import guide
    p = ctx.project
    steps = checklist(ctx.db, p)
    nxt = next((s for s in steps if s["state"] != "done" and not s["optional"]), None)
    journeys = []
    for j in ctx.db.rows("journey", "ORDER BY created_at DESC"):
        g = guide(ctx, j)
        step_ = next((s for s in g["steps"] if s["key"] == g["next"]), None)
        journeys.append({"ref": j["ref"], "title": j["title"], "intent": j["intent"], "formats": g["formats"],
                         "slots": g["slots"], "sources": g["sources"], "duration_s": g["duration_s"],
                         "done": g["done"], "of": len(g["steps"]), "next": g["next"],
                         "next_title": step_["title"] if step_ else None,
                         "states": [s["state"] for s in g["steps"]]})
    return {"project": p.summary(), "steps": steps, "next": nxt["key"] if nxt else None, "journeys": journeys,
            "folders": {k: _folder(p.root / k) for k in ("sources", "recipes", "exports")}}


class RevealIn(BaseModel):
    what: str = Field("root", description="root, sources, recipes, exports, an export (X3), or a path inside the project",
                      json_schema_extra={"pos": 0})


def open_in_file_manager(path: Path) -> None:
    if os.environ.get("RECOMP_NO_REVEAL"):
        return
    if sys.platform == "win32":
        if path.is_file():
            subprocess.Popen(["explorer", "/select,", str(path)])
        else:
            os.startfile(str(path))  # noqa: S606 — opens a folder of the user's own project
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R" if path.is_file() else "", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path if path.is_dir() else path.parent)])


@verb("project.reveal", RevealIn, examples=["recomp project reveal exports", "recomp project reveal X3"])
def project_reveal(ctx: Ctx, inp: RevealIn):
    """Open a project folder (or an export's folder) in the file manager on this computer."""
    root = ctx.project.root
    w = inp.what.strip()
    if w in ("", "root", "project"):
        path = root
    elif w in ("sources", "recipes", "exports", "cache", "music"):
        path = ctx.project.dir(w)
    elif w.upper().startswith("X") and w[1:].isdigit():
        path = Path(refs.resolve(ctx.db, w.upper(), "export")[1]["folder"])
    else:
        path = (root / w).resolve()
        if root.resolve() not in path.parents and path != root.resolve():
            raise RecompError("E_INVALID", "only folders inside the project can be revealed", hint="e.g. exports, X3")
    if not path.exists():
        raise RecompError("E_NOT_FOUND", f"{path} does not exist yet")
    open_in_file_manager(path)
    return {"opened": str(path)}


class BrowseIn(BaseModel):
    path: str | None = Field(None, description="Folder to list (default: drives on Windows, else the home folder)",
                             json_schema_extra={"pos": 0})
    all: bool = Field(False, description="Show every file, not only media and subtitles")


@verb("source.browse", BrowseIn, needs_project=False, examples=[r"recomp source browse D:\Movies"])
def source_browse(ctx: Ctx, inp: BrowseIn):
    """List a folder's subfolders, media and subtitle files (read-only), to pick sources without typing paths."""
    if not inp.path:
        if sys.platform == "win32":
            drives = [f"{d}:\\" for d in string.ascii_uppercase if Path(f"{d}:\\").exists()]
            return {"path": None, "parent": None, "dirs": [{"name": d, "path": d} for d in drives], "files": []}
        base = Path.home()
    else:
        base = Path(inp.path).expanduser()
    if not base.is_dir():
        raise RecompError("E_NOT_FOUND", f"not a folder: {base}")
    dirs, files = [], []
    try:
        entries = sorted(base.iterdir(), key=lambda p: p.name.lower())
    except PermissionError as exc:
        raise RecompError("E_INVALID", f"cannot read {base}: {exc}")
    for p in entries:
        if p.name.startswith(".") or p.name.startswith("$"):
            continue
        try:
            if p.is_dir():
                dirs.append({"name": p.name, "path": str(p)})
            elif p.is_file():
                ext = p.suffix.lower()
                kind = "media" if ext in ff.MEDIA_EXTS else "subtitle" if ext in ff.SUB_EXTS else None
                if kind or inp.all:
                    files.append({"name": p.name, "path": str(p), "kind": kind or "other",
                                  "mb": round(p.stat().st_size / 1e6, 1)})
        except OSError:
            continue
    parent = str(base.parent) if base.parent != base else None
    return {"path": str(base), "parent": parent, "dirs": dirs, "files": files,
            "media": sum(1 for f in files if f["kind"] == "media")}
