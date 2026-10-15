"""A project is a folder: ``recomp.project.json`` + ``recomp.db`` + working subfolders."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from ..envelope import RecompError
from . import config
from .ids import ulid
from .store import Database

MANIFEST = "recomp.project.json"
DB_NAME = "recomp.db"
SUBDIRS = ("sources", "cache", "music", "recipes", "exports", "jobs")
KINDS = ("movies", "channel", "speaker", "topic", "mixed")


class Project:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        manifest = self.root / MANIFEST
        if not manifest.exists():
            raise RecompError("E_NO_PROJECT", f"{self.root} is not a Recomposer project",
                              hint="Create one with `recomp project init <folder>`.")
        self.meta = json.loads(manifest.read_text(encoding="utf-8"))
        self._db: Database | None = None

    @property
    def name(self) -> str:
        return self.meta.get("name", self.root.name)

    @property
    def db(self) -> Database:
        if self._db is None:
            self._db = Database(self.root / DB_NAME)
        return self._db

    def close(self) -> None:
        if self._db is not None:
            self._db.close()
            self._db = None

    def dir(self, *parts: str) -> Path:
        path = self.root.joinpath(*parts)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def save_meta(self) -> None:
        tmp = self.root / (MANIFEST + ".tmp")
        tmp.write_text(json.dumps(self.meta, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self.root / MANIFEST)

    def summary(self) -> dict:
        return {"name": self.name, "path": str(self.root), "kind": self.meta.get("kind"),
                "languages": self.meta.get("languages", ["en"]), "id": self.meta.get("id")}


def slug(text: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()
    return s or "project"


def create(root: Path, name: str | None, kind: str, languages: list[str]) -> Project:
    root = Path(root).expanduser()
    if not root.is_absolute():
        root = Path(config.get("projects_root")) / root
    root = root.resolve()
    if (root / MANIFEST).exists():
        raise RecompError("E_EXISTS", f"a project already exists at {root}",
                          hint=f"Open it with `recomp project use {root}`.")
    if kind not in KINDS:
        raise RecompError("E_INVALID", f"kind must be one of {', '.join(KINDS)}")
    root.mkdir(parents=True, exist_ok=True)
    meta = {"recomp": 1, "id": ulid(), "name": name or root.name, "kind": kind,
            "languages": languages or ["en"]}
    (root / MANIFEST).write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    for d in SUBDIRS:
        (root / d).mkdir(exist_ok=True)
    project = Project(root)
    project.db  # creates and migrates the database
    return project


def find_upwards(start: Path) -> Path | None:
    cur = start.resolve()
    for candidate in [cur, *cur.parents]:
        if (candidate / MANIFEST).exists():
            return candidate
    return None


def resolve(explicit: str | None = None) -> Project:
    """--project flag > RECOMP_PROJECT > a project folder at or above cwd > the current project."""
    target = explicit or os.environ.get("RECOMP_PROJECT")
    if target:
        reg = config.registry()
        if target in reg["projects"]:
            return Project(Path(reg["projects"][target]["path"]))
        return Project(Path(target))
    found = find_upwards(Path.cwd())
    if found:
        return Project(found)
    reg = config.registry()
    current = reg.get("current")
    if current and current in reg["projects"]:
        return Project(Path(reg["projects"][current]["path"]))
    raise RecompError("E_NO_PROJECT", "no project selected",
                      hint="Run `recomp project list`, then `recomp project use <name>`, "
                           "or `recomp project init <folder>`.")
