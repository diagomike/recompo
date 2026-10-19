"""The studio library: followed creators' back-catalogue transcripts (text only), searchable across all of them."""

from __future__ import annotations

import json

from ..core.store import Tx
from ..core.timecode import clock
from ..verbs.search import fts_query


def add_doc(tx: Tx, follow: dict | None, key: str, meta: dict, segments: list[dict]) -> dict:
    """One episode's transcript into the library (the doc row is op-logged; its lines are bulk data)."""
    spoken = sum(max(0.0, s["end"] - s["start"]) for s in segments)
    doc = tx.insert("lib_doc", {
        "follow_id": follow["id"] if follow else None, "key": key,
        "creator": meta.get("creator") or (follow["name"] if follow else ""), "title": meta.get("title", ""),
        "published": meta.get("published"), "url": meta.get("url", ""), "video_id": meta.get("video_id"),
        "route": meta.get("route") or {}, "language": meta.get("language"),
        "stats": {"lines": len(segments), "spoken_s": round(spoken, 1),
                  "speakers": sorted({s["speaker"] for s in segments if s.get("speaker")})[:12],
                  "chapters": meta.get("chapters") or []}})
    tx.redoable = False
    tx.conn.executemany('INSERT INTO lib_seg(doc_id, idx, start, "end", speaker, text) VALUES(?,?,?,?,?,?)',
                        [(doc["id"], i, float(s["start"]), float(s["end"]), s.get("speaker"), s["text"])
                         for i, s in enumerate(segments)])
    return doc


def remove_doc(tx: Tx, doc: dict) -> None:
    """Not undoable (the lines are bulk data): `follow backfill` fetches a removed transcript again."""
    tx.conn.execute("DELETE FROM lib_seg WHERE doc_id=?", (doc["id"],))
    tx.delete("lib_doc", doc["id"], log=False)


def search(db, query: str, creators: list[str] | None = None, since: str | None = None, until: str | None = None,
           limit: int = 20, context: int = 1, mode: str = "auto") -> dict:
    """Where the followed creators said something: hits with the episode, time, speaker and a link at that moment."""
    modes = ["all", "any"] if mode == "auto" else [mode]
    rows, used = [], modes[0]
    for m in modes:
        q = fts_query(query, m)
        if not q:
            break
        sql = ('SELECT s.id, s.doc_id, s.idx, s.start, s."end", s.speaker, d.ref, d.creator, d.title, d.published, '
               "d.url, d.video_id, d.route, bm25(lib_seg_fts) AS score, snippet(lib_seg_fts, 0, '[', ']', '…', 24) AS snip "
               "FROM lib_seg_fts JOIN lib_seg s ON s.id=lib_seg_fts.rowid JOIN lib_doc d ON d.id=s.doc_id "
               "WHERE lib_seg_fts MATCH ?")
        params: list = [q]
        if creators:
            sql += f" AND d.creator IN ({','.join('?' * len(creators))})"
            params += creators
        if since:
            sql += " AND d.published >= ?"
            params.append(since)
        if until:
            sql += " AND d.published <= ?"
            params.append(until)
        rows = db.all(sql + " ORDER BY score LIMIT ?", (*params, limit))
        used = m
        if rows:
            break
    hits = []
    for r in rows:
        ctx = db.all('SELECT start, "end", speaker, text FROM lib_seg WHERE doc_id=? AND idx BETWEEN ? AND ? ORDER BY idx',
                     (r["doc_id"], r["idx"] - context, r["idx"] + context))
        route = json.loads(r["route"]) if r["route"] else {}
        hits.append({"doc": r["ref"], "creator": r["creator"], "title": r["title"], "published": r["published"],
                     "at": clock(r["start"]), "start": round(r["start"], 2), "speaker": r["speaker"], "match": r["snip"],
                     "context": " ".join(c["text"] for c in ctx), "timing": route.get("timing"),
                     "link": watch_link(r["video_id"], r["start"]) if r["video_id"] and route.get("timing") == "video"
                     else r["url"]})
    by_creator: dict[str, int] = {}
    for h in hits:
        by_creator[h["creator"]] = by_creator.get(h["creator"], 0) + 1
    return {"query": query, "mode": used, "hits": hits, "by_creator": by_creator}


def watch_link(video_id: str, start: float) -> str:
    return f"https://youtu.be/{video_id}?t={int(start)}"
