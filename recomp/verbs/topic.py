"""Research wing, part two (P17b): topics in the air → what my creators said about them → a journey.

`topic suggest` lists prompts from the news (and who among the followed creators has talked about them),
`topic add` names a topic and its terms, `topic scan` finds the creators' episodes about it (feeds, their own
channel search, the library, project transcripts), fetches missing transcripts the cheap way and writes the
**brief**; `journey from-topic` turns chosen passages into cuts and a draft journey with a section per creator.
"""

from __future__ import annotations

import re
import time

from pydantic import BaseModel, Field

from .. import registry
from ..core import config, studio
from ..core import project as P
from ..core.timecode import clock
from ..envelope import RecompError, Result
from ..registry import Ctx, verb
from ..research import feeds, library, podcasts, topics, transcripts, youtube
from .follow import get_follow, project_name, since_date

SUGGEST_FROM = ("news", "trends", "wikipedia", "hn")


def get_topic(db, target: str) -> dict:
    row = db.by_ref("topic", target.upper()) if re.fullmatch(r"[Tt]\d+", target or "") else None
    if row is None:
        rows = db.rows("topic", "WHERE lower(title)=lower(?)", (target,))
        row = rows[0] if rows else None
    if row is None:
        raise RecompError("E_NOT_FOUND", f"no topic {target!r}", hint="`recomp topic list` shows them.")
    return row


def brief_topic(t: dict) -> dict:
    b = t["brief"] or {}
    return {"ref": t["ref"], "title": t["title"], "terms": t["terms"], "follows": t["follows"] or "all",
            "since": t["since"], "projects": t["projects"], "scanned": (t["state"] or {}).get("scanned_at_iso"),
            "creators": len(b.get("creators") or []), "passages": (b.get("summary") or {}).get("passages", 0),
            "journeys": b.get("journeys") or []}


# ---- suggest ------------------------------------------------------------------------------------

def _voices(db, terms: list[str], window: int = 8) -> dict[str, int]:
    """Episodes per followed creator in the library where two of these terms come up within about a minute of
    talk (``window`` lines). Words found in most of the library's episodes say nothing and are left out."""
    words = [t for t in terms if len(t) > 1][:4]
    if not words:
        return {}
    total = db.scalar("SELECT COUNT(*) FROM lib_doc") or 0
    lines: dict[str, dict[str, list[int]]] = {}
    for w in words:
        try:
            rows = db.all("SELECT s.doc_id, s.idx FROM lib_seg_fts JOIN lib_seg s ON s.id=lib_seg_fts.rowid "
                          "WHERE lib_seg_fts MATCH ?", (f'"{w.lower()}"',))
        except Exception:  # noqa: BLE001 — an odd headline token must not break the list
            continue
        docs = {r["doc_id"] for r in rows}
        if total >= 4 and len(docs) > total / 2:
            continue
        for r in rows:
            lines.setdefault(r["doc_id"], {}).setdefault(w, []).append(r["idx"])
    out: dict[str, int] = {}
    for doc, by_word in lines.items():
        if len(words) == 1 and sum(len(v) for v in by_word.values()) < 3:
            continue  # one word mentioned in passing is not an opinion
        if len(words) > 1:
            ws = list(by_word)
            near = any(abs(i - j) <= window for a in range(len(ws)) for b in range(a + 1, len(ws))
                       for i in by_word[ws[a]] for j in by_word[ws[b]])
            if not near:
                continue
        creator = db.scalar("SELECT creator FROM lib_doc WHERE id=?", (doc,))
        out[creator] = out.get(creator, 0) + 1
    return out


class SuggestIn(BaseModel):
    section: str = Field("top", description=f"Google News section: {', '.join(topics.SECTIONS)}")
    query: str | None = Field(None, description="Search the news of the last 7 days instead of a section")
    sources: list[str] = Field(default_factory=lambda: ["news", "hn"],
                               description="news, trends (Google Trends daily, US), wikipedia (most viewed; needs "
                                           "`config set research.contact`), hn")
    limit: int = Field(12, description="Prompts per source")


@verb("topic.suggest", SuggestIn, effect="network", needs_project=False,
      examples=["recomp topic suggest --section technology", 'recomp topic suggest --query "AI models"',
                "recomp topic suggest --sources news,trends"])
