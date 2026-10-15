"""The hub service: recipes as a social network.

    python -m hub [--port 8790] [--data <folder>]

Auth is local (scrypt-hashed passwords, bearer tokens). Recipes carry only sources, timecodes, text and
credits; the hub never stores media. Visibility: public (listed), unlisted (link only), private (owner).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import threading
import time
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, Response

from recomp.core.ids import ulid

from . import db as hubdb

STATIC = Path(__file__).resolve().parents[1] / "recomp" / "static" / "app"
HANDLE = re.compile(r"^[a-z0-9_]{2,24}$")

app = FastAPI(title="Recomposer hub", docs_url="/api/hub/docs")
app.add_middleware(CORSMiddleware, allow_origin_regex=r"http://(127\.0\.0\.1|localhost)(:\d+)?",
                   allow_methods=["*"], allow_headers=["*"])

_state: dict = {"conn": None, "data": None}
_lock = threading.RLock()


def data_dir() -> Path:
    if _state["data"] is None:
        _state["data"] = Path(os.environ.get("RECOMP_HUB_DATA") or (Path.home() / ".recomp" / "hub"))
    return _state["data"]


def conn():
    if _state["conn"] is None:
        _state["conn"] = hubdb.connect(data_dir() / "hub.db")
    return _state["conn"]


def q(sql: str, params=()):
    with _lock:
        return conn().execute(sql, params).fetchall()


def q1(sql: str, params=()):
    with _lock:
        return conn().execute(sql, params).fetchone()


def run(sql: str, params=()):
    with _lock:
        return conn().execute(sql, params)


# ---- auth -----------------------------------------------------------------------------------

def _hash(password: str, salt: str) -> str:
    return hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=2 ** 14, r=8, p=1).hex()


def current_user(authorization: str | None, required: bool = True):
    token = (authorization or "").removeprefix("Bearer ").strip()
    row = q1("SELECT u.* FROM session s JOIN user u ON u.id=s.user_id WHERE s.token=?", (token,)) if token else None
    if row is None and required:
        raise HTTPException(401, "sign in first")
    return row


def _session(user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    run("INSERT INTO session(token, user_id, created) VALUES(?,?,?)", (token, user_id, time.time()))
    return token


@app.post("/api/hub/auth/register")
async def register(request: Request):
    body = await request.json()
    handle = (body.get("handle") or "").strip().lower()
    password = body.get("password") or ""
    if not HANDLE.match(handle):
        raise HTTPException(400, "handle: 2–24 lowercase letters, digits or _")
    if len(password) < 8:
        raise HTTPException(400, "password: at least 8 characters")
    if q1("SELECT 1 FROM user WHERE handle=?", (handle,)):
        raise HTTPException(409, "that handle is taken")
    salt = secrets.token_hex(16)
    uid = ulid()
    run("INSERT INTO user(id, handle, display, bio, pw_salt, pw_hash, created) VALUES(?,?,?,?,?,?,?)",
        (uid, handle, body.get("display") or handle, body.get("bio") or "", salt, _hash(password, salt), time.time()))
    return {"token": _session(uid), "handle": handle}


@app.post("/api/hub/auth/login")
async def login(request: Request):
    body = await request.json()
    row = q1("SELECT * FROM user WHERE handle=?", ((body.get("handle") or "").lower(),))
    if row is None or not hmac.compare_digest(row["pw_hash"], _hash(body.get("password") or "", row["pw_salt"])):
        raise HTTPException(401, "wrong handle or password")
    return {"token": _session(row["id"]), "handle": row["handle"]}


@app.post("/api/hub/auth/logout")
def logout(authorization: str | None = Header(None)):
    token = (authorization or "").removeprefix("Bearer ").strip()
    run("DELETE FROM session WHERE token=?", (token,))
    return {"ok": True}


@app.get("/api/hub/me")
def me(authorization: str | None = Header(None)):
    u = current_user(authorization)
    return {"handle": u["handle"], "display": u["display"], "bio": u["bio"]}


# ---- recipes --------------------------------------------------------------------------------

def _visible(r, user) -> bool:
    return r["visibility"] in ("public", "unlisted") or (user is not None and user["id"] == r["owner_id"])


def source_key(e: dict) -> str:
    if e.get("kind") == "link" and e.get("id"):
        return f"{e.get('platform') or 'web'}:{e['id']}"
    title = re.sub(r"[^a-z0-9]+", "-", (e.get("title") or "").lower()).strip("-")
    return f"work:{title}:{e.get('year') or ''}"


def _index_sources(rid: str, rec: dict) -> None:
    run("DELETE FROM recipe_source WHERE recipe_id=?", (rid,))
    run("DELETE FROM moment WHERE recipe_id=?", (rid,))
    keys = {}
    for ref, e in (rec.get("sources") or {}).items():
        k = source_key(e)
        keys[ref] = k
        run("INSERT OR REPLACE INTO recipe_source(recipe_id, key, title, creator, platform, url, duration) VALUES(?,?,?,?,?,?,?)",
            (rid, k, e.get("title") or "", e.get("creator") or "", e.get("platform"), e.get("url"), e.get("duration")))
    for s in rec.get("slots") or []:
        if s.get("source") in keys:
            run("INSERT INTO moment(recipe_id, key, t_in, t_out) VALUES(?,?,?,?)", (rid, keys[s["source"]], s["in"], s["out"]))


def _validate(rec: dict) -> None:
    from recomp.compose.recipe import validate
    errs = validate(rec)
    if errs:
        raise HTTPException(400, "invalid recipe: " + "; ".join(errs[:5]))
    blob = json.dumps(rec)
    if re.search(r"[A-Za-z]:\\\\|file:///", blob):
        raise HTTPException(400, "recipe contains local file paths")


def _save_thumb(rid: str, b64: str | None) -> str | None:
    if not b64:
        return None
    raw = base64.b64decode(b64)
    if len(raw) > 600_000:
        raise HTTPException(413, "thumbnail too large")
    p = data_dir() / "thumbs" / f"{rid}.jpg"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(raw)
    return f"/api/hub/thumbs/{rid}.jpg"


@app.post("/api/hub/recipes")
async def publish(request: Request, authorization: str | None = Header(None)):
    user = current_user(authorization)
    body = await request.json()
    rec = body.get("recipe") or {}
    _validate(rec)
    vis = body.get("visibility", "public")
    if vis not in ("public", "unlisted", "private"):
        raise HTTPException(400, "visibility: public, unlisted or private")
    rid = body.get("id")
    now = time.time()
    tags = sorted({t for s in rec.get("slots", []) for t in s.get("tags", []) if t not in ("draft", "imported")})[:12]
    langs = sorted({rec.get("language") or "en"} | set(body.get("languages") or []))
    if rid:
        r = q1("SELECT * FROM recipe WHERE id=?", (rid,))
        if r is None or r["owner_id"] != user["id"]:
            raise HTTPException(404 if r is None else 403, "not your recipe")
        n = r["version"] + 1
        run("UPDATE recipe SET title=?, intent=?, description=?, visibility=?, tags=?, languages=?, version=?, hash=?, "
            "duration=?, slots=?, updated=? WHERE id=?",
            (rec["title"], rec.get("intent", ""), rec.get("description", ""), vis, json.dumps(tags), json.dumps(langs), n,
             rec.get("hash"), rec.get("duration"), len(rec["slots"]), now, rid))
    else:
        rid = ulid()
        n = 1
        run("INSERT INTO recipe(id, owner_id, title, intent, description, visibility, tags, languages, version, hash, "
            "forked_from, duration, slots, created, updated) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (rid, user["id"], rec["title"], rec.get("intent", ""), rec.get("description", ""), vis, json.dumps(tags),
             json.dumps(langs), 1, rec.get("hash"), body.get("forked_from"), rec.get("duration"), len(rec["slots"]), now, now))
    thumb = _save_thumb(rid, body.get("thumbnail"))
    if thumb:
        run("UPDATE recipe SET thumbnail=? WHERE id=?", (thumb, rid))
    run("INSERT INTO recipe_version(recipe_id, n, hash, body, created) VALUES(?,?,?,?,?)",
        (rid, n, rec.get("hash"), json.dumps(rec, ensure_ascii=False), now))
    _index_sources(rid, rec)
    return {"id": rid, "version": n, "url": f"/r/{rid}"}


def _card(r, user=None) -> dict:
    owner = q1("SELECT handle, display FROM user WHERE id=?", (r["owner_id"],))
    votes = q1("SELECT COALESCE(SUM(value),0) AS score, COUNT(*) AS n FROM vote WHERE recipe_id=?", (r["id"],))
    comments = q1("SELECT COUNT(*) FROM comment WHERE recipe_id=? AND deleted=0", (r["id"],))[0]
    mine = q1("SELECT value FROM vote WHERE recipe_id=? AND user_id=?", (r["id"], user["id"])) if user else None
    srcs = [dict(s) for s in q("SELECT key, title, creator, platform FROM recipe_source WHERE recipe_id=?", (r["id"],))]
    return {"id": r["id"], "title": r["title"], "intent": r["intent"], "owner": owner["handle"], "owner_display": owner["display"],
            "visibility": r["visibility"], "tags": json.loads(r["tags"]), "languages": json.loads(r["languages"]),
            "version": r["version"], "duration": r["duration"], "slots": r["slots"], "thumbnail": r["thumbnail"],
            "forked_from": r["forked_from"], "score": votes["score"], "votes": votes["n"], "my_vote": mine["value"] if mine else 0,
            "comments": comments, "sources": srcs, "created": r["created"], "updated": r["updated"]}


@app.get("/api/hub/recipes/{rid}")
def get_recipe(rid: str, authorization: str | None = Header(None), version: int | None = None):
    user = current_user(authorization, required=False)
    r = q1("SELECT * FROM recipe WHERE id=?", (rid,))
    if r is None or not _visible(r, user):
        raise HTTPException(404, "no such recipe")
    v = q1("SELECT body FROM recipe_version WHERE recipe_id=? AND n=?", (rid, version or r["version"]))
    out = _card(r, user)
    out["recipe"] = json.loads(v["body"])
    out["links"] = [dict(x) for x in q("SELECT url, platform, lang, created FROM post_link WHERE recipe_id=? ORDER BY created", (rid,))]
    out["forks"] = [x["id"] for x in q("SELECT id FROM recipe WHERE forked_from=? AND visibility='public'", (rid,))]
    return out


@app.delete("/api/hub/recipes/{rid}")
def delete_recipe(rid: str, authorization: str | None = Header(None)):
    user = current_user(authorization)
    r = q1("SELECT owner_id FROM recipe WHERE id=?", (rid,))
    if r is None or r["owner_id"] != user["id"]:
        raise HTTPException(403, "not your recipe")
    run("DELETE FROM recipe WHERE id=?", (rid,))
    return {"deleted": rid}


@app.post("/api/hub/recipes/{rid}/vote")
async def vote(rid: str, request: Request, authorization: str | None = Header(None)):
    user = current_user(authorization)
    value = int((await request.json()).get("value", 0))
    if value not in (-1, 0, 1):
        raise HTTPException(400, "value: 1, -1 or 0")
    r = q1("SELECT * FROM recipe WHERE id=?", (rid,))
    if r is None or not _visible(r, user):
        raise HTTPException(404)
    if value == 0:
        run("DELETE FROM vote WHERE user_id=? AND recipe_id=?", (user["id"], rid))
    else:
        run("INSERT INTO vote(user_id, recipe_id, value, created) VALUES(?,?,?,?) "
            "ON CONFLICT(user_id, recipe_id) DO UPDATE SET value=excluded.value", (user["id"], rid, value, time.time()))
    return _card(r, user)


@app.get("/api/hub/recipes/{rid}/comments")
def comments(rid: str, authorization: str | None = Header(None)):
    user = current_user(authorization, required=False)
    r = q1("SELECT * FROM recipe WHERE id=?", (rid,))
    if r is None or not _visible(r, user):
        raise HTTPException(404)
    rows = q("SELECT c.*, u.handle FROM comment c JOIN user u ON u.id=c.user_id WHERE recipe_id=? ORDER BY created", (rid,))
    out = []
    for c in rows:
        out.append({"id": c["id"], "parent": c["parent_id"], "by": c["handle"],
                    "body": "(deleted)" if c["deleted"] else c["body"], "created": c["created"], "edited": c["edited"]})
    return out


@app.post("/api/hub/recipes/{rid}/comments")
async def add_comment(rid: str, request: Request, authorization: str | None = Header(None)):
    user = current_user(authorization)
    body = await request.json()
    text = (body.get("body") or "").strip()
    if not text or len(text) > 4000:
        raise HTTPException(400, "comment: 1–4000 characters")
    parent = body.get("parent")
    if parent:
        p = q1("SELECT parent_id, recipe_id FROM comment WHERE id=?", (parent,))
        if p is None or p["recipe_id"] != rid:
            raise HTTPException(400, "no such parent comment")
        if p["parent_id"]:
            parent = p["parent_id"]  # one level of threading
    r = q1("SELECT * FROM recipe WHERE id=?", (rid,))
    if r is None or not _visible(r, user):
        raise HTTPException(404)
    cid = ulid()
    run("INSERT INTO comment(id, recipe_id, user_id, parent_id, body, created) VALUES(?,?,?,?,?,?)",
        (cid, rid, user["id"], parent, text, time.time()))
    return {"id": cid}


@app.delete("/api/hub/comments/{cid}")
def delete_comment(cid: str, authorization: str | None = Header(None)):
    user = current_user(authorization)
    c = q1("SELECT c.user_id, r.owner_id FROM comment c JOIN recipe r ON r.id=c.recipe_id WHERE c.id=?", (cid,))
    if c is None or user["id"] not in (c["user_id"], c["owner_id"]):
        raise HTTPException(403)
    run("UPDATE comment SET deleted=1 WHERE id=?", (cid,))
    return {"deleted": cid}


@app.post("/api/hub/recipes/{rid}/fork")
def fork(rid: str, authorization: str | None = Header(None)):
    user = current_user(authorization)
    r = q1("SELECT * FROM recipe WHERE id=?", (rid,))
    if r is None or not _visible(r, user):
        raise HTTPException(404)
    v = q1("SELECT body FROM recipe_version WHERE recipe_id=? AND n=?", (rid, r["version"]))
    rec = json.loads(v["body"])
    nid = ulid()
    now = time.time()
    run("INSERT INTO recipe(id, owner_id, title, intent, description, visibility, tags, languages, version, hash, forked_from, "
        "duration, slots, thumbnail, created, updated) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (nid, user["id"], rec["title"], r["intent"], r["description"], "private", r["tags"], r["languages"], 1, r["hash"], rid,
         r["duration"], r["slots"], r["thumbnail"], now, now))
    run("INSERT INTO recipe_version(recipe_id, n, hash, body, created) VALUES(?,?,?,?,?)", (nid, 1, r["hash"], v["body"], now))
    _index_sources(nid, rec)
    return {"id": nid, "forked_from": rid}


@app.post("/api/hub/recipes/{rid}/links")
async def add_link(rid: str, request: Request, authorization: str | None = Header(None)):
    user = current_user(authorization)
    r = q1("SELECT owner_id FROM recipe WHERE id=?", (rid,))
    if r is None or r["owner_id"] != user["id"]:
        raise HTTPException(403, "only the owner links posts")
    body = await request.json()
    url = (body.get("url") or "").strip()
    if not re.match(r"^https?://", url):
        raise HTTPException(400, "url must start with http(s)://")
    host = re.sub(r"^https?://(www\.)?", "", url).split("/")[0]
    run("INSERT INTO post_link(id, recipe_id, url, platform, lang, user_id, created) VALUES(?,?,?,?,?,?,?)",
        (ulid(), rid, url, host, body.get("lang"), user["id"], time.time()))
    return {"ok": True, "platform": host}


@app.post("/api/hub/report")
async def report(request: Request, authorization: str | None = Header(None)):
    user = current_user(authorization)
    body = await request.json()
    run("INSERT INTO report(id, recipe_id, comment_id, user_id, reason, created) VALUES(?,?,?,?,?,?)",
        (ulid(), body.get("recipe"), body.get("comment"), user["id"], (body.get("reason") or "")[:500], time.time()))
    return {"ok": True}


# ---- people and feeds -----------------------------------------------------------------------

@app.post("/api/hub/users/{handle}/follow")
def follow(handle: str, authorization: str | None = Header(None)):
    user = current_user(authorization)
    t = q1("SELECT id FROM user WHERE handle=?", (handle,))
    if t is None:
        raise HTTPException(404)
    if t["id"] == user["id"]:
        raise HTTPException(400, "you can't follow yourself")
    run("INSERT OR IGNORE INTO follow(follower_id, followee_id, created) VALUES(?,?,?)", (user["id"], t["id"], time.time()))
    return {"following": handle}


@app.delete("/api/hub/users/{handle}/follow")
def unfollow(handle: str, authorization: str | None = Header(None)):
    user = current_user(authorization)
    t = q1("SELECT id FROM user WHERE handle=?", (handle,))
    if t:
        run("DELETE FROM follow WHERE follower_id=? AND followee_id=?", (user["id"], t["id"]))
    return {"unfollowed": handle}


@app.get("/api/hub/users/{handle}")
def profile(handle: str, authorization: str | None = Header(None)):
    viewer = current_user(authorization, required=False)
    u = q1("SELECT * FROM user WHERE handle=?", (handle,))
    if u is None:
        raise HTTPException(404)
    own = viewer is not None and viewer["id"] == u["id"]
    rows = q("SELECT * FROM recipe WHERE owner_id=? " + ("" if own else "AND visibility='public' ") + "ORDER BY updated DESC", (u["id"],))
    followers = q1("SELECT COUNT(*) FROM follow WHERE followee_id=?", (u["id"],))[0]
    following = q1("SELECT COUNT(*) FROM follow WHERE follower_id=?", (u["id"],))[0]
    is_following = bool(viewer and q1("SELECT 1 FROM follow WHERE follower_id=? AND followee_id=?", (viewer["id"], u["id"])))
    return {"handle": u["handle"], "display": u["display"], "bio": u["bio"], "followers": followers, "following": following,
            "is_following": is_following, "recipes": [_card(r, viewer) for r in rows]}


def _trending(card: dict) -> float:
    age_h = (time.time() - card["created"]) / 3600
    return (card["score"] + 0.5 * card["comments"] + 1) / (age_h + 2) ** 1.5


@app.get("/api/hub/feed")
def feed(kind: str = "new", tag: str | None = None, source: str | None = None, q_: str | None = Query(None, alias="q"), limit: int = 30,
         authorization: str | None = Header(None)):
    viewer = current_user(authorization, required=False)
    where, params = ["r.visibility='public'"], []
    if kind == "following":
        if viewer is None:
            raise HTTPException(401, "sign in to see who you follow")
        where.append("r.owner_id IN (SELECT followee_id FROM follow WHERE follower_id=?)")
        params.append(viewer["id"])
    elif kind == "mine":
        if viewer is None:
            raise HTTPException(401)
        where = ["r.owner_id=?"]
        params = [viewer["id"]]
    if tag:
        where.append("r.tags LIKE ?")
        params.append(f'%"{tag}"%')
    if source:
        where.append("r.id IN (SELECT recipe_id FROM recipe_source WHERE key=?)")
        params.append(source)
    if q_:
        where.append("(r.title LIKE ? OR r.intent LIKE ?)")
        params += [f"%{q_}%", f"%{q_}%"]
    rows = q(f"SELECT r.* FROM recipe r WHERE {' AND '.join(where)} ORDER BY r.updated DESC LIMIT 500", params)
    cards = [_card(r, viewer) for r in rows]
    if kind == "trending":
        cards.sort(key=_trending, reverse=True)
    elif kind == "top":
        cards.sort(key=lambda c: c["score"], reverse=True)
    return {"kind": kind, "items": cards[:limit]}


@app.get("/api/hub/sources/{key:path}")
def source_page(key: str, authorization: str | None = Header(None), bins: int = 60):
    viewer = current_user(authorization, required=False)
    s = q1("SELECT * FROM recipe_source WHERE key=? LIMIT 1", (key,))
    if s is None:
        raise HTTPException(404)
    rows = q("SELECT r.* FROM recipe r JOIN recipe_source rs ON rs.recipe_id=r.id WHERE rs.key=? AND r.visibility='public' "
             "ORDER BY r.updated DESC", (key,))
    dur = s["duration"] or max([m["t_out"] for m in q("SELECT t_out FROM moment WHERE key=?", (key,))] or [1])
    heat = [0] * bins
    for m in q("SELECT m.t_in, m.t_out FROM moment m JOIN recipe r ON r.id=m.recipe_id WHERE m.key=? AND r.visibility='public'",
               (key,)):
        a = int(m["t_in"] / dur * bins)
        b = int(m["t_out"] / dur * bins)
        for k in range(max(0, a), min(bins, b + 1)):
            heat[k] += 1
    return {"key": key, "title": s["title"], "creator": s["creator"], "platform": s["platform"], "url": s["url"],
            "duration": dur, "heat": heat, "recipes": [_card(r, viewer) for r in rows]}


@app.get("/api/hub/tags")
def tags():
    counts: dict[str, int] = {}
    for r in q("SELECT tags FROM recipe WHERE visibility='public'"):
        for t in json.loads(r["tags"]):
            counts[t] = counts.get(t, 0) + 1
    return sorted(({"tag": k, "recipes": v} for k, v in counts.items()), key=lambda x: -x["recipes"])[:60]


@app.get("/api/hub/thumbs/{name}")
def thumb(name: str):
    p = (data_dir() / "thumbs" / name).resolve()
    if p.parent != (data_dir() / "thumbs").resolve() or not p.exists():
        raise HTTPException(404)
    return FileResponse(p, media_type="image/jpeg")


@app.get("/api/hub/health")
def health():
    return {"ok": True, "hub": True}


@app.get("/{full_path:path}")
def spa(full_path: str):
    if full_path.startswith("api/"):
        raise HTTPException(404)
    target = (STATIC / full_path).resolve() if full_path else None
    if target and target.is_file() and STATIC.resolve() in target.parents:
        return FileResponse(target)
    index = STATIC / "index.html"
    if index.exists():
        html = index.read_text(encoding="utf-8").replace("<head>", "<head><script>window.__HUB__=location.origin</script>", 1)
        return HTMLResponse(html, headers={"Cache-Control": "no-cache"})
    return HTMLResponse("<h1>Recomposer hub</h1>")


def main(argv=None) -> int:
    import argparse

    import uvicorn
    ap = argparse.ArgumentParser(prog="python -m hub")
    ap.add_argument("--port", type=int, default=8790)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--data", default=None)
    a = ap.parse_args(argv)
    if a.data:
        _state["data"] = Path(a.data)
    print(f"Recomposer hub on http://{a.host}:{a.port} (data: {data_dir()})")
    uvicorn.run(app, host=a.host, port=a.port, log_level="warning")
    return 0
