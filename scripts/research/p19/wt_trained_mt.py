"""P19 worktree `trained-mt`: the IWSLT 2023 dubbing baseline (a trained duration-aware NMT) on the P19 bench.

The model (Sockeye transformer, target factors + auxiliary counters; Chronopoulou 2023 / Pal 2023) reads German BPE
text plus one duration bin per target speech segment and writes English phonemes, each with a duration in frames
(22050 Hz / 256 hop), with [pause] between segments. We give it the **German speaker's segments** from the P19 frames
(the same frames the LLM loop wrote for), turn its phonemes back into words with the provided phoneme→grapheme
model, and score exactly like the other mechanisms.

Runs under the Sockeye environment (Python 3.10, torch 1.13, the authors' fork), from the iwslt-autodub-task folder:

    python wt_trained_mt.py bins   --iwslt IWSLT --mfa MFA --n 150000 --out durations_freq.pkl
    python wt_trained_mt.py inputs --iwslt IWSLT --frames frames.json --bins durations_freq.pkl --ids ids.txt --out in.json
    sockeye-translate ... (see README)
    python wt_trained_mt.py post   --hyp out.txt --ids ids.txt --out-dir DIR      # phonetic words per segment for P2G
    python wt_trained_mt.py collect --ids ids.txt --words p2g.txt --map map.json --hyp out.txt --out cands.json
"""

from __future__ import annotations

import argparse
import codecs
import json
import os
import pickle
import random
import sys
from collections import defaultdict
from pathlib import Path

FPS = 22050 / 256


def cmd_bins(a):
    sys.path.insert(0, str(a.iwslt))
    from preprocessing_scripts import get_speech_durations
    test = set()
    for sub in ("subset1", "subset2"):
        test |= {n.split(".")[0] for n in (a.iwslt / "data/test" / f"{sub}.filenames.txt").read_text().split()}
    files = sorted(p for p in a.mfa.glob("*.json") if p.stem not in test)
    random.Random(0).shuffle(files)
    freq = defaultdict(int)
    n = 0
    for p in files[: a.n]:
        try:
            data = json.loads(p.read_text())
            get_speech_durations(data, freq, 0, return_durations=True)
            n += 1
        except Exception:
            continue
    with open(a.out, "wb") as f:
        pickle.dump(freq, f)
    print(f"durations from {n} utterances, {sum(freq.values())} segments")


def cmd_inputs(a):
    sys.path.insert(0, str(a.iwslt))
    from preprocessing_scripts import Bin
    from subword_nmt.apply_bpe import BPE
    freq = pickle.load(open(a.bins, "rb"))
    b = Bin(freq, n=100)
    bpe = BPE(codecs.open(a.iwslt / "data/training/de_codes_10k", encoding="utf-8"))
    frames = json.loads(a.frames.read_text(encoding="utf-8"))
    ids = a.ids.read_text().split()
    with open(a.out, "w", encoding="utf-8") as f:
        for i in ids:
            fr = frames[i]
            segs = [max(1, round(s["dur"] * FPS)) for s in fr["segments"]]
            text = bpe.process_line(fr["de"].replace("[pause]", " ").strip())
            text = " ".join(text.split())
            bins = b.find_bin(segs)
            line = {"text": f"{text} <||> {' '.join(bins)}", "target_prefix": "<shift>",
                    "target_prefix_factors": ["0", str(sum(segs)), str(segs[0]), str(len(segs) - 1)],
                    "target_segment_durations": segs, "use_target_prefix_all_chunks": False}
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
    print(f"wrote {len(ids)} inputs")


def parse_hyp(line):
    """Model output tokens 'PH|dur|total|seg|pauses' → list of segments, each a list of (phoneme, frames), with
    <eow> kept as word boundaries."""
    toks = line.strip().split()[1:]  # first token is the <shift> pad
    segs, cur = [], []
    for t in toks:
        f = t.split("|")
        ph = f[0]
        dur = int(f[1]) if len(f) > 1 and f[1].lstrip("-").isdigit() else 0
        if ph == "[pause]":
            segs.append(cur)
            cur = []
        else:
            cur.append((ph, dur))
    segs.append(cur)
    return segs


def cmd_post(a):
    ids = a.ids.read_text().split()
    a.out_dir.mkdir(parents=True, exist_ok=True)
    lines, mapping = [], []
    for i, line in zip(ids, open(a.hyp, encoding="utf-8")):
        for k, seg in enumerate(parse_hyp(line)):
            words, cur = [], []
            for ph, _ in seg:
                if ph == "<eow>":
                    if cur:
                        words.append("-".join(cur))
                    cur = []
                elif ph not in ("sp", "<shift>"):
                    cur.append(ph)
            if cur:
                words.append("-".join(cur))
            lines.append(" ".join(words) if words else "X")
            mapping.append([i, k, sum(d for _, d in seg) / FPS])
    (a.out_dir / "segments.phoneticwords").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (a.out_dir / "map.json").write_text(json.dumps(mapping))
    print(f"{len(lines)} segments for phoneme-to-grapheme")


def cmd_collect(a):
    ids = a.ids.read_text().split()
    mapping = json.loads(a.map.read_text())
    words = [w.strip() for w in open(a.words, encoding="utf-8")]
    out, own = {i: [] for i in ids}, {i: [] for i in ids}
    for (i, k, sec), w in zip(mapping, words):
        out[i].append(w.replace("@@ ", "").replace("@@", ""))
        own[i].append(round(sec, 3))
    a.out.write_text(json.dumps({"TRAINED_MT": out, "_model_durations_s": own}, ensure_ascii=False, indent=1),
                     encoding="utf-8")
    print(f"collected {len(out)} items")


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("bins")
    p.add_argument("--iwslt", type=Path, required=True)
    p.add_argument("--mfa", type=Path, required=True)
    p.add_argument("--n", type=int, default=150000)
    p.add_argument("--out", type=Path, required=True)
    p = sp.add_parser("inputs")
    p.add_argument("--iwslt", type=Path, required=True)
    p.add_argument("--frames", type=Path, required=True)
    p.add_argument("--bins", type=Path, required=True)
    p.add_argument("--ids", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p = sp.add_parser("post")
    p.add_argument("--hyp", type=Path, required=True)
    p.add_argument("--ids", type=Path, required=True)
    p.add_argument("--out-dir", type=Path, required=True)
    p = sp.add_parser("collect")
    p.add_argument("--ids", type=Path, required=True)
    p.add_argument("--words", type=Path, required=True)
    p.add_argument("--map", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    os.chdir(a.iwslt) if getattr(a, "iwslt", None) else None
    {"bins": cmd_bins, "inputs": cmd_inputs, "post": cmd_post, "collect": cmd_collect}[a.cmd](a)


if __name__ == "__main__":
    main()