def topic_suggest(ctx: Ctx, inp: SuggestIn):
    """What is in the air, as prompts: headlines and lists, each with the followed creators who have talked about it
    in the library. Pick one (`recomp topic add <n>`) or name your own; the news is a prompt, not a scoreboard."""
    if inp.section not in topics.SECTIONS:
        raise RecompError("E_INVALID", f"section: {', '.join(topics.SECTIONS)}")
    bad = [s for s in inp.sources if s not in SUGGEST_FROM]
    if bad:
        raise RecompError("E_INVALID", f"sources: {', '.join(SUGGEST_FROM)}")
    items, warnings = [], []
    fetchers = {"news": lambda: topics.news(inp.section, inp.query, inp.limit), "trends": lambda: topics.google_trends("US", inp.limit),
                "wikipedia": lambda: topics.wikipedia_top(inp.limit), "hn": lambda: topics.hacker_news(inp.limit)}
    for s in inp.sources:
        try:
            items += fetchers[s]()
        except RecompError as exc:
            warnings.append(f"{s}: {exc.message}" + (f" ({exc.hint})" if exc.hint else ""))
    db = ctx.studio
    for it in items:
        it["terms"] = topics.key_terms(it["title"])
        it["voices"] = _voices(db, it["terms"])
    order = {s: k for k, s in enumerate(inp.sources)}
    items.sort(key=lambda i: (-len(i["voices"]), -sum(i["voices"].values()), order.get(i["from"], 9)))
    for n, it in enumerate(items, start=1):
        it["n"] = n
    studio.set_state(db, "topic_suggestions", {"at": time.time(), "items": items})
    if not items and warnings:
        raise RecompError("E_EXTERNAL", "; ".join(warnings), hint="Try again shortly, or name your own topic: `recomp topic add \"…\"`.")
    return Result(data={"suggestions": items}, warnings=warnings,
                  next=['recomp topic add <n> [--terms "…"]   # or: recomp topic add "your own topic" --terms "…"'])


# ---- topics -------------------------------------------------------------------------------------

class TopicAddIn(BaseModel):
    title: str = Field(..., description="The topic in your words, or a number from the last `topic suggest`",
                       json_schema_extra={"pos": 0})
    terms: list[str] = Field(default_factory=list, description="Words and phrases that mean it (default: from the title)")
    follows: list[str] = Field(default_factory=list, description="Only these creators (default: everyone followed)")
    since: str | None = Field("2y", description="How far back to look: 2y, 18m or a date")
    news_query: str | None = Field(None, description="Headlines to keep as context (default: the title)")
    project: list[str] = Field(default_factory=list, description="Where its journeys go (default: the current project)")
    note: str = ""


@verb("topic.add", TopicAddIn, effect="write", needs_project=False,
      examples=['recomp topic add "AI models are getting good" --terms "AI,model,AGI,superintelligence,copy itself"',
                "recomp topic add 3 --project ai-and-ideas"])
def topic_add(ctx: Ctx, inp: TopicAddIn):
    """Name a topic to compile: what the followed creators said about it, now and in the past."""
    db = ctx.studio
    title, terms, query = inp.title.strip(), list(inp.terms), inp.news_query
    if title.isdigit():
        sugg = (studio.get_state(db, "topic_suggestions") or {}).get("items") or []
        hit = next((s for s in sugg if str(s["n"]) == title), None)
        if hit is None:
            raise RecompError("E_NOT_FOUND", f"{title} is not in the last `topic suggest` list")
        title, terms, query = hit["title"], terms or hit["terms"], query or " ".join(hit["terms"][:3])
    terms = terms or topics.key_terms(title, 6)
    follows = [get_follow(db, f)["ref"] for f in inp.follows]
    projects = [project_name(p) for p in inp.project]
    if not projects:
        try:
            projects = [P.resolve(None).name]
        except RecompError:
            projects = []
    with ctx.studio_op(f"topic {title[:60]}") as tx:
        row = tx.insert("topic", {"title": title, "terms": terms, "follows": follows, "since": inp.since,
                                  "news_query": query or title, "projects": projects, "note": inp.note,
                                  "brief": {}, "state": {}})
    return Result(data=brief_topic(row), refs=[row["ref"]],
                  next=[f"recomp topic scan {row['ref']}   # find what each creator said; writes the brief"])


@verb("topic.list", registry.NoInput, needs_project=False)
def topic_list(ctx: Ctx, inp):
    """Topics, their terms, last scan and the journeys made from them."""
    return [brief_topic(t) for t in ctx.studio.rows("topic", "ORDER BY created_at DESC")]


class TopicEditIn(BaseModel):
    ref: str = Field(..., json_schema_extra={"pos": 0})
    title: str | None = None
    terms: list[str] | None = Field(None, description="Replace the terms")
    follows: list[str] | None = Field(None, description="Replace the creators ([] = everyone)")
    since: str | None = None
    news_query: str | None = None
    project: list[str] | None = None
    note: str | None = None


@verb("topic.edit", TopicEditIn, effect="write", needs_project=False,
      examples=['recomp topic edit T1 --terms "AI,AGI,superintelligence,control"'])
