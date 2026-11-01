"""Score two-sided dub conditions: timing with the target voice, meaning from target-side verifications.

    python eval_twosided.py --maps M --frames F --mt mt.jsonl --verified V --wholeline WV --voice VOICE --cache C \
        --ruler R --cond NAME=chosen.json ... --out scores.json
"""
import argparse, json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent))
import bench as B  # noqa: E402
import mctr as M  # noqa: E402
from wt_llm_loop import load_ruler, place  # noqa: E402
from wt_multiround import Voice  # noqa: E402

ap = argparse.ArgumentParser()
for k in ("maps", "frames", "mt", "verified", "wholeline", "voice", "cache", "ruler", "out"):
    ap.add_argument("--" + k, type=Path, required=True)
ap.add_argument("--cond", action="append", default=[])
a = ap.parse_args()
maps = json.loads(a.maps.read_text(encoding="utf-8"))
frames = json.loads(a.frames.read_text(encoding="utf-8"))
mt = {json.loads(l)["key"]: json.loads(l)["text"] for l in a.mt.read_text(encoding="utf-8").splitlines() if l.strip()}
ver = json.loads(a.verified.read_text(encoding="utf-8"))
whole = json.loads(a.wholeline.read_text(encoding="utf-8"))
v = Voice(a.voice, a.cache)
ruler, _ = load_ruler(a.ruler)
conds = {}
ids = list(whole)
conds["MT whole line + placement"] = {i: {"phrases": place(mt[frames[i]["de"].replace(" [pause]", "").strip()].split(),
                                                           [s["dur"] for s in frames[i]["segments"]], ruler),
                                          "meaning": whole[i]} for i in ids}
for spec in a.cond:
    name, path = spec.split("=", 1)
    ch = json.loads(Path(path).read_text(encoding="utf-8"))
    out = {}
    for i in ids:
        cov, errs = set(), 0
        for s in ch[i]["sources"]:
            x = ver.get(f"{i}|{s['src'].strip()}")
            if x:
                cov |= set(x["covered"])
                errs += len(x["errors"])
        out[i] = {"phrases": ch[i]["phrases"], "meaning": {"covered": sorted(cov), "errors": ["e"] * errs}}
    conds[name] = out
res = {}
for name, out in conds.items():
    ov, ratios = [], []
    wsum = wcov = cn = ck = errs = lines_ok = 0
    for i in ids:
        item = {"id": i, "segments": frames[i]["segments"]}
        ov.append(B.score_item(item, out[i]["phrases"], v)["speech_overlap"])
        for s, t in zip(frames[i]["segments"], out[i]["phrases"]):
            if t.strip():
                ratios.append(v(t) / s["dur"])
        cov = set(out[i]["meaning"]["covered"])
        core_ok = True
        for u in maps[i]["units"]:
            w = M.TIER_W[u["tier"]]
            wsum += w
            wcov += w * (u["id"] in cov)
            if u["tier"] == "core":
                cn += 1
                ck += u["id"] in cov
                core_ok &= u["id"] in cov
        e = len(out[i]["meaning"]["errors"])
        errs += e
        lines_ok += core_ok and e == 0
    r = np.array(ratios)
    res[name] = {"voice_overlap": round(float(np.mean(ov)), 3), "in_band_0.8_1.05": round(float(((r >= .8) & (r <= 1.05)).mean()), 3),
                 "within_20pct": round(float((np.abs(r - 1) <= .2).mean()), 3), "over_1.1": round(float((r > 1.1).mean()), 3),
                 "meaning_weighted": round(wcov / wsum, 3), "core_kept": round(ck / cn, 3), "mt_errors_per_line": round(errs / len(ids), 2),
                 "lines_clean_and_complete": round(lines_ok / len(ids), 3)}
v.save()
a.out.write_text(json.dumps(res, indent=1), encoding="utf-8")
for k, x in res.items():
    print(f"{k:38s} " + "  ".join(f"{a}={b}" for a, b in x.items()))
