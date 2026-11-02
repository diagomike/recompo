"""P20 follow-up: Google Translate (recompo's keyless engine, recomp/lang/google.py, batched as `lang translate --engine google`)
vs the offline NLLB-200 outputs, on the same inputs. Back-translation stays independent of Google:
MADLAD-400 for am/sw, NLLB-200 for om (MADLAD's Oromo->English is unusable, see om_diagnosis.json)."""
import json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(Path(__file__).parent))
from recomp.lang.google import Translator
import mt
D = ROOT / "docs/research/P20-nuance-transfer/data"
BACK = {"am": "madlad", "sw": "madlad", "om": "nllb"}


def google(texts, tgt):
    """recompo's batched Google mode (tagged blocks of ~4k characters, verified id by id; no context lines, so each
    line is translated on its own). Google rate-limits cloud IPs (302 to google.com/sorry): wait and retry."""
    from recomp.envelope import RecompError
    for attempt in range(12):
        try:
            tr = Translator("en", tgt, context=0, pause_s=3.0)
            got = tr.translate([{"id": i, "text": t} for i, t in enumerate(texts)])
            return [got.get(i, "") for i in range(len(texts))]
        except RecompError as e:
            print(f"  rate-limited ({e}); waiting 5 min", flush=True); time.sleep(300)
    raise SystemExit("Google kept refusing")


def run(inp: dict, fields: dict, outp: Path):
    out = json.loads(outp.read_text()) if outp.exists() else {}
    keys = sorted(inp)
    for lang in ("es", "am", "om", "sw"):
        for cond, field in fields.items():
            tag = f"{lang}:{cond}"
            if (lang == "es" and cond != "M0") or tag in out:
                continue
            fw = google([inp[k][field] for k in keys], lang)
            bk = [""] * len(fw) if lang == "es" else mt.translate(fw, lang, "en", BACK[lang])
            out[tag] = {k: {"mt": f, "back": b} for k, f, b in zip(keys, fw, bk)}
            outp.write_text(json.dumps(out, indent=1, ensure_ascii=False)); print(tag, flush=True)


run(json.loads((D / "mt_inputs_en.json").read_text()), {"M0": "M0", "M1": "M1", "M2": "M2"}, D / "google_outputs.json")
run(json.loads((D / "stress_set.json").read_text()), {"M0": "text", "M1": "M1", "M2": "M2"}, D / "google_stress_outputs.json")
print("done")