def topic_edit(ctx: Ctx, inp: TopicEditIn):
    """Change a topic's title, terms, creators, time range, headline query or projects (scan again after)."""
    db = ctx.studio
    t = get_topic(db, inp.ref)
    fields = {k: getattr(inp, k) for k in ("title", "terms", "since", "news_query", "note") if getattr(inp, k) is not None}
    if inp.follows is not None:
        fields["follows"] = [get_follow(db, f)["ref"] for f in inp.follows]
    if inp.project is not None:
        fields["projects"] = [project_name(p) for p in inp.project]
    with ctx.studio_op(f"edit {t['ref']}") as tx:
        row = tx.update("topic", t["id"], fields)
    return brief_topic(row)


class TopicRefIn(BaseModel):
    ref: str = Field(..., json_schema_extra={"pos": 0})


@verb("topic.remove", TopicRefIn, effect="write", needs_project=False)
def topic_remove(ctx: Ctx, inp: TopicRefIn):
    """Drop a topic and its brief (journeys made from it stay in their projects)."""
    db = ctx.studio
    t = get_topic(db, inp.ref)
    with ctx.studio_op(f"remove {t['ref']}") as tx:
        tx.delete("topic", t["id"])
    return {"removed": t["ref"], "title": t["title"]}


# ---- scan ---------------------------------------------------------------------------------------

class ScanIn(BaseModel):
    ref: str = Field(..., json_schema_extra={"pos": 0})
    fetch: int = Field(3, description="Missing transcripts to fetch per creator in this scan")
    episodes: int = Field(4, description="Episodes to keep per creator in the brief")
    passages: int = Field(3, description="Passages to keep per episode")
    news: bool = Field(True, description="Keep this week's headlines on the topic as context")


def _follow_episodes(db, f: dict, t: dict, since: str | None, fetch: int, missing: list[dict]) -> int:
    """Bring the creator's episodes about the topic into the library (cheapest route first). Returns how many."""
    terms = t["terms"]
    fd = f["feeds"] or {}
    have = {r["key"] for r in db.all("SELECT key FROM lib_doc")}
    todo: list[dict] = []
    asr: list[dict] = []
    episodes = []

    def rel(title: str, desc: str) -> int:
        # A title about the topic counts three times a description (show notes mention sponsors, "AI-powered" ones too).
        return 3 * topics.mentions(title, terms) + topics.mentions(desc, terms)

    if fd.get("podcast"):
        episodes = podcasts.read(fd["podcast"]["feed"])["items"]
        for ep in episodes:
            if since and ep["published"] and ep["published"] < since:
                continue
            r = rel(ep["title"], ep["description"])
            if not r:
                continue
            key = f"pod:{ep['guid']}"
            if key in have:
                continue
            if ep["route"]["kind"] in ("published", "lex"):
                todo.append({"key": key, "title": ep["title"], "published": ep["published"], "url": ep["link"] or ep["audio_url"],
                             "video_id": ep.get("video_id"), "route": ep["route"], "rel": r})
            elif ep["route"]["kind"] == "asr":
                asr.append({"title": ep["title"], "published": ep["published"], "why": "audio only: needs ASR",
                            "do": "take it into a project (`recomp inbox take`), then `recomp transcript asr <S>`", "rel": r})
    if fd.get("youtube"):
        query = t["news_query"] if len(t["news_query"] or "") < 40 else " ".join(t["terms"][:2])
        try:
            vids = youtube.search_in_channel(fd["youtube"], query, 20)
        except RecompError as exc:
            vids = []
            missing.append({"title": f"{f['name']} channel search", "why": exc.message})
        for v in vids:
            r = rel(v["title"], v["description"])
            if not r:
                continue
            # The same conversation in the podcast feed (or already in the library) is cheaper.
            if any(feeds.title_match(v["title"], ep["title"]) >= 0.45 for ep in episodes if ep["route"]["kind"] != "asr"):
                continue
            if db.one("SELECT 1 FROM lib_doc WHERE video_id=?", (v["video_id"],)) or f"yt:{v['video_id']}" in have:
                continue
            todo.append({"key": f"yt:{v['video_id']}", "title": v["title"], "published": v.get("published"), "url": v["url"],
                         "video_id": v["video_id"], "route": {"kind": "captions", "video_id": v["video_id"], "timing": "video"},
                         "rel": r})
    # Most on-topic first (newest first among equals: the lists are newest first and the sort is stable).
    todo.sort(key=lambda x: -x["rel"])
    missing += sorted(asr, key=lambda x: -x["rel"])
    added = 0
    blocked = False
    for item in todo:
        if added >= fetch:
            missing.append({"title": item["title"], "published": item["published"], "why": "not fetched in this scan",
                            "do": "scan again with a larger --fetch"})
            continue
        if blocked and item["route"]["kind"] == "captions":
            missing.append({"title": item["title"], "why": "YouTube is refusing caption requests"})
            continue
        try:
            got = transcripts.fetch(item["route"])
        except RecompError as exc:
            if exc.code == "E_EXTERNAL" and item["route"]["kind"] == "captions":
                blocked = True
            missing.append({"title": item["title"], "published": item["published"], "why": exc.message})
            continue
        if not got["segments"]:
            continue
        with db.op("topic.scan", "machine", {"topic": t["ref"]}) as tx:
            tx.summary = f"library: {item['title'][:60]}"
            library.add_doc(tx, f, item["key"], {"creator": f["person"] or f["name"], "title": item["title"],
                                                 "published": item["published"] or got.get("published"), "url": item["url"],
                                                 "video_id": got.get("video_id") or item["video_id"],
                                                 "route": {**item["route"], "timing": got.get("timing")},
                                                 "chapters": got.get("chapters") or []}, got["segments"])
        added += 1
    return added


