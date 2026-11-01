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
    engine: str | None = Field(None, description="Draft every untranslated line by MT: nllb, m2m100, bergamot (offline) or google (online)")
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
    elif inp.engine in ("nllb", "m2m100", "bergamot"):  # offline drafts (worker env)
        from ..lang import llmdub
        src_lang = j["language"] or "en"
        pending = [u for u in us if inp.overwrite or u["key"] not in have]
        if pending:
            mt = llmdub.MT(ctx.project)
            for u, text in zip(pending, mt.translate([u["text"] for u in pending], src_lang, inp.to, inp.engine)):
                if text:
                    todo[u["key"]] = (text, "google")  # a machine draft, like google's
            mt.save()
    elif inp.engine:
        raise RecompError("E_INVALID", "engine must be google (online) or nllb, m2m100, bergamot (offline)")
    for key, text in inp.translations.items():
        todo[key] = (text, method)
    by_key = {u["key"]: u for u in us}
    unknown = [k for k in todo if k not in by_key]
    if unknown:
        raise RecompError("E_INVALID", f"unknown keys: {unknown[:5]}", hint="Use the keys from --template")
    written, kept = 0, []

    def write(tx, items) -> None:
        nonlocal written
        for key, (text, how) in items:
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

    # Machine drafts are the machine's, whoever asked for them: the agent and the user can both refine them later.
    drafts = [(k, v) for k, v in todo.items() if v[1] == "google"]
    own = [(k, v) for k, v in todo.items() if v[1] != "google"]
    if drafts:
        with ctx.db.op("lang.translate", "machine", ctx.args) as tx:
            tx.summary = f"google draft {j['ref']} → {inp.to}"
            write(tx, drafts)
    if own or not drafts:
        with ctx.op(f"translate {j['ref']} → {inp.to}") as tx:
            write(tx, own)
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
    lang: str = Field(..., description="Language code (two letters, or any ISO 639-3 code MMS-TTS has)", json_schema_extra={"pos": 0})
    online: bool | None = Field(None, description="Also list online edge voices (default: when the dub may go online)")


@verb("lang.voices", VoicesIn, effect="network",
      examples=["recomp lang voices om", "recomp lang voices am --online",
                "recomp config set tts.mms.am facebook/mms-tts-amh   # the language's offline voice"])
def lang_voices(ctx: Ctx, inp: VoicesIn):
    """Voices for a language: offline ones first (MMS-TTS, cloned original voices, Windows SAPI) with whether they are installed, then online edge voices when allowed. The default is marked."""
    from ..lang import llmdub, tts
    online = inp.online if inp.online is not None else bool(llmdub.resolve(ctx.project)[0].get("online"))
    try:
        backend, default = tts.voice_for(inp.lang, online=online)
    except RecompError:
        backend, default = None, None
    offline = tts.offline_voices(inp.lang)
    for v in offline:
        v["default"] = v["voice"] in (default, f"{backend}:{default}")
    edge, warnings = [], []
    if online:
        try:
            edge = tts.edge_voices(inp.lang)
        except RecompError as exc:
            warnings.append(f"online voices unavailable: {exc.message}")
        for v in edge:
            v["default"] = v["voice"] == default
    missing = [v["voice"][4:] for v in offline if v["backend"] == "mms" and not v["installed"]]
    nxt = []
    if missing:
        nxt.append(f"recomp dub models --to {inp.lang} --download   # fetch {missing[0]} once, then it runs offline")
    nxt.append(f'recomp lang say "…" --lang {inp.lang} --voice {offline[0]["voice"] if offline else "<voice>"}   # audition')
    return Result(data={"lang": inp.lang, "online": online, "default": {"backend": backend, "voice": default},
                        "offline": offline, "online_voices": edge,
                        "choose": {"for the dub": "recomp dub settings --at project|S1|J1 --voice <voice>",
                                   "for a language": f"recomp config set tts.mms.{inp.lang} <model>  (offline) · "
                                                     f"recomp config set tts.voices.{inp.lang} <edge voice>  (online)",
                                   "for one export": "recomp export run J1 --langs " + inp.lang + " --voice <voice>"}},
                  warnings=warnings, next=nxt)


class SayIn(BaseModel):
    text: str = Field(..., json_schema_extra={"pos": 0})
    lang: str = "en"
    voice: str | None = Field(None, description="mms:<model> (offline), sapi:<name>, an edge voice (online), or the default")


