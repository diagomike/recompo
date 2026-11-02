"""P20 N4: timing of the Spanish conditions and recompo-style option selection.
Duration estimate = syllables / typical rate (recompo timing.py: en 6.19, es 7.82 syl/s). Ratio = target/source.
Selection mirrors `dub fit`: prefer the fullest option inside the band 0.8-1.05; else the option closest to the band
(running long costs 3x). [bracketed] prosody cues are stripped from the spoken text and kept as cues."""
import json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "p19"))
from timing import syllables, rate
D = Path(__file__).resolve().parents[3] / "docs/research/P20-nuance-transfer/data"
es = json.loads((D / "es_outputs.json").read_text())
src = {l["id"]: l["text"] for s in json.loads((D / "scenes_R.json").read_text()) for l in s["lines"]}
def spoken(t): return re.sub(r"\s*\[[^\]]*\]", "", t or "").strip()
def ratio(t, k): return (syllables(spoken(t)) / rate("es")) / (syllables(src[k]) / rate("en"))
def cost(r): return 0 if 0.8 <= r <= 1.05 else (3 if r > 1.05 else 1) * abs(r - (1.05 if r > 1.05 else 0.8))
def pick(opts, k):
    opts = [o for o in opts if o]
    return min(opts, key=lambda o: (cost(ratio(o, k)), -len(o)))
sel = {}
for k, v in es.items():
    sel[k] = {"S0": spoken(v["S0"]), "S1": spoken(pick([v["S1f"], v["S1c"]], k)), "S1_compact_chosen": bool(v["S1c"]) and pick([v["S1f"], v["S1c"]], k) == v["S1c"],
              "S2": spoken(pick([v["S2"], v["S2t"]], k)), "S2_cue": "; ".join(re.findall(r"\[([^\]]*)\]", v["S2"] or "")),
              "ratio": {c: round(ratio(t, k), 2) for c, t in (("S0", v["S0"]), ("S1", pick([v["S1f"], v["S1c"]], k)), ("S2", pick([v["S2"], v["S2t"]], k)))}}
(D / "es_selected.json").write_text(json.dumps(sel, indent=1, ensure_ascii=False))
import statistics as st
for c in ("S0", "S1", "S2"):
    rs = [s["ratio"][c] for s in sel.values()]
    print(c, "median ratio", round(st.median(rs), 2), "in band", f"{100 * sum(0.8 <= r <= 1.05 for r in rs) / len(rs):.0f}%",
          "over 1.1", f"{100 * sum(r > 1.1 for r in rs) / len(rs):.0f}%")
print("S1 compact chosen:", sum(s["S1_compact_chosen"] for s in sel.values()), "lines")
