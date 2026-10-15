"""The hub from the studio side: sign in, publish recipes, pull and fork others', vote, comment, follow, link posts.

Publishing beyond this machine is the user's decision: to a non-local hub, `hub publish` requires
``--confirm``, which an agent passes only after the user said so in chat.
"""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, Field

from ..compose import recipe as R
from ..core import config, refs
from ..envelope import RecompError, Result
from ..registry import Ctx, NoInput, verb


def base(url: str | None = None) -> str:
    return (url or config.get("hub.url") or "http://127.0.0.1:8790").rstrip("/")


def is_local(url: str) -> bool:
    return (urlparse(url).hostname or "") in ("127.0.0.1", "localhost", "::1")


def _tokens() -> dict:
    p = config.home() / "hub_token.json"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_tokens(d: dict) -> None:
    (config.home() / "hub_token.json").write_text(json.dumps(d, indent=1), encoding="utf-8")


def call(method: str, path: str, body: dict | None = None, auth: bool = True, url: str | None = None) -> dict:
    b = base(url)
    headers = {}
    if auth:
        tok = _tokens().get(b, {}).get("token")
        if tok:
            headers["Authorization"] = f"Bearer {tok}"
    try:
        r = httpx.request(method, b + path, json=body, headers=headers, timeout=30)
    except httpx.HTTPError as exc:
        raise RecompError("E_NETWORK", f"hub unreachable at {b}: {exc}",
                          hint="Start it: `python -m hub` (local) or check config hub.url") from exc
    if r.status_code >= 400:
        try:
            detail = r.json().get("detail")
        except ValueError:
            detail = r.text[:200]
        code = {401: "E_PRECEDENCE", 403: "E_PRECEDENCE", 404: "E_NOT_FOUND", 409: "E_EXISTS"}.get(r.status_code, "E_EXTERNAL")
        hint = "Sign in: `recomp hub login --handle <you>`" if r.status_code == 401 else None
        raise RecompError(code, f"hub: {detail}", hint=hint)
    return r.json()


def _rid(value: str) -> str:
    """Accept a recipe id or a hub URL (…/r/<id>)."""
    return value.rstrip("/").split("/r/")[-1].split("/")[-1]


class LoginIn(BaseModel):
    handle: str
    password: str | None = Field(None, description="Default: env RECOMP_HUB_PASSWORD. Agents: only for local test accounts.")
    register_: bool = Field(False, alias="register", description="Create the account first (local hubs)")
    display: str | None = None
    url: str | None = Field(None, description="Hub URL (default config hub.url)")
    model_config = {"populate_by_name": True}


@verb("hub.login", LoginIn, effect="network", needs_project=False)
def hub_login(ctx: Ctx, inp: LoginIn):
    """Sign in to a hub (or register on a local one) and keep the session token in the studio home."""
    pw = inp.password or os.environ.get("RECOMP_HUB_PASSWORD")
    if not pw:
        raise RecompError("E_INVALID", "no password given", hint="Set RECOMP_HUB_PASSWORD or pass --password")
    b = base(inp.url)
    if inp.register_:
        if not is_local(b):
            raise RecompError("E_PRECEDENCE", "accounts on a public hub are created by the user, not the agent")
        res = call("POST", "/api/hub/auth/register", {"handle": inp.handle, "password": pw, "display": inp.display}, False, b)
    else:
        res = call("POST", "/api/hub/auth/login", {"handle": inp.handle, "password": pw}, False, b)
    t = _tokens()
    t[b] = {"token": res["token"], "handle": res["handle"]}
    _save_tokens(t)
    return {"hub": b, "handle": res["handle"]}


@verb("hub.whoami", NoInput, needs_project=False)
def hub_whoami(ctx: Ctx, inp: NoInput):
    """Who the studio is signed in as on the configured hub."""
    b = base()
    me = call("GET", "/api/hub/me")
    return {"hub": b, **me}


@verb("hub.logout", NoInput, effect="network", needs_project=False)
def hub_logout(ctx: Ctx, inp: NoInput):
    """Sign out of the configured hub."""
    b = base()
    try:
        call("POST", "/api/hub/auth/logout")
    finally:
        t = _tokens()
        t.pop(b, None)
        _save_tokens(t)
    return {"hub": b, "signed_out": True}