def _iso(yyyymmdd: str | None) -> str | None:
    d = (yyyymmdd or "")[:8]
    return f"{d[:4]}-{d[4:6]}-{d[6:]}" if len(d) == 8 and d.isdigit() else None


def _project_docs(f: dict) -> list[dict]:
    """Primary transcripts of the follow's sources already in its projects (e.g. M2's alex-oconnor episodes)."""
    names = {n.lower() for n in (f["name"], f["person"]) if n}
    out = []
    for pname in f["projects"] or []:
        try:
            proj = P.Project(P.locate(pname))
        except RecompError:
            continue
        try:
            db = proj.db
            for s in db.rows("source"):
                if not any(n in (s["creator"] or "").lower() for n in names):
                    continue
                tr = db.one("SELECT id, ref FROM transcript WHERE source_id=? AND is_primary=1", (s["id"],))
                if not tr:
                    continue
                segs = [{"start": r["start"], "end": r["end"], "text": r["text"], "speaker": r["who"]} for r in db.all(
                    'SELECT g.start, g."end", g.text, COALESCE(p.name, g.speaker) AS who FROM segment g '
                    "LEFT JOIN person p ON p.id=g.person_id WHERE g.transcript_id=? ORDER BY g.idx", (tr["id"],))]
                out.append({"where": f"{proj.name}:{s['ref']}", "project": proj.name, "source": s["ref"], "title": s["title"],
                            "published": _iso((s["meta"] or {}).get("upload_date")),
                            "video_id": s["platform_id"] if s["platform"] == "youtube" else None, "timing": "video",
                            "url": s["uri"], "segments": segs})
        finally:
            proj.close()
    return out


@verb("topic.scan", ScanIn, effect="network", needs_project=False,
      examples=["recomp topic scan T1", "recomp topic scan T1 --fetch 6"])
