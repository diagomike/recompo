"""Music: search open-licensed audio, fetch it with its licence, keep a local library, lay beds under journeys."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from pydantic import BaseModel, Field

from ..core import refs
from ..core.timecode import parse
from ..envelope import RecompError, Result
from ..media import ff
from ..music import openverse
from ..registry import Ctx, NoInput, verb
from .journey import journey_of, mirror
from .ui import get_state, set_state


class SearchIn(BaseModel):
    query: str = Field(..., description='Mood, genre or instrument, e.g. "melancholic piano"', json_schema_extra={"pos": 0})
    licence: str = Field("safe", description="safe (CC0, CC BY, public domain) | commercial (adds BY-SA) | any")
    min_s: float | None = Field(None, description="Shortest track in seconds")
    max_s: float | None = Field(None, description="Longest track in seconds")
    limit: int = 12


@verb("music.search", SearchIn, effect="network",
      examples=['recomp music search "melancholic piano" --min-s 60', 'recomp music search "ambient strings" --licence any'])
def music_search(ctx: Ctx, inp: SearchIn):
    """Search open-licensed music (Openverse: Freesound, Jamendo, ccMixter…). Results are numbered for `music get`."""
    res = openverse.search(inp.query, inp.licence, page_size=min(50, inp.limit * 2), min_s=inp.min_s, max_s=inp.max_s)
    res = res[:inp.limit]
    set_state(ctx.db, "music_search", {"query": inp.query, "results": res})
    return Result(data=[{"n": k, **{x: r[x] for x in ("title", "artist", "licence", "note", "duration", "source", "tags", "page_url", "id")}}
                        for k, r in enumerate(res, start=1)],
                  next=["recomp music get <n>   # downloads it with its licence"])


class GetIn(BaseModel):
    pick: str = Field(..., description="Number from the last search, or an Openverse audio id", json_schema_extra={"pos": 0})


@verb("music.get", GetIn, effect="network", examples=["recomp music get 3"])
def music_get(ctx: Ctx, inp: GetIn):
    """Download a track (from the last search, or by Openverse id) into the project's music folder, with its licence."""
    db = ctx.db
    item = None
    if re.fullmatch(r"\d+", inp.pick):
        last = get_state(db, "music_search") or {}
        res = last.get("results") or []
        n = int(inp.pick)
        if not 1 <= n <= len(res):
            raise RecompError("E_NOT_FOUND", f"no result #{n} in the last search", hint="`recomp music search …` first")
        item = res[n - 1]
    elif re.fullmatch(r"M\d+", inp.pick):
        tr = refs.resolve(db, inp.pick, "music_track")[1]
        if not tr.get("provider_id"):
            raise RecompError("E_INVALID", f"{tr['ref']} has no provider id to fetch")
        item = openverse.detail(tr["provider_id"])
    else:
        item = openverse.detail(inp.pick)
    existing = db.rows("music_track", "WHERE provider=? AND provider_id=?", ("openverse", item["id"]))
    if existing and existing[0].get("file") and Path(existing[0]["file"]).exists():
        return Result(data=_brief(existing[0]), refs=[existing[0]["ref"]], warnings=["already in the library"])
    folder = ctx.project.dir("music")
    ext = (item.get("filetype") or "").lower().strip(".")
    if ext not in ("mp3", "ogg", "wav", "flac", "m4a", "opus", "aac"):
        ext = "mp3" if ext.startswith("mp3") or not ext else re.sub(r"[^a-z0-9]", "", ext)[:4] or "mp3"
    safe = re.sub(r"[^A-Za-z0-9]+", "-", item["title"]).strip("-")[:40] or "track"
    dest = folder / f"{safe}-{item['id'][:8]}.{ext}"
    openverse.download(item["url"], dest)
    try:
        info = ff.probe(dest)
        dur = info.duration
    except RecompError:
        dest.unlink(missing_ok=True)
        raise RecompError("E_EXTERNAL", "the downloaded file is not playable audio")
    fields = {"provider": "openverse", "provider_id": item["id"], "url": item["url"], "page_url": item.get("page_url"),
              "file": str(dest), "title": item["title"], "artist": item["artist"], "licence": item["licence"],
              "licence_url": item.get("licence_url") or "", "attribution": item.get("attribution") or "",
              "duration": dur, "meta": {"source": item.get("source"), "tags": item.get("tags")}}
    with ctx.op(f"music {item['title']!r}") as tx:
        if existing:
            tr = tx.update("music_track", existing[0]["id"], fields)
        else:
            tr = tx.insert("music_track", fields)
    (dest.with_suffix(".licence.txt")).write_text(
        f"{item['title']} by {item['artist']}\n{item['licence']} {item.get('licence_url', '')}\n{item.get('page_url', '')}\n"
        f"{item.get('attribution', '')}\n", encoding="utf-8")
    return Result(data=_brief(tr), refs=[tr["ref"]], next=[f"recomp music bed add <journey> {tr['ref']}"])


def _brief(t: dict) -> dict:
    return {"ref": t["ref"], "title": t["title"], "artist": t["artist"], "licence": t["licence"], "duration": t["duration"],
            "file": t["file"], "provider": t["provider"], "page_url": t["page_url"], "has_file": bool(t["file"] and Path(t["file"]).exists())}


class LibAddIn(BaseModel):
    file: str = Field(..., json_schema_extra={"pos": 0})
    title: str = ""
    artist: str = ""
    licence: str = Field(..., description="Licence you hold it under, e.g. 'CC BY 4.0' or 'own work'")
    licence_url: str = ""
    url: str = ""