@verb("lang.say", SayIn, effect="network",
      examples=['recomp lang say "ሰላም" --lang am', 'recomp lang say "Akkam jirta" --lang om --voice mms:facebook/mms-tts-orm'])
def lang_say(ctx: Ctx, inp: SayIn):
    """Voice a single line into the project's cache (to audition a voice)."""
    from ..lang import tts
    import hashlib
    out = ctx.project.dir("cache", "dub", "say") / (hashlib.sha1((inp.lang + (inp.voice or "") + inp.text).encode()).hexdigest()[:12] + ".wav")
    from ..lang import llmdub
    if inp.voice == "clone":
        raise RecompError("E_INVALID", "cloned voices need the original line's audio, so they are export-only",
                          hint=f"`recomp export run <journey> --langs {inp.lang} --voice clone`")
    dur = tts.synth(inp.text, inp.lang, out, voice=inp.voice, online=bool(llmdub.resolve(ctx.project)[0].get("online")))
    return {"file": str(out), "seconds": round(dur, 2)}


# ---- editing translations (P15) ----

def _layout(db, profile: str | None, lang: str, sample: str) -> dict | None:
    if not profile:
        return None
    from ..render import ass, profiles
    p = db.rows("profile", "WHERE name=?", (profile,))
    if not p:
        raise RecompError("E_NOT_FOUND", f"profile {profile!r} not found", hint="`recomp profile list`")
    return ass.caption_layout(profiles.resolve(p[0]["settings"]), lang, sample)


class LinesIn(BaseModel):
    journey: str = Field(..., json_schema_extra={"pos": 0})
    lang: str = Field(..., description="Language code", json_schema_extra={"pos": 1})
    over: bool = Field(False, description="Only lines too long to speak in their time (to shorten)")
    missing: bool = Field(False, description="Only lines with no translation yet")
    profile: str | None = Field(None, description="Also count caption screens per line under this profile's caption box")
    find: str | None = Field(None, description="Only lines whose source or translation contains this text")


@verb("lang.lines", LinesIn,
      examples=["recomp lang lines J1 am --over", "recomp lang lines J1 am --profile shorts", "recomp lang lines J1 fr --missing"])
def lang_lines(ctx: Ctx, inp: LinesIn):
    """Every line of a journey in one language: source, translation, length against its speaking budget, who wrote it."""
    db = ctx.db
    j = journey_of(db, inp.journey)
    us = units(db, j)
    have = existing(db, inp.lang, us)
    cps = CPS.get(inp.lang, 15.0)
    sample = " ".join(h["text"] for h in list(have.values())[:20])
    layout = _layout(db, inp.profile, inp.lang, sample)
    rows, over_n = [], 0
    for u in us:
        h = have.get(u["key"])
        text = h["text"] if h else None
        row = {"key": u["key"], "kind": u["kind"], "at": u["at"], "source": u["text"], "text": text,
               "by": (h["method"] if h["method"] == "google" else h["created_by"]) if h else None}
        if u["dur"]:
            budget = int(u["dur"] * cps)
            row.update(dur=u["dur"], budget=budget)
            if text:
                row.update(chars=len(text), fit=round(len(text) / max(1, budget), 2))
                if len(text) > budget * 1.15:
                    row["over"] = True
                    over_n += 1
        if layout and text and u["kind"] == "segment":
            from ..render.ass import split_timed
            row["screens"] = len(split_timed(text, 0, 1, layout["max_chars"] * layout["max_lines"]))
        if inp.over and not row.get("over"):
            continue
        if inp.missing and text:
            continue
        if inp.find and inp.find.lower() not in (u["text"] + " " + (text or "")).lower():
            continue
        rows.append(row)
    data = {"journey": j["ref"], "lang": inp.lang, "coverage": f"{len(have)}/{len(us)}", "over_budget": over_n,
            "chars_per_second": cps, "lines": rows}
    if layout:
        data["caption_box"] = layout
    nxt = [f"recomp lang edit {j['ref']} {inp.lang} --key <key> --text <shorter line>"] if rows else []
    return Result(data=data, next=nxt)


class LangEditIn(BaseModel):
    journey: str = Field(..., json_schema_extra={"pos": 0})
    lang: str = Field(..., json_schema_extra={"pos": 1})
    key: str | None = Field(None, description="One line's key (from `lang lines`)")
    text: str | None = Field(None, description="Its new text")
    lines: dict[str, str] = Field(default_factory=dict, description="Many lines: {key: text} (use --input)")


