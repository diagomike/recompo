"""Studio home: settings, the project registry and the hub login.

``RECOMP_HOME`` overrides the location (tests always set it to a temp folder).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

DEFAULTS: dict[str, Any] = {
    "projects_root": r"C:\Recomposer\projects",
    "worker": {
        "python": r"D:\LangBridgeLocal\.venv\Scripts\python.exe",
        "hf_home": r"D:\LangBridgeLocal\cache\hf",
        "asr_model": "mobiuslabsgmbh/faster-whisper-large-v3-turbo",
        "asr_compute_type": "int8",
        "threads": 0,
        "default_backend": "local",
        "remote_folder": "",
    },
    "hub": {"url": "http://127.0.0.1:8790"},
    "studio": {"host": "127.0.0.1", "port": 8770},
    "tts": {
        "voices": {
            "en": "en-US-AriaNeural",
            "am": "am-ET-MekdesNeural",
            "sw": "sw-KE-ZuriNeural",
            "fr": "fr-FR-DeniseNeural",
            "so": "so-SO-UbaxNeural",
            "es": "es-ES-ElviraNeural",
            "ar": "ar-SA-ZariyahNeural",
        },
        "mms": {"om": "facebook/mms-tts-orm"},
    },
    "render": {"cache_max_gb": 8},
    "network": {"yt_sleep_subtitles": 3, "yt_retries": 4, "link_video": "full", "link_video_height": 720},
    # P17 research wing: follow checks run this often while the studio is open (0 = only on request);
    # a follow's first check puts this many of the newest items in the inbox; backfill goes back this far;
    # contact: your email or URL for APIs whose policy asks for it (Wikipedia's most-viewed list); empty = skip them.
    "research": {"check_every_h": 2, "first_check_items": 3, "backfill_since": "2y", "contact": ""},
}


def home() -> Path:
    env = os.environ.get("RECOMP_HOME")
    path = Path(env) if env else Path.home() / ".recomp"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _read(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _write(path: Path, value: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def _merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load() -> dict:
    return _merge(DEFAULTS, _read(home() / "config.json", {}))


def get(dotted: str, default: Any = None) -> Any:
    node: Any = load()
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def set_value(dotted: str, value: Any) -> dict:
    path = home() / "config.json"
    data = _read(path, {})
    node = data
    parts = dotted.split(".")
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node[parts[-1]] = value
    _write(path, data)
    return load()


# ---- project registry -------------------------------------------------------------------

def registry() -> dict:
    return _read(home() / "projects.json", {"current": None, "projects": {}})


def save_registry(reg: dict) -> None:
    _write(home() / "projects.json", reg)


def register_project(name: str, path: Path, make_current: bool = True) -> dict:
    reg = registry()
    reg["projects"][name] = {"path": str(path)}
    if make_current:
        reg["current"] = name
    save_registry(reg)
    return reg


def env_value(key: str) -> str | None:
    """Read a user-supplied key from the environment or ``<home>/.env``. Never logged."""
    if os.environ.get(key):
        return os.environ[key]
    path = home() / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k.strip() == key:
                return v.strip().strip('"').strip("'")
    return None
