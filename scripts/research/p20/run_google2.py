"""P20 follow-up, in two resumable stages (the one-shot run_google.py was killed mid-run in the cloud box):
  fw   Google forward translations for every language x condition (batched, few requests), saved per block
  back independent back-translation per block (MADLAD-400 for am/sw, NLLB-200 for om), saved per block
Usage: run_google2.py fw|back [max_blocks]"""
import json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(Path(__file__).parent))
D = ROOT / "docs/research/P20-nuance-transfer/data"
BACK = {"am": "madlad", "sw": "madlad", "om": "nllb"}
SETS = [(D / "mt_inputs_en.json", {"M0": "M0", "M1": "M1", "M2": "M2"}, D / "google_outputs.json"),
        (D / "stress_set.json", {"M0": "text", "M1": "M1", "M2": "M2"}, D / "google_stress_outputs.json")]
stage, budget = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 99
for inp_p, fields, outp in SETS:
    inp = json.loads(inp_p.read_text()); keys = sorted(inp)
    out = json.loads(outp.read_text()) if outp.exists() else {}
    for lang in ("es", "am", "om", "sw"):
        for cond, field in fields.items():
            tag = f"{lang}:{cond}"
            if lang == "es" and cond != "M0":
                continue
            if stage == "fw" and tag not in out and budget > 0:
                from recomp.lang.google import Translator
                tr = Translator("en", lang, context=0, pause_s=2.0)
                got = tr.translate([{"id": i, "text": inp[k][field]} for i, k in enumerate(keys)])
                out[tag] = {k: {"mt": got.get(i, ""), "back": "" if lang == "es" else None} for i, k in enumerate(keys)}
                budget -= 1; print(outp.name, tag, "fw", tr.calls, "calls", flush=True)
            elif stage == "back" and tag in out and lang != "es" and any(v["back"] is None for v in out[tag].values()) and budget > 0:
                import mt
                src = [out[tag][k]["mt"] for k in keys]
                bk = []
                for i in range(0, len(src), 8):  # small batches: a 3B model with beam 4 on CPU
                    bk += mt.translate(src[i:i + 8], lang, "en", BACK[lang])
                for k, b in zip(keys, bk): out[tag][k]["back"] = b
                budget -= 1; print(outp.name, tag, "back", flush=True)
            outp.write_text(json.dumps(out, indent=1, ensure_ascii=False))
print("stage done")