@verb("lang.edit", LangEditIn, effect="write",
      examples=["recomp lang edit J1 am --key seg:5121 --text <new line>",
                "recomp lang edit J1 am --input fixes.json   # {lines: {key: text}}"])
def lang_edit(ctx: Ctx, inp: LangEditIn):
    """Set one or many translated lines (a shorter line, a better word). Lines the user wrote are kept unless you are the user."""
    lines = dict(inp.lines)
    if inp.key:
        if inp.text is None:
            raise RecompError("E_INVALID", "--key needs --text")
        lines[inp.key] = inp.text
    if not lines:
        raise RecompError("E_INVALID", "give --key and --text, or --input with {lines: {key: text}}")
    return lang_translate(ctx, TranslateIn(journey=inp.journey, to=inp.lang, translations=lines))


class LangReplaceIn(BaseModel):
    lang: str = Field(..., description="Language code", json_schema_extra={"pos": 0})
    find: str = Field(..., json_schema_extra={"pos": 1})
    replace: str = Field(..., json_schema_extra={"pos": 2})
    journey: str | None = Field(None, description="Only this journey's lines (default: every translation in the language)")
    regex: bool = False
    case: bool = False
    whole: bool = Field(False, description="Whole words only")
    dry_run: bool = False


@verb("lang.replace", LangReplaceIn, effect="write",
      examples=["recomp lang replace am ንቃተ-ህሊና 'ንቃተ ህሊና' --dry-run", "recomp lang replace fr 'Anil Set' 'Anil Seth' --journey J1"])
def lang_replace(ctx: Ctx, inp: LangReplaceIn):
    """Find and replace across a language's translations: terminology, name spellings, punctuation."""
    from ..transcript import edit as E
    db = ctx.db
    pat = E.compile_pattern(inp.find, inp.regex, inp.case, inp.whole)
    repl = inp.replace if inp.regex else inp.replace.replace("\\", "\\\\")
    rows = db.rows("translation", "WHERE lang=? ORDER BY kind, target_id", (inp.lang,))
    if inp.journey:
        j = journey_of(db, inp.journey)
        keys = {(u["kind"], u["target"]) for u in units(db, j)}
        rows = [r for r in rows if (r["kind"], r["target_id"]) in keys]
    plan = []
    for r in rows:
        new = " ".join(pat.sub(repl, r["text"]).split())
        if new != r["text"]:
            plan.append((r, new))
    skipped = []
    if not inp.dry_run and plan:
        with ctx.op(f"replace in {inp.lang} translations") as tx:
            for r, new in plan:
                try:
                    tx.update("translation", r["id"], {"text": new})
                except RecompError:
                    skipped.append(f"{r['kind']}:{r['target_id']}")
    changes = [{"key": f"{r['kind']}:{r['target_id']}", "before": r["text"], "after": new} for r, new in plan[:40]]
    return Result(data={"dry_run": inp.dry_run, "replaced": len(plan) - len(skipped), "changes": changes,
                        "kept_users": skipped},
                  next=["run again without --dry-run to apply"] if inp.dry_run and plan else [])


class ClearIn(BaseModel):
    journey: str = Field(..., json_schema_extra={"pos": 0})
    lang: str = Field(..., json_schema_extra={"pos": 1})
    keys: str | None = Field(None, description="Comma list of keys (default: every line of the journey in this language)")
    method: str | None = Field(None, description="Only lines written this way: google, agent, user")


@verb("lang.clear", ClearIn, effect="write",
      examples=["recomp lang clear J1 om --method google", "recomp lang clear J1 am --keys seg:5121,seg:5122"])
def lang_clear(ctx: Ctx, inp: ClearIn):
    """Remove translations of a journey (all, some keys, or only one method's drafts) so they can be redone."""
    db = ctx.db
    j = journey_of(db, inp.journey)
    want = {k.strip() for k in inp.keys.split(",")} if inp.keys else None
    gone, kept = 0, []
    with ctx.op(f"clear {inp.lang} of {j['ref']}") as tx:
        for u in units(db, j):
            if want is not None and u["key"] not in want:
                continue
            r = db.one("SELECT id, method, created_by FROM translation WHERE lang=? AND kind=? AND target_id=?",
                       (inp.lang, u["kind"], u["target"]))
            if r is None or (inp.method and inp.method not in (r["method"], r["created_by"])):
                continue
            try:
                tx.delete("translation", r["id"])
                gone += 1
            except RecompError:
                kept.append(u["key"])
    return {"journey": j["ref"], "lang": inp.lang, "removed": gone, "kept_users": kept}
