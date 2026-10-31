"""MCTR: meaning-conserving, top-down timed rephrasing for dubbing (P19 worktree `mctr`).

A line is rephrased to fit a speaker's speech segments in rounds, *top-down*: first what it means, then which parts
of the meaning each segment can carry in its time, then words.

  1. UNDERSTAND (LLM, once per line) → a meaning map: gist, locked terms (names, numbers, negation), and meaning
     units (MUs), each with its source words and a tier: core (must survive), support (keep if time allows),
     colour (droppable: intensifiers, hedges, discourse markers).
  2. ALLOCATE (algorithm) → each MU goes to the segment where the speaker says its source words (character
     position mapped onto the speech timeline); each segment gets a time budget and a syllable budget at the
     voice's measured rate.
  3. REALISE (LLM) → per segment 2–3 variants (tight / normal / full), each labelled with the MUs it expresses.
  4. MEASURE + SELECT (algorithm, exact) → every variant is spoken by the dub voice and timed; the combination of
     one variant per segment that keeps every core MU and maximises
         Σ weight(covered MUs) − α·Σ fit_penalty(voice/segment) − β·duplicates
     is found by enumeration (≤ 4^k combinations for k ≤ 4 segments; exact).
  5. ROUNDS → segments whose chosen variant is still outside the band get a revision request with the exact units
     to keep or drop and the syllables to gain or lose; stop when everything is in band or nothing improves.
  6. VERIFY (LLM-judge, optional) → for the final text, which MUs are expressed, what was added, any polarity or
     fact error → a meaning-coverage score independent of a single reference translation.

The LLM steps are prompts with JSON outputs (templates in `PROMPTS`); `FileBackend` writes a request and reads the
response (an agent such as Claude Code fills it in), and an API backend only has to implement `complete()`.

    python mctr.py plan     --maps maps.json --frames frames.json --cache voice.json [--ids ids.txt]
    python mctr.py select   --maps maps.json --frames frames.json --variants variants.json --cache voice.json \
                            --voice VOICE --out chosen.json [--revise revise.txt]
    python mctr.py score    --maps maps.json --annotations ann.json
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import timing as T  # noqa: E402

TIER_W = {"core": 3.0, "support": 2.0, "colour": 1.0}
BAND = (0.8, 1.05)
ALPHA, BETA = 4.0, 1.0
GAMMA = 0.0        # cost per piece of content a variant adds beyond the source (meaning-conserving mode: 2.0)
SOFT_FLOOR = None
ERR_COST = 3.0     # cost per verified meaning error in a variant (wrong word, polarity, garbling)  # meaning-conserving mode: under-fill down to this ratio is cheap (silence beats invention)

PROMPTS = {
    "understand": (
        "You prepare a line for dubbing. Source ({src_lang}): {source}\n"
        "Return JSON: {{gist, keep:[verbatim terms], units:[{{id, text (meaning, in {tgt_lang}), src (exact source "
        "words), tier: core|support|colour}}]}}. Units are small propositions or modifiers, in source order; core = "
        "the line is wrong without it; support = loses detail without it; colour = tone only."),
    "realise": (
        "Line meaning: {gist}. Segment {k} of {n} lasts {dur:.2f}s ≈ {syl:.0f} syllables for this voice "
        "(band {lo:.0f}–{hi:.0f}). It must carry units {must}; it may add {may}. Previous segment ends with: "
        "'{prev}'. Write 3 variants (tight, normal, full) of natural spoken {tgt_lang}; return JSON "
        "[{{text, units:[ids]}}]."),
    "revise": (
        "Segment {k} '{text}' measures {ratio:.2f}× its time. {action}. Keep units {must}. Return 2–3 variants as "
        "JSON [{{text, units}}]."),
    "verify": (
        "Source: {source}\nUnits: {units}\nDub line: {line}\nReturn JSON {{covered:[ids], added:[phrases not in the "
        "source], errors:[meaning or polarity errors]}}."),
}


@dataclass
class Unit:
    id: str
    text: str
    src: str
    tier: str
    seg: int = 0

    @property
    def w(self) -> float:
        return TIER_W.get(self.tier, 1.0)


@dataclass
class Line:
    id: str
    source: str
    gist: str
    keep: list[str]
    units: list[Unit]
    segs: list[dict] = field(default_factory=list)


class FileBackend:
    """LLM backend for agent-in-the-loop runs: requests are written to a file, responses read from another."""

    def __init__(self, folder: Path):
        self.folder = folder
        folder.mkdir(parents=True, exist_ok=True)

    def complete(self, name: str, prompt: str):
        req, resp = self.folder / f"{name}.prompt.txt", self.folder / f"{name}.json"
        req.write_text(prompt, encoding="utf-8")
        return json.loads(resp.read_text(encoding="utf-8")) if resp.exists() else None


# ---- 2. allocation ---------------------------------------------------------------------------------------------

def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", s.lower())).strip()


def allocate(line: Line) -> None:
    """Put each unit in the segment whose stretch of the speech timeline contains the middle of its source words.
    Source position is measured in characters (a fair proxy for speaking time within one line)."""
    src = _norm(line.source.replace("[pause]", " "))
    total = sum(s["dur"] for s in line.segs)
    edges, acc = [], 0.0
    for s in line.segs:
        acc += s["dur"]
        edges.append(acc / total)
    last = 0
    for u in line.units:
        frag = _norm(u.src)
        pos = src.find(frag) if frag else -1
        if pos < 0 and frag:  # fall back to its first word
            pos = src.find(frag.split()[0])
        if pos < 0:
            u.seg = last
            continue
        mid = (pos + len(frag) / 2) / max(1, len(src))
        u.seg = next((k for k, e in enumerate(edges) if mid <= e + 1e-9), len(edges) - 1)
        u.seg = max(u.seg, last)  # keep source order monotone across segments
        last = u.seg


def voice_rate(cache: dict, lang: str = "en") -> float:
    syl = sum(T.syllables(t, lang) for t in cache)
    dur = sum(cache.values())
    return syl / dur if dur else T.rate(lang)


# ---- 4. exact selection ----------------------------------------------------------------------------------------

def fit_penalty(ratio: float, lo: float = BAND[0], hi: float = BAND[1]) -> float:
    if ratio <= 0:
        return 4.0
    if lo <= ratio <= hi:
        return 0.0
    if SOFT_FLOOR and SOFT_FLOOR <= ratio < lo:
        return 0.1 + 2 * math.log(lo / ratio) ** 2  # a little silence is fine
    d = math.log(ratio / (hi if ratio > hi else lo))
    return (3.0 if ratio > hi else 1.0) * 25 * d * d + 0.25


def select(line: Line, variants: dict[int, list[dict]], dur) -> dict:
    """Exact best combination of one variant per segment (see module doc). Variants: {seg: [{text, units}]}."""
    segs = list(range(len(line.segs)))
    pools = [variants.get(k) or [{"text": "", "units": []}] for k in segs]
    core = {u.id for u in line.units if u.tier == "core"}
    wt = {u.id: u.w for u in line.units}
    best, best_any = None, None
    for combo in itertools.product(*pools):
        cov, dup, fit, adds, errs = set(), 0, 0.0, 0, 0
        ratios = []
        for k, v in zip(segs, combo):
            us = set(v.get("units", []))
            adds += len(v.get("added", []))
            errs += len(v.get("errors", []))
            dup += len(cov & us)
            cov |= us
            r = dur(v["text"]) / line.segs[k]["dur"] if v["text"].strip() else 0.0
            ratios.append(round(r, 3))
            if not v["text"].strip() and line.segs[k]["dur"] < 0.3:
                continue  # a breath-length segment may stay silent
            fit += fit_penalty(r)
        score = sum(wt.get(u, 0) for u in cov) - ALPHA * fit - BETA * dup - GAMMA * adds - ERR_COST * errs
        cand = {"score": round(score, 3), "phrases": [v["text"] for v in combo], "units": sorted(cov),
                "ratios": ratios, "missing_core": sorted(core - cov), "added": adds}
        if best_any is None or score > best_any["score"]:
            best_any = cand
        if core <= cov and (best is None or score > best["score"]):
            best = cand
    out = best or best_any
    out["kept_all_core"] = best is not None
    return out


def revision_requests(line: Line, chosen: dict, rate: float) -> list[str]:
    reqs = []
    for k, (t, r) in enumerate(zip(chosen["phrases"], chosen["ratios"])):
        s = line.segs[k]
        if (not t.strip() and s["dur"] < 0.3) or BAND[0] <= r <= BAND[1] or (SOFT_FLOOR and SOFT_FLOOR <= r < BAND[0]):
            continue
        need = (BAND[0] + BAND[1]) / 2 * s["dur"] - (r * s["dur"])
        must = [u.id for u in line.units if u.seg == k and u.tier == "core"]
        opt = [f"{u.id}({u.tier})" for u in line.units if u.seg == k and u.tier != "core"]
        action = (f"Shorten by ~{-need * rate:.0f} syllables: drop colour, then support units" if need < 0 else
                  f"Lengthen by ~{need * rate:.0f} syllables: add support/colour units first, no new content")
        reqs.append(f"{line.id}[{k + 1}] {s['dur']:.2f}s ×{r:.2f}: '{t}' → {action}; core {must}; optional {opt}")
    return reqs


# ---- loading ---------------------------------------------------------------------------------------------------

def load_lines(maps_path: Path, frames_path: Path, ids: list[str] | None = None) -> dict[str, Line]:
    maps = json.loads(maps_path.read_text(encoding="utf-8"))
    frames = json.loads(frames_path.read_text(encoding="utf-8"))
    out = {}
    for i, m in maps.items():
        if ids and i not in ids:
            continue
        ln = Line(i, frames[i].get("de") or frames[i].get("en"), m.get("gist") or m.get("best_en", ""), m.get("keep", []),
                  [Unit(u["id"], u["text"], u.get("src", ""), u["tier"]) for u in m["units"]], frames[i]["segments"])
        if all("seg" in u for u in m["units"]):  # pivot maps pin units to segments from per-segment MT views
            for un, u in zip(ln.units, m["units"]):
                un.seg = int(u["seg"]) - 1
        else:
            allocate(ln)
        out[i] = ln
    return out


def _voice(args):
    from wt_multiround import Voice
    return Voice(args.voice, args.cache)


def cmd_plan(a):
    cache = json.loads(a.cache.read_text()) if a.cache.exists() else {}
    rate = voice_rate(cache)
    lines = load_lines(a.maps, a.frames, a.ids.read_text().split() if a.ids else None)
    print(f"# voice rate {rate:.2f} syl/s; band {BAND[0]}–{BAND[1]}")
    for ln in lines.values():
        print(f"{ln.id} | {ln.source.replace(' [pause]', '')}\n  gist: {ln.gist}  keep: {ln.keep}")
        for k, s in enumerate(ln.segs):
            us = [f"{u.id}:{u.tier}:{u.text}" for u in ln.units if u.seg == k]
            print(f"  [{k + 1}] {s['dur']:.2f}s ≈ {s['dur'] * rate:.0f} syl ({s['dur'] * rate * BAND[0]:.0f}–"
                  f"{s['dur'] * rate * BAND[1]:.0f}) ← {'; '.join(us) or '(no units)'}")


def cmd_select(a):
    global GAMMA, SOFT_FLOOR
    if a.conserve:
        GAMMA, SOFT_FLOOR = 2.0, 0.65
    v = _voice(a)
    cache = v.cache
    rate = voice_rate(cache) if cache else 3.8
    lines = load_lines(a.maps, a.frames)
    variants = json.loads(a.variants.read_text(encoding="utf-8"))
    out, reqs = {}, []
    for i, ln in lines.items():
        vv = {int(k) - 1: x for k, x in variants.get(i, {}).items()}
        if not vv:
            continue
        ch = select(ln, vv, v)
        out[i] = ch
        reqs += revision_requests(ln, ch, rate)
    v.save()
    a.out.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    n = sum(len(c["ratios"]) for c in out.values())
    inb = sum(1 for c in out.values() for r in c["ratios"] if BAND[0] <= r <= BAND[1])
    soft = sum(1 for c in out.values() for r in c["ratios"] if SOFT_FLOOR and SOFT_FLOOR <= r < BAND[0])
    over = sum(1 for c in out.values() for r in c["ratios"] if r > 1.1)
    print(f"lines {len(out)}  segments in band {inb}/{n}  soft under-fill {soft}  over 1.1× {over}  "
          f"core kept {sum(c['kept_all_core'] for c in out.values())}/{len(out)}  additions {sum(c['added'] for c in out.values())}")
    if a.revise:
        a.revise.write_text("\n".join(reqs) + "\n", encoding="utf-8")
        print(f"{len(reqs)} revision requests → {a.revise}")


def cmd_score(a):
    """Meaning coverage from verification annotations {cond: {id: {covered, added, errors}}}."""
    maps = json.loads(a.maps.read_text(encoding="utf-8"))
    ann = json.loads(a.annotations.read_text(encoding="utf-8"))
    res = {}
    for cond, items in ann.items():
        wsum = wcov = core_n = core_k = added = errors = 0
        for i, x in items.items():
            units = maps[i]["units"]
            cov = set(x.get("covered", []))
            for u in units:
                w = TIER_W[u["tier"]]
                wsum += w
                wcov += w * (u["id"] in cov)
                if u["tier"] == "core":
                    core_n += 1
                    core_k += u["id"] in cov
            added += len(x.get("added", []))
            errors += len(x.get("errors", []))
        res[cond] = {"lines": len(items), "weighted_coverage": round(wcov / wsum, 3),
                     "core_kept": round(core_k / core_n, 3), "additions_per_line": round(added / len(items), 2),
                     "errors_per_line": round(errors / len(items), 2)}
    print(json.dumps(res, indent=1))
    if a.out:
        a.out.write_text(json.dumps(res, indent=1), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("plan")
    p.add_argument("--maps", type=Path, required=True)
    p.add_argument("--frames", type=Path, required=True)
    p.add_argument("--cache", type=Path, required=True)
    p.add_argument("--ids", type=Path)
    p = sp.add_parser("select")
    for k in ("maps", "frames", "variants", "cache", "voice", "out"):
        p.add_argument("--" + k, type=Path, required=True)
    p.add_argument("--revise", type=Path)
    p.add_argument("--conserve", action="store_true",
                   help="Meaning-conserving mode: added content costs 2.0 each; under-fill to 0.65× is cheap")
    p = sp.add_parser("score")
    p.add_argument("--maps", type=Path, required=True)
    p.add_argument("--annotations", type=Path, required=True)
    p.add_argument("--out", type=Path)
    a = ap.parse_args()
    {"plan": cmd_plan, "select": cmd_select, "score": cmd_score}[a.cmd](a)


if __name__ == "__main__":
    main()
