from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from recomp import registry


@pytest.fixture(autouse=True)
def recomp_home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("RECOMP_HOME", str(home))
    monkeypatch.delenv("RECOMP_PROJECT", raising=False)
    monkeypatch.setenv("RECOMP_ACTOR", "agent")
    # Keep tests away from real projects and the real worker unless a test opts in.
    home.mkdir()
    (home / "config.json").write_text(json.dumps({"projects_root": str(tmp_path / "projects")}), encoding="utf-8")
    return home


@pytest.fixture
def proj(tmp_path):
    root = tmp_path / "projects" / "p1"
    env = registry.run("project.init", {"path": str(root), "kind": "mixed", "agent_kit": False})
    assert env["ok"], env
    return root


def run(verb: str, args: dict | None = None, project: Path | None = None, actor: str = "agent", **kw) -> dict:
    env = registry.run(verb, args or {}, actor=actor, project_arg=str(project) if project else None, **kw)
    return env


def ok(verb: str, args: dict | None = None, project: Path | None = None, actor: str = "agent", **kw):
    env = run(verb, args, project, actor, **kw)
    assert env["ok"], json.dumps(env, indent=1, default=str)
    return env["data"]


@pytest.fixture
def R():
    return run


@pytest.fixture
def OK():
    return ok
