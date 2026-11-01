"""The LLM dubber (P19): timed, meaning-conserving dub lines in any language pair, written by you (the agent).

Each stage hands you a template and takes your JSON back (``--input``). The machine does the language-free work:
MT views, the target voice as the ruler, the exact choice and back-translation checks.

    recomp dub settings J1 --to om         # effective settings and the route for each source (change: --at …)
    recomp dub understand J1 --to om --template   → write the meaning map  → --input maps.json
    recomp dub write J1 --to om --template        → write options per speech frame → --input options.json
    recomp dub fit J1 --to om              # MT, voice, choose; writes the lines as translations
    recomp dub verify J1 --to om --template       → mark back-translations → --input checks.json, then fit again
    recomp dub write J1 --to om --template        # round 2: only the frames still out of band
    recomp export run J1 --profiles shorts --langs om   # voices each frame at the speaker's own pauses
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from ..compose import recipe as R
from ..core import config, refs
from ..envelope import RecompError, Result
from ..lang import llmdub as L
from ..registry import Ctx, verb
from ..workers import jobs
from ..workers.tasks_lang import lines, put, work
from .journey import journey_of

SETTING_HELP = {
    "route": "auto | direct | source (src-en: the LLM writes in the source) | target (tgt-en: writes the target) | "
             "middle (mid-en: one middle language) | multi (two or more middle languages)",
    "middle": "Middle languages in order, e.g. en or en,es (multi: two or more)",
    "budget": "economy (one writing language, fewest tokens) | quality (two writing languages pooled)",
    "views_mt": "MT systems for the understanding views, paired with the middle languages: google, nllb, bergamot",
    "mt": "MT system into the target and for back-translation: google, nllb, bergamot",
    "verify": "auto (when the target is weak and MT crossed) | always | never",
    "conserve": "Meaning-conserving mode: cost added content, allow short silences",
    "rounds": "Rewrite rounds offered for frames still out of band",
    "band": "Good fit as voice time / speaker time, low,high (default 0.8,1.05)",
    "mt_prior": "Pooled options: cost of an MT-crossed option so a directly written line wins near-ties",
    "min_pause": "A pause this long (s) splits a line into speech frames",
    "strong": "Languages the LLM is strong in (overrides the built-in list)",
    "voice": "Target voice (default: the language's configured voice)",
}


def _src_lang(ctx: Ctx, s: dict) -> str:
    return s.get("language") or (ctx.project.meta.get("languages") or ["en"])[0]


# ---- settings ----------------------------------------------------------------------------------------------------

class SettingsIn(BaseModel):
    target: str | None = Field(None, description="Journey or source to show (J1, S2); default: the project",
                               json_schema_extra={"pos": 0})
    to: str | None = Field(None, description="Target language: also show the route the settings give")
    at: str | None = Field(None, description="Where to change settings: studio, project, a source (S1) or a journey (J1)")
    clear: list[str] = Field(default_factory=list, description="Settings to remove at --at (fall back to the layer below)")
    route: str | None = Field(None, description=SETTING_HELP["route"])
    middle: list[str] | None = Field(None, description=SETTING_HELP["middle"])
    budget: str | None = Field(None, description=SETTING_HELP["budget"])
    views_mt: list[str] | None = Field(None, description=SETTING_HELP["views_mt"])
    mt: str | None = Field(None, description=SETTING_HELP["mt"])
    verify: str | None = Field(None, description=SETTING_HELP["verify"])
    conserve: bool | None = Field(None, description=SETTING_HELP["conserve"])
    rounds: int | None = Field(None, description=SETTING_HELP["rounds"])
    band: list[float] | None = Field(None, description=SETTING_HELP["band"])
    mt_prior: float | None = Field(None, description=SETTING_HELP["mt_prior"])
    min_pause: float | None = Field(None, description=SETTING_HELP["min_pause"])
    strong: list[str] | None = Field(None, description=SETTING_HELP["strong"])
    voice: str | None = Field(None, description=SETTING_HELP["voice"])
    targets: list[str] | None = Field(None, description="Languages this media is to be dubbed into (a note shown with the settings)")


def _changes(inp: SettingsIn) -> dict:
    return L.normalise({k: getattr(inp, k) for k in (*L.FIELDS, "targets") if getattr(inp, k) is not None})


def apply_settings(ctx: Ctx, at: str, changes: dict, clear: list[str] | None = None) -> str:
    """Write dub settings at one layer: studio, project, a source or a journey. Returns the layer's name."""
    clear = clear or []
    bad = [c for c in clear if c not in (*L.FIELDS, "targets")]
    if bad:
        raise RecompError("E_INVALID", f"unknown setting(s) {bad}", hint=f"Settings: {', '.join(L.FIELDS)}")
    if at == "studio":
        cur = {k: v for k, v in (config.get("dub") or {}).items() if k not in clear}
        cur.update(changes)
        config.set_value("dub", cur)
        return "studio"
    if at == "project":
        cur = {k: v for k, v in (ctx.project.meta.get("dub") or {}).items() if k not in clear}
        cur.update(changes)
        ctx.project.meta["dub"] = cur
        ctx.project.save_meta()
        return "project"
    db = ctx.db
    if at.upper().startswith("S"):
        s = refs.source(db, at)
        meta = dict(s.get("meta") or {})
        meta["dub"] = {**{k: v for k, v in (meta.get("dub") or {}).items() if k not in clear}, **changes}
        with ctx.op(f"dub settings {s['ref']}") as tx:
            tx.update("source", s["id"], {"meta": meta})
        return f"source {s['ref']}"
    j = journey_of(db, at)
    st = dict(j.get("settings") or {})
    st["dub"] = {**{k: v for k, v in (st.get("dub") or {}).items() if k not in clear}, **changes}
    with ctx.op(f"dub settings {j['ref']}") as tx:
        tx.update("journey", j["id"], {"settings": st})
    return f"journey {j['ref']}"


