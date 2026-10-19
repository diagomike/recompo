"""Projects: create, switch, list, show, and install the agent kit into a project folder."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from ..core import config
from ..core import project as P
from ..envelope import RecompError, Result
from ..registry import Ctx, NoInput, verb
from . import agentkit


class InitIn(BaseModel):
    path: str = Field(..., description="Folder for the project (relative names go under projects_root)",
                      json_schema_extra={"pos": 0})
    name: str | None = Field(None, description="Display name (default: folder name)")
    kind: str = Field("mixed", description="movies, channel, speaker, topic or mixed")
    languages: list[str] = Field(default_factory=lambda: ["en"], description="Working languages, e.g. en,am")
    agent_kit: bool = Field(True, description="Write AGENTS.md, CLAUDE.md, skills and .mcp.json into the folder")


@verb("project.init", InitIn, effect="write", needs_project=False,
      examples=["recomp project init dark-knight --kind movies",
                r"recomp project init C:\Recomposer\projects\alex-oconnor --kind channel"])
def project_init(ctx: Ctx, inp: InitIn):
    """Create a project folder and make it the current project."""
    proj = P.create(Path(inp.path), inp.name, inp.kind, inp.languages)
    try:
        written = agentkit.install(proj.root) if inp.agent_kit else []
        config.register_project(proj.name, proj.root)
        from ..render.profiles import seed_profiles
        seed_profiles(proj)
        return Result(data={**proj.summary(), "agent_kit": written},
                      next=[f'recomp source add "<file, folder, glob or link>"', "recomp context"])
    finally:
        proj.close()


class UseIn(BaseModel):
    target: str = Field(..., description="Project name (from `project list`) or folder",
                        json_schema_extra={"pos": 0})


@verb("project.use", UseIn, effect="write", needs_project=False)
def project_use(ctx: Ctx, inp: UseIn):
    """Make a project the current one (by registered name or by folder)."""
    reg = config.registry()
    if inp.target in reg["projects"]:
        root = Path(reg["projects"][inp.target]["path"])
    else:
        root = Path(inp.target)
    proj = P.Project(root)
    try:
        config.register_project(proj.name, proj.root)
        return proj.summary()
    finally:
        proj.close()


@verb("project.list", NoInput, needs_project=False)
def project_list(ctx: Ctx, inp: NoInput):
    """Registered projects and which one is current."""
    reg = config.registry()
    out = []
    for name, info in sorted(reg["projects"].items()):
        exists = (Path(info["path"]) / P.MANIFEST).exists()
        out.append({"name": name, "path": info["path"], "current": name == reg.get("current"),
                    "exists": exists})
    return {"current": reg.get("current"), "projects": out}


@verb("project.forget", UseIn, effect="write", needs_project=False)
def project_forget(ctx: Ctx, inp: UseIn):
    """Remove a project from the studio's list (its folder and files are left untouched)."""
    reg = config.registry()
    name = inp.target if inp.target in reg["projects"] else next(
        (n for n, i in reg["projects"].items() if Path(i["path"]).name == inp.target or i["path"] == inp.target), None)
    if name is None:
        raise RecompError("E_NOT_FOUND", f"{inp.target!r} is not in the project list")
    path = reg["projects"].pop(name)["path"]
    if reg.get("current") == name:
        reg["current"] = None
    config.save_registry(reg)
    return {"forgotten": name, "folder_kept": path}


@verb("project.show", NoInput)
def project_show(ctx: Ctx, inp: NoInput):
    """The current project's manifest and folder."""
    return {**ctx.project.summary(), "meta": ctx.project.meta}


class SetIn(BaseModel):
    name: str | None = None
    kind: str | None = None
    languages: list[str] | None = None
    description: str | None = None
    themes: list[str] | None = Field(None, description="What this project is about: cut suggestions for new posts "
                                                       "from followed creators use these (e.g. consciousness,free will)")


@verb("project.set", SetIn, effect="write", examples=['recomp project set --themes "consciousness,free will"'])
def project_set(ctx: Ctx, inp: SetIn):
    """Change the project's name, kind, languages, description or themes."""
    meta = ctx.project.meta
    for k, v in inp.model_dump(exclude_none=True).items():
        if k == "kind" and v not in P.KINDS:
            raise RecompError("E_INVALID", f"kind must be one of {', '.join(P.KINDS)}")
        meta[k] = v
    ctx.project.save_meta()
    return ctx.project.summary()


class BackupIn(BaseModel):
    out: str | None = Field(None, description="Zip file to write (default: <project>/../<name>-backup-<date>.zip)")
    exports: bool = Field(False, description="Include rendered exports (large)")


@verb("project.backup", BackupIn, effect="write")
def project_backup(ctx: Ctx, inp: BackupIn):
    """Zip the project's work (database, recipes, music with licences, captions) without source media or caches.
    Restore by unzipping anywhere and `recomp project use <folder>`, then `source relink` if media moved."""
    import sqlite3
    import time
    import zipfile
    root = ctx.project.root
    out = Path(inp.out) if inp.out else root.parent / f"{root.name}-backup-{time.strftime('%Y%m%d-%H%M')}.zip"
    snap = root / "cache" / "backup.db"
    snap.parent.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(str(root / P.DB_NAME))
    dst = sqlite3.connect(str(snap))
    src.backup(dst)  # a consistent copy even while the studio is running
    src.close()
    dst.close()
    n = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(root / P.MANIFEST, P.MANIFEST)
        z.write(snap, P.DB_NAME)
        for sub in ("recipes", "music"):
            for f in (root / sub).rglob("*"):
                if f.is_file():
                    z.write(f, f.relative_to(root).as_posix())
                    n += 1
        for f in (root / "sources").rglob("*"):
            if f.is_file() and f.suffix in (".json", ".json3", ".vtt", ".srt"):
                z.write(f, f.relative_to(root).as_posix())
                n += 1
        if inp.exports:
            for f in (root / "exports").rglob("*"):
                if f.is_file():
                    z.write(f, f.relative_to(root).as_posix())
                    n += 1
        for f in [root / "AGENTS.md", root / "CLAUDE.md"]:
            if f.exists():
                z.write(f, f.name)
    snap.unlink(missing_ok=True)
    return {"zip": str(out), "files": n + 2, "mb": round(out.stat().st_size / 1e6, 2)}


class KitIn(BaseModel):
    overwrite: bool = Field(True, description="Overwrite existing kit files (your own CLAUDE.md notes below the marker are kept)")


@verb("project.agent-kit", KitIn, effect="write")
def project_agent_kit(ctx: Ctx, inp: KitIn):
    """(Re)install the agent kit into the project folder: AGENTS.md, CLAUDE.md, skills, .mcp.json."""
    return {"written": agentkit.install(ctx.project.root, overwrite=inp.overwrite)}
