"""Working-language routing for timed dubbing (P19 worktree `routes`).

The LLM only ever works in languages it is strong in ("working languages"). Which ones, and how many, is a
per-pair choice:

  direct         source and target both strong: understand the source, write timed lines in the target (MCTR).
  target-direct  source weak, target strong: understand through MT views into a pivot, then write the target
                 directly. No second MT hop.
  source-side    source strong, target weak: write options in the source (or a pivot), MT them, time the target
                 (two-sided optimiser).
  pivot          both weak: understand through MT views into a pivot, write options in the pivot, MT them.

Budget knob:
  economy        one working language for writing (fewest tokens).
  quality        two working languages: options are written in both and pooled, and the exact selector picks
                 per segment from either (more tokens, more candidates per segment).

Commands:
  plan      print the route for a pair:      routes.py plan --src am --tgt om [--budget quality --pivots en,es]
  select    choose one option per segment for a route (E = pivot options through MT, D = target written directly,
            X = both pooled), and write steering requests for what is still out of band
  cascade   the naive baseline: whole-line MT to the pivot, MT to the target, placement onto the segments
  report    timing metrics for chosen files; tokens: LLM text written/read per route
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import mctr as M  # noqa: E402
import timing as T  # noqa: E402

# Rough LLM strength by language (edit per model). "strong": the LLM can read nuance and write natural, timed text.
STRENGTH = {l: "strong" for l in ("en", "es", "fr", "de", "it", "pt", "nl", "zh", "ja", "ru", "ar", "hi")}
STRENGTH.update({l: "weak" for l in ("am", "om", "ti", "so", "wo", "ha", "yo", "ig", "rw")})


def plan(src: str, tgt: str, budget: str = "economy", pivots: list[str] | None = None) -> dict:
    s, t = STRENGTH.get(src, "weak"), STRENGTH.get(tgt, "weak")
    pivots = pivots or ["en"]
    if budget == "economy":
        pivots = pivots[:1]
    if s == "strong" and t == "strong":
        route, read, write = "direct", [src], [tgt]
    elif t == "strong":
        route, read, write = "target-direct", pivots, [tgt] + (pivots[:1] if budget == "quality" else [])
    elif s == "strong":
        route, read, write = "source-side", [src], ([src] + [p for p in pivots if p != src])[: 2 if budget == "quality" else 1]
    else:
        route, read, write = "pivot", pivots, pivots
    steps = []
    if s == "weak":
        steps.append(f"ASR {src} → MT views into {', '.join(read)} (whole, per segment, terse/full, glosses) + prosody")
        steps.append("LLM: meaning map in " + read[0] + " with units pinned to source segments, confidence, ambiguities")
    else:
        steps.append(f"ASR {src} → LLM meaning map (units allocated to segments)")
    for w in write:
        steps.append(f"LLM: options per segment in {w}" + ("" if w == tgt else f" → MT {w}→{tgt}"))
    steps.append(f"{tgt} voice: time every option on the source speaker's segments → exact selection"
                 + (" over the pooled options" if len(write) > 1 else ""))
    steps.append("steer what is out of band (round 2)")
    if t == "weak":
        steps.append(f"verify: back-translate the chosen {tgt} into {read[0]}, check units and errors")
    if s == "weak":
        steps.append("low-confidence lines → human review")
    return {"src": src, "tgt": tgt, "route": route, "budget": budget, "reads_in": read, "writes_in": write, "steps": steps}


def load_mt(path: Path | None) -> dict[str, str]:
    out = {}
    if path and path.exists():
        for l in path.read_text(encoding="utf-8").splitlines():
            if l.strip():
                r = json.loads(l)
                out[r["key"].strip()] = r["text"]
    return out


MT_PRIOR = 0.0  # pooled route: cost on an MT-route option, so a directly written one wins near-ties


def variants_for(i: str, route: str, opts_en: dict, mt: dict, opts_tg: dict) -> dict[int, list[dict]]:
    out: dict[int, list[dict]] = {}

    def add(k, v):
        pool = out.setdefault(int(k) - 1, [])
        if not any(p["text"] == v["text"] for p in pool):
            pool.append(v)
    if route in ("E", "X"):
        for k, vs in opts_en.get(i, {}).items():
            for x in vs:
                s = x["src"].strip()
                add(k, {"text": mt.get(s, "") if s else "", "src": s, "units": x.get("units", []), "via": "pivot",
                        "strategy": x.get("strategy", "orig"), "penalty": MT_PRIOR if route == "X" else 0.0})
    if route in ("D", "X"):
        for k, vs in opts_tg.get(i, {}).items():
            for x in vs:
                add(k, {"text": x["src"].strip(), "src": x["src"].strip(), "units": x.get("units", []), "via": "direct",
                        "strategy": x.get("strategy", "orig")})
    return out


def cmd_select(a):
    from wt_multiround import Voice
    global MT_PRIOR
    MT_PRIOR = a.mt_prior
    if a.conserve:
        M.GAMMA, M.SOFT_FLOOR = 2.0, 0.65
    v = Voice(a.voice, a.cache)
    lines = M.load_lines(a.maps, a.frames)
    mt = load_mt(a.mt)
    opts_en = {}
    for p in a.opts_en or []:
        for i, segs in json.loads(p.read_text(encoding="utf-8")).items():
            for k, vs in segs.items():
                opts_en.setdefault(i, {}).setdefault(k, []).extend(vs)
    opts_tg = {}
    for p in a.opts_tgt or []:
        for i, segs in json.loads(p.read_text(encoding="utf-8")).items():
            for k, vs in segs.items():
                opts_tg.setdefault(i, {}).setdefault(k, []).extend(vs)
    rate_t = M.voice_rate(v.cache, a.tgt) if v.cache else 5.5
    out, reqs = {}, []
    for i, ln in lines.items():
        var = variants_for(i, a.route, opts_en, mt, opts_tg)
        if not var:
            continue
        ch = M.select(ln, var, v)
        ch["via"] = [next((x["via"] for x in var.get(k, []) if x["text"] == t), "") for k, t in enumerate(ch["phrases"])]
        ch["src"] = [next((x["src"] for x in var.get(k, []) if x["text"] == t), "") for k, t in enumerate(ch["phrases"])]
        out[i] = ch
        pivot_pairs = [(v(x["text"]), T.syllables(x["src"], "en")) for vs in var.values() for x in vs
                       if x["via"] == "pivot" and x["text"].strip()]
        e = sum(p for p, _ in pivot_pairs) / max(1.0, sum(s for _, s in pivot_pairs)) if pivot_pairs else 0
        for k, (t, r) in enumerate(zip(ch["phrases"], ch["ratios"])):
            s = ln.segs[k]
            if (not t.strip() and s["dur"] < 0.3) or M.BAND[0] <= r <= M.BAND[1] or (M.SOFT_FLOOR and M.SOFT_FLOOR <= r < M.BAND[0]):
                continue
            units = [f"{u.id}:{u.tier}:{u.text}" for u in ln.units if u.seg == k]
            if a.route == "E":
                need = f"write English of ~{0.95 * s['dur'] / e:.0f} syl (expansion {e:.3f}s/syl)" if e else ""
            else:
                need = f"write {a.tgt} of ~{0.93 * s['dur'] * rate_t:.0f} syl"
            reqs.append(f"{i}[{k + 1}] {s['dur']:.2f}s ×{r:.2f} | now '{ch['src'][k]}' → {need}; units {units}")
    v.save()
    a.out.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    rs = [r for c in out.values() for r in c["ratios"]]
    inb = sum(M.BAND[0] <= r <= M.BAND[1] for r in rs)
    from collections import Counter
    via = Counter(x for c in out.values() for x, t in zip(c["via"], c["phrases"]) if t.strip())
    print(f"route {a.route}: lines {len(out)}  in band {inb}/{len(rs)}  over 1.1× {sum(r > 1.1 for r in rs)}  "
          f"core kept {sum(c['kept_all_core'] for c in out.values())}/{len(out)}  chosen via {dict(via)}")
    if a.revise:
        a.revise.write_text("\n".join(reqs) + ("\n" if reqs else ""), encoding="utf-8")
        print(f"{len(reqs)} steering requests → {a.revise}")


def cmd_cascade(a):
    """Whole-line pivot MT (the `whole` view) → target MT of that line → split onto the segments by syllables."""
    from twosided import split_source
    views = load_mt(a.views)
    mt = load_mt(a.mt)
    frames = json.loads(a.frames.read_text(encoding="utf-8"))
    out = {}
    for i in a.ids.read_text().split():
        segs = frames[i]["segments"]
        tgt = mt.get(views.get(f"{i}|whole", "").strip(), "")
        out[i] = {"phrases": split_source(tgt.split(), [s["dur"] for s in segs], a.tgt)}
    a.out.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"cascade for {len(out)} lines")


def metrics(chosen: dict, frames: dict, v) -> dict:
    from bench import score_item
    rs, ov = [], []
    for i, c in chosen.items():
        item = {"segments": frames[i]["segments"]}
        sc = score_item(item, c["phrases"], v)
        ov.append(sc["speech_overlap"])
        rs += [r for r in sc["seg_ratio"] if r is not None]
    n = len(rs)
    pct = lambda k: round(100 * k / n, 1)  # noqa: E731
    return {"segments": n, "speech_overlap": round(sum(ov) / len(ov), 3),
            "in_band_0.8_1.05": pct(sum(0.8 <= r <= 1.05 for r in rs)), "within_20pct": pct(sum(abs(r - 1) <= 0.2 for r in rs)),
            "over_1.1": pct(sum(r > 1.1 for r in rs)), "under_0.65": pct(sum(0 < r < 0.65 or r == 0 for r in rs))}


def cmd_report(a):
    from wt_multiround import Voice
    v = Voice(a.voice, a.cache)
    frames = json.loads(a.frames.read_text(encoding="utf-8"))
    res = {}
    for spec in a.chosen:
        name, path = spec.split("=", 1)
        res[name] = metrics(json.loads(Path(path).read_text(encoding="utf-8")), frames, v)
    v.save()
    for k, m in res.items():
        print(f"{k:22s} " + "  ".join(f"{x}={y}" for x, y in m.items()))
    if a.out:
        a.out.write_text(json.dumps(res, indent=1), encoding="utf-8")


def _llm_chars(p: Path) -> int:
    """Characters of LLM text in a file: option files count only the option text (plus a little per option for its
    labels); anything else counts whole."""
    if not p.exists():
        return 0
    txt = p.read_text(encoding="utf-8")
    if p.name.startswith("opts_"):
        d = json.loads(txt)
        return sum(len(x["src"]) + 20 for segs in d.values() for vs in segs.values() for x in vs)
    return len(txt)


def cmd_tokens(a):
    """LLM tokens per route, approximated as characters / 4. Spec: name=w:file+w:file+r:file (w written, r read)."""
    res = {}
    for spec in a.spec:
        name, files = spec.split("=", 1)
        w = r = 0
        for f in files.split("+"):
            kind, path = f.split(":", 1)
            n = _llm_chars(Path(path))
            w, r = (w + n, r) if kind == "w" else (w, r + n)
        res[name] = {"written_tokens": round(w / 4), "read_tokens": round(r / 4), "total_tokens": round((w + r) / 4)}
    for k, x in res.items():
        print(f"{k:22s} {x}")
    if a.out:
        a.out.write_text(json.dumps(res, indent=1), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("plan")
    p.add_argument("--src", required=True)
    p.add_argument("--tgt", required=True)
    p.add_argument("--budget", choices=["economy", "quality"], default="economy")
    p.add_argument("--pivots", default="en")
    p = sp.add_parser("select")
    for k in ("maps", "frames", "voice", "cache", "out"):
        p.add_argument("--" + k, type=Path, required=True)
    p.add_argument("--route", choices=["E", "D", "X"], required=True)
    p.add_argument("--opts-en", type=Path, nargs="*")
    p.add_argument("--opts-tgt", type=Path, nargs="*")
    p.add_argument("--mt", type=Path)
    p.add_argument("--tgt", default="es")
    p.add_argument("--revise", type=Path)
    p.add_argument("--conserve", action="store_true")
    p.add_argument("--mt-prior", type=float, default=0.0,
                   help="pooled route: score cost per MT-route option (0.5 ≈ prefer the directly written line unless it fits clearly worse)")
    p = sp.add_parser("cascade")
    for k in ("views", "mt", "frames", "ids", "out"):
        p.add_argument("--" + k, type=Path, required=True)
    p.add_argument("--tgt", default="es")
    p = sp.add_parser("report")
    for k in ("frames", "voice", "cache"):
        p.add_argument("--" + k, type=Path, required=True)
    p.add_argument("--chosen", nargs="+", required=True, help="name=path")
    p.add_argument("--out", type=Path)
    p = sp.add_parser("tokens")
    p.add_argument("--spec", nargs="+", required=True)
    p.add_argument("--out", type=Path)
    a = ap.parse_args()
    if a.cmd == "plan":
        print(json.dumps(plan(a.src, a.tgt, a.budget, a.pivots.split(",")), indent=1, ensure_ascii=False))
        return
    {"select": cmd_select, "cascade": cmd_cascade, "report": cmd_report, "tokens": cmd_tokens}[a.cmd](a)


if __name__ == "__main__":
    main()