def topic_scan(ctx: Ctx, inp: ScanIn):
    """Find what each followed creator said about the topic: their feeds and channel search for episodes on it,
    transcripts fetched the cheap way into the library, plus project transcripts; ranks passages and writes the
    brief (`recomp topic brief T1`). The ranking is a shortlist: read and choose."""
    db = ctx.studio
    t = get_topic(db, inp.ref)
    since = since_date(t["since"]) if t["since"] else None
    follows = [get_follow(db, r) for r in t["follows"]] if t["follows"] else db.rows("follow", "ORDER BY created_at")
    if not follows:
        raise RecompError("E_NOT_FOUND", "nothing is followed yet", hint="`recomp follow add …` first.")
    warnings: list[str] = []
    news = []
    if inp.news:
        try:
            news = topics.news(query=t["news_query"] or t["title"], limit=8)
        except RecompError as exc:
            warnings.append(f"headlines: {exc.message}")
    creators, pid = [], 0
    for f in follows:
        missing: list[dict] = []
        try:
            fetched = _follow_episodes(db, f, t, since, inp.fetch, missing)
        except RecompError as exc:
            warnings.append(f"{f['name']}: {exc.message}")
            fetched = 0
        docs = []
        for d in db.rows("lib_doc", "WHERE follow_id=? ORDER BY published DESC", (f["id"],)):
            if since and d["published"] and d["published"] < since:
                continue
            segs = [dict(r) for r in db.all('SELECT start, "end", speaker, text FROM lib_seg WHERE doc_id=? ORDER BY idx', (d["id"],))]
            docs.append({"where": d["ref"], "title": d["title"], "published": d["published"], "video_id": d["video_id"],
                         "timing": (d["route"] or {}).get("timing"), "url": d["url"], "segments": segs})
        lib_videos = {d["video_id"] for d in docs if d["video_id"]}
        docs += [d for d in _project_docs(f) if not (d["video_id"] and d["video_id"] in lib_videos)]
        episodes = []
        for d in docs:
            ps = topics.passages(d["segments"], t["terms"], inp.passages)
            if not ps:
                continue
            for p in ps:
                pid += 1
                p["id"] = f"p{pid}"
                p["at"] = f"{clock(p['start'], 0)}–{clock(p['end'], 0)}"
                p["link"] = library.watch_link(d["video_id"], p["start"]) if d["video_id"] and d["timing"] == "video" else d["url"]
            episodes.append({k: d[k] for k in ("where", "title", "published", "video_id", "timing", "url")} |
                            {"best": max(p["score"] for p in ps), "passages": ps})
        episodes.sort(key=lambda e: -e["best"])
        kept = episodes[:inp.episodes]
        creators.append({"follow": f["ref"], "name": f["person"] or f["name"], "fetched": fetched, "episodes": kept,
                         "missing": missing[:12]})
    # Passage ids in reading order (creator by creator).
    n = 0
    for c in creators:
        for e in c["episodes"]:
            for p in e["passages"]:
                n += 1
                p["id"] = f"p{n}"
    dates = [e["published"] for c in creators for e in c["episodes"] if e["published"]]
    summary = {"creators": sum(1 for c in creators if c["episodes"]), "episodes": sum(len(c["episodes"]) for c in creators),
               "passages": n, "oldest": min(dates) if dates else None, "newest": max(dates) if dates else None}
    brief = {"topic": t["ref"], "title": t["title"], "terms": t["terms"], "since": since, "news": news,
             "creators": creators, "summary": summary, "journeys": (t["brief"] or {}).get("journeys") or [],
             "scanned_at": time.time()}
    now = time.time()
    with db.op(ctx.verb_name, ctx.actor, ctx.args) as tx:
        tx.summary = f"brief {t['ref']}: {n} passages from {summary['creators']} creators"
        tx.update("topic", t["id"], {"brief": brief, "state": {"scanned_at": now,
                                                               "scanned_at_iso": time.strftime("%Y-%m-%d %H:%M", time.localtime(now))}})
    if tx.op_id:
        ctx.last_op = tx.op_id
    path = write_brief_md(t, brief)
    return Result(data={"topic": t["ref"], "summary": summary, "brief_file": str(path),
                        "creators": [{"name": c["name"], "episodes": len(c["episodes"]), "fetched": c["fetched"],
                                      "missing": len(c["missing"])} for c in creators]},
                  warnings=warnings, next=[f"recomp topic brief {t['ref']}",
                                           f"recomp journey from-topic {t['ref']} --passages p1,p4,… --project <P>"])


def brief_md(t: dict, b: dict) -> str:
    lines = [f"# Topic brief {t['ref']}: {t['title']}", "",
             f"Terms: {', '.join(t['terms'])} · since {b.get('since') or 'any time'} · "
             f"{b['summary']['passages']} passages from {b['summary']['creators']} creators", ""]
    if b.get("news"):
        lines += ["## In the news this week", ""] + [f"- {n['title']} ({n['source']}, {n['date']})" for n in b["news"]] + [""]
    for c in b["creators"]:
        lines += [f"## {c['name']} ({c['follow']})", ""]
        if not c["episodes"]:
            lines += ["Nothing on this topic in the transcripts we have.", ""]
        for e in c["episodes"]:
            clock_note = "" if e["timing"] == "video" else " · podcast timing"
            lines += [f"### {e['title']} ({e['published'] or 'date unknown'}) · {e['where']}{clock_note}", ""]
            for p in e["passages"]:
                who = f" ({', '.join(p['speakers'])})" if p["speakers"] else ""
                lines.append(f"- **{p['id']}** {p['at']}{who} · score {p['score']} [{', '.join(p['terms'])}] "
                             f"{p['link'] or ''}\n  {p['text'][:420]}…")
            lines.append("")
        for m in c["missing"]:
            lines.append(f"- not read: {m['title']}: {m['why']}")
        if c["missing"]:
            lines.append("")
    return "\n".join(lines) + "\n"


def write_brief_md(t: dict, b: dict):
    folder = config.home() / "topics"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{t['ref']}-brief.md"
    path.write_text(brief_md(t, b), encoding="utf-8")
    return path


class BriefIn(BaseModel):
    ref: str = Field(..., json_schema_extra={"pos": 0})
    format: str = Field("json", description="json or md")
    creator: str | None = Field(None, description="Only this creator's part")


