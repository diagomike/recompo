"""Writing transcripts: one op-logged transcript row, bulk (not op-logged) segments and words."""

from __future__ import annotations

import time

from ..core.store import Tx


def add_transcript(tx: Tx, source: dict, segments: list[dict], origin: str, language: str | None,
                   label: str = "", model: str | None = None, make_primary: bool | None = None,
                   stats: dict | None = None) -> dict:
    has_primary = tx.one("SELECT 1 FROM transcript WHERE source_id=? AND is_primary=1", (source["id"],))
    primary = (not has_primary) if make_primary is None else make_primary
    if primary and has_primary:
        for old in tx.all("SELECT id FROM transcript WHERE source_id=? AND is_primary=1", (source["id"],)):
            tx.update("transcript", old["id"], {"is_primary": 0})
    has_words = any(s.get("words") for s in segments)
    words_total = sum(len(s.get("words") or []) for s in segments)
    spoken = sum(max(0.0, s["end"] - s["start"]) for s in segments)
    st = {"segments": len(segments), "words": words_total, "spoken_s": round(spoken, 1),
          "first": segments[0]["start"] if segments else None, "last": segments[-1]["end"] if segments else None}
    st.update(stats or {})
    tr = tx.insert("transcript", {"source_id": source["id"], "origin": origin, "language": language,
                                  "label": label, "model": model, "is_primary": int(primary),
                                  "has_words": int(has_words), "stats": st},
                   ref_kind=f"{source['ref']}.t")
    tx.redoable = False  # segments are bulk data; re-run the import instead of redo
    write_segments(tx, tr["id"], segments)
    return tr


def write_segments(tx: Tx, transcript_id: str, segments: list[dict]) -> None:
    now = time.time()
    actor = tx.actor
    conn = tx.conn
    for i, s in enumerate(segments):
        cur = conn.execute(
            'INSERT INTO segment(transcript_id, idx, start, "end", text, speaker, conf, created_by, prov, '
            "created_at, updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (transcript_id, i, float(s["start"]), float(s["end"]), s["text"], s.get("speaker"),
             s.get("conf"), actor, "{}", now, now))
        words = s.get("words") or []
        if words:
            conn.executemany('INSERT INTO word(segment_id, idx, start, "end", text, prob) VALUES(?,?,?,?,?,?)',
                             [(cur.lastrowid, j, float(w["start"]), float(w["end"]), w["text"], w.get("prob"))
                              for j, w in enumerate(words)])


def primary(db, source_id: str) -> dict | None:
    rows = db.rows("transcript", "WHERE source_id=? ORDER BY is_primary DESC, created_at DESC LIMIT 1", (source_id,))
    return rows[0] if rows else None
