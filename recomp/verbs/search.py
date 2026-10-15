"""Search across every source's transcript (SQLite FTS5, BM25), with context and ready cut commands."""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from ..core import refs
from ..core.timecode import clock
from ..registry import Ctx, verb

_TOKEN = re.compile(r"[\w']+", re.UNICODE)


def fts_query(text: str, mode: str = "all") -> str:
    """Plain words → FTS5. Quoted phrases are kept; words become prefix-matched terms."""
    phrases = re.findall(r'"([^"]+)"', text)
    rest = re.sub(r'"[^"]+"', " ", text)
    terms = [f'"{p.strip()}"' for p in phrases if p.strip()]
    for tok in _TOKEN.findall(rest):
        tok = tok.replace("'", "")
        if len(tok) > 1 and tok.upper() not in ("AND", "OR", "NOT", "NEAR"):
            terms.append(f'"{tok}"*' if len(tok) > 3 else f'"{tok}"')
    if not terms:
        return ""
    return (" OR " if mode == "any" else " AND ").join(terms)


class SearchIn(BaseModel):
    query: str = Field(..., description='Words or "exact phrases"', json_schema_extra={"pos": 0})
    sources: list[str] = Field(default_factory=list, description="Limit to these source refs")
    chapter: str | None = Field(None, description="Limit to one chapter")
    speaker: str | None = Field(None, description="Limit to a speaker label or person name")
    all_transcripts: bool = Field(False, description="Search every transcript, not only the primary ones")
    context: int = Field(1, description="Segments of context before and after")
    limit: int = Field(20)
    mode: str = Field("auto", description="all (every word), any, or auto (all, then any if nothing found)")


def run_search(db, inp: SearchIn) -> tuple[list[dict], str]:
    modes = ["all", "any"] if inp.mode == "auto" else [inp.mode]
    used = modes[0]
    rows = []
    for m in modes:
        q = fts_query(inp.query, m)
        if not q:
            return [], m
        sql = ('SELECT s.id, s.idx, s.start, s."end", s.text, s.speaker, s.person_id, s.transcript_id, '
               't.source_id, t.ref AS tref, src.ref AS sref, src.title AS stitle, bm25(segment_fts) AS score, '
               "snippet(segment_fts, 0, '[', ']', '…', 24) AS snip "
               "FROM segment_fts JOIN segment s ON s.id=segment_fts.rowid "
               "JOIN transcript t ON t.id=s.transcript_id JOIN source src ON src.id=t.source_id "
               "WHERE segment_fts MATCH ?")
        params: list = [q]
        if not inp.all_transcripts:
            sql += " AND t.is_primary=1"
        if inp.sources:
            ids = [refs.source(db, r)["id"] for r in inp.sources]
            sql += f" AND t.source_id IN ({','.join('?' * len(ids))})"
            params += ids
        if inp.chapter:
            ch = refs.resolve(db, inp.chapter, "chapter")[1]
            sql += ' AND t.source_id=? AND s."end" > ? AND s.start < ?'
            params += [ch["source_id"], ch["start"], ch["end"]]
        if inp.speaker:
            person = db.one("SELECT id FROM person WHERE name LIKE ? OR ref=?", (inp.speaker, inp.speaker))
            if person:
                sql += " AND s.person_id=?"
                params.append(person["id"])
            else:
                sql += " AND s.speaker=?"
                params.append(inp.speaker)
        rows = db.all(sql + " ORDER BY score LIMIT ?", (*params, inp.limit))
        used = m
        if rows:
            break
    return [dict(r) for r in rows], used


@verb("search", SearchIn,
      examples=['recomp search "free will"', "recomp search forgiveness --sources S1,S4 --limit 10",
                'recomp search "everlasting life" --speaker "Pastor Chris"'])
def search(ctx: Ctx, inp: SearchIn):
    """Find where something is said, across all sources. Each hit has its chapter, surrounding lines and a ready `cut add` command."""
    db = ctx.db
    rows, used = run_search(db, inp)
    hits = []
    for r in rows:
        ctxrows = db.all('SELECT idx, start, "end", text FROM segment WHERE transcript_id=? AND idx BETWEEN ? AND ? '
                         "ORDER BY idx", (r["transcript_id"], r["idx"] - inp.context, r["idx"] + inp.context))
        ch = db.one('SELECT ref, title FROM chapter WHERE source_id=? AND start<=? AND "end">? ORDER BY start DESC LIMIT 1',
                    (r["source_id"], r["start"], r["start"]))
        a = ctxrows[0]["start"] if ctxrows else r["start"]
        b = ctxrows[-1]["end"] if ctxrows else r["end"]
        hits.append({
            "source": r["sref"], "title": r["stitle"], "at": clock(r["start"]), "start": round(r["start"], 2),
            "idx": r["idx"], "match": r["snip"], "speaker": r["speaker"],
            "chapter": {"ref": ch["ref"], "title": ch["title"]} if ch else None,
            "context": " ".join(c["text"] for c in ctxrows),
            "cut": f"recomp cut add {r['sref']} --segments {ctxrows[0]['idx'] if ctxrows else r['idx']}..{ctxrows[-1]['idx'] if ctxrows else r['idx']}"
                   f"  # {clock(a)}–{clock(b)}",
        })
    by_source: dict[str, int] = {}
    for h in hits:
        by_source[h["source"]] = by_source.get(h["source"], 0) + 1
    return {"query": inp.query, "mode": used, "hits": hits, "by_source": by_source}
