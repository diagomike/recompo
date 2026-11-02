"""P20: blind judging sheets. For each gold item: English context, the item's function (rubric), and the candidates
shuffled under letters A.. with each candidate's own rendering of the item's dependency lines. The key (letter ->
condition) is written to a separate file. Usage: judge_sheet.py es | mt"""
import json, random, sys
from pathlib import Path
D = Path(__file__).resolve().parents[3] / "docs/research/P20-nuance-transfer/data"
gold = json.loads((D / "gold_items.json").read_text())
scenes = json.loads((D / "scenes_R.json").read_text())
src = {l["id"]: f'{l["speaker"]}: {l["text"]}' for s in scenes for l in s["lines"]}
order = [l["id"] for s in scenes for l in s["lines"]]
mode = sys.argv[1]
if mode == "es":
    sel = json.loads((D / "es_selected.json").read_text())
    mtout = json.loads((D / "mt_outputs.json").read_text()) if (D / "mt_outputs.json").exists() else {}
    def cand(cond, line):
        if cond == "MTes": return mtout["es:M0"][line]["mt"]
        return sel[line][cond]
    conds = ["S0", "S1", "S2"] + (["MTes"] if "es:M0" in mtout else [])
else:
    mtout = json.loads((D / "mt_outputs.json").read_text())
    lang = sys.argv[2]
    def cand(cond, line): return mtout[f"{lang}:{cond}"][line]["back"]
    conds = ["M0", "M1", "M2"]
rng = random.Random(11 if mode == "es" else 12 + len(sys.argv[-1]))
sheet, key = [], {}
for g in gold:
    i = order.index(g["line"])
    ctx = [src[x] for x in order[max(0, i - 2):i] if x.split("-")[0] == g["line"].split("-")[0]]
    deps = [d for d in g["deps"] if d != g["line"]]
    cs = conds[:]; rng.shuffle(cs)
    letters = {}
    for L, c in zip("ABCD", cs):
        letters[L] = {"line": cand(c, g["line"]), "deps": {d: cand(c, d) for d in deps if d in (sel if mode == "es" else mtout[f"{lang}:M0"])}}
        key[f'{g["id"]}:{L}'] = c
    sheet.append({"id": g["id"], "context": ctx, "source": src[g["line"]], "trigger": g["trigger"], "function": g["func"],
                  "deps_source": {d: src[d] for d in deps}, "candidates": letters})
tag = mode if mode == "es" else f"mt_{sys.argv[2]}"
(D / f"sheet_{tag}.json").write_text(json.dumps(sheet, indent=1, ensure_ascii=False))
Path(sys.argv[-1] if sys.argv[-1].endswith(".key.json") else f"/home/user/data_untrusted/keys_{tag}.key.json").write_text(json.dumps(key))
print(len(sheet), "items,", len(conds), "candidates each")
