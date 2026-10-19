"""Research wing, part one (P17a): find creators, follow them, an inbox of their new posts, a transcript library.

Studio-level: follows, the inbox and the library live in the studio store (``studio.db``), not in a project;
each follow names the projects it feeds. We follow people and shows we love and make journeys from what they
say (D-22); nothing here ranks what performs.
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
from ..research import feeds, library, podcasts, transcripts, youtube

RIGHTS = ("campaign", "permitted", "private")
ONLY = ("videos", "shorts", "all")


# ---- helpers ------------------------------------------------------------------------------------

def get_follow(db, target: str) -> dict:
    """A follow by ref (F2) or name."""
    row = db.by_ref("follow", target.upper()) if re.fullmatch(r"[Ff]\d+", target or "") else None
    if row is None:
        rows = db.rows("follow", "WHERE lower(name)=lower(?) OR lower(person)=lower(?)", (target, target))
        row = rows[0] if rows else None
    if row is None:
        raise RecompError("E_NOT_FOUND", f"no follow {target!r}", hint="`recomp follow list` shows them.")
    return row


def get_item(db, ref: str) -> dict:
    row = db.by_ref("inbox", ref.upper())
    if row is None:
        raise RecompError("E_NOT_FOUND", f"no inbox item {ref!r}", hint="`recomp inbox list` shows them.")
    return row


def get_doc(db, ref: str) -> dict:
    row = db.by_ref("lib_doc", ref.upper())
    if row is None:
        raise RecompError("E_NOT_FOUND", f"no library transcript {ref!r}", hint="`recomp library list` shows them.")
    return row


def project_name(target: str) -> str:
    """A registered project's name (validated), from its name, folder or path."""
    path = P.locate(target)
    if not (path / P.MANIFEST).exists():
        raise RecompError("E_NO_PROJECT", f"no project {target!r}",
                          hint="`recomp project list` shows them; `recomp project init <name>` makes one.")
    proj = P.Project(path)
    if proj.name not in config.registry()["projects"]:
        config.register_project(proj.name, proj.root, make_current=False)
    return proj.name


def _days(spec: str | None) -> float | None:
    """'2y', '18m', '90d' → days."""
    if not spec:
        return None
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*([dmy]?)", spec.strip().lower())
    if not m:
        raise RecompError("E_INVALID", f"{spec!r}: use 90d, 18m, 2y or a date", hint="e.g. --since 2y or --since 2024-01-01")
    return float(m.group(1)) * {"d": 1, "m": 30.44, "y": 365.25, "": 1}[m.group(2)]


def since_date(spec: str | None) -> str | None:
    if not spec:
        return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", spec.strip()):
        return spec.strip()
    days = _days(spec)
    return time.strftime("%Y-%m-%d", time.gmtime(time.time() - days * 86400))


def brief_follow(db, f: dict) -> dict:
    yt, pod = (f["feeds"] or {}).get("youtube"), (f["feeds"] or {}).get("podcast")
    counts = {r["status"]: r["n"] for r in db.all("SELECT status, COUNT(*) AS n FROM inbox WHERE follow_id=? GROUP BY status", (f["id"],))}
    docs = db.scalar("SELECT COUNT(*) FROM lib_doc WHERE follow_id=?", (f["id"],)) or 0
    st = f["state"] or {}
    return {"ref": f["ref"], "name": f["name"], "person": f["person"] or None, "projects": f["projects"],
            "youtube": yt.get("url") if yt else None, "podcast": pod.get("feed") if pod else None,
            "route": (pod or {}).get("route") or ("captions" if yt else None),
            "appearances": bool((f["feeds"] or {}).get("appearances")), "only": f["only_kind"], "match": f["match"] or None,
            "rights": (f["rights"] or {}).get("status", "private"), "inbox_new": counts.get("new", 0),
            "taken": counts.get("taken", 0), "library": docs, "checked": st.get("checked_at_iso"),
            "error": st.get("error")}


def brief_item(i: dict) -> dict:
    return {"ref": i["ref"], "title": i["title"], "kind": i["kind"], "channel": i["channel"], "published": i["published"],
            "duration": clock(i["duration"], 0) if i["duration"] else None, "url": i["url"], "project": i["project"] or None,
            "route": (i["route"] or {}).get("kind", "captions" if i["video_id"] else None), "status": i["status"],
            "taken": i["taken"] or None}


# ---- find ---------------------------------------------------------------------------------------

class FindIn(BaseModel):
    query: str = Field(..., description="A subject, a channel or show name, or a person", json_schema_extra={"pos": 0})
    kind: str = Field("all", description="channels, podcasts, person or all")
    limit: int = Field(8, description="Results per kind")
    routes: bool = Field(True, description="Check which podcasts publish transcripts (reads the start of each feed)")


@verb("find.creators", FindIn, effect="network", needs_project=False,
      examples=['recomp find creators "philosophy podcast"', 'recomp find creators "Alex O\'Connor" --kind person',
                'recomp find creators "Lex Fridman" --kind podcasts'])
