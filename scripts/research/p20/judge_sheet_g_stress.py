"""P20: blind sheet for Google on the stress set. Per item and language, Google M0/M1/M2 (back-translated for
am/om/sw; Spanish shown as is) under shuffled letters. Key goes to data_untrusted.
Usage: judge_sheet_g_stress.py   (prints the sheet; writes data/sheet_g_stress.json)
Score: score_g_stress.py"""
import json, random
from pathlib import Path
D = Path(__file__).resolve().parents[3] / "docs/research/P20-nuance-transfer/data"
S = json.loads((D / "stress_set.json").read_text()); G = json.loads((D / "google_stress_outputs.json").read_text())
rnd = random.Random(2077); sheet, key = [], {}
for item in sorted(S, key=lambda x: int(x[1:])):
    it = S[item]
    for lang in ("es", "am", "om", "sw"):
        conds = ["M0"] if lang == "es" else ["M0", "M1", "M2"]
        rnd.shuffle(conds); cands = {}
        for L, c in zip("ABC", conds):
            o = G[f"{lang}:{c}"][item]; cands[L] = o["mt"] if lang == "es" else o["back"]; key[f"{item}:{lang}:{L}"] = c
        sheet.append({"item": item, "lang": lang, "src": it["text"], "func": it["gold"][3], "cands": cands})
(D / "sheet_g_stress.json").write_text(json.dumps(sheet, indent=1, ensure_ascii=False))
Path("/home/user/data_untrusted/keys_g_stress.key.json").write_text(json.dumps(key))
for s in sheet:
    print(f"## {s['item']} {s['lang']}  SRC: {s['src'][:150]}\n   FUNC: {s['func']}")
    for L, t in s["cands"].items(): print(f"   {L}: {t[:220]}")
