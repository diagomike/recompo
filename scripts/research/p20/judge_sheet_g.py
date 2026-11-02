"""P20 follow-up: blind sheets for the Google outputs.
  mt <lang>  Google M0/M1/M2 back-translations (same protocol as judge_sheet.py mt)
  es         raw Spanish: NLLB vs Google vs Claude line-alone (S0), shuffled
Keys go to /home/user/data_untrusted/keys_g_<tag>.key.json."""
import json, random, sys
from pathlib import Path
D = Path(__file__).resolve().parents[3] / "docs/research/P20-nuance-transfer/data"
gold = json.loads((D / "gold_items.json").read_text())
scenes = json.loads((D / "scenes_R.json").read_text())
src = {l["id"]: f'{l["speaker"]}: {l["text"]}' for s in scenes for l in s["lines"]}
order = [l["id"] for s in scenes for l in s["lines"]]
G = json.loads((D / "google_outputs.json").read_text())
mode = sys.argv[1]
if mode == "mt":
    lang = sys.argv[2]; tag = f"g_mt_{lang}"; conds = ["M0", "M1", "M2"]
    cand = lambda c, line: G[f"{lang}:{c}"][line]["back"]  # noqa: E731
    lines_ok = G[f"{lang}:M0"]
else:
    tag = "g_es"; conds = ["NLLB", "GOOGLE", "S0"]
    N = json.loads((D / "mt_outputs.json").read_text())["es:M0"]; S = json.loads((D / "es_selected.json").read_text())
    cand = lambda c, line: {"NLLB": N[line]["mt"], "GOOGLE": G["es:M0"][line]["mt"], "S0": S[line]["S0"]}[c]  # noqa: E731
    lines_ok = S
rng = random.Random(31 + len(tag)); sheet, key = [], {}
for g in gold:
    i = order.index(g["line"]); deps = [d for d in g["deps"] if d != g["line"]]
    cs = conds[:]; rng.shuffle(cs); letters = {}
    for L, c in zip("ABC", cs):
        letters[L] = {"line": cand(c, g["line"]), "deps": {d: cand(c, d) for d in deps if d in lines_ok}}
        key[f'{g["id"]}:{L}'] = c
    sheet.append({"id": g["id"], "context": [src[x] for x in order[max(0, i - 2):i] if x.split("-")[0] == g["line"].split("-")[0]],
                  "source": src[g["line"]], "trigger": g["trigger"], "function": g["func"], "candidates": letters})
(D / f"sheet_{tag}.json").write_text(json.dumps(sheet, indent=1, ensure_ascii=False))
Path(f"/home/user/data_untrusted/keys_{tag}.key.json").write_text(json.dumps(key))
for it in sheet:
    print(f"## {it['id']}  SRC: {it['source'][-120:]}\n   FUNC: {it['function']}")
    for L, c in it["candidates"].items():
        print(f"   {L}: {c['line'][:230]}" + (" || deps: " + " / ".join(v[:80] for v in c["deps"].values()) if c["deps"] else ""))