def find_creators(ctx: Ctx, inp: FindIn):
    """Find channels, podcasts and a person's appearances to follow. Each result says how its transcripts can be had
    (published, lex, captions, asr); `recomp follow add <n>` follows result n."""
    if inp.kind not in ("channels", "podcasts", "person", "all"):
        raise RecompError("E_INVALID", "kind: channels, podcasts, person or all")
    results, warnings = [], []
    if inp.kind in ("channels", "all"):
        try:
            results += youtube.search_channels(inp.query, inp.limit)
        except RecompError as exc:
            warnings.append(f"YouTube channel search: {exc.message}")
    if inp.kind in ("podcasts", "all"):
        try:
            pods = podcasts.search(inp.query, inp.limit)
            for p in pods:
                p["route"] = None
            if inp.routes:
                # Each feed's start, read side by side (sequentially five feeds took ~40 s here).
                from concurrent.futures import ThreadPoolExecutor

                def peek(p):
                    try:
                        p["route"] = podcasts.peek_route(p["feed"])
                    except RecompError as exc:
                        p["route_error"] = exc.message
                with ThreadPoolExecutor(max_workers=5) as pool:
                    list(pool.map(peek, pods[:5]))
            results += pods
        except RecompError as exc:
            warnings.append(f"podcast search: {exc.message}")
    if inp.kind in ("person", "all"):
        try:
            person = youtube.search_person(inp.query, 40)
            for g in person["channels"][:inp.limit]:
                results.append({"kind": "appearances", "name": g["channel"], "url": g["url"], "channel_id": g["channel_id"],
                                "videos": len(g["videos"]), "examples": [v["title"] for v in g["videos"][:3]],
                                "route": "captions"})
        except RecompError as exc:
            warnings.append(f"person search: {exc.message}")
    for n, r in enumerate(results, start=1):
        r["n"] = n
        r["follow"] = f"recomp follow add {n} --project <project>"
    studio.set_state(ctx.studio, "find_results", {"query": inp.query, "results": results})
    if not results and warnings:
        raise RecompError("E_EXTERNAL", "; ".join(warnings), hint="Try again in a few minutes, or one kind at a time.")
    return Result(data={"query": inp.query, "results": results}, warnings=warnings,
                  next=["recomp follow add <n> --project <project> [--person \"…\"] [--podcast <feed|name>]"])


# ---- follow -------------------------------------------------------------------------------------

class FollowAddIn(BaseModel):
    target: str = Field(..., description="@handle or channel link, a podcast feed URL, a number from the last "
                                         "`find creators`, or a name", json_schema_extra={"pos": 0})
    project: list[str] = Field(default_factory=list, description="Projects this follow feeds (default: the current one)")
    name: str | None = Field(None, description="What to call it (default: the channel or show title)")
    person: str | None = Field(None, description="The person (host) this follow is about, e.g. \"Alex O'Connor\"")
    podcast: str | None = Field(None, description="Their podcast: feed URL or show name (looked up on iTunes)")
    appearances: bool = Field(False, description="Also watch for the person as a guest on other channels")
    only: str = Field("videos", description="videos, shorts or all")
    match: str | None = Field(None, description="Only items whose title matches (regex, case-insensitive)")
    rights: str = Field("private", description="campaign, permitted or private (D-23); applies to sources it brings in")
    evidence: str | None = Field(None, description="Link to the clipping program's terms or the creator's permission")
    note: str = ""


def _is_feed(url: str) -> bool:
    return bool(re.match(r"https?://", url)) and "youtube.com" not in url and "youtu.be" not in url


@verb("follow.add", FollowAddIn, effect="network", needs_project=False,
      examples=["recomp follow add @CosmicSkeptic --project alex-oconnor --person \"Alex O'Connor\" --podcast \"Within Reason\"",
                "recomp follow add https://lexfridman.com/feed/podcast --project ai-and-ideas --name \"Lex Fridman\"",
                "recomp follow add 3 --project ai-and-ideas"])
