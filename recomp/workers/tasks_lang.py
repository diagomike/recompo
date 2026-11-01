"""Language jobs: the LLM dubber's fit (MT the options, voice them, choose exactly, ask for checks and rewrites)."""

from __future__ import annotations

from ..compose import recipe as R
from ..envelope import RecompError
from ..lang import llmdub as L
from ..transcript.store import primary
from .jobs import JobCtx, task


def lines(db, project, j: dict, lang: str) -> list[dict]:
    """The journey's spoken lines with their speech frames, source language, effective settings and route."""
    out, seen, cache = [], set(), {}
    for it in R.timeline(db, j):
        src = db.get("source", it["source"]["id"])
        tr = primary(db, src["id"])
        if not tr:
            continue
        if src["id"] not in cache:
            eff, _ = L.resolve(project, src, j)
            src_lang = src.get("language") or tr.get("language") or (project.meta.get("languages") or ["en"])[0]
            cache[src["id"]] = (eff, L.plan(src_lang, lang, eff), src_lang)
        eff, route, src_lang = cache[src["id"]]
        for s in db.all('SELECT id, start, "end", text FROM segment WHERE transcript_id=? AND "end" > ? AND start < ? ORDER BY idx',
                        (tr["id"], it["in"] + 0.05, it["out"] - 0.05)):
            if s["id"] in seen:
                continue
            seen.add(s["id"])
            span = (max(s["start"], it["in"]), min(s["end"], it["out"]))
            words = [(w[0], w[1], w[2]) for w in db.all('SELECT start, "end", text FROM word WHERE segment_id=? ORDER BY idx',
                                                       (s["id"],))]
            out.append({"key": f"seg:{s['id']}", "seg": s["id"], "source": src["ref"], "src_lang": src_lang, "text": s["text"],
                        "span": span, "frames": L.frames(words, span, s["text"], eff["min_pause"]), "settings": eff,
                        "route": route})
    return out


def work(db, j: dict, lang: str, kind: str) -> dict[str, dict]:
    return {r["key"]: r for r in db.rows("dub_work", "WHERE journey_id=? AND lang=? AND kind=? ORDER BY updated_at",
                                         (j["id"], lang, kind))}


def put(tx, db, j: dict, lang: str, kind: str, key: str, data: dict, round_: int = 1, log: bool = True) -> None:
    row = db.one("SELECT id FROM dub_work WHERE journey_id=? AND lang=? AND kind=? AND key=?", (j["id"], lang, kind, key))
    if row:
        tx.update("dub_work", row["id"], {"data": data, "round": round_}, log=log)
    else:
        tx.insert("dub_work", {"journey_id": j["id"], "lang": lang, "kind": kind, "key": key, "data": data, "round": round_},
                  log=log)