@verb("topic.brief", BriefIn, needs_project=False, examples=["recomp topic brief T1", "recomp topic brief T1 --format md"])
def topic_brief(ctx: Ctx, inp: BriefIn):
    """The topic brief: per creator, the episodes and passages (who speaks, times, links) and what could not be read."""
    t = get_topic(ctx.studio, inp.ref)
    b = t["brief"] or {}
    if not b:
        raise RecompError("E_NOT_FOUND", f"{t['ref']} has no brief yet", hint=f"`recomp topic scan {t['ref']}`")
    if inp.creator:
        b = {**b, "creators": [c for c in b["creators"] if inp.creator.lower() in c["name"].lower() or c["follow"] == inp.creator.upper()]}
    if inp.format == "md":
        return {"topic": t["ref"], "markdown": brief_md(t, b)}
    return b


# ---- journey from a topic -----------------------------------------------------------------------

class FromTopicIn(BaseModel):
    topic: str = Field(..., json_schema_extra={"pos": 0})
    passages: list[str] = Field(default_factory=list, description="Passage ids from the brief, in order (default: the "
                                                                   "best two per creator)")
    by: str = Field("creator", description="Sections per creator, or per stance (needs --stances)")
    stances: list[str] = Field(default_factory=list, description='Stance per passage for --by stance, e.g. "p1=worried,p4=hopeful"')
    title: str | None = Field(None, description="Journey title (default: What my creators think about <topic>)")
    formats: list[str] = Field(default_factory=lambda: ["shorts", "landscape"])
    lower_thirds: bool = Field(True, description="Name who speaks on every slot")


def _source_for(ctx: Ctx, proj: P.Project, ep: dict, creator: str, warnings: list[str]):
    """The project source for a brief episode (added if needed) and a function: brief time → its shift onto the
    source's clock. A podcast-only episode is matched to its YouTube upload by words first (`research.match`)."""
    from ..research import match
    from ..transcript.store import add_transcript
    db = proj.db
    zero = lambda t: 0.0  # noqa: E731
    if ep["where"].startswith(f"{proj.name}:"):
        return db.by_ref("source", ep["where"].split(":", 1)[1]), zero
    sdb = ctx.studio
    doc = sdb.by_ref("lib_doc", ep["where"]) if re.fullmatch(r"L\d+", ep["where"]) else None
    segs = [dict(r) for r in sdb.all('SELECT start, "end", speaker, text FROM lib_seg WHERE doc_id=? ORDER BY idx',
                                     (doc["id"],))] if doc else []
    vid = ep.get("video_id") or (doc or {}).get("video_id")
    found = None
    if not vid and doc and ep["timing"] != "video":
        f = sdb.get("follow", doc["follow_id"]) if doc["follow_id"] else None
        names = [n for n in ((f or {}).get("name"), (f or {}).get("person"), creator) if n]
        try:
            found = match.find_upload(doc["title"], segs, names)
        except RecompError as exc:
            warnings.append(f"{doc['ref']}: YouTube refused the search for its upload ({exc.message})")
        if found:
            vid = found["video_id"]
            with sdb.op("journey.from-topic", "machine", {"doc": doc["ref"]}) as tx:
                tx.summary = f"{doc['ref']} is YouTube {vid}"
                doc = tx.update("lib_doc", doc["id"], {"video_id": vid, "route": {**(doc["route"] or {}),
                                                                                "video_offset_s": found["offset_s"]}})
        else:
            warnings.append(f"{doc['ref']}: no YouTube upload matched its words; cutting from the podcast audio")
    pctx = Ctx(actor=ctx.actor, project=proj, verb_name="journey.from-topic", args={})
    if vid:
        row = db.one("SELECT id FROM source WHERE platform='youtube' AND platform_id=?", (vid,))
        if row:
            src = db.get("source", row["id"])
        else:
            from .ui import set_state
            url = f"https://www.youtube.com/watch?v={vid}"
            title = (found or {}).get("title") or ep["title"]
            set_state(db, "pick_list", {"url": url, "title": title, "channel": creator,
                                        "entries": [{"n": 1, "id": vid, "title": title, "duration_s": None, "duration": None,
                                                     "url": url, "views": None, "date": (ep.get("published") or "").replace("-", "") or None}]})
            # Captions only when no transcript on the video's clock comes along (the library's, or the match's).
            env = registry.run("source.add", {"pick": ["1"], "subtitles": not (found or (doc and ep["timing"] == "video"))},
                               actor=ctx.actor, project=proj)
            if not env["ok"]:
                raise RecompError(env["error"]["code"], env["error"]["message"], hint=env["error"].get("hint"))
            warnings += env.get("warnings") or []
            got = (env["data"]["added"] or env["data"]["skipped"])[0]
            src = db.by_ref("source", got["ref"])
        if found and not db.one("SELECT 1 FROM transcript WHERE source_id=? AND origin='captions'", (src["id"],)):
            with pctx.op(f"captions for {src['ref']}") as tx:
                add_transcript(tx, src, found["captions"]["segments"], origin="captions", language=src.get("language") or "en",
                               label="YouTube captions (matched to the podcast)",
                               make_primary=not db.one("SELECT 1 FROM transcript WHERE source_id=? AND is_primary=1", (src["id"],)))
    else:
        from .follow import _add_episode
        ref = _add_episode(pctx, {"meta": {"audio_url": ep["url"], "guid": doc["key"] if doc else None},
                                  "url": ep["url"], "channel": creator, "title": ep["title"], "published": ep.get("published"),
                                  "duration": None}, {"person": creator})
        src = db.by_ref("source", ref)
    # The library transcript comes along (on the source's clock: primary when there is none; podcast clock: aside).
    has_primary = db.one("SELECT 1 FROM transcript WHERE source_id=? AND is_primary=1", (src["id"],))
    already = db.one("SELECT 1 FROM transcript WHERE source_id=? AND label LIKE ?", (src["id"], f"%library {doc['ref']}%")) if doc else True
    if doc and not already and not (has_primary and ep["timing"] == "video"):
        on_clock = ep["timing"] == "video" or not vid
        with pctx.op(f"transcript for {src['ref']} from library {doc['ref']}") as tx:
            add_transcript(tx, src, segs, origin="published", language=src.get("language") or "en",
                           label=f"library {doc['ref']} ({(doc['route'] or {}).get('kind')})" + ("" if on_clock else " (podcast timing)"),
                           make_primary=on_clock and not has_primary,
                           stats={"timing": "video" if on_clock else "podcast", "library": doc["ref"]})
    if not vid or ep["timing"] == "video" or not doc:
        return src, zero
    return src, _podcast_shift(db, src, doc, segs, warnings)