def follow_add(ctx: Ctx, inp: FollowAddIn):
    """Follow a creator or show: their YouTube channel and/or podcast feed, for the projects named. New posts land in
    the inbox on `follow check` (and every 2 h while the studio runs)."""
    if inp.only not in ONLY:
        raise RecompError("E_INVALID", f"only: {', '.join(ONLY)}")
    if inp.rights not in RIGHTS:
        raise RecompError("E_INVALID", f"rights: {', '.join(RIGHTS)}")
    if inp.rights != "private" and not inp.evidence:
        raise RecompError("E_INVALID", f"{inp.rights} needs --evidence (the program's terms or the creator's permission)",
                          hint="Without evidence a source stays private: everything works except the posting queue.")
    if inp.match:
        re.compile(inp.match)
    db = ctx.studio
    target = inp.target.strip()
    yt = pod = None
    found = None
    if target.isdigit():
        res = (studio.get_state(db, "find_results") or {}).get("results") or []
        found = next((r for r in res if str(r["n"]) == target), None)
        if found is None:
            raise RecompError("E_NOT_FOUND", f"{target} is not in the last `find creators` results",
                              hint="Run `recomp find creators \"…\"` again.")
        target = found.get("feed") or found.get("url") or ""
    if _is_feed(target):
        show = podcasts.read_head(target)
        pod = {"feed": target, "title": show["title"], "author": show["author"],
               "route": (show["items"][0]["route"]["kind"] if show["items"] else "none")}
    elif target.startswith("@") or "youtube.com" in target or re.fullmatch(r"UC[\w-]{22}", target):
        yt = youtube.resolve_channel(target)
    else:
        hits = youtube.search_channels(target, 1)
        if not hits:
            raise RecompError("E_NOT_FOUND", f"no channel found for {target!r}", hint=f"`recomp find creators \"{target}\"`")
        yt = youtube.resolve_channel(hits[0]["url"])
    if inp.podcast and pod is None:
        feed_url = inp.podcast if _is_feed(inp.podcast) else None
        if feed_url is None:
            pods = podcasts.search(inp.podcast, 3)
            if not pods:
                raise RecompError("E_NOT_FOUND", f"no podcast found for {inp.podcast!r}", hint="Give the feed URL instead.")
            feed_url = pods[0]["feed"]
        show = podcasts.read_head(feed_url)
        pod = {"feed": feed_url, "title": show["title"], "author": show["author"],
               "route": (show["items"][0]["route"]["kind"] if show["items"] else "none")}
    for other in db.rows("follow"):
        oyt, opod = (other["feeds"] or {}).get("youtube") or {}, (other["feeds"] or {}).get("podcast") or {}
        if (yt and yt.get("channel_id") and oyt.get("channel_id") == yt["channel_id"]) or \
                (pod and opod.get("feed") == pod["feed"]):
            raise RecompError("E_EXISTS", f"already followed as {other['ref']} ({other['name']})",
                              hint=f"`recomp follow edit {other['ref']} …` changes it.")
    projects = [project_name(p) for p in inp.project]
    if not projects:
        try:
            projects = [P.resolve(None).name]
        except RecompError:
            projects = []
    name = inp.name or (yt or {}).get("channel") or (pod or {}).get("title") or target
    # A show followed on its own speaks with its host's voice (the library and briefs name the person):
    # "The Diary Of A CEO with Steven Bartlett" → Steven Bartlett, else the feed's author.
    person = inp.person or ""
    if not person and pod and not yt:
        m = re.search(r"\bwith\s+([A-Z][\w.'-]+(?:\s+[A-Z][\w.'-]+){0,3})\s*$", pod.get("title") or "")
        person = m.group(1) if m else (pod.get("author") or "")
    if inp.appearances and not person:
        raise RecompError("E_INVALID", "--appearances needs --person (whose guest appearances to watch)")
    rights = {"status": inp.rights}
    if inp.evidence:
        rights["evidence"] = inp.evidence
    with ctx.studio_op(f"follow {name}") as tx:
        row = tx.insert("follow", {"name": name, "person": person, "projects": projects,
                                   "feeds": {"youtube": yt, "podcast": pod, "appearances": inp.appearances},
                                   "only_kind": inp.only, "match": inp.match or "", "rights": rights, "note": inp.note,
                                   "state": {}})
    warnings = [] if projects else ["no project named: new items wait in the inbox until `inbox take … --project P`"]
    return Result(data=brief_follow(db, row), refs=[row["ref"]], warnings=warnings,
                  next=[f"recomp follow check --follow {row['ref']}   # newest items into the inbox",
                        f"recomp follow backfill {row['ref']}   # back catalogue transcripts into the library"])


class FollowListIn(BaseModel):
    project: str | None = Field(None, description="Only follows feeding this project")


@verb("follow.list", FollowListIn, needs_project=False, examples=["recomp follow list", "recomp follow list --project alex-oconnor"])
def follow_list(ctx: Ctx, inp: FollowListIn):
    """Followed creators and shows: feeds, transcript route, new inbox items, library size, last check."""
    db = ctx.studio
    rows = db.rows("follow", "ORDER BY created_at")
    if inp.project:
        name = project_name(inp.project)
        rows = [r for r in rows if name in (r["projects"] or [])]
    return [brief_follow(db, r) for r in rows]


class FollowEditIn(BaseModel):
    ref: str = Field(..., description="Follow ref or name", json_schema_extra={"pos": 0})
    name: str | None = None
    person: str | None = None
    project: list[str] | None = Field(None, description="Replace the projects it feeds")
    podcast: str | None = Field(None, description="Set the podcast feed (URL or show name)")
    appearances: bool | None = None
    only: str | None = None
    match: str | None = Field(None, description="Title filter (regex); \"\" clears it")
    rights: str | None = Field(None, description="campaign, permitted or private")
    evidence: str | None = None
    note: str | None = None


@verb("follow.edit", FollowEditIn, effect="write", needs_project=False,
      examples=['recomp follow edit F1 --project alex-oconnor,ai-and-ideas', 'recomp follow edit F2 --match "AI|conscious"'])
def follow_edit(ctx: Ctx, inp: FollowEditIn):
    """Change a follow: name, person, projects, podcast feed, appearances, title filter, rights, note."""
    db = ctx.studio
    f = get_follow(db, inp.ref)
    fields: dict = {}
    for k in ("name", "person", "note"):
        if getattr(inp, k) is not None:
            fields[k] = getattr(inp, k)
    if inp.project is not None:
        fields["projects"] = [project_name(p) for p in inp.project]
    if inp.only is not None:
        if inp.only not in ONLY:
            raise RecompError("E_INVALID", f"only: {', '.join(ONLY)}")
        fields["only_kind"] = inp.only
    if inp.match is not None:
        if inp.match:
            re.compile(inp.match)
        fields["match"] = inp.match
    feeds_ = dict(f["feeds"] or {})
    if inp.appearances is not None:
        feeds_["appearances"] = inp.appearances
    if inp.podcast is not None:
        feed_url = inp.podcast if _is_feed(inp.podcast) else (podcasts.search(inp.podcast, 1) or [{}])[0].get("feed")
        if not feed_url:
            raise RecompError("E_NOT_FOUND", f"no podcast found for {inp.podcast!r}")
        show = podcasts.read_head(feed_url)
        feeds_["podcast"] = {"feed": feed_url, "title": show["title"], "author": show["author"],
                             "route": show["items"][0]["route"]["kind"] if show["items"] else "none"}
    if feeds_ != (f["feeds"] or {}):
        fields["feeds"] = feeds_
    if inp.rights is not None or inp.evidence is not None:
        rights = dict(f["rights"] or {})
        if inp.rights is not None:
            if inp.rights not in RIGHTS:
                raise RecompError("E_INVALID", f"rights: {', '.join(RIGHTS)}")
            rights["status"] = inp.rights
        if inp.evidence is not None:
            rights["evidence"] = inp.evidence
        if rights.get("status", "private") != "private" and not rights.get("evidence"):
            raise RecompError("E_INVALID", f"{rights['status']} needs --evidence")
        fields["rights"] = rights
    with ctx.studio_op(f"edit {f['ref']}") as tx:
        row = tx.update("follow", f["id"], fields)
    return brief_follow(db, row)


