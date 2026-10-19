"""Rights statuses (D-23): every source is ``campaign``, ``permitted`` or ``private``.

* ``campaign``: a clipping program run or authorised by the rights holder covers it (terms linked as evidence).
* ``permitted``: the creator's permission is verified (evidence linked).
* ``private``: everything else. Watching, ingesting, cutting, journeys and recipes all work fully; only the posting
  queue refuses it, and making a recipe public asks the user first.
"""

from __future__ import annotations

STATUSES = ("campaign", "permitted", "private")
POSTABLE = ("campaign", "permitted")


def status(src: dict) -> str:
    s = (src.get("rights") or {}).get("status")
    return s if s in STATUSES else "private"


def sources_of_journey(db, journey_id: str) -> list[dict]:
    rows = db.all("SELECT DISTINCT c.source_id FROM slot sl JOIN cut c ON c.id=sl.cut_id WHERE sl.journey_id=?", (journey_id,))
    return [db.get("source", r["source_id"]) for r in rows]


def sources_of_export(db, exp: dict) -> list[dict]:
    if exp.get("journey_id"):
        return sources_of_journey(db, exp["journey_id"])
    if exp.get("cut_id"):
        c = db.get("cut", exp["cut_id"])
        return [db.get("source", c["source_id"])] if c else []
    return []


def summary(srcs: list[dict]) -> list[dict]:
    return [{"ref": s["ref"], "title": s["title"], "creator": s["creator"], "status": status(s),
             "evidence": (s.get("rights") or {}).get("evidence"), "owner": (s.get("rights") or {}).get("owner")}
            for s in srcs]


def private(srcs: list[dict]) -> list[dict]:
    return [s for s in summary(srcs) if s["status"] == "private"]


def public_consequences(priv: list[dict]) -> list[str]:
    """What making a recipe public changes for its private sources (shown before the user answers)."""
    out = []
    for s in priv:
        name = s["creator"] or s["owner"] or "its creator"
        out.append(f"{s['ref']} \"{s['title']}\" ({name}) gets a public page on the hub, plays to strangers through "
                   f"the official embed, and carries your name next to {name}'s.")
    return out