@verb("dub.settings", SettingsIn, effect="write",
      examples=["recomp dub settings J1 --to om",
                "recomp dub settings --at project --route multi --middle en,es --views-mt google,nllb",
                "recomp dub settings --at S2 --route tgt-en --budget quality",
                "recomp dub settings --at studio --strong en,es,fr,de,am",
                "recomp dub settings --at J1 --clear route,budget"])
def dub_settings(ctx: Ctx, inp: SettingsIn):
    """Show or change the LLM dubber's settings. Layers, lowest first: studio → project → source → journey; each shown value says where it came from."""
    changes = _changes(inp)
    changed = None
    if changes or inp.clear:
        if not inp.at:
            raise RecompError("E_INVALID", "say where to change them with --at studio|project|S1|J1")
        changed = apply_settings(ctx, inp.at, changes, inp.clear)
    db = ctx.db
    target = inp.target or (inp.at if inp.at and inp.at not in ("studio", "project") else None)
    out: dict = {"changed": changed, "fields": SETTING_HELP}
    if target and target.upper().startswith("J"):
        j = journey_of(db, target)
        per = []
        for sid in dict.fromkeys(it["source"]["id"] for it in R.timeline(db, j)):
            s = db.get("source", sid)
            eff, origin = L.resolve(ctx.project, s, j)
            row = {"source": s["ref"], "language": _src_lang(ctx, s), "settings": eff, "from": origin}
            if inp.to:
                row["plan"] = L.plan(_src_lang(ctx, s), inp.to, eff)
            per.append(row)
        out.update(journey=j["ref"], sources=per)
    elif target:
        s = refs.source(db, target)
        eff, origin = L.resolve(ctx.project, s)
        out.update(source=s["ref"], language=_src_lang(ctx, s), settings=eff, **{"from": origin})
        if inp.to:
            out["plan"] = L.plan(_src_lang(ctx, s), inp.to, eff)
    else:
        eff, origin = L.resolve(ctx.project)
        out.update(settings=eff, **{"from": origin})
        if inp.to:
            out["plan"] = L.plan((ctx.project.meta.get("languages") or ["en"])[0], inp.to, eff)
    nxt = [f"recomp dub understand {target} --to {inp.to} --template"] if target and target.upper().startswith("J") and inp.to else []
    return Result(data=out, next=nxt)


# ---- understand ------------------------------------------------------------------------------------------------