class FollowRemoveIn(BaseModel):
    ref: str = Field(..., json_schema_extra={"pos": 0})
    library: bool = Field(False, description="Also drop its transcripts from the library")


@verb("follow.remove", FollowRemoveIn, effect="write", needs_project=False)
def follow_remove(ctx: Ctx, inp: FollowRemoveIn):
    """Stop following. Its inbox items go too (undo restores them); library transcripts stay unless --library."""
    db = ctx.studio
    f = get_follow(db, inp.ref)
    dropped = 0
    with ctx.studio_op(f"unfollow {f['name']}") as tx:
        if inp.library:
            for d in db.rows("lib_doc", "WHERE follow_id=?", (f["id"],)):
                library.remove_doc(tx, d)
                dropped += 1
        tx.delete("follow", f["id"])
    return {"removed": f["ref"], "name": f["name"], "library_removed": dropped}


# ---- checking for new items ------------------------------------------------------------------------

def _collect(f: dict) -> list[dict]:
    """Every current item of a follow (newest first): uploads, podcast episodes paired with them, appearances."""
    fd = f["feeds"] or {}
    yt, pod = fd.get("youtube"), fd.get("podcast")
    items: list[dict] = []
    episodes = podcasts.read(pod["feed"])["items"][:60] if pod else []
    if yt:
        for v in youtube.uploads(yt, f["only_kind"] or "videos", limit=30):
            item = {"key": f"yt:{v['video_id']}", "kind": v["kind"], "title": v["title"], "channel": yt.get("channel") or "",
                    "url": v["url"], "video_id": v["video_id"], "published": v.get("published"), "duration": v.get("duration"),
                    "route": {"kind": "captions", "timing": "video"}, "meta": {"views": v.get("views")}}
            # The same episode in the podcast feed may publish its transcript: pair by title words.
            best, score = None, 0.0
            for ep in episodes:
                s = feeds.title_match(v["title"], ep["title"])
                if ep.get("video_id") == v["video_id"]:
                    s = 1.0
                if s > score:
                    best, score = ep, s
            if best is not None and score >= 0.45:
                item["published"] = item["published"] or best["published"]
                item["duration"] = item["duration"] or best["duration"]
                item["meta"]["podcast"] = {"guid": best["guid"], "title": best["title"], "audio_url": best["audio_url"],
                                           "match": round(score, 2)}
                if best["route"]["kind"] in ("published", "lex"):
                    item["route"] = best["route"]
            items.append(item)
    elif pod:
        for ep in episodes:
            items.append({"key": f"pod:{ep['guid']}", "kind": "episode", "title": ep["title"], "channel": pod.get("title") or "",
                          "url": ep["link"] or ep["audio_url"] or "", "video_id": ep.get("video_id"), "published": ep["published"],
                          "duration": ep["duration"], "route": ep["route"],
                          "meta": {"audio_url": ep["audio_url"], "guid": ep["guid"], "description": ep["description"][:600]}})
    person = f["person"] or (pod or {}).get("author")
    if fd.get("appearances") and person:
        own = (yt or {}).get("channel_id")
        for g in youtube.search_person(person, 20)["channels"]:
            if own and g["channel_id"] == own:
                continue
            for v in g["videos"]:
                items.append({"key": f"yt:{v['video_id']}", "kind": "appearance", "title": v["title"], "channel": g["channel"] or "",
                              "url": v["url"], "video_id": v["video_id"], "published": None, "duration": v["duration"],
                              "route": {"kind": "captions", "timing": "video"}, "meta": {"views": v.get("views")}})
    if f["match"]:
        rx = re.compile(f["match"], re.I)
        items = [i for i in items if rx.search(i["title"] or "")]
    seen, out = set(), []
    for i in items:
        if i["key"] not in seen:
            seen.add(i["key"])
            out.append(i)
    return out


