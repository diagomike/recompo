"""P19 worktree `algorithmic`: timed rephrasing with no neural translation or LLM.

Input: any translation of the line (here Claude's plain translation R0, standing in for "any MT", and the human
CoVoST reference). Output: phrases fitted to the German speaker's speech segments. Steps:

1. **Placement**: the rate-matching DP lays the words on the segments (worktree `placement`).
2. **Length edits per segment**: a beam search over small edits from a *language pack*:
   - contractions and expansions ("do not" ↔ "don't"),
   - phrase shortcuts both ways ("in order to" ↔ "to", "were able to" ↔ "could"),
   - dropping optional words ("really", "just", "that" after verbs of saying), inserting a few fillers,
   - WordNet synonyms of content words (frequent, single-word ones).
3. **Judges**: a word trigram language model (stupid backoff, from 400 k English sentences) for fluency; edit
   costs for meaning drift; the duration ruler for fit. Cost = 10·log²(d/T) (×1.5 when long) + 0.1·ΔLM + Σ edits.
4. **Voice calibration** (optional): each segment's ruler is rescaled by the real voice's ratio on the original
   phrase; the top candidates are then synthesized and the best real fit kept (the algorithmic analogue of R3).

Only step 2's pack is English-specific. Another language needs its own contractions/shortcuts/fillers, a synonym
source (Open Multilingual WordNet, or one mined from a dub corpus) and a text corpus for the n-gram LM.

    python wt_algorithmic.py --frames frames.json --cands cands.json --lm lm.pkl --ruler ruler.json \
        --voice VOICE_DIR --wordnet NLTK_DATA --out algo.json
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import ngram_lm as NG  # noqa: E402
from wt_llm_loop import load_ruler, place  # noqa: E402

# ---- English language pack ------------------------------------------------------------------------------------
CONTRACT = [("do not", "don't"), ("does not", "doesn't"), ("did not", "didn't"), ("is not", "isn't"),
            ("are not", "aren't"), ("was not", "wasn't"), ("were not", "weren't"), ("cannot", "can't"),
            ("could not", "couldn't"), ("would not", "wouldn't"), ("should not", "shouldn't"), ("will not", "won't"),
            ("have not", "haven't"), ("has not", "hasn't"), ("had not", "hadn't"), ("i am", "i'm"), ("you are", "you're"),
            ("we are", "we're"), ("they are", "they're"), ("he is", "he's"), ("she is", "she's"), ("it is", "it's"),
            ("that is", "that's"), ("there is", "there's"), ("i have", "i've"), ("i will", "i'll"), ("i would", "i'd"),
            ("let us", "let's"), ("it will", "it'll"), ("you will", "you'll"), ("we will", "we'll"), ("i had", "i'd")]
# (long, short, reversible): expanding a bare function word ("to" → "in order to", "and" → "as well as") misfires
SHORTCUT = [("in order to", "to"), ("is able to", "can"), ("are able to", "can"), ("was able to", "could"),
            ("were able to", "could"), ("a lot of", "lots of"), ("at the moment", "now"), ("for a moment", "briefly"),
            ("a great deal", "a lot"), ("as well as", "and"), ("more or less", "roughly"), ("all of the", "all the"),
            ("in the end", "finally"), ("right away", "at once"), ("a little bit", "a bit"), ("a number of", "some"),
            ("is going to", "will"), ("are going to", "will"), ("am going to", "will"), ("going to", "gonna"),
            ("the whole", "all the"), ("each and every", "every"), ("kind of", "sort of"), ("make sure", "ensure")]
DROP = {"really": 0.25, "very": 0.25, "just": 0.25, "actually": 0.25, "quite": 0.3, "simply": 0.3, "also": 0.35,
        "truly": 0.3, "even": 0.45, "still": 0.5, "then": 0.4, "so": 0.45, "now": 0.5, "all": 0.5, "both": 0.45,
        "certainly": 0.3, "surely": 0.35, "indeed": 0.3, "eventually": 0.5, "finally": 0.5}
THAT_AFTER = {"said", "say", "says", "think", "thought", "know", "knew", "feel", "felt", "believe", "hope", "sure",
              "glad", "saying", "realized", "noticed", "found", "seems", "seemed", "is", "was"}
INSERT = {"really": 0.6, "just": 0.6, "then": 0.7}
NO_EXPAND = {"now", "some", "will", "gonna", "every", "briefly", "finally", "roughly", "lots"}
PRONOUNS = {"i", "you", "he", "she", "it", "we", "they"}
MAX_EDIT_DROP = 4.0  # nats: any single edit the trigram LM finds this much less likely is vetoed
STOP = set("a an the and or but of to in on at by for with from as is are was were be been am i you he she it we they "
           "me him her us them my your his its our their this that these those there here not no do does did have has "
           "had will would can could shall should may might must so if then than what who which when where how".split())
COST = {"contract": 0.05, "expand": 0.1, "shortcut": 0.3, "unshortcut": 0.35, "drop": None, "insert": None, "syn": 0.6}

PUNCT = re.compile(r"^([\"'“”„(\[]*)(.*?)([\"'“”)\].,;:!?–-]*)$")


def split_tok(tok: str):
    m = PUNCT.match(tok)
    return m.group(1), m.group(2), m.group(3)


class Pack:
    def __init__(self, lm: NG.LM, wordnet_dir: str | None):
        self.lm = lm
        self.wn = None
        if wordnet_dir:
            os.environ["NLTK_DATA"] = wordnet_dir
            from nltk.corpus import wordnet as wn
            wn.ensure_loaded()
            self.wn = wn
        self._syn = {}

    def synonyms(self, word: str) -> list[str]:
        w = word.lower()
        if w in self._syn:
            return self._syn[w]
        out = []
        if self.wn and w.isalpha() and w not in STOP and len(w) > 2:
            for pos in ("n", "v", "a", "r"):
                for s in self.wn.synsets(w, pos=pos)[:2]:
                    names = [l.name() for l in s.lemmas()]
                    if w not in names:
                        continue
                    for n in names:
                        n = n.lower()
                        if n != w and n.isalpha() and self.lm.freq(n) >= 50 and n not in out:
                            out.append(n)
        self._syn[w] = out[:6]
        return self._syn[w]

    def edits(self, tokens: list[str]):
        """Every single edit of a token list: (new tokens, kind, cost)."""
        low = [split_tok(t)[1].lower() for t in tokens]
        n = len(tokens)
        for src, dst, kinds in ((CONTRACT, 0, ("contract", "expand")), (SHORTCUT, 0, ("shortcut", "unshortcut"))):
            for a, b in src:
                pairs = [(a, b, kinds[0])]
                if not (kinds[1] == "unshortcut" and len(b.split()) == 1 and b in STOP | NO_EXPAND):
                    pairs.append((b, a, kinds[1]))
                for x, y, kind in pairs:
                    xs = x.split()
                    for i in range(n - len(xs) + 1):
                        if low[i:i + len(xs)] == xs:
                            nxt = low[i + len(xs)] if i + len(xs) < n else ""
                            if kind == "expand" and nxt in PRONOUNS:
                                continue  # "Don't you dare" ≠ "Do not you dare"
                            if kind == "contract" and x in ("i had", "i have") and nxt in ("the", "a", "an", "no"):
                                continue  # possession does not contract: "I had the urge" ≠ "I'd the urge"
                            pre = split_tok(tokens[i])[0]
                            post = split_tok(tokens[i + len(xs) - 1])[2]
                            ys = y.split()
                            if tokens[i][len(pre):len(pre) + 1].isupper():
                                ys[0] = ys[0].capitalize()
                            ys[0] = pre + ys[0]
                            ys[-1] = ys[-1] + post
                            yield tokens[:i] + ys + tokens[i + len(xs):], kind, COST[kind]
        for i, w in enumerate(low):
            pre, core, post = split_tok(tokens[i])
            if w in DROP and n > 1:
                new = tokens[:i] + tokens[i + 1:]
                if (pre or post) and i < len(new):  # keep attached punctuation on the neighbour
                    new[i] = pre + new[i] if pre and i < len(new) else new[i]
                yield new, "drop", DROP[w]
            if w == "that" and i > 0 and low[i - 1] in THAT_AFTER and not post:
                yield tokens[:i] + tokens[i + 1:], "drop", 0.2
            for s in self.synonyms(core):
                s2 = s.capitalize() if core[:1].isupper() else s
                yield tokens[:i] + [pre + s2 + post] + tokens[i + 1:], "syn", COST["syn"]
        # deletion-based compression: drop a span of 2–3 words (stop words and adverbs cheap, content words dear)
        for L in (2, 3):
            for i in range(n - L + 1):
                if n - L < 2:
                    break
                span = low[i:i + L]
                c = sum(0.3 if (w in STOP or w in DROP) else 0.8 for w in span)
                new = tokens[:i] + tokens[i + L:]
                post = split_tok(tokens[i + L - 1])[2]
                if post and i > 0 and not split_tok(new[i - 1])[2]:
                    new[i - 1] = new[i - 1] + post
                yield new, "drop_span", c
        if not any(w in INSERT for w in low):  # one inserted filler per phrase at most
            for i in range(1, n):
                if split_tok(tokens[i - 1])[2]:
                    continue  # not right after punctuation
                for w, c in INSERT.items():
                    yield tokens[:i] + [w] + tokens[i:], "insert", c


LAMBDA = 0.1


def fit_cost(d: float, T: float) -> float:
    r = math.log(max(0.05, d) / max(0.1, T))
    return 10 * r * r * (1.5 if r > 0 else 1.0)


def search(pack: Pack, phrases: list[str], k: int, T: float, dur, beam: int = 30, depth: int = 3):
    """Best edit of phrase k (others fixed) for target T; returns (text, cost, edits)."""
    def sentence(ph):
        return " ".join(p for p in phrases[:k] + [ph] + phrases[k + 1:] if p)
    base_lp, _ = pack.lm.score(sentence(phrases[k]))
    toks0 = phrases[k].split()

    def total(toks, ecost):
        txt = " ".join(toks)
        lp, _ = pack.lm.score(sentence(txt))
        return fit_cost(dur(txt), T) + LAMBDA * max(0.0, base_lp - lp) + ecost

    start = (total(toks0, 0.0), toks0, 0.0, [])
    frontier, best, seen = [start], start, {" ".join(toks0)}
    for _ in range(depth):
        cand = []
        for _, toks, ec, hist in frontier:
            parent_lp, _ = pack.lm.score(sentence(" ".join(toks)))
            for new, kind, c in pack.edits(toks):
                key = " ".join(new)
                if key in seen or not new:
                    continue
                seen.add(key)
                lp, _ = pack.lm.score(sentence(key))
                if parent_lp - lp > MAX_EDIT_DROP:
                    continue
                ec2 = ec + c
                cand.append((total(new, ec2), new, ec2, hist + [kind]))
        if not cand:
            break
        cand.sort(key=lambda x: x[0])
        frontier = cand[:beam]
        if frontier[0][0] < best[0]:
            best = frontier[0]
    return " ".join(best[1]), best[0], best[3], [(" ".join(t), c) for c, t, *_ in sorted(frontier)[:5]]


def main():
    ap = argparse.ArgumentParser()
    for k in ("frames", "cands", "lm", "ruler", "out"):
        ap.add_argument("--" + k, type=Path, required=True)
    ap.add_argument("--voice", type=Path)
    ap.add_argument("--wordnet", type=str)
    ap.add_argument("--inputs", default="R0", help="Comma list of condition names in --cands to rephrase (REF = reference)")
    ap.add_argument("--iwslt", type=Path)
    ap.add_argument("--lam", type=float, default=0.1, help="Weight of the language-model fluency loss (per nat)")
    ap.add_argument("--tag", default="", help="Suffix for the condition names")
    a = ap.parse_args()
    global LAMBDA
    LAMBDA = a.lam
    frames = json.loads(a.frames.read_text(encoding="utf-8"))
    cands = json.loads(a.cands.read_text(encoding="utf-8"))
    dur, _ = load_ruler(a.ruler)
    pack = Pack(NG.load(a.lm), a.wordnet)
    measured = None
    if a.voice:
        import sherpa_onnx as so
        v = a.voice
        vits = so.OfflineTtsVitsModelConfig(model=str(next(v.glob("*.onnx"))), lexicon=str(v / "lexicon.txt"),
                                            tokens=str(v / "tokens.txt"))
        tts = so.OfflineTts(so.OfflineTtsConfig(model=so.OfflineTtsModelConfig(vits=vits, num_threads=4)))
        cache = {}

        def measured(t):
            t = t.strip()
            if not t:
                return 0.0
            if t not in cache:
                au = tts.generate(t, sid=0, speed=1.0)
                x = np.abs(np.array(au.samples, dtype=np.float32))
                idx = np.flatnonzero(x > 0.02 * x.max()) if x.size else []
                cache[t] = (idx[-1] - idx[0]) / au.sample_rate if len(idx) else 0.0
            return cache[t]
    sources = {}
    for name in a.inputs.split(","):
        if name == "REF":
            refs = {}
            for sub in ("subset1", "subset2"):
                for k, line in enumerate((a.iwslt / "data/test" / f"{sub}.en").read_text(encoding="utf-8").splitlines()):
                    refs[f"{sub}-{k}"] = line
            sources["REF"] = {i: refs[i] for i in cands["R0"]}
        else:
            sources[name] = {i: " ".join(v) for i, v in cands[name].items()}
    out, log = {}, {}
    for name, texts in sources.items():
        ruler_out, voice_out = {}, {}
        for i, text in texts.items():
            segs = frames[i]["segments"]
            phrases = place(text.split(), [s["dur"] for s in segs], dur)
            edited = list(phrases)
            for k, s in enumerate(segs):
                if not edited[k].strip():
                    continue
                best, cost, hist, _ = search(pack, edited, k, s["dur"], dur)
                edited[k] = best
                log.setdefault(name, []).append({"id": i, "seg": k, "from": phrases[k], "to": best, "edits": hist})
            ruler_out[i] = edited
            if measured:
                vphr = list(edited)
                for k, s in enumerate(segs):
                    if not vphr[k].strip():
                        continue
                    m = measured(vphr[k])
                    if m / s["dur"] <= 1.1 and m / s["dur"] >= 0.8:
                        continue
                    scale = m / max(0.05, dur(vphr[k]))
                    _, _, _, top = search(pack, vphr, k, s["dur"], lambda t, sc=scale: sc * dur(t), beam=30, depth=3)
                    pool = [vphr[k]] + [t for t, _ in top]
                    vphr[k] = min(pool, key=lambda t: fit_cost(measured(t), s["dur"]) + (0 if t == vphr[k] else 0.3))
                voice_out[i] = vphr
            print(f"{name} {i} done", file=sys.stderr)
        out[f"ALGO{a.tag}({name})"] = ruler_out
        if measured:
            out[f"ALGO+voice{a.tag}({name})"] = voice_out
    a.out.write_text(json.dumps({"cands": out, "log": log}, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