def _podcast_shift(db, src: dict, doc: dict, segs: list[dict], warnings: list[str]):
    """Podcast clock → video clock: measured near each passage against the video's word-timed transcript (inserted
    ads move the offset during an episode); the episode-wide offset where a passage can't be matched."""
    from ..research import match
    from ..transcript import align
    tr = db.one("SELECT id FROM transcript WHERE source_id=? AND has_words=1 AND origin<>'published' ORDER BY is_primary DESC",
                (src["id"],))
    if not tr:
        warnings.append(f"{src['ref']}: the passage times follow the podcast, and there is no video transcript to align them "
                        f"to yet; check the cut (`recomp transcript fetch-captions {src['ref']}`, then run this again)")
        return lambda t: 0.0
    words = [dict(r) for r in db.all('SELECT w.start, w."end", w.text FROM word w JOIN segment s ON s.id=w.segment_id '
                                     "WHERE s.transcript_id=? ORDER BY w.start", (tr["id"],))]
    base = (doc["route"] or {}).get("video_offset_s")
    if base is None:
        base = align.estimate_offset(match._window(segs, *match.PROBE) or segs[:200], words).get("offset_s")
    if base is None:
        warnings.append(f"{src['ref']}: could not align the podcast transcript to the video; check the cut times")
        return lambda t: 0.0

    def shift(t: float) -> float:
        est = match.offset_near(segs, words, t, base)
        off = est["offset_s"] if est.get("offset_s") is not None and est.get("matched", 0) >= 10 else base
        return -float(off)
    return shift


def _guests(src: dict, ep: dict, creator: str) -> list[str]:
    """Who is in a passage whose transcript names no speakers: the guest its title names, and the creator."""
    from ..research.topics import guest_from_title
    guest = guest_from_title(src.get("title") or "") or guest_from_title(ep.get("title") or "")
    return [guest, creator] if guest and guest.lower() != creator.lower() else [creator]


@verb("journey.from-topic", FromTopicIn, effect="write",
      examples=["recomp journey from-topic T1", "recomp journey from-topic T1 --passages p2,p5,p7,p9,p11,p12",
                'recomp journey from-topic T1 --by stance --stances "p2=worried,p5=worried,p9=hopeful"'])
