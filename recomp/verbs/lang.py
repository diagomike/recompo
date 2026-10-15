"""Languages: translate a journey's lines (yourself, or a Google draft), check coverage, list voices, dub."""

from __future__ import annotations

from pydantic import BaseModel, Field

from ..compose import recipe as R
from ..core import refs
from ..core.timecode import clock
from ..envelope import RecompError, Result
from ..registry import Ctx, verb
from ..transcript.store import primary
from .journey import journey_of

CPS = {"am": 11.0, "om": 13.0, "ti": 11.0}  # comfortable characters per second when spoken


def units(db, j: dict) -> list[dict]:
    """Everything in a journey that a translation needs: spoken lines, overlays, the title."""
    out = [{"key": "title", "kind": "title", "target": j["id"], "text": j["title"], "at": None, "dur": None}]
    seen = set()
    for it in R.timeline(db, j):
        tr = primary(db, it["source"]["id"])
        if not tr:
            continue
        for s in db.all('SELECT id, start, "end", text FROM segment WHERE transcript_id=? AND "end" > ? AND start < ? ORDER BY idx',
                        (tr["id"], it["in"] + 0.05, it["out"] - 0.05)):
            if s["id"] in seen:
                continue
            seen.add(s["id"])
            out.append({"key": f"seg:{s['id']}", "kind": "segment", "target": str(s["id"]), "text": s["text"],
                        "at": clock(s["start"]), "dur": round(min(s["end"], it["out"]) - max(s["start"], it["in"]), 2),
                        "slot": it["ref"]})
    for o in db.rows("overlay", "WHERE journey_id=? ORDER BY at", (j["id"],)):
        out.append({"key": f"ovl:{o['ref']}", "kind": "overlay", "target": o["id"], "text": o["text"], "at": None, "dur": None,
                    "overlay_kind": o["kind"]})
    return out


def existing(db, lang: str, us: list[dict]) -> dict[str, dict]:
    got = {}
    for u in us:
        r = db.one("SELECT id, text, method, created_by FROM translation WHERE lang=? AND kind=? AND target_id=?",
                   (lang, u["kind"], u["target"]))
        if r:
            got[u["key"]] = dict(r)
    return got


class TranslateIn(BaseModel):
    journey: str = Field(..., json_schema_extra={"pos": 0})
    to: str = Field(..., description="Target language code (am, sw, fr, om, …)")
    template: bool = Field(False, description="Return the lines to translate (with timing budgets) instead of writing")
    translations: dict[str, str] = Field(default_factory=dict, description="{key: text} from the template (use --input)")
    engine: str | None = Field(None, description="google: draft every untranslated line with Google's web endpoint")
    overwrite: bool = Field(False, description="With --engine: also replace lines translated before (never the user's)")


@verb("lang.translate", TranslateIn, effect="write",
      examples=["recomp lang translate J1 --to am --template", "recomp lang translate J1 --to am --input am.json",
                "recomp lang translate J1 --to sw --engine google"])
