"""P20: un-blind judged sheets with the key and aggregate: mean meaning, mean effect, effect-kept rate (effect >= 2),
broken by item group (all / humorous / laugh points / L / C / U / P / with dependencies).
Usage: score_judged.py <tag e.g. mt_am|es> [key path]"""
import json, sys, statistics as st
from pathlib import Path
D = Path(__file__).resolve().parents[3] / "docs/research/P20-nuance-transfer/data"
tag = sys.argv[1]
key = json.loads(Path(sys.argv[2] if len(sys.argv) > 2 else f"/home/user/data_untrusted/keys_{tag}.key.json").read_text())
J = json.loads((D / f"judged_{tag}.json").read_text())
gold = {g["id"]: g for g in json.loads((D / "gold_items.json").read_text())}
rows = []
for item, cands in J.items():
    g = gold[item]
    for L, sc in cands.items():
        rows.append({"item": item, "cond": key[f"{item}:{L}"], "meaning": sc[0], "effect": sc[1], "humor": g["humor"], "punch": g["punch"],
                     "bound": g["bound"], "deps": bool([d for d in g["deps"] if d != g["line"]]), **({"natural": sc[2]} if len(sc) > 2 else {})})
groups = {"all": lambda r: True, "humor": lambda r: r["humor"], "laugh": lambda r: r["punch"], "L": lambda r: r["bound"] == "L",
          "C": lambda r: r["bound"] == "C", "U": lambda r: r["bound"] == "U", "P": lambda r: r["bound"] == "P", "deps": lambda r: r["deps"]}
conds = sorted({r["cond"] for r in rows})
res = {}
for gname, f in groups.items():
    for c in conds:
        xs = [r for r in rows if r["cond"] == c and f(r)]
        if not xs: continue
        res.setdefault(gname, {})[c] = {"n": len(xs), "meaning": round(st.mean(r["meaning"] for r in xs), 2), "effect": round(st.mean(r["effect"] for r in xs), 2),
                                        "effect_kept": round(sum(r["effect"] >= 2 for r in xs) / len(xs), 2),
                                        **({"natural": round(st.mean(r["natural"] for r in xs), 2)} if "natural" in xs[0] else {})}
(D / f"scores_{tag}.json").write_text(json.dumps(res, indent=1))
for gname, d in res.items():
    print(f"{gname:6s} " + "  ".join(f"{c}: m{v['meaning']:.2f} e{v['effect']:.2f} kept{100*v['effect_kept']:.0f}%" + (f" nat{100*v['natural']:.0f}%" if 'natural' in v else "") + f" (n{v['n']})" for c, v in d.items()))
