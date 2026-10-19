"""Background follow checks while the studio runs (P17-Q6: every ``research.check_every_h`` hours; no OS scheduler)."""

from __future__ import annotations

import threading
import time

from ..core import config, studio

TICK_S = 600  # look every 10 minutes whether a check is due


def due(now: float | None = None) -> bool:
    every_h = float(config.get("research.check_every_h") or 0)
    if every_h <= 0:
        return False
    db = studio.open_db()
    try:
        if not db.scalar("SELECT COUNT(*) FROM follow"):
            return False
        last = (studio.get_state(db, "last_check") or {}).get("at") or 0
    finally:
        db.close()
    return (now or time.time()) - last >= every_h * 3600


def run_once() -> dict | None:
    """One check if due; the result envelope, or None."""
    if not due():
        return None
    from .. import registry
    return registry.run("follow.check", {}, actor="machine")


def start() -> threading.Thread:
    def loop():
        time.sleep(30)  # let the server come up first
        while True:
            try:
                run_once()
            except Exception:  # noqa: BLE001 — a failed check is recorded on the follow; never stop the loop
                pass
            time.sleep(TICK_S)
    t = threading.Thread(target=loop, name="follow-checks", daemon=True)
    t.start()
    return t
