"""P20 N3: does the existing understanding carry each gold nuance item?

Layer A = storylens P1 fact ledger (joke/quote facts, beats). Layer B = recompo `dub understand` map (best + units;
the dub writer sees only these, not the source line). Automatic checks per item:
  flagged  A: a joke/quote fact overlaps the line;  B: notes non-empty for the line
  trigger  the item's trigger words survive (>= 70 % of content tokens) in A fact value/text  |  B best/units
  flatten  B: trigger lost from best+units  -> the writer can no longer see the wording the nuance lives in
Manual judgements (mechanism, dependency) are in data/audit_manual.json and merged here.
"""
import json, re, sys
from pathlib import Path
D = Path(sys.argv[1] if len(sys.argv) > 1 else "docs/research/P20-nuance-transfer/data")
gold = json.loads((D / "gold_items.json").read_text())
A = json.loads((D / "baseline_A_storylens_p1.json").read_text())
B = json.loads((D / "baseline_B_recompo_maps.json").read_text())
STOP = set("a an the to of and or is it i you he she we they that this my your his her be so on in for with at no not".split())
def toks(s): return [w for w in re.findall(r"[a-z0-9']+", s.lower().replace("’", "'")) if w not in STOP]
def kept(trigger, text):
    t = set(toks(trigger)); return bool(t) and len(t & set(toks(text))) / len(t) >= 0.7
rows = []
for it in gold:
    sc, ln = it["line"].split("-L"); n = int(ln)
    fa = [f for f in A[sc]["facts"] if f["lines"][0] <= n <= f["lines"][1]]
    m = B[it["line"]]
    btxt = m["best"] + " | " + " | ".join(u["text"] for u in m["units"])
    tt = set(toks(it["trigger"]))
    carriers = [u["tier"] for u in m["units"] if tt & set(toks(u["text"]))]
    if not kept(it["trigger"], " ".join(u["text"] for u in m["units"])): unit_tier = "none"      # paraphrased away in the units
    elif "colour" in carriers: unit_tier = "colour"                                                # part of it is droppable colour
    else: unit_tier = "core" if "core" in carriers else "support"
    rows.append({"id": it["id"], "bound": it["bound"], "humor": it["humor"], "deps": bool(it["deps"] and it["deps"] != [it["line"]]),
                 "A_flag": any(f["kind"] in ("joke", "quote") for f in fa),
                 "A_trigger": any(kept(it["trigger"], f["value"] + " " + f["text"]) for f in fa),
                 "B_flag": bool(m["notes"]), "B_trigger": kept(it["trigger"], btxt), "B_unit_tier": unit_tier,
                 "B_flattened": unit_tier in ("none", "colour"),
                 "A_facts": [f["kind"] + ": " + f["text"] for f in fa], "B": btxt + (f"  [notes: {m['notes']}]" if m["notes"] else "")})
man = json.loads((D / "audit_manual.json").read_text()) if (D / "audit_manual.json").exists() else {}
for r in rows: r.update({k: v for k, v in man.get(r["id"], {}).items() if v is not None})
(D / "audit_rows.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False))
def pct(k, sub=None):
    xs = [r for r in rows if sub is None or sub(r)]
    v = [r[k] for r in xs if k in r]
    return f"{100 * sum(map(bool, v)) / max(1, len(v)):.0f}%" if v else "-"
print(f"{len(rows)} items")
for name, sub in (("all", None), ("humor", lambda r: r["humor"]), ("L-bound", lambda r: r["bound"] == "L"), ("C-bound", lambda r: r["bound"] == "C"),
                  ("U", lambda r: r["bound"] == "U"), ("with deps", lambda r: r["deps"])):
    print(f"{name:10s} A flag {pct('A_flag', sub):>4} trig {pct('A_trigger', sub):>4} mech {pct('A_mech', sub):>4} dep {pct('A_dep', sub):>4} | "
          f"B flag {pct('B_flag', sub):>4} trig {pct('B_trigger', sub):>4} mech {pct('B_mech', sub):>4} dep {pct('B_dep', sub):>4} flat(auto) {pct('B_flattened', sub):>4} flat(manual) {pct('B_flat_genuine', sub):>4}")

from collections import Counter
print("B unit tier carrying the trigger:", dict(Counter(r["B_unit_tier"] for r in rows)))
print("  humorous items:", dict(Counter(r["B_unit_tier"] for r in rows if r["humor"])))