def check_follow(ctx: Ctx, f: dict, first_n: int) -> dict:
    db = ctx.studio
    items = _collect(f)
    seen = {r["key"] for r in db.all("SELECT key FROM follow_seen WHERE follow_id=?", (f["id"],))}
    first = not (f["state"] or {}).get("checked_at") or not seen  # never checked (or restored by undo)
    fresh = [i for i in items if i["key"] not in seen]
    to_inbox = fresh[:first_n] if first else fresh
    project = (f["projects"] or [""])[0]
    added = []
    now = time.time()
    # Feed reading is machine work, whoever pressed Check: the items are the machine's, the choices are yours.
    with db.op(ctx.verb_name, "machine", ctx.args) as tx:
        tx.summary = f"check {f['name']}: {len(to_inbox)} new"
        for i in to_inbox:
            row = tx.insert("inbox", {"follow_id": f["id"], "project": project, **i})
            added.append(row)
        tx.conn.executemany("INSERT OR IGNORE INTO follow_seen(follow_id, key, at) VALUES(?,?,?)",
                            [(f["id"], i["key"], now) for i in items])
        tx.update("follow", f["id"], {"state": {"checked_at": now, "checked_at_iso": time.strftime("%Y-%m-%d %H:%M", time.localtime(now)),
                                                "items": len(items), "new": len(to_inbox), "error": None,
                                                "first_check_held_back": max(0, len(fresh) - len(to_inbox)) if first else 0}})
        if added:
            tx.event("inbox", {"follow": f["ref"], "new": [r["ref"] for r in added]})
    if tx.op_id:
        ctx.last_op = tx.op_id
    return {"follow": f["ref"], "name": f["name"], "new": [brief_item(r) for r in added],
            "first_check": first, "held_back": (len(fresh) - len(to_inbox)) if first else 0}


class CheckIn(BaseModel):
    follow: list[str] = Field(default_factory=list, description="Only these follows (default: all)")
    first: int | None = Field(None, description="On a follow's first check, how many of the newest items to put in the inbox")


@verb("follow.check", CheckIn, effect="network", needs_project=False,
      examples=["recomp follow check", "recomp follow check --follow F2"])
def follow_check(ctx: Ctx, inp: CheckIn):
    """Look for new posts from followed creators; new ones go to the inbox of the follow's first project.
    A follow's first check takes only the newest few (`research.first_check_items`) and marks the rest as seen."""
    db = ctx.studio
    rows = [get_follow(db, r) for r in inp.follow] if inp.follow else db.rows("follow", "ORDER BY created_at")
    if not rows:
        raise RecompError("E_NOT_FOUND", "nothing is followed yet", hint="`recomp find creators \"…\"`, then `recomp follow add`.")
    first_n = inp.first if inp.first is not None else int(config.get("research.first_check_items") or 3)
    out, warnings = [], []
    for f in rows:
        try:
            out.append(check_follow(ctx, f, first_n))
        except RecompError as exc:
            warnings.append(f"{f['ref']} {f['name']}: {exc.message}")
            with db.op(ctx.verb_name, "machine", ctx.args) as tx:
                st = dict(f["state"] or {})
                st.update({"error": exc.message, "error_at": time.time()})
                tx.update("follow", f["id"], {"state": st}, log=False)
            out.append({"follow": f["ref"], "name": f["name"], "new": [], "error": exc.message})
    studio.set_state(db, "last_check", {"at": time.time(), "follows": len(rows)})
    total = sum(len(o["new"]) for o in out)
    return Result(data={"new": total, "follows": out}, warnings=warnings,
                  refs=[i["ref"] for o in out for i in o["new"]],
                  next=["recomp inbox list", "recomp inbox take <I…>   # into the project: transcript, chapters, cut candidates"]
                  if total else [])


# ---- the inbox ----------------------------------------------------------------------------------

class InboxListIn(BaseModel):
    project: str | None = None
    status: str = Field("new", description="new, taken, dismissed or all")
    follow: str | None = None
    limit: int = 50


@verb("inbox.list", InboxListIn, needs_project=False, examples=["recomp inbox list", "recomp inbox list --status all --follow F1"])
def inbox_list(ctx: Ctx, inp: InboxListIn):
    """New posts from followed creators, waiting to be taken into a project or dismissed."""
    db = ctx.studio
    where, params = [], []
    if inp.status != "all":
        where.append("status=?")
        params.append(inp.status)
    if inp.project:
        where.append("project=?")
        params.append(project_name(inp.project))
    if inp.follow:
        where.append("follow_id=?")
        params.append(get_follow(db, inp.follow)["id"])
    sql = ("WHERE " + " AND ".join(where)) if where else ""
    rows = db.rows("inbox", f"{sql} ORDER BY created_at DESC, ref DESC LIMIT ?", (*params, inp.limit))
    names = {f["id"]: f["name"] for f in db.rows("follow")}
    return [{**brief_item(r), "follow": names.get(r["follow_id"])} for r in rows]


class TakeIn(BaseModel):
    refs: list[str] = Field(..., description="Inbox items", json_schema_extra={"pos": 0})
    project: str | None = Field(None, description="Take into this project (default: the item's)")
    suggest: bool = Field(True, description="Suggest cuts on the project's themes when a transcript is ready")


def _themes(proj: P.Project, f: dict | None) -> list[str]:
    themes = list(proj.meta.get("themes") or [])
    if not themes and f and f.get("match"):
        themes = [t for t in re.split(r"[|,]", f["match"]) if len(t) > 2]
    return themes


