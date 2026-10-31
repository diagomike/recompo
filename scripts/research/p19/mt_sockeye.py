"""Black-box MT adapter: the IWSLT 2023 German→English Sockeye model, used as a stand-in for an MT-only target
language (Google/NLLB for Amharic or Oromo on the user's PC).

Each input chunk is translated on its own (one speech segment = one chunk). The model wants a duration bin per
segment; the adapter gives it the chunk's **natural** length (its German syllables at a neutral 4.4 syl/s), so it
behaves like ordinary MT that knows nothing about the target timing. Runs under the Sockeye environment
(Python 3.10, torch 1.13, the authors' fork), from the iwslt-autodub-task folder:

    python mt_sockeye.py --iwslt IWSLT --bins durations_freq.pkl --in chunks.jsonl --out out.jsonl
    chunks.jsonl: {"key": ..., "text": "German chunk"} per line → out.jsonl: {"key": ..., "text": "english words"}
"""
import argparse
import codecs
import json
import os
import pickle
import re
import subprocess
import sys
import tempfile
from pathlib import Path

FPS = 22050 / 256
VOWELS = re.compile(r"[aeiouyäöü]+", re.I)


def natural_frames(text: str) -> int:
    syl = max(1, len(VOWELS.findall(text)))
    return max(20, round(syl / 4.4 * FPS))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iwslt", type=Path, required=True)
    ap.add_argument("--bins", type=Path, required=True)
    ap.add_argument("--in", dest="inp", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    sys.path.insert(0, str(a.iwslt))
    os.chdir(a.iwslt)
    from preprocessing_scripts import Bin
    from subword_nmt.apply_bpe import BPE
    b = Bin(pickle.load(open(a.bins, "rb")), n=100)
    bpe = BPE(codecs.open("data/training/de_codes_10k", encoding="utf-8"))
    rows = [json.loads(l) for l in a.inp.read_text(encoding="utf-8").splitlines() if l.strip()]
    bindir = Path(sys.executable).parent
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        with open(td / "in.json", "w", encoding="utf-8") as f:
            for r in rows:
                fr = natural_frames(r["text"])
                text = " ".join(bpe.process_line(r["text"].strip()).split())
                f.write(json.dumps({"text": f"{text} <||> {b.find_bin([fr])[0]}", "target_prefix": "<shift>",
                                    "target_prefix_factors": ["0", str(fr), str(fr), "0"],
                                    "target_segment_durations": [fr], "use_target_prefix_all_chunks": False},
                                   ensure_ascii=False) + "\n")
        subprocess.run([str(bindir / "sockeye-translate"), "-i", str(td / "in.json"), "-o", str(td / "out.txt"),
                        "--models", "models/sockeye/trained_baselines/baseline_factored_noised0.1/model",
                        "--checkpoints", "78", "-b", "5", "--batch-size", "16", "--chunk-size", "20000",
                        "--output-type", "translation_with_factors", "--max-output-length", "768",
                        "--force-factors-stepwise", "frames", "total_remaining", "segment_remaining", "pauses_remaining",
                        "--json-input", "--use-cpu", "--quiet"], check=True, capture_output=True)
        phon = []
        for line in open(td / "out.txt", encoding="utf-8"):
            words, cur = [], []
            for t in line.split()[1:]:
                ph = t.split("|")[0]
                if ph == "<eow>":
                    if cur:
                        words.append("-".join(cur))
                    cur = []
                elif ph not in ("sp", "[pause]", "<shift>"):
                    cur.append(ph)
            if cur:
                words.append("-".join(cur))
            phon.append(" ".join(words) or "X")
        (td / "p.txt").write_text("\n".join(phon) + "\n")
        bp = subprocess.run([str(bindir / "subword-nmt"), "apply-bpe", "-c",
                             "models/phoneme_to_grapheme/phoneme_to_grapheme_bpe_10k", "-i", str(td / "p.txt")],
                            capture_output=True, text=True, check=True).stdout
        (td / "p.bpe").write_text("\n".join(" ".join(l.split()[:1023]) for l in bp.splitlines()) + "\n")
        subprocess.run([str(bindir / "sockeye-translate"), "--models", "models/phoneme_to_grapheme", "--checkpoints", "48",
                        "-b", "5", "--batch-size", "32", "--chunk-size", "20000", "-i", str(td / "p.bpe"),
                        "-o", str(td / "w.txt"), "--use-cpu", "--quiet"], check=True, capture_output=True)
        words = [re.sub(r"(@@ )|(@@ ?$)", "", l.strip()) for l in open(td / "w.txt", encoding="utf-8")]
    with open(a.out, "w", encoding="utf-8") as f:
        for r, w in zip(rows, words):
            f.write(json.dumps({"key": r["key"], "text": w}, ensure_ascii=False) + "\n")
    print(f"translated {len(rows)} chunks")


if __name__ == "__main__":
    main()
