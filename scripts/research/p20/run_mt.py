"""P20 N5: forward MT (NLLB 1.3B) of M0/M1/M2 English inputs into am/om/sw (+ raw es), back-translation with
MADLAD-400 3B (an independent model family). Writes data/mt_outputs.json; resumable."""
import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent)); import mt
D = Path(__file__).resolve().parents[3] / "docs/research/P20-nuance-transfer/data"
inp = json.loads((D / "mt_inputs_en.json").read_text())
outp = D / "mt_outputs.json"
out = json.loads(outp.read_text()) if outp.exists() else {}
keys = sorted(inp)
jobs = [(l, c) for l in ("am", "om", "sw") for c in ("M0", "M1", "M2")] + [("es", "M0")]
for lang, cond in jobs:
    tag = f"{lang}:{cond}"
    if tag in out and len(out[tag]) == len(keys) and all("back" in v for v in out[tag].values()): continue
    t = time.time()
    fw = mt.translate([inp[k][cond] for k in keys], "en", lang, "nllb")
    res = {k: {"mt": f} for k, f in zip(keys, fw)}
    if lang != "es":
        bk = []
        for i in range(0, len(fw), 8): bk += mt.translate(fw[i:i + 8], lang, "en", "madlad")
        for k, b in zip(keys, bk): res[k]["back"] = b
    else:
        for k in keys: res[k]["back"] = ""
    out[tag] = res; outp.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(tag, f"{time.time() - t:.0f}s", flush=True)
print("done")
