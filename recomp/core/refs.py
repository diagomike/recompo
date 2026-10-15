"""Short references (``S1``, ``S1.c4``, ``S1.t2``, ``C17``, ``J2``, ``J2#3``, ``O5``, ``M1``,
``B1``, ``P3``, ``X4``, ``job12``) and their resolution to rows."""

from __future__ import annotations

import re

from ..envelope import RecompError
from .store import Database

PATTERNS = [
    (re.compile(r"^S\d+\.c\d+$"), "chapter"),
    (re.compile(r"^S\d+\.t\d+$"), "transcript"),
    (re.compile(r"^S\d+$"), "source"),
    (re.compile(r"^C\d+$"), "cut"),
    (re.compile(r"^J\d+$"), "journey"),
    (re.compile(r"^O\d+$"), "overlay"),
    (re.compile(r"^M\d+$"), "music_track"),
    (re.compile(r"^B\d+$"), "music_bed"),
    (re.compile(r"^P\d+$"), "person"),
    (re.compile(r"^X\d+$"), "export"),
    (re.compile(r"^job\d+$"), "job"),
]
SLOT = re.compile(r"^(J\d+)#(\d+)$")
NAMES = {"source": "source", "chapter": "chapter", "transcript": "transcript", "cut": "cut",
         "journey": "journey", "overlay": "overlay", "music_track": "music track", "music_bed": "music bed",
         "person": "person", "export": "export", "job": "job", "slot": "slot"}


def kind_of(ref: str) -> str | None:
    ref = ref.strip()
    if SLOT.match(ref):
        return "slot"
    for pat, table in PATTERNS:
        if pat.match(ref):
            return table
    return None


def resolve(db: Database, ref: str, expect: str | tuple[str, ...] | None = None) -> tuple[str, dict]:
    ref = (ref or "").strip()
    expected = (expect,) if isinstance(expect, str) else expect
    m = SLOT.match(ref)
    if m:
        journey = db.by_ref("journey", m.group(1))
        if journey is None:
            raise RecompError("E_NOT_FOUND", f"journey {m.group(1)} not found")
        slots = db.rows("slot", "WHERE journey_id=? ORDER BY pos", (journey["id"],))
        n = int(m.group(2))
        if not 1 <= n <= len(slots):
            raise RecompError("E_NOT_FOUND", f"{ref}: {m.group(1)} has {len(slots)} slot(s)")
        table, row = "slot", slots[n - 1]
    else:
        table = kind_of(ref)
        row = None
        if table:
            row = db.by_ref(table, ref)
        elif expected:
            for t in expected:  # ULID or name fallback
                row = db.get(t, ref)
                if row is None and t == "profile":
                    row = db.rows("profile", "WHERE name=?", (ref,))[:1]
                    row = row[0] if row else None
                if row is not None:
                    table = t
                    break
        if row is None:
            what = NAMES.get(table or "", (expected or ["item"])[0])
            raise RecompError("E_NOT_FOUND", f"{what} {ref!r} not found",
                              hint="List what exists with `recomp context` or the noun's `list` verb.")
    if expected and table not in expected:
        raise RecompError("E_INVALID", f"{ref} is a {NAMES.get(table, table)}, expected "
                                       f"{' or '.join(NAMES.get(e, e) for e in expected)}")
    return table, row


def source(db: Database, ref: str) -> dict:
    return resolve(db, ref, "source")[1]


def slot_ref(db: Database, slot: dict) -> str:
    journey = db.get("journey", slot["journey_id"])
    ids = [r["id"] for r in db.all("SELECT id FROM slot WHERE journey_id=? ORDER BY pos", (slot["journey_id"],))]
    return f"{journey['ref']}#{ids.index(slot['id']) + 1}"