def journey_from_topic(ctx: Ctx, inp: FromTopicIn):
    """Draft "What my creators think about X" from a topic brief: chosen passages become cuts (with why and who speaks)
    in this project, grouped into a section per creator (or per stance); episodes not yet here are added first."""
    sdb = ctx.studio
    t = get_topic(sdb, inp.topic)
    b = t["brief"] or {}
    if not b.get("creators"):
        raise RecompError("E_NOT_FOUND", f"{t['ref']} has no brief yet", hint=f"`recomp topic scan {t['ref']}`")
    index = {}
    for c in b["creators"]:
        for e in c["episodes"]:
            for p in e["passages"]:
                index[p["id"]] = (c, e, p)
    if inp.passages:
        ids = [p.split(".")[-1].lower() for p in inp.passages]
        unknown = [i for i in ids if i not in index]
        if unknown:
            raise RecompError("E_NOT_FOUND", f"not in {t['ref']}'s brief: {', '.join(unknown)}", hint=f"`recomp topic brief {t['ref']}`")
    else:
        ids = []
        for c in b["creators"]:
            ps = sorted((p for e in c["episodes"] for p in e["passages"]), key=lambda p: -p["score"])[:2]
            ids += [p["id"] for p in ps]
        ids = ids[:8]
        if not ids:
            raise RecompError("E_NOT_FOUND", f"{t['ref']}'s brief has no passages", hint="Edit the terms and scan again.")
    stance = {}
    if inp.by == "stance":
        for s in inp.stances:
            if "=" in s:
                k, v = s.split("=", 1)
                stance[k.strip().split(".")[-1].lower()] = v.strip()
        if not stance:
            raise RecompError("E_INVALID", "--by stance needs --stances \"p1=worried,p4=hopeful\"")
    elif inp.by != "creator":
        raise RecompError("E_INVALID", "by: creator or stance")
    proj = ctx.project
    warnings: list[str] = []
    cuts: list[tuple[str, str]] = []  # (group, cut ref)
    sources: dict[str, tuple] = {}  # brief episode → (project source, shift function)
    for pid in ids:
        c, e, p = index[pid]
        if e["where"] not in sources:
            sources[e["where"]] = _source_for(ctx, proj, e, c["name"], warnings)
        src, shifter = sources[e["where"]]
        shift = shifter(p["start"])
        a, z = max(0.0, p["start"] + shift), p["end"] + shift
        words = " ".join(p["text"].split()[:9])
        env = registry.run("cut.add", {"ref": src["ref"], "from": f"{a:.2f}", "to": f"{z:.2f}",
                                       "title": f"{c['name']}: {words}…",
                                       "why": f"{c['name']} on \"{t['title']}\" ({e['title'][:80]}, {e['published'] or 'undated'})",
                                       "people": p["speakers"] or _guests(src, e, c["name"]), "tags": ["topic:" + t["ref"]] + p["terms"][:3],
                                       "note": f"{t['ref']}.{pid} score {p['score']}" + ("" if e["timing"] == "video" or not shift else f"; podcast clock shifted {shift:+.1f}s")},
                           actor=ctx.actor, project=proj)
        if not env["ok"]:
            warnings.append(f"{pid}: {env['error']['message']}")
            continue
        cuts.append((stance.get(pid, "Other views") if inp.by == "stance" else c["name"], env["data"]["ref"]))
    if not cuts:
        raise RecompError("E_EXTERNAL", "no cut could be made from the chosen passages", data=warnings)
    groups: dict[str, list[str]] = {}
    for g, ref in cuts:
        groups.setdefault(g, []).append(ref)
    title = inp.title or f"What my creators think about {t['title']}"
    names = ", ".join(groups) if inp.by == "creator" else ", ".join(sorted({c["name"] for c, _, _ in (index[i] for i in ids)}))
    env = registry.run("journey.new", {"title": title, "intent": f"What {names} said about {t['title']}",
                                       "description": f"Compiled from topic {t['ref']} ({', '.join(t['terms'][:6])}).",
                                       "formats": inp.formats}, actor=ctx.actor, project=proj)
    if not env["ok"]:
        raise RecompError(env["error"]["code"], env["error"]["message"], hint=env["error"].get("hint"))
    jref = env["data"]["ref"]
    slot = 1
    for g, refs_ in groups.items():
        registry.run("journey.add", {"journey": jref, "cuts": refs_}, actor=ctx.actor, project=proj)
        registry.run("journey.section", {"journey": jref, "heading": g, "at": slot}, actor=ctx.actor, project=proj)
        slot += len(refs_)
    if inp.lower_thirds:
        lt = registry.run("overlay.auto-lower-thirds", {"journey": jref}, actor=ctx.actor, project=proj)
        if not lt["ok"]:
            warnings.append(f"lower thirds: {lt['error']['message']}")
    journeys = list(b.get("journeys") or []) + [{"project": proj.name, "journey": jref, "at": time.time()}]
    with sdb.op(ctx.verb_name, ctx.actor, ctx.args) as tx:
        tx.summary = f"{t['ref']} → {proj.name} {jref}"
        tx.update("topic", t["id"], {"brief": {**b, "journeys": journeys}})
    return Result(data={"journey": jref, "title": title, "sections": {g: r for g, r in groups.items()},
                        "cuts": [r for _, r in cuts], "sources": {k: v[0]["ref"] for k, v in sources.items()}},
                  refs=[jref] + [r for _, r in cuts], warnings=warnings,
                  next=[f"recomp journey show {jref}", f"recomp journey guide {jref}   # order it into an argument, then look and check"])