class UnderstandIn(BaseModel):
    journey: str = Field(..., json_schema_extra={"pos": 0})
    to: str = Field(..., description="Target language code")
    template: bool = Field(False, description="Return the evidence for each line (source text or MT views) to write the map from")
    maps: dict[str, dict] = Field(default_factory=dict, description="{key: {best, confidence, notes, units:[{id, text, tier, frame}]}} (use --input)")
    keys: list[str] = Field(default_factory=list, description="Only these lines (seg:… keys)")


@verb("dub.understand", UnderstandIn, effect="write",
      examples=["recomp dub understand J1 --to om --template", "recomp dub understand J1 --to om --input maps.json"])
def dub_understand(ctx: Ctx, inp: UnderstandIn):
    """Stage 1: the meaning map. The template shows each line's speech frames and its evidence: the source itself when you read it well, otherwise independent MT views in the middle language(s). Write units (core/support/colour) pinned to frames."""
    db = ctx.db
    j = journey_of(db, inp.journey)
    ls = [ln for ln in lines(db, ctx.project, j, inp.to) if not inp.keys or ln["key"] in inp.keys]
    if inp.template:
        mt = L.MT(ctx.project)
        have = work(db, j, inp.to, "map")
        batches: dict[tuple, list[str]] = {}
        for ln in ls:
            for v in ln["route"]["views"]:
                batches.setdefault((ln["src_lang"], v["lang"], v["mt"]), []).extend([ln["text"]] + [f["text"] for f in ln["frames"]])
        got = {}
        for (sl, vl, eng), texts in batches.items():
            uniq = sorted(set(t for t in texts if t.strip()))
            for t, r in zip(uniq, mt.translate(uniq, sl, vl, eng)):
                got[(sl, vl, eng, t)] = r
        mt.save()
        out = []
        for ln in ls:
            item = {"key": ln["key"], "source": ln["source"], "route": ln["route"]["route"],
                    "frames": [{"n": k + 1, "dur": f["dur"]} for k, f in enumerate(ln["frames"])]}
            if ln["route"]["views"]:
                item["views"] = [{"lang": v["lang"], "mt": v["mt"], "whole": got.get((ln["src_lang"], v["lang"], v["mt"], ln["text"]), ""),
                                  "frames": [got.get((ln["src_lang"], v["lang"], v["mt"], f["text"]), "") for f in ln["frames"]]}
                                 for v in ln["route"]["views"]]
            else:
                item["text"] = ln["text"]
                item["frames"] = [dict(fr, text=f["text"]) for fr, f in zip(item["frames"], ln["frames"])]
            if ln["key"] in have:
                item["current"] = have[ln["key"]]["data"]
            out.append(item)
        return Result(data={"journey": j["ref"], "to": inp.to, "lines": out,
                            "write": "For each key: {best: the line's meaning in " + (ls[0]["route"]["reads"][0] if ls else "en") +
                                     ", confidence: high|medium|low, notes: what you resolved or could not, "
                                     "units: [{id: u1…, text, tier: core|support|colour, frame: n}]}. Read every view: "
                                     "they come from independent MT and disagree where the meaning is at risk."},
                      next=[f"recomp dub understand {j['ref']} --to {inp.to} --input maps.json   # {{\"maps\": {{key: …}}}}"])
    by = {ln["key"]: ln for ln in ls}
    bad = [k for k in inp.maps if k not in by]
    if bad:
        raise RecompError("E_INVALID", f"unknown keys: {bad[:5]}", hint="Use the keys from --template")
    if not inp.maps:
        raise RecompError("E_INVALID", "give --template, or --input with {maps: {key: …}}")
    for k, m in inp.maps.items():
        us = m.get("units") or []
        ids = [u.get("id") for u in us]
        if not us or len(set(ids)) != len(ids) or any(u.get("tier", "core") not in L.TIER_W for u in us):
            raise RecompError("E_INVALID", f"{k}: units need unique ids and tier core|support|colour")
        nf = len(by[k]["frames"])
        for u in us:
            u["frame"] = int(u.get("frame") or 1)
            if not 1 <= u["frame"] <= nf:
                raise RecompError("E_INVALID", f"{k}: unit {u['id']} frame {u['frame']} (this line has {nf})")
    with ctx.op(f"dub understand {j['ref']} → {inp.to}") as tx:
        for k, m in inp.maps.items():
            put(tx, db, j, inp.to, "map", k, m)
    have = work(db, j, inp.to, "map")
    return Result(data={"journey": j["ref"], "to": inp.to, "written": len(inp.maps), "mapped": f"{len(have)}/{len(ls)}",
                        "low_confidence": [k for k, m in inp.maps.items() if str(m.get("confidence", "")).lower() == "low"]},
                  next=[f"recomp dub write {j['ref']} --to {inp.to} --template"])


