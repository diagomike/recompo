"""Two-sided dub optimiser: rephrase on the SOURCE side (where the LLM is strong), translate with MT (the only
engine for languages like Amharic or Oromo), time the TARGET with its own voice, and choose.

Per line (source text + the speaker's speech segments):

  1. CHUNK      the source is split into one chunk per speech segment (placement DP on source syllables, breaks
                preferred at punctuation), so MT translates segment by segment and timing stays local.
  2. OPTIONS    the LLM writes, in the SOURCE language, 2–4 alternatives per chunk, each labelled with the meaning
                units it carries (MCTR maps) and a strategy:
                  orig     the chunk as spoken
                  compact  colour/support units dropped, shorter wording
                  plain    MT-friendly: standard word order, explicit subject, no idiom, short clauses
                  full     every unit explicit (for long segments)
                  steer    round 2: written to a syllable target computed from this line's measured MT expansion
  3. TRANSLATE  every option through the MT black box (no timing information given to it).
  4. MEASURE    every translation spoken by the target voice and timed (cached).
  5. SELECT     exact choice of one option per segment (mctr.select: max meaning, band 0.8–1.05, core units kept,
                optional conserve mode).
  6. STEER      for segments still out of band: expansion ratio e = voice seconds per source syllable, measured on
                this line's own options → the source syllables needed = target seconds / e → new source options.
  7. VERIFY     meaning of the chosen target (here judged in English; for Amharic/Oromo: back-translate with MT
                and judge the back-translation against the source units).

    python twosided.py chunks  --maps M --frames F --out chunks.json
    python twosided.py mtjobs  --options opts.json --done mt.jsonl --out todo.jsonl
    python twosided.py select  --maps M --frames F --options opts.json --mt mt.jsonl --voice V --cache C --out chosen.json \
                               [--revise revise.txt] [--conserve] [--only-orig] [--strategies orig,compact]
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import mctr as M  # noqa: E402
import timing as T  # noqa: E402


def split_source(words: list[str], durs: list[float], lang: str) -> list[str]:
    """DP: share the source words over the segments ∝ their durations (syllable rate match), breaks preferred after
    punctuation."""
    k, n = len(durs), len(words)
    if k == 1 or n < k:
        return [" ".join(words)] + [""] * (k - 1)
    syl = [max(0.5, T.syllables(w, lang)) for w in words]
    cum = np.concatenate([[0.0], np.cumsum(syl)])
    tot_syl, tot_d = cum[-1], sum(durs)
    INF = 1e18
    cost = np.full((k + 1, n + 1), INF)
    back = np.zeros((k + 1, n + 1), int)
    cost[0, 0] = 0
    for p in range(1, k + 1):
        for j in range(p, n - (k - p) + 1):
            bonus = 0.6 if p < k and re.search(r"[,.;:!?–]$", words[j - 1]) else 0.0
            for i in range(p - 1, j):
                if cost[p - 1, i] < INF:
                    share = (cum[j] - cum[i]) / tot_syl
                    c = cost[p - 1, i] + math.log(max(0.02, share) / (durs[p - 1] / tot_d)) ** 2 - bonus
                    if c < cost[p, j]:
                        cost[p, j], back[p, j] = c, i
    out, j = [], n
    for p in range(k, 0, -1):
        i = back[p, j]
        out.append(" ".join(words[i:j]))
        j = i
    return out[::-1]


def cmd_chunks(a):
    maps = json.loads(a.maps.read_text(encoding="utf-8"))
    frames = json.loads(a.frames.read_text(encoding="utf-8"))
    out = {}
    for i in maps:
        src = frames[i][a.field].replace("[pause]", " ")
        out[i] = split_source(src.split(), [s["dur"] for s in frames[i]["segments"]], a.lang)
    a.out.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    for i, ch in out.items():
        print(i, " | ".join(ch))


def cmd_mtjobs(a):
    opts = json.loads(a.options.read_text(encoding="utf-8"))
    done = set()
    if a.done.exists():
        done = {json.loads(l)["key"] for l in a.done.read_text(encoding="utf-8").splitlines() if l.strip()}
    with open(a.out, "w", encoding="utf-8") as f:
        n = 0
        for i, segs in opts.items():
            for k, vs in segs.items():
                for v in vs:
                    key = v["src"].strip()
                    if key and key not in done:
                        done.add(key)
                        f.write(json.dumps({"key": key, "text": key}, ensure_ascii=False) + "\n")
                        n += 1
    print(f"{n} new source chunks to translate")


def load_mt(path: Path) -> dict[str, str]:
    out = {}
    for l in path.read_text(encoding="utf-8").splitlines():
        if l.strip():
            r = json.loads(l)
            out[r["key"]] = r["text"]
    return out


def cmd_select(a):
    if a.conserve:
        M.GAMMA, M.SOFT_FLOOR = 2.0, 0.65
    from wt_multiround import Voice
    v = Voice(a.voice, a.cache)
    mt = load_mt(a.mt)
    opts = json.loads(a.options.read_text(encoding="utf-8"))
    lines = M.load_lines(a.maps, a.frames)
    keep = set(a.strategies.split(",")) if a.strategies else None
    verified = json.loads(a.verified.read_text(encoding="utf-8")) if a.verified and a.verified.exists() else {}
    rate = M.voice_rate(v.cache) if v.cache else 4.0
    out, reqs, unverified = {}, [], []
    for i, ln in lines.items():
        if i not in opts:
            continue
        variants = {}
        for k, vs in opts[i].items():
            pool = []
            for x in vs:
                if keep and x.get("strategy", "orig") not in keep:
                    continue
                tgt = mt.get(x["src"].strip(), "") if x["src"].strip() else ""
                ver = verified.get(f"{i}|{x['src'].strip()}")
                units = ver["covered"] if ver else x.get("units", [])
                pool.append({"text": tgt, "src": x["src"], "units": units, "strategy": x.get("strategy", "orig"),
                             "added": x.get("added", []), "errors": ver.get("errors", []) if ver else [],
                             "verified": bool(ver) or not x["src"].strip()})
            variants[int(k) - 1] = pool
        ch = M.select(ln, variants, v)
        ch["sources"] = []
        for k, t in enumerate(ch["phrases"]):
            x = next((x for x in variants.get(k, []) if x["text"] == t), {})
            if x and not x.get("verified"):
                unverified.append({"key": f"{i}|{x['src'].strip()}", "src": x["src"], "mt": t, "claimed": x["units"],
                                   "units": {u.id: u.text for u in ln.units if u.seg == k}})
            src = next((x["src"] for x in variants.get(k, []) if x["text"] == t), "")
            strat = next((x["strategy"] for x in variants.get(k, []) if x["text"] == t), "")
            ch["sources"].append({"src": src, "strategy": strat})
        out[i] = ch
        # steering: expansion ratio of this line = target voice seconds per source syllable, over its options
        pairs = [(v(x["text"]), T.syllables(x["src"], a.src_lang)) for vs in variants.values() for x in vs if x["text"].strip()]
        e = sum(p for p, _ in pairs) / max(1.0, sum(s for _, s in pairs))
        for k, (t, r) in enumerate(zip(ch["phrases"], ch["ratios"])):
            s = ln.segs[k]
            if (not t.strip() and s["dur"] < 0.3) or M.BAND[0] <= r <= M.BAND[1] or (M.SOFT_FLOOR and M.SOFT_FLOOR <= r < M.BAND[0]):
                continue
            need = 0.95 * s["dur"] / e if e else 0
            cur = T.syllables(ch["sources"][k]["src"], a.src_lang)
            reqs.append(f"{i}[{k + 1}] {s['dur']:.2f}s target×{r:.2f} | src '{ch['sources'][k]['src']}' ({cur:.0f} syl) → "
                        f"MT '{t}' | expansion {e:.3f}s/syl → write source of ~{need:.0f} syl; "
                        f"units here: {[u.id + ':' + u.tier for u in ln.units if u.seg == k]}")
    v.save()
    a.out.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    n = sum(len(c["ratios"]) for c in out.values())
    inb = sum(1 for c in out.values() for r in c["ratios"] if M.BAND[0] <= r <= M.BAND[1])
    over = sum(1 for c in out.values() for r in c["ratios"] if r > 1.1)
    from collections import Counter
    used = Counter(s["strategy"] for c in out.values() for s in c["sources"] if s["src"])
    print(f"lines {len(out)}  in band {inb}/{n}  over 1.1× {over}  core kept {sum(c['kept_all_core'] for c in out.values())}"
          f"/{len(out)}  strategies chosen {dict(used)}")
    if a.revise:
        a.revise.write_text("\n".join(reqs) + "\n", encoding="utf-8")
        print(f"{len(reqs)} steering requests → {a.revise}")
    if a.verify_out:
        a.verify_out.write_text(json.dumps(unverified, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{len(unverified)} chosen options need target-side verification → {a.verify_out}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("chunks")
    for k in ("maps", "frames", "out"):
        p.add_argument("--" + k, type=Path, required=True)
    p.add_argument("--field", default="de")
    p.add_argument("--lang", default="de")
    p = sp.add_parser("mtjobs")
    for k in ("options", "done", "out"):
        p.add_argument("--" + k, type=Path, required=True)
    p = sp.add_parser("select")
    for k in ("maps", "frames", "options", "mt", "voice", "cache", "out"):
        p.add_argument("--" + k, type=Path, required=True)
    p.add_argument("--revise", type=Path)
    p.add_argument("--conserve", action="store_true")
    p.add_argument("--strategies", default="")
    p.add_argument("--src-lang", default="de")
    p.add_argument("--verified", type=Path, help="{line|source chunk: {covered, errors}} from target-side checks")
    p.add_argument("--verify-out", type=Path, help="write the chosen options that still need checking")
    a = ap.parse_args()
    {"chunks": cmd_chunks, "mtjobs": cmd_mtjobs, "select": cmd_select}[a.cmd](a)


if __name__ == "__main__":
    main()
