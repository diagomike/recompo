"""Export profiles, previews, the export matrix (journeys × profiles × languages), single-cut exports, checks."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from ..compose import recipe as R
from ..core import refs
from ..envelope import RecompError, Result
from ..registry import Ctx, NoInput, verb
from ..render import profiles
from ..workers import jobs

PROFILE_FIELDS = ("width", "height", "fps", "reframe", "captions", "caption_style", "overlays", "lower_thirds", "music",
                  "endcard", "endcard_seconds", "title_card", "loudness", "crf", "preset", "dub_mode", "multitrack")


@verb("profile.list", NoInput)
def profile_list(ctx: Ctx, inp: NoInput):
    """Export profiles: format and treatment, separate from journey content."""
    out = []
    for p in ctx.db.rows("profile", "ORDER BY created_at"):
        s = p["settings"]
        out.append({"name": p["name"], "size": f"{s['width']}x{s['height']}", "reframe": s["reframe"],
                    "captions": f"{s['captions']}:{s['caption_style']}", "music": s["music"], "endcard": s["endcard"],
                    "description": s.get("description", ""), "by": p["created_by"]})
    return out


class NameIn(BaseModel):
    name: str = Field(..., json_schema_extra={"pos": 0})


@verb("profile.show", NameIn)
def profile_show(ctx: Ctx, inp: NameIn):
    """One profile's full settings."""
    p = ctx.db.rows("profile", "WHERE name=?", (inp.name,))
    if not p:
        raise RecompError("E_NOT_FOUND", f"profile {inp.name!r} not found")
    return {"name": p[0]["name"], **p[0]["settings"]}


class ProfileIn(BaseModel):
    name: str = Field(..., json_schema_extra={"pos": 0})
    from_: str | None = Field(None, alias="from", description="Start from this profile")
    width: int | None = None
    height: int | None = None
    fps: int | None = None
    reframe: str | None = Field(None, description="fit-blur | fit-pad | crop-center | crop-x")
    captions: str | None = Field(None, description="burn | sidecar | off")
    caption_style: str | None = Field(None, description="clean | karaoke")
    overlays: bool | None = None
    lower_thirds: bool | None = None
    music: bool | None = None
    endcard: bool | None = None
    endcard_seconds: float | None = None
    title_card: bool | None = None
    loudness: float | None = None
    crf: int | None = None
    preset: str | None = None
    dub_mode: str | None = Field(None, description="voiceover | replace")
    description: str | None = None
    model_config = {"populate_by_name": True}


def _settings(inp: ProfileIn, base: dict) -> dict:
    s = dict(base)
    for k in (*PROFILE_FIELDS, "description"):
        v = getattr(inp, k, None)
        if v is not None:
            s[k] = v
    if s["reframe"] not in ("fit-blur", "fit-pad", "crop-center", "crop-x"):
        raise RecompError("E_INVALID", "reframe must be fit-blur, fit-pad, crop-center or crop-x")
    if s["captions"] not in ("burn", "sidecar", "off") or s["caption_style"] not in ("clean", "karaoke"):
        raise RecompError("E_INVALID", "captions: burn|sidecar|off; caption_style: clean|karaoke")
    s["width"], s["height"] = int(s["width"]) // 2 * 2, int(s["height"]) // 2 * 2
    return profiles.resolve(s)


@verb("profile.new", ProfileIn, effect="write",
      examples=["recomp profile new reel --from shorts --caption-style clean --no-music"])
def profile_new(ctx: Ctx, inp: ProfileIn):
    """Create an export profile (optionally from another)."""
    db = ctx.db
    if db.rows("profile", "WHERE name=?", (inp.name,)):
        raise RecompError("E_EXISTS", f"profile {inp.name!r} exists", hint="`recomp profile edit`")
    base = profiles.BASE
    if inp.from_:
        b = db.rows("profile", "WHERE name=?", (inp.from_,))
        if not b:
            raise RecompError("E_NOT_FOUND", f"profile {inp.from_!r} not found")
        base = b[0]["settings"]
    with ctx.op(f"profile {inp.name}") as tx:
        tx.insert("profile", {"name": inp.name, "settings": _settings(inp, base)})
    return profile_show(ctx, NameIn(name=inp.name))


@verb("profile.edit", ProfileIn, effect="write")
def profile_edit(ctx: Ctx, inp: ProfileIn):
    """Change an export profile."""
    db = ctx.db
    p = db.rows("profile", "WHERE name=?", (inp.name,))
    if not p:
        raise RecompError("E_NOT_FOUND", f"profile {inp.name!r} not found")
    with ctx.op(f"edit profile {inp.name}") as tx:
        tx.update("profile", p[0]["id"], {"settings": _settings(inp, p[0]["settings"])})
    return profile_show(ctx, NameIn(name=inp.name))