# ---- write -----------------------------------------------------------------------------------------------------

class WriteIn(BaseModel):
    journey: str = Field(..., json_schema_extra={"pos": 0})
    to: str = Field(..., description="Target language code")
    template: bool = Field(False, description="Return what to write: per frame its time, syllable target, units and languages; after a fit, only the rewrites still needed")
    options: dict[str, dict] = Field(default_factory=dict, description="{key: {frame n: [{text, lang, units, strategy}]}} (use --input)")
    keys: list[str] = Field(default_factory=list, description="Only these lines")
    all: bool = Field(False, description="Template: every line, not only those still needing work")


@verb("dub.write", WriteIn, effect="write",
      examples=["recomp dub write J1 --to om --template", "recomp dub write J1 --to om --input options.json"])
def dub_write(ctx: Ctx, inp: WriteIn):
    """Stage 2: options per speech frame, in the route's writing language(s), each labelled with the units it carries. After a fit, the template lists only the frames to rewrite, with a syllable target."""
    db = ctx.db
    j = journey_of(db, inp.journey)
    ls = [ln for ln in lines(db, ctx.project, j, inp.to) if not inp.keys or ln["key"] in inp.keys]
    maps, opts, choice = work(db, j, inp.to, "map"), work(db, j, inp.to, "options"), work(db, j, inp.to, "choice")
    if inp.template:
        rate = L.Ruler(ctx.project, inp.to, ls[0]["settings"].get("voice") if ls else None).rate()
        out, missing = [], []
        for ln in ls:
            if ln["key"] not in maps:
                missing.append(ln["key"])
                continue
            mp = maps[ln["key"]]["data"]
            ch = (choice.get(ln["key"]) or {}).get("data")
            if ch and not inp.all:
                if not ch["steer"]:
                    continue
                out.append({"key": ln["key"], "best": mp.get("best"), "rewrite": ch["steer"], "writes": ln["route"]["writes"]})
                continue
            out.append({"key": ln["key"], "best": mp.get("best"), "writes": ln["route"]["writes"],
                        "frames": [{"n": k + 1, "dur": f["dur"], "target_syllables": round(0.93 * f["dur"] * rate),
                                    "units": [u for u in mp["units"] if int(u.get("frame", 1)) == k + 1]}
                                   for k, f in enumerate(ln["frames"])]})
        return Result(data={"journey": j["ref"], "to": inp.to, "lines": out, "unmapped": missing,
                            "write": "For each key: {frame n: [2–4 options {text, lang (one of writes), units: [ids it "
                                     "carries], strategy: orig|compact|full|plain|steer}]}. Natural spoken lines, no new "
                                     "facts; syllable targets are for the target voice. Writing in a language other than the "
                                     "target: plain, MT-friendly wording (no idioms, explicit subjects)."},
                      next=[f"recomp dub write {j['ref']} --to {inp.to} --input options.json   # {{\"options\": {{key: …}}}}"])
    by = {ln["key"]: ln for ln in ls}
    bad = [k for k in inp.options if k not in by]
    if bad:
        raise RecompError("E_INVALID", f"unknown keys: {bad[:5]}", hint="Use the keys from --template")
    if not inp.options:
        raise RecompError("E_INVALID", "give --template, or --input with {options: {key: {frame: [...]}}}")
    added = 0
    with ctx.op(f"dub write {j['ref']} → {inp.to}") as tx:
        for k, per in inp.options.items():
            ln = by[k]
            cur = ((opts.get(k) or {}).get("data") or {}).get("frames") or {}
            cur = {fk: list(vs) for fk, vs in cur.items()}
            for fk, vs in per.items():
                n = int(fk)
                if not 1 <= n <= len(ln["frames"]):
                    raise RecompError("E_INVALID", f"{k}: frame {n} (this line has {len(ln['frames'])})")
                have = {L.option_id(k, n, v["lang"], v["text"]) for v in cur.get(str(n), [])}
                for v in vs:
                    v = {"text": str(v.get("text", "")).strip(), "lang": v.get("lang") or ln["route"]["writes"][0],
                         "units": list(v.get("units") or []), "strategy": v.get("strategy", "orig"), "added": v.get("added", [])}
                    oid = L.option_id(k, n, v["lang"], v["text"])
                    if oid not in have:
                        cur.setdefault(str(n), []).append(v)
                        have.add(oid)
                        added += 1
            prev = opts.get(k)
            put(tx, db, j, inp.to, "options", k, {"frames": cur}, round_=(prev["round"] + 1) if prev else 1)
    return Result(data={"journey": j["ref"], "to": inp.to, "lines": len(inp.options), "options_added": added},
                  next=[f"recomp dub fit {j['ref']} --to {inp.to}"])


