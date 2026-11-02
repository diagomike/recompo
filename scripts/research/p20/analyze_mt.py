"""P20 N5 automatic measures on the MT arm:
- length: estimated target duration / source duration (recompo timing.py syllables + rates; am/om/sw use the
  cross-language mean rate, as recompo does until calibrated)
- literalism: for idiom/slang items whose English input still contains the idiom, does the back-translation keep
  the literal image word (e.g. 'card', 'tunnel', 'lucky') where the target has no such idiom?  (heuristic list)
"""
import json, sys, statistics as st
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "p19"))
from timing import syllables, rate
D = Path(__file__).resolve().parents[3] / "docs/research/P20-nuance-transfer/data"
mt = json.loads((D / "mt_outputs.json").read_text())
src = {l["id"]: l["text"] for s in json.loads((D / "scenes_R.json").read_text()) for l in s["lines"]}
res = {}
for tag, rows in mt.items():
    lang = tag.split(":")[0]
    rs = [(syllables(v["mt"]) / rate(lang)) / (syllables(src[k]) / rate("en")) for k, v in rows.items()]
    res[tag] = {"median_ratio": round(st.median(rs), 2), "over_1.1": round(sum(r > 1.1 for r in rs) / len(rs), 2),
                "in_band": round(sum(0.8 <= r <= 1.05 for r in rs) / len(rs), 2)}
(D / "mt_length.json").write_text(json.dumps(res, indent=1))
for k, v in sorted(res.items()): print(k, v)