def take_item(ctx: Ctx, item: dict, project: str, suggest: bool) -> dict:
    db = ctx.studio
    f = db.get("follow", item["follow_id"]) if item["follow_id"] else None
    pname = project_name(project)
    proj = P.Project(P.locate(pname))
    route = item["route"] or {}
    out: dict = {"item": item["ref"], "project": pname, "steps": []}
    try:
        pctx = Ctx(actor=ctx.actor, project=proj, verb_name="inbox.take", args={"item": item["ref"]})
        transcript_now = route.get("kind") in ("lex", "published")
        # Published words first: a Lex page also names the episode's YouTube video (and follows its clock).
        words = transcripts.fetch(route) if transcript_now else None
        video_id = item["video_id"] or (words or {}).get("video_id")
        if video_id:
            from .ui import set_state
            url = item["url"] if item["video_id"] else f"https://www.youtube.com/watch?v={video_id}"
            entry = {"n": 1, "id": video_id, "title": item["title"], "duration_s": item["duration"],
                     "duration": clock(item["duration"], 0) if item["duration"] else None, "url": url,
                     "views": (item["meta"] or {}).get("views"), "date": (item["published"] or "").replace("-", "") or None}
            set_state(proj.db, "pick_list", {"url": url, "title": item["title"], "channel": item["channel"], "entries": [entry]})
            # Lex transcripts follow the video's clock: no need to ask YouTube for captions.
            env = registry.run("source.add", {"pick": ["1"], "subtitles": route.get("kind") != "lex"},
                               actor=ctx.actor, project=proj)
            if not env["ok"]:
                raise RecompError(env["error"]["code"], env["error"]["message"], hint=env["error"].get("hint"))
            got = (env["data"]["added"] or env["data"]["skipped"])[0]
            ref = got["ref"]
            out["steps"].append({"source.add": ref, "jobs": env["data"].get("jobs") or [], "warnings": env.get("warnings") or []})
        else:
            ref = _add_episode(pctx, item, f)
            out["steps"].append({"source.add": ref, "kind": "podcast episode (audio)"})
        out["source"] = ref
        src = proj.db.by_ref("source", ref)
        # Rights from the follow (D-23): campaign / permitted / private.
        if f and (f["rights"] or {}).get("status"):
            rights = dict(src["rights"] or {})
            rights.update({k: v for k, v in f["rights"].items() if k in ("status", "evidence")})
            with pctx.op(f"rights {ref} from {f['ref']}") as tx:
                src = tx.update("source", src["id"], {"rights": rights})
        has_tr = proj.db.one("SELECT 1 FROM transcript WHERE source_id=?", (src["id"],))
        if words and not has_tr:
            got = words
            on_audio = not video_id
            video_clock = got.get("timing") == "video" or on_audio  # a feed transcript fits the feed's own audio
            from ..transcript.store import add_transcript
            label = {"lex": "lexfridman.com transcript", "published": "the podcast's published transcript"}[route["kind"]]
            if not video_clock:
                label += " (podcast timing: align before cutting video)"
            with pctx.op(f"transcript for {ref} ({route['kind']})") as tx:
                tr = add_transcript(tx, src, got["segments"], origin="published", language=src.get("language") or "en",
                                    label=label, make_primary=video_clock,
                                    stats={"route": route["kind"], "timing": "video" if video_clock else "podcast",
                                           "url": route.get("url")})
            out["steps"].append({"transcript": tr["ref"], "route": route["kind"], "lines": len(got["segments"]),
                                 "primary": bool(video_clock)})
            if got.get("chapters") and not (src["meta"] or {}).get("chapters"):
                meta = dict(src["meta"] or {})
                meta["chapters"] = [{"start": c["start"], "end": c["end"], "title": c["title"]} for c in got["chapters"]]
                with pctx.op(f"chapters for {ref} from the transcript page") as tx:
                    src = tx.update("source", src["id"], {"meta": meta}, log=False)
        elif route.get("kind") == "asr" and not video_id:
            env = registry.run("transcript.asr", {"ref": ref}, actor=ctx.actor, project=proj)
            out["steps"].append({"transcript.asr": env["data"] if env["ok"] else env["error"]["message"]})
        if (src["meta"] or {}).get("chapters") and not proj.db.one("SELECT 1 FROM chapter WHERE source_id=?", (src["id"],)):
            env = registry.run("chapter.seed", {"ref": ref}, actor=ctx.actor, project=proj)
            out["steps"].append({"chapter.seed": len(env["data"]) if env["ok"] and isinstance(env["data"], list) else
                                 (env["data"] if env["ok"] else env["error"]["message"])})
        primary = proj.db.one("SELECT 1 FROM transcript WHERE source_id=? AND is_primary=1", (src["id"],))
        themes = _themes(proj, f)
        out["candidates"] = []
        if suggest and primary and themes:
            for theme in themes[:4]:
                env = registry.run("cut.suggest", {"query": theme, "sources": [ref], "limit": 3}, actor=ctx.actor, project=proj)
                if env["ok"]:
                    out["candidates"] += [{**c, "theme": theme} for c in env["data"]["candidates"]]
        out["next"] = ([f"recomp cut add {ref} --from … --to … --title \"…\" --why \"…\""] if out["candidates"] else []) + \
            ([f"recomp job wait {j} --timeout 120" for s in out["steps"] for j in s.get("jobs", [])]) + \
            ([] if themes else [f"recomp project set --themes \"…\"   # then: recomp cut suggest \"<theme>\" --sources {ref}"]) + \
            [f"recomp chapter list --source {ref}"]
    finally:
        proj.close()
    taken = {"project": pname, "source": out["source"], "at": time.time(), "candidates": len(out["candidates"])}
    with ctx.studio_op(f"take {item['ref']} into {pname}") as tx:
        tx.update("inbox", item["id"], {"status": "taken", "taken": taken, "project": pname})
    return out


