"""P20: MT arm for the stress set (proverbs, idioms, running jokes). Same systems as run_mt.py."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent)); import mt
D = Path(__file__).resolve().parents[3] / "docs/research/P20-nuance-transfer/data"
S = json.loads((D / "stress_set.json").read_text()); keys = sorted(S)
out = {}
for lang in ("am", "om", "sw", "es"):
    for cond, field in (("M0", "text"), ("M1", "M1"), ("M2", "M2")):
        if lang == "es" and cond != "M0": continue
        fw = mt.translate([S[k][field] for k in keys], "en", lang, "nllb")
        bk = mt.translate(fw, lang, "en", "madlad") if lang != "es" else [""] * len(fw)
        out[f"{lang}:{cond}"] = {k: {"mt": f, "back": b} for k, f, b in zip(keys, fw, bk)}
        print(lang, cond, flush=True)
(D / "stress_mt_outputs.json").write_text(json.dumps(out, indent=1, ensure_ascii=False)); print("stress done")