def lang_translate(ctx: Ctx, inp: TranslateIn):
    """Translate a journey's spoken lines, overlays and title. Get the template, write the translations yourself (best), or draft with --engine google."""
    db = ctx.db
    j = journey_of(db, inp.journey)
    us = units(db, j)
    have = existing(db, inp.to, us)
    cps = CPS.get(inp.to, 15.0)
    if inp.template:
        lines = []
        for u in us:
            item = {"key": u["key"], "text": u["text"]}
            if u["dur"]:
                item["at"] = u["at"]
                item["max_chars"] = int(u["dur"] * cps)
            if u["key"] in have:
                item["current"] = have[u["key"]]["text"]
            lines.append(item)
        return Result(data={"journey": j["ref"], "to": inp.to, "lines": lines,
                            "missing": sum(1 for u in us if u["key"] not in have)},
                      next=[f"recomp lang translate {j['ref']} --to {inp.to} --input {inp.to}.json   # {{\"translations\": {{key: text}}}}"])
    todo: dict[str, tuple[str, str]] = {}
    method = "agent" if ctx.actor == "agent" else ctx.actor
    if inp.engine == "google":
        from ..lang.google import Translator
        src_lang = j["language"] or "en"
        pending = [u for u in us if inp.overwrite or u["key"] not in have]
        if pending:
            tr = Translator(src_lang, inp.to)
            res = tr.translate([{"id": k, "text": u["text"]} for k, u in enumerate(pending)])
            for k, u in enumerate(pending):
                if res.get(k):
                    todo[u["key"]] = (res[k], "google")
    elif inp.engine:
        raise RecompError("E_INVALID", "engine must be google (or give --input with your own translations)")
    for key, text in inp.translations.items():
        todo[key] = (text, method)
    by_key = {u["key"]: u for u in us}
    unknown = [k for k in todo if k not in by_key]
    if unknown:
        raise RecompError("E_INVALID", f"unknown keys: {unknown[:5]}", hint="Use the keys from --template")
    written, kept = 0, []
    with ctx.op(f"translate {j['ref']} → {inp.to}") as tx:
        for key, (text, how) in todo.items():
            u = by_key[key]
            row = db.one("SELECT id, created_by, prov FROM translation WHERE lang=? AND kind=? AND target_id=?",
                         (inp.to, u["kind"], u["target"]))
            if row:
                if how == "google" and row["created_by"] == "user":
                    kept.append(key)
                    continue
                try:
                    tx.update("translation", row["id"], {"text": text.strip(), "method": how})
                except RecompError:
                    kept.append(key)
                    continue
            else:
                tx.insert("translation", {"lang": inp.to, "kind": u["kind"], "target_id": u["target"], "text": text.strip(),
                                          "method": how})
            written += 1
    have = existing(db, inp.to, us)
    long_lines = [k for k, u in by_key.items() if u["dur"] and k in have and len(have[k]["text"]) > u["dur"] * cps * 1.15]
    return Result(data={"journey": j["ref"], "to": inp.to, "written": written, "kept_users": kept,
                        "coverage": f"{len(have)}/{len(us)}", "likely_too_long": long_lines[:20]},
                  warnings=[f"{len(long_lines)} line(s) may be too long to speak in their time: shorten them"] if long_lines else [],
                  next=[f"recomp export run {j['ref']} --profiles shorts --langs {inp.to}"])


class StatusIn(BaseModel):
    journey: str = Field(..., json_schema_extra={"pos": 0})


@verb("lang.status", StatusIn)
def lang_status(ctx: Ctx, inp: StatusIn):
    """Translation coverage per language for a journey, and who wrote it (agent, google, user)."""
    db = ctx.db
    j = journey_of(db, inp.journey)
    us = units(db, j)
    langs = [r[0] for r in db.all("SELECT DISTINCT lang FROM translation ORDER BY lang")]
    out = {}
    for lang in langs:
        have = existing(db, lang, us)
        if not have:
            continue
        methods: dict[str, int] = {}
        for h in have.values():
            methods[h["method"]] = methods.get(h["method"], 0) + 1
        out[lang] = {"coverage": f"{len(have)}/{len(us)}", "complete": len(have) == len(us), "by": methods}
    return {"journey": j["ref"], "units": len(us), "languages": out}


class VoicesIn(BaseModel):
    lang: str = Field(..., json_schema_extra={"pos": 0})


@verb("lang.voices", VoicesIn, effect="network", examples=["recomp lang voices am"])
def lang_voices(ctx: Ctx, inp: VoicesIn):
    """Voices available for a language (edge neural voices; the configured default is marked)."""
    from ..core import config
    from ..lang import tts
    try:
        backend, default = tts.voice_for(inp.lang)
    except RecompError:
        backend, default = None, None
    vs = []
    try:
        vs = tts.edge_voices(inp.lang)
    except RecompError as exc:
        if backend != "mms":
            raise exc
    for v in vs:
        v["default"] = v["voice"] == default
    return {"lang": inp.lang, "default": {"backend": backend, "voice": default}, "edge": vs,
            "mms": (config.get("tts.mms") or {}).get(inp.lang)}


class SayIn(BaseModel):
    text: str = Field(..., json_schema_extra={"pos": 0})
    lang: str = "en"
    voice: str | None = None


@verb("lang.say", SayIn, effect="network", examples=['recomp lang say "ሰላም" --lang am'])
def lang_say(ctx: Ctx, inp: SayIn):
    """Voice a single line into the project's cache (to audition a voice)."""
    from ..lang import tts
    import hashlib
    out = ctx.project.dir("cache", "dub", "say") / (hashlib.sha1((inp.lang + (inp.voice or "") + inp.text).encode()).hexdigest()[:12] + ".wav")
    dur = tts.synth(inp.text, inp.lang, out, voice=inp.voice)
    return {"file": str(out), "seconds": round(dur, 2)}