def _add_episode(pctx: Ctx, item: dict, f: dict | None) -> str:
    """A podcast episode without a YouTube video: an audio link source (cut and play from the feed's audio)."""
    db = pctx.db
    meta = item["meta"] or {}
    audio = meta.get("audio_url") or item["url"]
    existing = db.one("SELECT ref FROM source WHERE uri=?", (audio,))
    if existing:
        return existing["ref"]
    show = item["channel"]
    year = int(item["published"][:4]) if item["published"] else None
    with pctx.op(f"add episode {item['title'][:60]}") as tx:
        src = tx.insert("source", {
            "kind": "link", "uri": audio, "platform": "podcast", "platform_id": meta.get("guid"), "title": item["title"],
            "creator": (f or {}).get("person") or show, "year": year, "language": "en", "duration": item["duration"],
            "rights": {"kind": "link", "owner": show, "url": item["url"],
                       "notice": f"\"{item['title']}\", {show}" + (f" (podcast, {year})" if year else ""),
                       "licence": "platform standard licence"},
            "status": {"probe": "metadata"},
            "meta": {"podcast": True, "feed_item": meta.get("guid"), "page": item["url"],
                     "description": meta.get("description", ""), "chapters": []}})
    return src["ref"]


@verb("inbox.take", TakeIn, effect="network", needs_project=False,
      examples=["recomp inbox take I3", "recomp inbox take I3 I4 --project ai-and-ideas"])
def inbox_take(ctx: Ctx, inp: TakeIn):
    """Take new posts into a project: the source (metadata first), its transcript by the cheapest route, the creator's
    chapters, and cut candidates on the project's themes (`project set --themes`)."""
    db = ctx.studio
    out, warnings = [], []
    for r in inp.refs:
        item = get_item(db, r)
        if item["status"] == "taken":
            warnings.append(f"{item['ref']} was already taken into {item['taken'].get('project')} as {item['taken'].get('source')}")
            continue
        project = inp.project or item["project"]
        if not project:
            raise RecompError("E_INVALID", f"{item['ref']} has no project", hint=f"`recomp inbox take {item['ref']} --project <name>`")
        out.append(take_item(ctx, item, project, inp.suggest))
    return Result(data={"taken": out}, warnings=warnings, refs=[o["source"] for o in out])


class DismissIn(BaseModel):
    refs: list[str] = Field(..., json_schema_extra={"pos": 0})


@verb("inbox.dismiss", DismissIn, effect="write", needs_project=False, examples=["recomp inbox dismiss I5 I6"])
def inbox_dismiss(ctx: Ctx, inp: DismissIn):
    """Not for us: dismissed items stay out of the inbox (a later check does not bring them back)."""
    db = ctx.studio
    items = [get_item(db, r) for r in inp.refs]
    with ctx.studio_op(f"dismiss {', '.join(i['ref'] for i in items)}") as tx:
        for i in items:
            tx.update("inbox", i["id"], {"status": "dismissed"})
    return {"dismissed": [i["ref"] for i in items]}


# ---- the library ----------------------------------------------------------------------------------

class BackfillIn(BaseModel):
    ref: str = Field(..., description="Follow ref or name", json_schema_extra={"pos": 0})
    since: str | None = Field(None, description="How far back: 2y, 18m, 90d or a date (default research.backfill_since)")
    limit: int = Field(20, description="Transcripts to fetch in this run (run again to continue)")
    captions: bool = Field(True, description="For YouTube-only creators, fetch the videos' captions (one request each)")


@verb("follow.backfill", BackfillIn, effect="network", needs_project=False,
      examples=["recomp follow backfill F2", "recomp follow backfill \"Lex Fridman\" --since 2024-01-01 --limit 50"])
def follow_backfill(ctx: Ctx, inp: BackfillIn):
    """The back catalogue's transcripts (text only, no video) into the studio library, so "what did they say before"
    is a search: `recomp library search "…"`. Resumable: each run fetches up to --limit more."""
    db = ctx.studio
    f = get_follow(db, inp.ref)
    since = since_date(inp.since or config.get("research.backfill_since") or "2y")
    fd = f["feeds"] or {}
    have = {r["key"] for r in db.all("SELECT key FROM lib_doc WHERE follow_id=?", (f["id"],))}
    todo, skipped, warnings = [], {"needs_asr": 0, "older": 0}, []
    if fd.get("podcast"):
        show = podcasts.read(fd["podcast"]["feed"])
        for ep in show["items"]:
            if ep["published"] and ep["published"] < since:
                skipped["older"] += 1
                continue
            if ep["route"]["kind"] == "asr":
                skipped["needs_asr"] += 1
                continue
            if ep["route"]["kind"] == "none":
                continue
            key = f"pod:{ep['guid']}"
            if key not in have:
                todo.append({"key": key, "title": ep["title"], "published": ep["published"], "url": ep["link"] or ep["audio_url"],
                             "video_id": ep.get("video_id"), "route": ep["route"]})
    if fd.get("youtube") and inp.captions and not todo and not (fd.get("podcast") and fd["podcast"].get("route") in ("published", "lex")):
        for v in youtube.uploads(fd["youtube"], f["only_kind"] or "videos", limit=200):
            key = f"yt:{v['video_id']}"
            if key not in have:
                todo.append({"key": key, "title": v["title"], "published": v.get("published"), "url": v["url"],
                             "video_id": v["video_id"], "route": {"kind": "captions", "video_id": v["video_id"], "timing": "video"}})
    done = []
    for t in todo[:inp.limit]:
        try:
            got = transcripts.fetch(t["route"])
        except RecompError as exc:
            warnings.append(f"{t['title'][:60]}: {exc.message}")
            if exc.code == "E_EXTERNAL" and t["route"]["kind"] == "captions":
                warnings.append("YouTube is refusing caption requests; stopped. Run again later (or set network.cookies_file).")
                break
            continue
        if not got["segments"]:
            continue
        with db.op(ctx.verb_name, "machine", ctx.args) as tx:
            tx.summary = f"library: {t['title'][:60]}"
            doc = library.add_doc(tx, f, t["key"], {"creator": f["person"] or f["name"], "title": t["title"],
                                                   "published": t["published"] or got.get("published"), "url": t["url"],
                                                   "video_id": got.get("video_id") or t["video_id"],
                                                   "route": {**t["route"], "timing": got.get("timing")},
                                                   "chapters": got.get("chapters") or []}, got["segments"])
        done.append({"ref": doc["ref"], "title": t["title"], "published": t["published"], "lines": len(got["segments"]),
                     "route": t["route"]["kind"]})
    remaining = max(0, len(todo) - len(done)) if len(done) < len(todo) else 0
    return Result(data={"follow": f["ref"], "since": since, "added": done, "remaining": remaining,
                        "library": len(have) + len(done), "skipped": skipped}, warnings=warnings,
                  next=([f"recomp follow backfill {f['ref']}   # {remaining} more"] if remaining else []) +
                  ["recomp library search \"…\""])