# ---- fit -------------------------------------------------------------------------------------------------------

class FitIn(BaseModel):
    journey: str = Field(..., json_schema_extra={"pos": 0})
    to: str = Field(..., description="Target language code")


@verb("dub.fit", FitIn, effect="heavy", examples=["recomp dub fit J1 --to om"])
def dub_fit(ctx: Ctx, inp: FitIn):
    """Stage 3 (a job): translate options that cross into the target, voice every candidate, choose the best combination per line, write the chosen lines as translations and list checks and rewrites."""
    j = journey_of(ctx.db, inp.journey)
    job = jobs.enqueue(ctx.db, "dubfit", target=j["ref"], params={"journey_id": j["id"], "to": inp.to, "actor": ctx.actor})
    mode = jobs.kick(ctx.project)
    data = {"job": job["ref"], "runner": mode}
    if mode == "inline":
        row = ctx.db.get("job", job["id"])
        if row["status"] == "failed":
            raise RecompError("E_JOB", row.get("error") or "dub fit failed", hint=f"`recomp job show {job['ref']}`")
        data["result"] = row.get("result")
    return Result(data=data, job=job["ref"],
                  next=[f"recomp job wait {job['ref']}", f"recomp dub status {j['ref']} --to {inp.to}"])


# ---- verify ----------------------------------------------------------------------------------------------------

class VerifyIn(BaseModel):
    journey: str = Field(..., json_schema_extra={"pos": 0})
    to: str = Field(..., description="Target language code")
    template: bool = Field(False, description="Return the chosen target lines that crossed MT, back-translated, with their units")
    checks: dict[str, dict] = Field(default_factory=dict, description="{option id: {covered: [unit ids], errors: [...], added: [...]}} (use --input)")


@verb("dub.verify", VerifyIn, effect="write",
      examples=["recomp dub verify J1 --to om --template", "recomp dub verify J1 --to om --input checks.json"])
def dub_verify(ctx: Ctx, inp: VerifyIn):
    """Stage 4: meaning checks for target lines you cannot read. The template back-translates each chosen option into the middle language(s); mark which units survived and any error (wrong word, polarity, subject). Then fit again."""
    db = ctx.db
    j = journey_of(db, inp.journey)
    choice, maps = work(db, j, inp.to, "choice"), work(db, j, inp.to, "map")
    if inp.template:
        by = {ln["key"]: ln for ln in lines(db, ctx.project, j, inp.to)}
        mt = L.MT(ctx.project)
        items = []
        for key, row in choice.items():
            ch = row["data"]
            ln = by.get(key)
            if not ln or not ch["needs_check"]:
                continue
            back = ln["route"]["back_translate"] or [{"lang": ln["route"]["reads"][0], "mt": ln["settings"]["mt"]}]
            units = maps[key]["data"]["units"] if key in maps else []
            for k, (p, t) in enumerate(zip(ch["picks"], ch["phrases"])):
                if p["id"] not in ch["needs_check"]:
                    continue
                bts = {f"{b['lang']} ({b['mt']})": mt.translate([t], inp.to, b["lang"], b["mt"])[0] for b in back}
                items.append({"id": p["id"], "key": key, "frame": k + 1, "written": p["text"], "target": t,
                              "back_translations": bts, "units": [u for u in units if int(u.get("frame", 1)) == k + 1]})
        mt.save()
        return Result(data={"journey": j["ref"], "to": inp.to, "checks": items,
                            "write": "For each id: {covered: [unit ids the back-translation still carries], errors: [wrong word, "
                                     "reversed polarity, wrong subject…], added: [content not in the source]}. Judge the "
                                     "meaning, not the style; pronoun gender lost in back-translation alone is not an error."},
                      next=[f"recomp dub verify {j['ref']} --to {inp.to} --input checks.json   # {{\"checks\": {{id: …}}}}"])
    if not inp.checks:
        raise RecompError("E_INVALID", "give --template, or --input with {checks: {option id: …}}")
    known = {p["id"]: key for key, row in choice.items() for p in row["data"]["picks"] if p.get("id")}
    opts = work(db, j, inp.to, "options")
    for key, row in opts.items():
        for fk, vs in (row["data"].get("frames") or {}).items():
            for v in vs:
                known.setdefault(L.option_id(key, int(fk), v["lang"], v["text"]), key)
    bad = [i for i in inp.checks if i not in known]
    if bad:
        raise RecompError("E_INVALID", f"unknown option ids: {bad[:5]}", hint="Use the ids from --template")
    with ctx.op(f"dub verify {j['ref']} → {inp.to}") as tx:
        for oid, c in inp.checks.items():
            put(tx, db, j, inp.to, "verified", oid, {"covered": list(c.get("covered") or []), "errors": list(c.get("errors") or []),
                                                    "added": list(c.get("added") or []), "key": known[oid]})
    errs = sum(1 for c in inp.checks.values() if c.get("errors"))
    return Result(data={"journey": j["ref"], "to": inp.to, "checked": len(inp.checks), "with_errors": errs},
                  next=[f"recomp dub fit {j['ref']} --to {inp.to}   # chooses around the errors"])


