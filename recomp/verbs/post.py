"""Posting (P17c, D-10 and D-23): your channel, and a queue of exports you will upload yourself.

Only ``campaign`` and ``permitted`` sources may enter the queue (the gate is here, in the verb); every post
credits its creators (the export's description). Recomposer never uploads: `post open` hands you the file and the
text, and `post link` records where you posted it (on the journey and its hub recipe). Your own channel's numbers
are read-only (`channel stats`).
"""

from __future__ import annotations

import csv
import io
import re
import time
from pathlib import Path

from pydantic import BaseModel, Field

from .. import registry
from ..core import config, refs
from ..core import project as P
from ..core import rights as RS
from ..envelope import RecompError, Result
from ..registry import Ctx, NoInput, verb

UPLOAD_PAGES = {"youtube": "https://studio.youtube.com/", "tiktok": "https://www.tiktok.com/upload",
                "instagram": "https://www.instagram.com/"}
STATUSES = ("planned", "opened", "posted", "cancelled")


# ---- channel ----------------------------------------------------------------------------------------

def default_channel(ctx: Ctx, create: bool = True) -> dict | None:
    db = ctx.studio
    rows = db.rows("channel", "ORDER BY created_at LIMIT 1")
    if rows or not create:
        return rows[0] if rows else None
    # P17-Q3: a placeholder until you name your channel; posting works on it meanwhile.
    with db.op("channel.set", "machine", {}) as tx:
        tx.summary = "placeholder channel"
        return tx.insert("channel", {"name": "My channel (placeholder)", "platform": "youtube", "placeholder": 1})


def brief_channel(c: dict) -> dict:
    st = c["stats"] or {}
    return {"ref": c["ref"], "name": c["name"], "platform": c["platform"], "handle": c["handle"] or None,
            "url": c["url"] or None, "placeholder": bool(c["placeholder"]), "stats_imported": st.get("imported_at_iso"),
            "totals": st.get("totals")}


class ChannelSetIn(BaseModel):
    name: str | None = Field(None, description="What the channel is called")
    platform: str | None = Field(None, description="youtube, tiktok or instagram")
    handle: str | None = Field(None, description="@handle")
    url: str | None = None


@verb("channel.set", ChannelSetIn, effect="write", needs_project=False,
      examples=['recomp channel set --name "Ideas in a minute" --handle @ideasinaminute --platform youtube'])
def channel_set(ctx: Ctx, inp: ChannelSetIn):
    """Name the channel you post to (one channel; a placeholder is used until you do)."""
    fields = inp.model_dump(exclude_none=True)
    if "platform" in fields and fields["platform"] not in UPLOAD_PAGES:
        raise RecompError("E_INVALID", f"platform: {', '.join(UPLOAD_PAGES)}")
    if fields.get("handle") and not fields["handle"].startswith("@"):
        fields["handle"] = "@" + fields["handle"]
    if fields.get("handle") and not fields.get("url") and fields.get("platform", "youtube") == "youtube":
        fields["url"] = f"https://www.youtube.com/{fields['handle']}"
    c = default_channel(ctx, create=False)
    with ctx.studio_op(f"channel {fields.get('name') or ''}".strip()) as tx:
        if c is None:
            if not fields.get("name"):
                raise RecompError("E_INVALID", "give the channel a --name")
            c = tx.insert("channel", {"platform": "youtube", **fields, "placeholder": 0})
        else:
            c = tx.update("channel", c["id"], {**fields, "placeholder": 0} if fields.get("name") else fields)
    return brief_channel(c)


@verb("channel.show", NoInput, needs_project=False)
def channel_show(ctx: Ctx, inp: NoInput):
    """Your channel (or the placeholder), its imported numbers and the post counts."""
    c = default_channel(ctx, create=False)
    if c is None:
        return {"channel": None, "hint": "`recomp channel set --name … --handle @…`"}
    counts = {r["status"]: r["n"] for r in ctx.studio.all("SELECT status, COUNT(*) AS n FROM post GROUP BY status")}
    return {**brief_channel(c), "posts": counts}


class StatsIn(BaseModel):
    csv: str | None = Field(None, description="A YouTube Studio export (Analytics › Advanced › Export › Table data.csv)")
    api: bool = Field(False, description="Read the channel's public totals with your YOUTUBE_API_KEY (read-only)")