class LibSearchIn(BaseModel):
    query: str = Field(..., description='Words or "exact phrases"', json_schema_extra={"pos": 0})
    creator: list[str] = Field(default_factory=list, description="Only these creators (follow person or name)")
    since: str | None = Field(None, description="Only episodes since (2y, 2024-01-01)")
    until: str | None = Field(None, description="Only episodes until (date)")
    limit: int = 20
    context: int = 1


@verb("library.search", LibSearchIn, needs_project=False,
      examples=['recomp library search "copy itself"', 'recomp library search consciousness --creator "Lex Fridman" --since 2y'])
def library_search(ctx: Ctx, inp: LibSearchIn):
    """Search what the followed creators said, across their back catalogue (same as `search --scope library`)."""
    return library.search(ctx.studio, inp.query, inp.creator or None, since_date(inp.since) if inp.since else None,
                          inp.until, inp.limit, inp.context)


class LibListIn(BaseModel):
    follow: str | None = None
    limit: int = 100


@verb("library.list", LibListIn, needs_project=False, examples=["recomp library list --follow F2"])
def library_list(ctx: Ctx, inp: LibListIn):
    """Transcripts in the studio library: creator, episode, date, route, size."""
    db = ctx.studio
    if inp.follow:
        rows = db.rows("lib_doc", "WHERE follow_id=? ORDER BY published DESC LIMIT ?", (get_follow(db, inp.follow)["id"], inp.limit))
    else:
        rows = db.rows("lib_doc", "ORDER BY published DESC LIMIT ?", (inp.limit,))
    return [{"ref": d["ref"], "creator": d["creator"], "title": d["title"], "published": d["published"],
             "route": (d["route"] or {}).get("kind"), "timing": (d["route"] or {}).get("timing"),
             "lines": (d["stats"] or {}).get("lines"), "length": clock((d["stats"] or {}).get("spoken_s") or 0, 0)} for d in rows]


class LibShowIn(BaseModel):
    ref: str = Field(..., json_schema_extra={"pos": 0})
    from_: str | None = Field(None, alias="from", description="Start time (1:02:03)")
    to: str | None = None
    limit: int = Field(80, description="Lines to show")


@verb("library.show", LibShowIn, needs_project=False, examples=["recomp library show L4 --from 35:00 --to 37:00"])
def library_show(ctx: Ctx, inp: LibShowIn):
    """Read a library transcript (a stretch of it), with speakers and times."""
    from ..core.timecode import parse
    db = ctx.studio
    d = get_doc(db, inp.ref)
    a = parse(inp.from_) if inp.from_ else 0.0
    b = parse(inp.to) if inp.to else 1e9
    rows = db.all('SELECT start, "end", speaker, text FROM lib_seg WHERE doc_id=? AND "end">? AND start<? ORDER BY idx LIMIT ?',
                  (d["id"], a, b, inp.limit))
    return {"ref": d["ref"], "creator": d["creator"], "title": d["title"], "published": d["published"], "url": d["url"],
            "video_id": d["video_id"], "timing": (d["route"] or {}).get("timing"), "chapters": (d["stats"] or {}).get("chapters"),
            "lines": [{"at": clock(r["start"]), "start": round(r["start"], 2), "speaker": r["speaker"], "text": r["text"]} for r in rows]}


class LibRemoveIn(BaseModel):
    refs: list[str] = Field(..., json_schema_extra={"pos": 0})


@verb("library.remove", LibRemoveIn, effect="write", needs_project=False)
def library_remove(ctx: Ctx, inp: LibRemoveIn):
    """Drop transcripts from the library (run `follow backfill` to fetch them again)."""
    db = ctx.studio
    docs = [get_doc(db, r) for r in inp.refs]
    with ctx.studio_op(f"library remove {len(docs)}") as tx:
        for d in docs:
            library.remove_doc(tx, d)
    return {"removed": [d["ref"] for d in docs]}
