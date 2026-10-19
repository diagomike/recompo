"""The studio store: ``studio.db`` in the studio home, for what spans projects (follows, inbox, library, topics).

It is a :class:`~recomp.core.store.Database` with its own migrations, so writes get the same op log, undo,
precedence guard and events as a project's (``recomp op undo --studio``).
"""

from __future__ import annotations

import json
import time
from typing import Any

from . import config, schema
from .store import Database

FILE = "studio.db"


def open_db() -> Database:
    return Database(config.home() / FILE, schema.STUDIO_MIGRATIONS)


def get_state(db: Database, key: str, default: Any = None) -> Any:
    row = db.one("SELECT value FROM ui_state WHERE key=?", (key,))
    return json.loads(row["value"]) if row else default


def set_state(db: Database, key: str, value: Any) -> None:
    db.conn.execute("INSERT INTO ui_state(key, value, updated_at) VALUES(?,?,?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
                    (key, json.dumps(value, ensure_ascii=False), time.time()))
