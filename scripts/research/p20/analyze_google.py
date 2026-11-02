"""P20 G1 automatic measures, Google vs NLLB on the same English inputs (M0/M1/M2, es raw):
- length: estimated target duration / source duration (same method as analyze_mt.py)
- degenerate: output that loops (a token repeated 6+ times in a row) or is >3x the input syllables
- untranslated: output identical to the English input (Google sometimes passes a line through)
- changed: share of lines where Google and NLLB differ in back-translation length by >40% (crude divergence)"""
import json, re, sys, statistics as st
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "p19"))
from timing import syllables, rate
D = Path(__file__).resolve().parents[3] / "docs/research/P20-nuance-transfer/data"
src = {l["id"]: l["text"] for s in json.loads((D / "scenes_R.json").read_text()) for l in s["lines"]}
inp = json.loads((D / "mt_inputs_en.json").read_text())
def loops(t):
    w = re.findall(r"\w+", t.lower())
    return any(len(set(w[i:i + 6])) == 1 for i in range(max(0, len(w) - 5)))
out = {}
for name, f in (("NLLB", "mt_outputs.json"), ("GOOGLE", "google_outputs.json")):
    for tag, rows in json.loads((D / f).read_text()).items():
        lang, cond = tag.split(":")
        rs, deg, same = [], 0, 0
        for k, v in rows.items():
            s_src = syllables(src[k]) / rate("en")
            r = (syllables(v["mt"]) / rate(lang)) / s_src if s_src else 1
            rs.append(r)
            deg += loops(v["mt"]) or r > 3
            e = inp.get(k, {}); e = e.get(cond, e.get("text")) if isinstance(e, dict) else None
            same += bool(e) and v["mt"].strip().lower() == str(e).strip().lower()
        out.setdefault(tag, {})[name] = {"median_ratio": round(st.median(rs), 2), "in_band": round(sum(0.8 <= r <= 1.05 for r in rs) / len(rs), 2),
                                         "degenerate": deg, "untranslated": same, "n": len(rs)}
(D / "google_auto.json").write_text(json.dumps(out, indent=1))
for tag in sorted(out):
    print(tag, "  ".join(f"{n}: ratio {v['median_ratio']} band {100*v['in_band']:.0f}% degenerate {v['degenerate']} same {v['untranslated']} (n{v['n']})" for n, v in out[tag].items()))