class PublishIn(BaseModel):
    journey: str = Field(..., json_schema_extra={"pos": 0})
    visibility: str = Field("public", description="public | unlisted | private")
    confirm: bool = Field(False, description="Required for a non-local hub; only after the user said so in chat")


@verb("hub.publish", PublishIn, effect="publish", examples=["recomp hub publish J1 --visibility public"])
def hub_publish(ctx: Ctx, inp: PublishIn):
    """Share a journey's recipe on the hub (sources, timecodes, text, credits; never the media). Re-publishing adds a version."""
    db = ctx.db
    j = refs.resolve(db, inp.journey, "journey")[1]
    b = base()
    if not is_local(b) and not inp.confirm:
        raise RecompError("E_PRECEDENCE", f"{b} is not local: publishing there is the user's decision",
                          hint="Ask the user; if they agree in chat, repeat with --confirm.")
    rec = R.build(db, j, ctx.project.meta)
    links = dict(j.get("links") or {})
    hub_id = (links.get("hub_ids") or {}).get(b)
    langs = sorted({r[0] for r in db.all("SELECT DISTINCT lang FROM translation WHERE kind='title' AND target_id=?", (j["id"],))})
    thumb = None
    for p in sorted(ctx.project.dir("exports").glob(f"{j['ref']}-*/*/thumb.jpg"), key=lambda x: x.stat().st_mtime, reverse=True):
        if p.stat().st_size < 600_000:
            thumb = base64.b64encode(p.read_bytes()).decode()
            break
    rec.pop("links", None)
    res = call("POST", "/api/hub/recipes", {"recipe": rec, "visibility": inp.visibility, "id": hub_id, "languages": langs,
                                           "thumbnail": thumb, "forked_from": links.get("forked_from_id")})
    url = f"{b}/r/{res['id']}"
    links.setdefault("hub_ids", {})[b] = res["id"]
    links["hub"] = url
    with ctx.op(f"published {j['ref']}") as tx:
        tx.update("journey", j["id"], {"links": links, "status": "published"})
    R.write_mirror(ctx.project, db, db.get("journey", j["id"]))
    return Result(data={"journey": j["ref"], "url": url, "version": res["version"], "visibility": inp.visibility},
                  next=["Re-export to put the recipe link and QR code on the endcard: recomp export run "
                        f"{j['ref']} --profiles shorts"])


class IdIn(BaseModel):
    recipe: str = Field(..., description="Recipe id or hub URL", json_schema_extra={"pos": 0})


@verb("hub.show", IdIn, effect="network", needs_project=False)
def hub_show(ctx: Ctx, inp: IdIn):
    """A hub recipe: card, slots, credits, votes, comments count, linked posts."""
    r = call("GET", f"/api/hub/recipes/{_rid(inp.recipe)}")
    rec = r.pop("recipe")
    r["slots_detail"] = [{"source": s["source"], "in": s["in"], "out": s["out"], "title": s.get("title")} for s in rec["slots"]]
    return r


@verb("hub.pull", IdIn, effect="network", examples=["recomp hub pull http://127.0.0.1:8790/r/01K…"])
def hub_pull(ctx: Ctx, inp: IdIn):
    """Bring a hub recipe into this project as a journey (link sources are added; files are matched or marked missing)."""
    from ..compose.importer import import_recipe
    rid = _rid(inp.recipe)
    r = call("GET", f"/api/hub/recipes/{rid}")
    rec = r["recipe"]
    rec.setdefault("links", {})["hub"] = f"{base()}/r/{rid}"
    res = import_recipe(ctx, rec, forked_from=f"{base()}/r/{rid}")
    j = ctx.db.by_ref("journey", res.data["journey"])
    links = dict(j["links"] or {})
    links["forked_from_id"] = rid
    with ctx.op("pulled") as tx:
        tx.update("journey", j["id"], {"links": links})
    return res


@verb("hub.fork", IdIn, effect="network")
def hub_fork(ctx: Ctx, inp: IdIn):
    """Fork a hub recipe into your hub account (private) and pull it into this project to edit."""
    res = call("POST", f"/api/hub/recipes/{_rid(inp.recipe)}/fork")
    pulled = hub_pull(ctx, IdIn(recipe=res["id"]))
    return Result(data={"fork": f"{base()}/r/{res['id']}", **pulled.data}, refs=pulled.refs, warnings=pulled.warnings)


