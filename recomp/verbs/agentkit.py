"""Install the agent kit (AGENTS.md, CLAUDE.md, skills, .mcp.json, permissions) into a folder.

Templates live in ``recomp/agent_kit``. ``{{RECOMP}}`` becomes the absolute path of the
``recomp`` executable, ``{{PROJECT}}`` the project folder and ``{{REPO}}`` this code's folder.
A ``CLAUDE.md`` keeps anything you wrote below the ``<!-- your notes -->`` marker.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent / "agent_kit"
REPO = Path(__file__).resolve().parents[2]
NOTES_MARKER = "<!-- your notes below this line are kept when the kit is reinstalled -->"

READ_VERBS = ["context", "help", "doctor", "search", "transcript read", "transcript outline",
              "transcript list", "source list", "source show", "source status", "chapter list",
              "cut list", "cut show", "cut suggest", "journey list", "journey show", "journey validate",
              "op log", "ui selection", "ui notes", "job list", "job show", "job wait", "job tail",
              "music search", "profile list", "profile show", "export status", "speaker list",
              "lang voices", "hub feed", "hub whoami", "project list", "project show", "recipe show"]


def recomp_exe() -> str:
    scripts = Path(sys.executable).parent
    for name in ("recomp.exe", "recomp"):
        if (scripts / name).exists():
            return str(scripts / name)
    return "recomp"


def _render(text: str, root: Path) -> str:
    return (text.replace("{{RECOMP}}", recomp_exe().replace("\\", "/"))
                .replace("{{PROJECT}}", str(root).replace("\\", "/"))
                .replace("{{REPO}}", str(REPO).replace("\\", "/")))


def install(root: Path, overwrite: bool = True, repo_mode: bool = False) -> list[str]:
    root = Path(root)
    written: list[str] = []
    for src in sorted(KIT.rglob("*")):
        if src.is_dir() or "__pycache__" in src.parts:
            continue
        rel = src.relative_to(KIT)
        if repo_mode and rel.name == "AGENTS.project.md":
            continue
        name = rel.as_posix()
        if name == "AGENTS.project.md":
            rel = Path("AGENTS.md")
        dest = root / rel
        text = _render(src.read_text(encoding="utf-8"), root)
        if dest.name == "CLAUDE.md" and dest.exists():
            old = dest.read_text(encoding="utf-8")
            if NOTES_MARKER in old:
                text = text.split(NOTES_MARKER)[0] + NOTES_MARKER + old.split(NOTES_MARKER, 1)[1]
        if dest.exists() and not overwrite:
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")
        written.append(rel.as_posix())
    if not repo_mode:
        mcp = {"mcpServers": {"recomposer": {"command": recomp_exe(), "args": ["mcp"],
                                             "env": {"RECOMP_PROJECT": str(root)}}}}
        (root / ".mcp.json").write_text(json.dumps(mcp, indent=2), encoding="utf-8")
        written.append(".mcp.json")
    settings_path = root / ".claude" / "settings.json"
    settings = {}
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            settings = {}
    allow = set(settings.get("permissions", {}).get("allow", []))
    for v in READ_VERBS:
        allow.add(f"Bash(recomp {v}:*)")
    allow.add("mcp__recomposer__context")
    settings.setdefault("permissions", {})["allow"] = sorted(allow)
    if not repo_mode:
        settings["enabledMcpjsonServers"] = sorted(set(settings.get("enabledMcpjsonServers", [])) | {"recomposer"})
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    written.append(".claude/settings.json")
    return written


def write_shims(bin_dir: Path) -> list[str]:
    """Write ``recomp`` (sh) and ``recomp.cmd`` launchers into a folder on PATH."""
    bin_dir.mkdir(parents=True, exist_ok=True)
    exe = recomp_exe()
    sh = bin_dir / "recomp"
    sh.write_text(f'#!/bin/sh\nexec "{exe.replace(chr(92), "/")}" "$@"\n', encoding="utf-8", newline="\n")
    cmd = bin_dir / "recomp.cmd"
    cmd.write_text(f'@echo off\r\n"{exe}" %*\r\n', encoding="utf-8", newline="")
    return [str(sh), str(cmd)]


def copy_tree(src: Path, dest: Path) -> None:
    shutil.copytree(src, dest, dirs_exist_ok=True)