def _num(v: str | None) -> float | None:
    try:
        return float(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def parse_studio_csv(text: str) -> list[dict]:
    """YouTube Studio table export → rows {video_id, title, published, views, watch_hours, subscribers, impressions, ctr}."""
    rows = []
    for r in csv.DictReader(io.StringIO(text.lstrip("\ufeff"))):
        vid = (r.get("Content") or "").strip()
        if not vid or vid.lower() == "total":
            continue
        rows.append({"video_id": vid, "title": r.get("Video title", ""), "published": r.get("Video publish time", ""),
                     "views": _num(r.get("Views")), "watch_hours": _num(r.get("Watch time (hours)")),
                     "subscribers": _num(r.get("Subscribers")), "impressions": _num(r.get("Impressions")),
                     "ctr": _num(r.get("Impressions click-through rate (%)"))})
    return rows


@verb("channel.stats", StatsIn, effect="write", needs_project=False,
      examples=[r"recomp channel stats --csv C:\Users\me\Downloads\Table data.csv", "recomp channel stats --api"])
def channel_stats(ctx: Ctx, inp: StatsIn):
    """Your own channel's numbers (read-only): import a YouTube Studio CSV or read the public totals with your API key.
    Posts you linked get their video's row. Nobody else's numbers are read (D-22)."""
    c = default_channel(ctx)
    st = dict(c["stats"] or {})
    if inp.csv:
        path = Path(inp.csv)
        if not path.exists():
            raise RecompError("E_NOT_FOUND", f"no file {path}")
        rows = parse_studio_csv(path.read_text(encoding="utf-8-sig"))
        if not rows:
            raise RecompError("E_INVALID", "no video rows in that CSV",
                              hint="Export the table from YouTube Studio › Analytics › Advanced mode (Content = video id).")
        st["videos"] = rows
        st["totals"] = {"videos": len(rows), "views": sum(r["views"] or 0 for r in rows),
                        "watch_hours": round(sum(r["watch_hours"] or 0 for r in rows), 1)}
    elif inp.api:
        key = config.env_value("YOUTUBE_API_KEY")
        if not key:
            raise RecompError("E_INVALID", "no YouTube Data API key",
                              hint=f"Put YOUTUBE_API_KEY=… in {config.home() / '.env'}, or import a Studio CSV instead.")
        if not c["handle"]:
            raise RecompError("E_INVALID", "the channel has no handle", hint="`recomp channel set --handle @…`")
        from ..research import net
        from urllib.parse import urlencode
        data = net.get_json("https://www.googleapis.com/youtube/v3/channels?" +
                            urlencode({"part": "statistics", "forHandle": c["handle"], "key": key}))
        items = data.get("items") or []
        if not items:
            raise RecompError("E_NOT_FOUND", f"YouTube knows no channel {c['handle']}")
        s = items[0]["statistics"]
        st["totals"] = {"subscribers": _num(s.get("subscriberCount")), "views": _num(s.get("viewCount")),
                        "videos": _num(s.get("videoCount"))}
    else:
        raise RecompError("E_INVALID", "give --csv <file> or --api")
    now = time.time()
    st.update({"imported_at": now, "imported_at_iso": time.strftime("%Y-%m-%d %H:%M", time.localtime(now))})
    with ctx.studio_op("channel stats") as tx:
        c = tx.update("channel", c["id"], {"stats": st})
    by_id = {r["video_id"]: r for r in st.get("videos") or []}
    posts = []
    for p in ctx.studio.rows("post", "WHERE status='posted'"):
        m = re.search(r"(?:v=|youtu\.be/|shorts/)([\w-]{11})", p["url"] or "")
        if m and m.group(1) in by_id:
            posts.append({"post": p["ref"], "title": p["title"], **by_id[m.group(1)]})
    return {**brief_channel(c), "posts": posts}


# ---- the queue --------------------------------------------------------------------------------------

def get_post(db, ref: str) -> dict:
    row = db.by_ref("post", ref.upper())
    if row is None:
        raise RecompError("E_NOT_FOUND", f"no post {ref!r}", hint="`recomp post queue` lists them.")
    return row


def brief_post(p: dict) -> dict:
    return {"ref": p["ref"], "status": p["status"], "at": p["at"], "title": p["title"], "project": p["project"],
            "export": p["export"], "journey": p["journey"], "profile": p["profile"], "lang": p["lang"], "file": p["file"],
            "url": p["url"] or None, "credits": [f"{s['ref']} {s['creator'] or s['title']} ({s['status']})" for s in p["sources"] or []]}


def _when(at: str | None) -> str | None:
    if not at:
        return None
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            return time.strftime("%Y-%m-%d %H:%M", time.strptime(at.strip(), fmt))
        except ValueError:
            continue
    raise RecompError("E_INVALID", f"--at {at!r}: use 2026-10-20 18:00")


class PlanIn(BaseModel):
    ref: str = Field(..., description="A finished export (X3), or a journey (J1: its newest finished export)",
                     json_schema_extra={"pos": 0})
    profile: str | None = Field(None, description="With a journey: which format (shorts, landscape…)")
    lang: str | None = Field(None, description="With a journey: which language")
    at: str | None = Field(None, description="When you plan to post it, e.g. 2026-10-20 18:00")
    title: str | None = Field(None, description="Post title (default: the journey's)")


@verb("post.plan", PlanIn, effect="write",
      examples=["recomp post plan X4 --at \"2026-10-20 18:00\"", "recomp post plan J2 --profile shorts --lang en"])
def post_plan(ctx: Ctx, inp: PlanIn):
    """Put an export in the posting queue for your channel. Refuses private sources (E_RIGHTS): only campaign and
    permitted sources can be posted (D-23); the description credits every creator."""
    db = ctx.db
    if re.fullmatch(r"[Jj]\d+", inp.ref):
        j = refs.resolve(db, inp.ref.upper(), "journey")[1]
        sql, params = "WHERE journey_id=? AND status LIKE 'done%'", [j["id"]]
        if inp.profile:
            sql += " AND profile=?"
            params.append(inp.profile)
        if inp.lang:
            sql += " AND lang=?"
            params.append(inp.lang)
        rows = db.rows("export", sql + " ORDER BY updated_at DESC LIMIT 1", params)
        if not rows:
            raise RecompError("E_NOT_FOUND", f"{j['ref']} has no finished export" + (f" as {inp.profile}" if inp.profile else ""),
                              hint=f"`recomp export run {j['ref']} --profiles {inp.profile or 'shorts'}` first.")
        exp = rows[0]
    else:
        exp = refs.resolve(db, inp.ref.upper(), "export")[1]
    if not str(exp["status"]).startswith("done") or not (exp["outputs"] or {}).get("video"):
        raise RecompError("E_INVALID", f"{exp['ref']} is not finished ({exp['status']})", hint=f"`recomp export status {exp['ref']}`")
    srcs = RS.sources_of_export(db, exp)
    priv = RS.private(srcs)
    if priv:
        raise RecompError(
            "E_RIGHTS", f"{exp['ref']} uses {len(priv)} private source(s): only campaign and permitted sources can be posted",
            hint="Set a source's status when there is evidence: `recomp source rights S… --status permitted --evidence <link>` "
                 "(or campaign, with the program's terms). Private sources stay fine for everything else.",
            data={"private": priv})
    j = db.get("journey", exp["journey_id"]) if exp.get("journey_id") else None
    folder = Path(exp["folder"])
    desc = (folder / "description.txt").read_text(encoding="utf-8") if (folder / "description.txt").exists() else ""
    summary = RS.summary(srcs)
    missing = [s for s in summary if (s["creator"] or s["owner"] or "").lower() not in desc.lower()]
    if missing:  # every post credits its creators (D-09)
        desc = desc.rstrip() + "\n\nCredits: " + "; ".join(f"{s['title']} by {s['creator'] or s['owner']}" for s in missing) + "\n"
    ch = default_channel(ctx)
    with ctx.studio_op(f"plan post {exp['ref']}") as tx:
        p = tx.insert("post", {"channel_id": ch["id"], "project": ctx.project.name, "export": exp["ref"],
                               "journey": j["ref"] if j else None, "profile": exp["profile"], "lang": exp["lang"],
                               "title": inp.title or (j["title"] if j else exp["ref"]), "description": desc,
                               "file": exp["outputs"]["video"], "at": _when(inp.at), "status": "planned",
                               "sources": summary, "meta": {"folder": exp["folder"]}})
    warnings = [f"posting to a placeholder channel: `recomp channel set --name … --handle @…`"] if ch["placeholder"] else []
    return Result(data=brief_post(p), refs=[p["ref"]], warnings=warnings,
                  next=[f"recomp post open {p['ref']}   # the file and the text, ready to upload yourself"])


class QueueIn(BaseModel):
    status: str = Field("open", description="open (planned and opened), planned, opened, posted, cancelled or all")
    project: str | None = None


@verb("post.queue", QueueIn, needs_project=False, examples=["recomp post queue", "recomp post queue --status posted"])
def post_queue(ctx: Ctx, inp: QueueIn):
    """The posting queue: what you plan to upload, when, with which credits; and what you posted."""
    where, params = [], []
    if inp.status == "open":
        where.append("status IN ('planned','opened')")
    elif inp.status != "all":
        if inp.status not in STATUSES:
            raise RecompError("E_INVALID", f"status: open, all, {', '.join(STATUSES)}")
        where.append("status=?")
        params.append(inp.status)
    if inp.project:
        where.append("project=?")
        params.append(inp.project)
    sql = ("WHERE " + " AND ".join(where)) if where else ""
    rows = ctx.studio.rows("post", f"{sql} ORDER BY COALESCE(at, '9999'), created_at", params)
    return [brief_post(p) for p in rows]


class OpenIn(BaseModel):
    ref: str = Field(..., json_schema_extra={"pos": 0})
    reveal: bool = Field(False, description="Also show the file in the file manager")


@verb("post.open", OpenIn, effect="write", needs_project=False, examples=["recomp post open Q2 --reveal"])
def post_open(ctx: Ctx, inp: OpenIn):
    """Everything to upload a post yourself: the file, the title, the description with credits, the upload page."""
    db = ctx.studio
    p = get_post(db, inp.ref)
    if p["status"] == "cancelled":
        raise RecompError("E_INVALID", f"{p['ref']} was cancelled")
    if not Path(p["file"]).exists():
        raise RecompError("E_NOT_FOUND", f"{p['file']} is gone", hint=f"Re-export {p['export']} in {p['project']}.")
    ch = db.get("channel", p["channel_id"]) if p["channel_id"] else None
    if inp.reveal:
        from .workspace import open_in_file_manager
        open_in_file_manager(Path(p["file"]))
    if p["status"] == "planned":
        with ctx.studio_op(f"open {p['ref']}") as tx:
            p = tx.update("post", p["id"], {"status": "opened"})
    return {**brief_post(p), "description": p["description"],
            "upload_page": UPLOAD_PAGES.get((ch or {}).get("platform") or "youtube"),
            "channel": (ch or {}).get("name"),
            "next": f"After uploading: recomp post link {p['ref']} <the post's URL>"}


class LinkIn(BaseModel):
    ref: str = Field(..., json_schema_extra={"pos": 0})
    url: str = Field(..., description="Where you posted it", json_schema_extra={"pos": 1})


@verb("post.link", LinkIn, effect="write", needs_project=False,
      examples=["recomp post link Q2 https://youtube.com/shorts/abc123def45"])
def post_link(ctx: Ctx, inp: LinkIn):
    """Record where you posted it: on the post, on the journey and on its hub recipe (when published)."""
    db = ctx.studio
    p = get_post(db, inp.ref)
    if not re.match(r"https?://", inp.url):
        raise RecompError("E_INVALID", "give the post's full URL")
    warnings = []
    if p["journey"]:
        try:
            proj = P.Project(P.locate(p["project"]))
        except RecompError as exc:
            proj = None
            warnings.append(f"project {p['project']}: {exc.message}")
        if proj is not None:
            try:
                env = registry.run("hub.link-post", {"journey": p["journey"], "url": inp.url, "lang": p["lang"]},
                                   actor=ctx.actor, project=proj)
                if not env["ok"]:
                    warnings.append(f"journey link: {env['error']['message']}")
            finally:
                proj.close()
    with ctx.studio_op(f"posted {p['ref']}") as tx:
        p = tx.update("post", p["id"], {"status": "posted", "url": inp.url,
                                        "meta": {**(p["meta"] or {}), "posted_at": time.time()}})
    return Result(data=brief_post(p), warnings=warnings)


class CancelIn(BaseModel):
    ref: str = Field(..., json_schema_extra={"pos": 0})


@verb("post.cancel", CancelIn, effect="write", needs_project=False)
def post_cancel(ctx: Ctx, inp: CancelIn):
    """Take a post out of the queue (undo with `recomp op undo --studio`)."""
    p = get_post(ctx.studio, inp.ref)
    with ctx.studio_op(f"cancel {p['ref']}") as tx:
        p = tx.update("post", p["id"], {"status": "cancelled"})
    return brief_post(p)