class VoteIn(BaseModel):
    recipe: str = Field(..., json_schema_extra={"pos": 0})
    value: str = Field("up", description="up | down | clear", json_schema_extra={"pos": 1})


@verb("hub.vote", VoteIn, effect="publish", needs_project=False)
def hub_vote(ctx: Ctx, inp: VoteIn):
    """Vote a recipe up or down (or clear your vote)."""
    v = {"up": 1, "down": -1, "clear": 0}.get(inp.value)
    if v is None:
        raise RecompError("E_INVALID", "value: up, down or clear")
    card = call("POST", f"/api/hub/recipes/{_rid(inp.recipe)}/vote", {"value": v})
    return {"recipe": card["id"], "score": card["score"], "my_vote": card["my_vote"]}


class CommentIn(BaseModel):
    recipe: str = Field(..., json_schema_extra={"pos": 0})
    text: str = Field(..., json_schema_extra={"pos": 1})
    reply_to: str | None = None


@verb("hub.comment", CommentIn, effect="publish", needs_project=False)
def hub_comment(ctx: Ctx, inp: CommentIn):
    """Comment on a recipe (or reply to a comment)."""
    res = call("POST", f"/api/hub/recipes/{_rid(inp.recipe)}/comments", {"body": inp.text, "parent": inp.reply_to})
    return {"comment": res["id"]}


@verb("hub.comments", IdIn, effect="network", needs_project=False)
def hub_comments(ctx: Ctx, inp: IdIn):
    """The comments on a recipe."""
    return call("GET", f"/api/hub/recipes/{_rid(inp.recipe)}/comments")


class FollowIn(BaseModel):
    handle: str = Field(..., json_schema_extra={"pos": 0})
    undo: bool = False


@verb("hub.follow", FollowIn, effect="publish", needs_project=False)
def hub_follow(ctx: Ctx, inp: FollowIn):
    """Follow (or unfollow) someone on the hub."""
    return call("DELETE" if inp.undo else "POST", f"/api/hub/users/{inp.handle}/follow")


class FeedIn(BaseModel):
    kind: str = Field("trending", description="trending | new | top | following | mine")
    tag: str | None = None
    source: str | None = Field(None, description="Source key, e.g. youtube:T_7Fm1VujEs")
    query: str | None = None
    limit: int = 20


@verb("hub.feed", FeedIn, effect="network", needs_project=False)
def hub_feed(ctx: Ctx, inp: FeedIn):
    """Recipes on the hub: trending, new, top, from people you follow, or yours; filter by tag, source or text."""
    params = "&".join(f"{k}={httpx.QueryParams({k: v})[k]}" for k, v in
                      {"kind": inp.kind, "tag": inp.tag, "source": inp.source, "q": inp.query, "limit": inp.limit}.items() if v)
    res = call("GET", f"/api/hub/feed?{params}")
    return [{"id": c["id"], "title": c["title"], "by": c["owner"], "score": c["score"], "comments": c["comments"],
             "slots": c["slots"], "tags": c["tags"], "url": f"{base()}/r/{c['id']}"} for c in res["items"]]


class LinkPostIn(BaseModel):
    journey: str = Field(..., json_schema_extra={"pos": 0})
    url: str = Field(..., description="Where you posted the video", json_schema_extra={"pos": 1})
    lang: str | None = None


@verb("hub.link-post", LinkPostIn, effect="publish", examples=["recomp hub link-post J1 https://youtube.com/shorts/…"])
def hub_link_post(ctx: Ctx, inp: LinkPostIn):
    """Record where you posted a video made from this journey, on the journey and on its hub recipe."""
    db = ctx.db
    j = refs.resolve(db, inp.journey, "journey")[1]
    links = dict(j.get("links") or {})
    posts = list(links.get("posts") or [])
    posts.append({"url": inp.url, "lang": inp.lang})
    links["posts"] = posts
    with ctx.op(f"post link {j['ref']}") as tx:
        tx.update("journey", j["id"], {"links": links})
    hub_id = (links.get("hub_ids") or {}).get(base())
    synced = False
    if hub_id:
        call("POST", f"/api/hub/recipes/{hub_id}/links", {"url": inp.url, "lang": inp.lang})
        synced = True
    return {"journey": j["ref"], "posts": posts, "on_hub": synced}