def _export_row(ctx: Ctx, tx, journey: dict | None, cut: dict | None, profile: str, lang: str, preview: bool) -> dict:
    name = journey["ref"] if journey else cut["ref"]
    title = journey["title"] if journey else cut["title"]
    folder = ctx.project.dir("exports", f"{name}-{R.slug(title)}", f"{'preview-' if preview else ''}{profile}-{lang}")
    return tx.insert("export", {"journey_id": journey["id"] if journey else None, "cut_id": cut["id"] if cut else None,
                                "profile": profile, "lang": lang, "status": "queued", "folder": str(folder)})


def _profiles(db, names: list[str]) -> list[str]:
    for n in names:
        if not db.rows("profile", "WHERE name=?", (n,)):
            raise RecompError("E_NOT_FOUND", f"profile {n!r} not found", hint="`recomp profile list`")
    return names


class RunIn(BaseModel):
    journey: str = Field(..., json_schema_extra={"pos": 0})
    profiles: list[str] = Field(default_factory=lambda: ["landscape"])
    langs: list[str] = Field(default_factory=list, description="Languages (default: the journey's)")
    dub: bool = Field(True, description="Dub languages other than the journey's (needs translations); false = subtitles only")


@verb("export.run", RunIn, effect="heavy",
      examples=["recomp export run J1 --profiles shorts,landscape", "recomp export run J1 --profiles shorts --langs en,am,sw,fr"])
def export_run(ctx: Ctx, inp: RunIn):
    """Render a journey in every profile × language asked for (jobs). Outputs land in exports/<journey>/<profile>-<lang>/."""
    db = ctx.db
    j = refs.resolve(db, inp.journey, "journey")[1]
    names = _profiles(db, inp.profiles)
    langs = inp.langs or [j["language"]]
    queued = []
    with ctx.op(f"export {j['ref']}") as tx:
        rows = [(_export_row(ctx, tx, j, None, p, lang, False), lang) for p in names for lang in langs]
    for row, lang in rows:
        dub = inp.dub and lang != j["language"]
        job = jobs.enqueue(db, "export", target=row["ref"], params={"export": row["id"], "dub": dub}, dedupe=False)
        with ctx.db.op("export.queue", "machine") as tx:
            tx.update("export", row["id"], {"job_id": job["ref"]}, log=False)
        queued.append({"export": row["ref"], "profile": row["profile"], "lang": lang, "job": job["ref"], "folder": row["folder"]})
    mode = jobs.kick(ctx.project)
    return Result(data={"exports": queued, "runner": mode}, refs=[q["export"] for q in queued],
                  job=queued[0]["job"] if queued else None,
                  next=[f"recomp job wait {' '.join(q['job'] for q in queued)} --timeout 120", "recomp export status"])


class PreviewIn(BaseModel):
    target: str = Field(..., description="Journey or cut ref", json_schema_extra={"pos": 0})
    profile: str = Field("landscape", description="Which profile to approximate (rendered small and fast)")
    lang: str | None = None


@verb("preview", PreviewIn, effect="heavy", examples=["recomp preview J1", "recomp preview J1 --profile shorts", "recomp preview C4"])
def preview(ctx: Ctx, inp: PreviewIn):
    """A quick low-resolution render of a journey or cut in a profile's look (job); the viewer shows it when done."""
    db = ctx.db
    table, row = refs.resolve(db, inp.target, ("journey", "cut"))
    prof = db.rows("profile", "WHERE name=?", (inp.profile,))
    if not prof:
        raise RecompError("E_NOT_FOUND", f"profile {inp.profile!r} not found")
    s = prof[0]["settings"]
    scale = 480 / min(s["width"], s["height"])
    over = {"width": int(s["width"] * scale) // 2 * 2, "height": int(s["height"] * scale) // 2 * 2, "preset": "ultrafast",
            "crf": 30, "audio_bitrate": "96k", "endcard_seconds": min(2.0, s.get("endcard_seconds", 2))}
    lang = inp.lang or (row.get("language") if table == "journey" else None) or "en"
    with ctx.op(f"preview {inp.target}") as tx:
        exp = _export_row(ctx, tx, row if table == "journey" else None, row if table == "cut" else None, inp.profile, lang, True)
    job = jobs.enqueue(db, "export", target=exp["ref"], params={"export": exp["id"], "overrides": over, "preview": True},
                       dedupe=False)
    mode = jobs.kick(ctx.project)
    return Result(data={"export": exp["ref"], "job": job["ref"], "runner": mode, "folder": exp["folder"]},
                  job=job["ref"], refs=[exp["ref"]], next=[f"recomp job wait {job['ref']} --timeout 120", f"recomp ui show {exp['ref']}"])


class CutsIn(BaseModel):
    cuts: list[str] = Field(..., json_schema_extra={"pos": 0})
    profile: str = "clip"


