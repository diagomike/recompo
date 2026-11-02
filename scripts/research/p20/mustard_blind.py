"""P20 external check: sarcasm detection by the proposed nuance pass on MUStARD (Friends), labels hidden.
make: writes a blind sheet (context + utterance, no labels) and a separate key file.
score: compares data/mustard_answers.json against the key."""
import json, random, sys
from pathlib import Path
D = Path(__file__).resolve().parents[3] / "docs/research/P20-nuance-transfer/data"
if sys.argv[1] == "make":
    d = json.loads(Path(sys.argv[2]).read_text())
    fr = sorted(k for k, v in d.items() if v["show"] == "FRIENDS")
    pick = random.Random(7).sample(fr, 60)
    sheet = [{"id": k, "context": [f"{s}: {u}" for s, u in zip(d[k]["context_speakers"], d[k]["context"])], "utterance": f"{d[k]['speaker']}: {d[k]['utterance']}"} for k in pick]
    (D / "mustard_blind_sheet.json").write_text(json.dumps(sheet, indent=1, ensure_ascii=False))
    Path(sys.argv[3]).write_text(json.dumps({k: d[k]["sarcasm"] for k in pick}))
    print(len(sheet), "items written; key kept outside the sheet")
else:
    key = json.loads(Path(sys.argv[2]).read_text()); ans = json.loads((D / "mustard_answers.json").read_text())
    tp = sum(ans[k]["sarcastic"] and key[k] for k in key); fp = sum(ans[k]["sarcastic"] and not key[k] for k in key)
    fn = sum((not ans[k]["sarcastic"]) and key[k] for k in key); tn = len(key) - tp - fp - fn
    p, r = tp / max(1, tp + fp), tp / max(1, tp + fn)
    res = {"n": len(key), "positives": sum(key.values()), "tp": tp, "fp": fp, "fn": fn, "tn": tn, "accuracy": round((tp + tn) / len(key), 3),
           "precision": round(p, 3), "recall": round(r, 3), "f1": round(2 * p * r / max(1e-9, p + r), 3)}
    (D / "mustard_score.json").write_text(json.dumps(res, indent=1)); print(res)