@verb("music.library-add", LibAddIn, effect="write",
      examples=['recomp music library-add "D:\\Music\\theme.mp3" --title Theme --artist Me --licence "own work"'])
def music_library_add(ctx: Ctx, inp: LibAddIn):
    """Add a local audio file you have the rights to, with its licence (copied into the project)."""
    src = Path(inp.file)
    if not src.exists():
        raise RecompError("E_NOT_FOUND", f"no such file: {src}")
    info = ff.probe(src)
    if not info.audio:
        raise RecompError("E_INVALID", "no audio stream in that file")
    dest = ctx.project.dir("music") / src.name
    if dest.resolve() != src.resolve():
        shutil.copy(src, dest)
    with ctx.op(f"music {src.name}") as tx:
        tr = tx.insert("music_track", {"provider": "local", "file": str(dest), "title": inp.title or src.stem,
                                       "artist": inp.artist, "licence": inp.licence, "licence_url": inp.licence_url,
                                       "page_url": inp.url, "duration": info.duration})
    return Result(data=_brief(tr), refs=[tr["ref"]])


@verb("music.list", NoInput)
def music_list(ctx: Ctx, inp: NoInput):
    """Tracks in the project's library and the journeys they play under."""
    db = ctx.db
    out = []
    for t in db.rows("music_track", "ORDER BY created_at"):
        b = _brief(t)
        b["journeys"] = sorted({r[0] for r in db.all("SELECT j.ref FROM music_bed b JOIN journey j ON j.id=b.journey_id "
                                                     "WHERE b.track_id=?", (t["id"],))})
        out.append(b)
    return out


class BedIn(BaseModel):
    journey: str = Field(..., json_schema_extra={"pos": 0})
    track: str = Field(..., description="Music track ref, e.g. M1", json_schema_extra={"pos": 1})
    at: str = Field("0", description="Start on the journey timeline")
    dur: float | None = Field(None, description="Seconds (default: to the end of the journey)")
    track_in: str = Field("0", description="Start this far into the track")
    gain: float = Field(-16, description="Level in dB (under speech it is ducked further)")
    duck: float = Field(-10, description="How much to duck under speech, in dB")
    fade_in: float = 1.5
    fade_out: float = 2.5


@verb("music.bed-add", BedIn, effect="write", examples=["recomp music bed-add J1 M1 --gain -18"])
def music_bed_add(ctx: Ctx, inp: BedIn):
    """Lay a music bed under a journey (ducked automatically under speech)."""
    db = ctx.db
    j = journey_of(db, inp.journey)
    t = refs.resolve(db, inp.track, "music_track")[1]
    if not t["licence"]:
        raise RecompError("E_INVALID", f"{t['ref']} has no licence recorded")
    if "ND" in re.split(r"[\s\-]+", t["licence"].upper()):
        raise RecompError("E_INVALID", f"{t['ref']} is {t['licence']}: no-derivatives music cannot be synchronised to video",
                          hint="Pick a CC0 or CC BY track (`recomp music search … --licence safe`).")
    with ctx.op(f"bed {t['ref']} under {j['ref']}") as tx:
        b = tx.insert("music_bed", {"journey_id": j["id"], "track_id": t["id"], "at": parse(inp.at) or 0.0,
                                    "track_in": parse(inp.track_in) or 0.0, "dur": inp.dur, "gain_db": inp.gain,
                                    "duck_db": inp.duck, "fade_in": inp.fade_in, "fade_out": inp.fade_out})
    mirror(ctx, j["id"])
    warnings = [] if t.get("file") and Path(t["file"]).exists() else [f"{t['ref']} has no local file yet: `recomp music get {t['ref']}`"]
    return Result(data={"ref": b["ref"], "journey": j["ref"], "track": t["ref"], "title": t["title"], "gain_db": inp.gain},
                  refs=[b["ref"]], warnings=warnings)


class BedEditIn(BaseModel):
    ref: str = Field(..., description="Bed ref, e.g. B1", json_schema_extra={"pos": 0})
    at: str | None = None
    dur: float | None = None
    track_in: str | None = None
    gain: float | None = None
    duck: float | None = None
    fade_in: float | None = None
    fade_out: float | None = None


@verb("music.bed-edit", BedEditIn, effect="write")
def music_bed_edit(ctx: Ctx, inp: BedEditIn):
    """Change a bed's timing, level or ducking."""
    db = ctx.db
    b = refs.resolve(db, inp.ref, "music_bed")[1]
    f = {}
    if inp.at is not None:
        f["at"] = parse(inp.at)
    if inp.track_in is not None:
        f["track_in"] = parse(inp.track_in)
    for k, col in (("dur", "dur"), ("gain", "gain_db"), ("duck", "duck_db"), ("fade_in", "fade_in"), ("fade_out", "fade_out")):
        v = getattr(inp, k)
        if v is not None:
            f[col] = v
    with ctx.op(f"edit {b['ref']}") as tx:
        b = tx.update("music_bed", b["id"], f)
    mirror(ctx, b["journey_id"])
    return {k: b[k] for k in ("ref", "at", "dur", "track_in", "gain_db", "duck_db", "fade_in", "fade_out")}


class BedRmIn(BaseModel):
    ref: str = Field(..., json_schema_extra={"pos": 0})


@verb("music.bed-remove", BedRmIn, effect="write")
def music_bed_remove(ctx: Ctx, inp: BedRmIn):
    """Remove a music bed."""
    db = ctx.db
    b = refs.resolve(db, inp.ref, "music_bed")[1]
    with ctx.op(f"remove {b['ref']}") as tx:
        tx.delete("music_bed", b["id"])
    mirror(ctx, b["journey_id"])
    return {"removed": b["ref"]}