# ---- status ----------------------------------------------------------------------------------------------------

class StatusIn(BaseModel):
    journey: str = Field(..., json_schema_extra={"pos": 0})
    to: str = Field(..., description="Target language code")


@verb("dub.status", StatusIn, examples=["recomp dub status J1 --to om"])
def dub_status(ctx: Ctx, inp: StatusIn):
    """Where the LLM dub of a journey stands: lines mapped, options written, fit per line, checks and rewrites pending, and the next step."""
    db = ctx.db
    j = journey_of(db, inp.journey)
    ls = lines(db, ctx.project, j, inp.to)
    maps, opts, choice = work(db, j, inp.to, "map"), work(db, j, inp.to, "options"), work(db, j, inp.to, "choice")
    rows, checks, steer = [], 0, 0
    for ln in ls:
        ch = (choice.get(ln["key"]) or {}).get("data")
        r = {"key": ln["key"], "route": ln["route"]["route"], "frames": len(ln["frames"]),
             "mapped": ln["key"] in maps, "options": ln["key"] in opts}
        if ch:
            r.update(text=ch["text"], ratios=ch["ratios"], needs_check=len(ch["needs_check"]), rewrites=len(ch["steer"]),
                     missing_core=ch["missing_core"], round=choice[ln["key"]]["round"])
            checks += len(ch["needs_check"])
            steer += len(ch["steer"])
        if ln["key"] in maps:
            r["confidence"] = maps[ln["key"]]["data"].get("confidence")
        rows.append(r)
    routes = sorted({ln["route"]["route"] for ln in ls})
    if len(maps) < len(ls):
        nxt = f"recomp dub understand {j['ref']} --to {inp.to} --template"
    elif len(opts) < len(ls):
        nxt = f"recomp dub write {j['ref']} --to {inp.to} --template"
    elif len(choice) < len(ls):
        nxt = f"recomp dub fit {j['ref']} --to {inp.to}"
    elif checks:
        nxt = f"recomp dub verify {j['ref']} --to {inp.to} --template"
    elif steer:
        nxt = f"recomp dub write {j['ref']} --to {inp.to} --template   # rewrites, then fit"
    else:
        nxt = f"recomp lang translate {j['ref']} --to {inp.to} --template   # title and overlays, then export"
    return Result(data={"journey": j["ref"], "to": inp.to, "routes": routes, "lines": len(ls), "mapped": len(maps),
                        "with_options": len(opts), "fitted": len(choice), "checks_pending": checks, "rewrites_pending": steer,
                        "low_confidence": [r["key"] for r in rows if str(r.get("confidence", "")).lower() == "low"],
                        "per_line": rows}, next=[nxt])
