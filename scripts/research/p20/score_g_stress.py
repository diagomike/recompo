"""P20: un-blind the Google stress-set judgements and print them next to the NLLB stress scores (scores_stress.json)."""
import json, statistics as st
from pathlib import Path
D = Path(__file__).resolve().parents[3] / "docs/research/P20-nuance-transfer/data"
J = json.loads((D / "judged_g_stress.json").read_text())
key = json.loads(Path("/home/user/data_untrusted/keys_g_stress.key.json").read_text())
old = json.loads((D / "scores_stress.json").read_text())
rows = {}
for il, cands in J.items():
    item, lang = il.split(":")
    for L, (m, e) in cands.items():
        rows.setdefault(f"{lang}:{key[f'{item}:{lang}:{L}']}", []).append((m, e))
res = {k: {"meaning": round(st.mean(m for m, _ in v), 2), "effect": round(st.mean(e for _, e in v), 2),
           "effect_kept": round(sum(e >= 2 for _, e in v) / len(v), 2), "n": len(v)} for k, v in sorted(rows.items())}
(D / "scores_g_stress.json").write_text(json.dumps(res, indent=1))
for k, v in res.items():
    nl = old.get(k if not k.startswith("es:") else "es:MTes", {})
    print(f"{k:6s} GOOGLE kept {100*v['effect_kept']:.0f}% m{v['meaning']:.2f}   NLLB kept {100*nl.get('effect_kept',0):.0f}% m{nl.get('meaning',0):.2f}")