@verb("export.cuts", CutsIn, effect="heavy", examples=["recomp export cuts C4 C9 --profile clip"])
def export_cuts(ctx: Ctx, inp: CutsIn):
    """Export individual cuts (one video each) with their own credits."""
    db = ctx.db
    _profiles(db, [inp.profile])
    rows = [refs.resolve(db, c, "cut")[1] for c in inp.cuts]
    out = []
    with ctx.op("export cuts") as tx:
        exps = [_export_row(ctx, tx, None, c, inp.profile, db.get("source", c["source_id"]).get("language") or "en", False)
                for c in rows]
    for e in exps:
        job = jobs.enqueue(db, "export", target=e["ref"], params={"export": e["id"]}, dedupe=False)
        out.append({"export": e["ref"], "job": job["ref"], "folder": e["folder"]})
    mode = jobs.kick(ctx.project)
    return Result(data={"exports": out, "runner": mode}, refs=[o["export"] for o in out], job=out[0]["job"] if out else None)


def _brief(db, e: dict) -> dict:
    j = db.get("journey", e["journey_id"]) if e["journey_id"] else None
    c = db.get("cut", e["cut_id"]) if e["cut_id"] else None
    chk = e["checks"] or {}
    return {"ref": e["ref"], "of": (j or c or {}).get("ref"), "title": (j or c or {}).get("title"), "profile": e["profile"],
            "lang": e["lang"], "status": e["status"], "job": e["job_id"], "folder": e["folder"],
            "video": (e["outputs"] or {}).get("video"), "seconds": (e["outputs"] or {}).get("seconds"),
            "problems": [x for x in chk.get("checks", []) if not x["ok"]], "preview": "preview-" in (e["folder"] or "")}


class StatusIn(BaseModel):
    of: str | None = Field(None, description="Only exports of this journey or cut", json_schema_extra={"pos": 0})
    limit: int = 40


@verb("export.status", StatusIn)
def export_status(ctx: Ctx, inp: StatusIn):
    """Exports with status, outputs and failed checks (newest first)."""
    db = ctx.db
    where, params = "", ()
    if inp.of:
        t, row = refs.resolve(db, inp.of, ("journey", "cut"))
        where, params = (f"WHERE {t}_id=?", (row["id"],))
    rows = db.rows("export", f"{where} ORDER BY created_at DESC LIMIT ?", (*params, inp.limit))
    out = []
    for e in rows:
        b = _brief(db, e)
        if e["job_id"] and e["status"] in ("queued", "rendering"):
            jr = db.by_ref("job", e["job_id"])
            if jr:
                b["progress"] = round(jr["progress"], 2)
                b["job_status"] = jr["status"]
                if jr["status"] == "failed":
                    b["status"] = "failed"
                    b["error"] = jr["error"]
        out.append(b)
    return out


class ShowIn(BaseModel):
    ref: str = Field(..., json_schema_extra={"pos": 0})


@verb("export.show", ShowIn)
def export_show(ctx: Ctx, inp: ShowIn):
    """One export in full: files, checks and the ready-to-paste description."""
    db = ctx.db
    e = refs.resolve(db, inp.ref, "export")[1]
    out = _brief(db, e)
    out["checks"] = (e["checks"] or {}).get("checks", [])
    out["loudness"] = (e["checks"] or {}).get("loudness")
    folder = Path(e["folder"])
    out["files"] = sorted(p.name for p in folder.glob("*")) if folder.exists() else []
    desc = folder / "description.txt"
    out["description"] = desc.read_text(encoding="utf-8") if desc.exists() else None
    return out


@verb("export.check", ShowIn, effect="write")
def export_check(ctx: Ctx, inp: ShowIn):
    """Re-run the automatic checks on an export."""
    from ..render import checks
    db = ctx.db
    e = refs.resolve(db, inp.ref, "export")[1]
    plan_file = Path(e["folder"]) / "plan.json"
    if not plan_file.exists():
        raise RecompError("E_NOT_FOUND", "this export has not been rendered yet")
    plan = json.loads(plan_file.read_text(encoding="utf-8"))
    chk = checks.run(Path(e["folder"]), plan)
    with ctx.op(f"check {e['ref']}") as tx:
        tx.update("export", e["id"], {"checks": chk, "status": "done" if chk["ok"] else "done-with-problems"}, log=False)
    return chk


class PruneIn(BaseModel):
    max_gb: float | None = Field(None, description="Keep the render cache under this size (default: config render.cache_max_gb)")


@verb("cache.prune", PruneIn, effect="write")
def cache_prune(ctx: Ctx, inp: PruneIn):
    """Delete the oldest render intermediates until the cache fits (exports are untouched)."""
    from ..render.engine import prune_cache
    return prune_cache(ctx.project, inp.max_gb)


@verb("cache.size", NoInput)
def cache_size(ctx: Ctx, inp: NoInput):
    """Disk used by caches (render intermediates, frames, thumbnails, peaks) and exports."""
    out = {}
    for name in ("cache/render", "cache/frames", "cache/thumbs", "cache/peaks", "sources", "exports", "music"):
        p = ctx.project.root / name
        out[name] = round(sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) / 1e9, 3) if p.exists() else 0.0
    return {"gb": out}