def fit(project, j: dict, lang: str, actor: str, log=print, progress=None) -> dict:
    """MT every option that crosses into the target, voice every candidate, choose the best combination per line,
    write the chosen lines as translations (method ``llmdub``) and record checks and rewrite requests."""
    db = project.db
    ls = lines(db, project, j, lang)
    maps, opts, ver = work(db, j, lang, "map"), work(db, j, lang, "options"), work(db, j, lang, "verified")
    todo = [ln for ln in ls if ln["key"] in maps and ln["key"] in opts]
    if not todo:
        raise RecompError("E_INVALID", f"no lines with both a meaning map and options for {lang}",
                          hint=f"`recomp dub understand {j['ref']} --to {lang} --template`, then `recomp dub write …`")
    voice, online = todo[0]["settings"].get("voice"), bool(todo[0]["settings"].get("online"))
    mt, ruler = L.MT(project), L.Ruler(project, lang, voice, online)
    # 1. every option, translated into the target when it was written in another language
    cands: dict[str, dict[int, list[dict]]] = {}
    crossing: dict[tuple[str, str], list[str]] = {}
    for ln in todo:
        per = {}
        for fk, vs in (opts[ln["key"]]["data"].get("frames") or {}).items():
            per[int(fk) - 1] = [dict(v) for v in vs]
            for v in vs:
                if v["lang"] != lang and v["text"].strip():
                    eng = ln["route"]["mt_into"].get(v["lang"]) or \
                        L.engine_for(ln["settings"]["mt"], v["lang"], lang, bool(ln["settings"].get("online")))[0]
                    crossing.setdefault((v["lang"], eng), []).append(v["text"])
        cands[ln["key"]] = per
    translated = {}
    for (wl, engine), texts in crossing.items():
        uniq = sorted(set(texts))
        log(f"dub fit: MT {len(uniq)} option(s) {wl}→{lang} ({engine})")
        for t, r in zip(uniq, mt.translate(uniq, wl, lang, engine)):
            translated[(wl, t)] = r
    mt.save()
    for per in cands.values():
        for vs in per.values():
            for v in vs:
                v["target"] = v["text"] if v["lang"] == lang else translated.get((v["lang"], v["text"]), "")
    # 2. the target voice speaks every candidate once (cached across rounds and journeys)
    every = [v["target"] for per in cands.values() for vs in per.values() for v in vs if v["target"].strip()]
    log(f"dub fit: voicing {len(set(every))} candidate(s) with the {lang} voice")
    ruler.measure(every, progress=(lambda f, m: progress(0.1 + 0.7 * f, m)) if progress else None)
    rate = ruler.rate()
    # 3. exact choice per line, checks and rewrite requests
    results, written, kept, n_frames, inband, within, over, need_check, steer = {}, 0, [], 0, 0, 0, 0, 0, 0
    with db.op("dub.fit", actor, {"journey": j["ref"], "to": lang}) as tx:
        tx.summary = f"dub fit {j['ref']} → {lang}"
        for ln in todo:
            st, route = ln["settings"], ln["route"]
            mp = maps[ln["key"]]["data"]
            units = [{"id": u["id"], "tier": u.get("tier", "core")} for u in mp.get("units", [])]
            per = cands[ln["key"]]
            langs_here = {v["lang"] for vs in per.values() for v in vs}
            pooled = lang in langs_here and len(langs_here) > 1
            checking = bool(route["back_translate"]) or st.get("verify") == "always"
            variants = {}
            for k, fr in enumerate(ln["frames"]):
                pool = []
                for v in per.get(k, []):
                    oid = L.option_id(ln["key"], k + 1, v["lang"], v["text"])
                    vr = (ver.get(oid) or {}).get("data")
                    crossed = v["lang"] != lang
                    pool.append({"text": v["target"], "id": oid, "lang": v["lang"], "src_text": v["text"],
                                 "strategy": v.get("strategy", ""), "units": vr["covered"] if vr else v.get("units", []),
                                 "errors": vr.get("errors", []) if vr else [], "added": (vr or {}).get("added", v.get("added", [])),
                                 "penalty": st["mt_prior"] if pooled and crossed else 0.0,
                                 "checked": bool(vr) or not v["text"].strip() or not (checking and (crossed or st.get("verify") == "always"))})
                if not pool and fr["dur"] >= 0.3:
                    pool = [{"text": "", "units": [], "id": "", "lang": lang, "src_text": "", "checked": True}]
                variants[k] = pool
            ch = L.select(units, ln["frames"], variants, ruler, band=tuple(st["band"]), conserve=st["conserve"])
            picks = ch["picks"]
            unchecked = [p["id"] for p in picks if p.get("id") and not p.get("checked")]
            # expansion: target voice seconds per syllable of the writing language, on this line's crossed options
            pairs = [(ruler(v["text"]), L.syllables(v["src_text"])) for vs in variants.values() for v in vs
                     if v.get("lang") != lang and v["text"].strip()]
            e = sum(p for p, _ in pairs) / max(1.0, sum(s for _, s in pairs)) if pairs else 0.0
            lo, hi = st["band"]
            reqs = []
            for k, (p, r) in enumerate(zip(picks, ch["ratios"])):
                fr = ln["frames"][k]
                n_frames += 1
                inband += lo <= r <= hi
                within += abs(r - 1) <= 0.2
                over += r > 1.1
                if (not p["text"].strip() and fr["dur"] < 0.3) or lo <= r <= hi or (st["conserve"] and 0.65 <= r < lo):
                    continue
                wl = p.get("lang") or route["writes"][0]
                syl = 0.93 * fr["dur"] * rate if wl == lang else (0.93 * fr["dur"] / e if e else 0.93 * fr["dur"] * rate)
                reqs.append({"frame": k + 1, "dur": fr["dur"], "ratio": r, "now": p.get("src_text", ""), "lang": wl,
                             "target_syllables": round(syl), "action": "shorten" if r > hi else "lengthen",
                             "units": [u for u in mp.get("units", []) if int(u.get("frame", 1)) == k + 1]})
            text = " ".join(t for t in ch["phrases"] if t.strip())
            data = {"seg": ln["seg"], "span": list(ln["span"]), "frames": [{"start": f["start"], "end": f["end"], "dur": f["dur"]}
                                                                          for f in ln["frames"]],
                    "phrases": ch["phrases"], "ratios": ch["ratios"], "units": ch["units"], "missing_core": ch["missing_core"],
                    "picks": [{"id": p.get("id"), "lang": p.get("lang"), "text": p.get("src_text"), "strategy": p.get("strategy")}
                              for p in picks], "needs_check": unchecked, "steer": reqs, "score": ch["score"], "text": text,
                    "route": route["route"], "confidence": mp.get("confidence")}
            prev = work(db, j, lang, "choice").get(ln["key"])
            put(tx, db, j, lang, "choice", ln["key"], data, round_=(prev["round"] + 1) if prev else 1)
            need_check += len(unchecked)
            steer += len(reqs)
            if text:
                row = db.one("SELECT id FROM translation WHERE lang=? AND kind='segment' AND target_id=?", (lang, str(ln["seg"])))
                try:
                    if row:
                        tx.update("translation", row["id"], {"text": text, "method": "llmdub"})
                    else:
                        tx.insert("translation", {"lang": lang, "kind": "segment", "target_id": str(ln["seg"]), "text": text,
                                                  "method": "llmdub"})
                    written += 1
                except RecompError:
                    kept.append(ln["key"])
            results[ln["key"]] = {"ratios": ch["ratios"], "missing_core": ch["missing_core"], "needs_check": len(unchecked),
                                  "steer": len(reqs)}
    pct = lambda x: round(100 * x / max(1, n_frames), 1)  # noqa: E731
    low = [k for k in results if (maps[k]["data"].get("confidence") or "").lower() == "low"]
    return {"journey": j["ref"], "to": lang, "lines": len(todo), "without_options": len(ls) - len(todo), "written": written,
            "kept_users": kept, "frames": n_frames, "in_band_pct": pct(inband), "within_20pct": pct(within),
            "over_1_1_pct": pct(over), "missing_core_lines": [k for k, r in results.items() if r["missing_core"]],
            "needs_check": need_check, "steer_requests": steer, "low_confidence": low, "mt_calls": mt.calls}


@task("dubfit", lane="net")
def job_dubfit(ctx: JobCtx):
    p = ctx.params
    j = ctx.db.get("journey", p["journey_id"])
    if j is None:
        raise RecompError("E_NOT_FOUND", "journey gone")
    res = fit(ctx.project, j, p["to"], p.get("actor") or "agent", log=ctx.log, progress=ctx.progress)
    ctx.progress(1.0, f"{res['in_band_pct']} % of frames in band")
    return res
