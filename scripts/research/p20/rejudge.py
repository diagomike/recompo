"""P20 intra-rater check: re-shuffle 20 random items of a judged sheet under new letters (key kept apart);
'score' compares the re-judgement with the first pass per (item, condition): exact effect agreement and
agreement on effect>=2."""
import json, random, sys
from pathlib import Path
D = Path(__file__).resolve().parents[3] / "docs/research/P20-nuance-transfer/data"
tag, mode = sys.argv[1], sys.argv[2]
K1 = json.loads(Path(f"/home/user/data_untrusted/keys_{tag}.key.json").read_text())
sheet = {it["id"]: it for it in json.loads((D / f"sheet_{tag}.json").read_text())}
kp = Path(f"/home/user/data_untrusted/keys_{tag}_re.key.json")
if mode == "make":
    rng = random.Random(99); ids = rng.sample(sorted(sheet), 20); out = []; key = {}
    for i in ids:
        cands = list(sheet[i]["candidates"].items()); rng.shuffle(cands)
        out.append({**sheet[i], "candidates": {L: c for L, (_, c) in zip("ABCD", cands)}})
        for L, (old, _) in zip("ABCD", cands): key[f"{i}:{L}"] = K1[f"{i}:{old}"]
    (D / f"resheet_{tag}.json").write_text(json.dumps(out, indent=1, ensure_ascii=False)); kp.write_text(json.dumps(key))
    for it in out:
        print(f"## {it['id']}  SRC: {it['source'][:160]}\n   FUNC: {it['function']}")
        for L, c in it["candidates"].items(): print(f"   {L}: {c['line'][:240]}" + (" || deps: " + " / ".join(v[:90] for v in c["deps"].values()) if c["deps"] else ""))
else:
    K2 = json.loads(kp.read_text()); J1 = json.loads((D / f"judged_{tag}.json").read_text()); J2 = json.loads((D / f"rejudged_{tag}.json").read_text())
    first = {(i, K1[f"{i}:{L}"]): v for i, c in J1.items() for L, v in c.items()}
    pairs = [(first[(i, K2[f"{i}:{L}"])][1], v[1]) for i, c in J2.items() for L, v in c.items()]
    ex = sum(a == b for a, b in pairs) / len(pairs); kept = sum((a >= 2) == (b >= 2) for a, b in pairs) / len(pairs)
    within1 = sum(abs(a - b) <= 1 for a, b in pairs) / len(pairs)
    res = {"pairs": len(pairs), "effect_exact": round(ex, 2), "effect_within_1": round(within1, 2), "kept_agreement": round(kept, 2)}
    (D / f"rejudge_{tag}.json").write_text(json.dumps(res)); print(res)
