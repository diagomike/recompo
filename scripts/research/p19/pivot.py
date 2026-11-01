"""End-to-end pivot dubbing between two MT-only languages, through English (P19 worktree `pivot`).

    source audio ─ASR→ source text per speech segment ─MT views→ English evidence ─LLM→ pivot meaning map
    (units pinned to the source segments, ambiguities, prosody cues) ─LLM→ English options per segment ─MT→ target
    ─target voice→ durations on the SOURCE speaker's segments ─exact selection + target-side check→ the dub.

The LLM never reads the source or the target language: it reads only English MT views of the source and
(back-)translations of the target. This file does the language-free parts:

  asr       Parakeet TDT v3 over each source speech segment (Silero VAD frames from bench_frames.py)
  prosody   per segment: loudness relative to the line, and the pitch movement over the last 0.5 s
            (a final rise suggests a question, a loud segment suggests emphasis); pure numpy, no language model
  views     MT jobs: the whole line; each segment alone; the whole line asked short (×0.7 length) and long (×1.4);
            and glosses of the longest words
  sheet     the evidence sheet for the LLM: segment times, the four kinds of view, glosses, prosody flags.
            No source text is printed.
  cascade   the naive baseline: whole-line MT to English, which then goes to the target as one line

    python pivot.py asr --iwslt I --models M --frames F --ids ids.txt --out asr.json
    python pivot.py prosody --iwslt I --frames F --ids ids.txt --out prosody.json
    python pivot.py views --asr asr.json --out jobs.jsonl
    python pivot.py sheet --asr asr.json --prosody prosody.json --mt mt.jsonl --frames F --ids ids.txt
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
SR = 16000


def cmd_asr(a):
    from pilot_dub_pairs import Recogniser, load
    rec = Recogniser(a.models)
    frames = json.loads(a.frames.read_text(encoding="utf-8"))
    out = {}
    for i in a.ids.read_text().split():
        sub, k = i.split("-")
        x = load(str(a.iwslt / "x" / f"{sub}.{int(k) + 1}.wav"))
        segs = frames[i]["segments"]
        words = rec.words(x, [(s["start"], s["end"]) for s in segs])
        per = []
        for s in segs:
            ws = [w for w in words if w["start"] < s["end"] + 0.1 and w["end"] > s["start"] - 0.1]
            per.append(" ".join(w["text"] for w in ws))
        out[i] = {"segments": per, "whole": " ".join(per), "words": words}
    a.out.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"ASR on {len(out)} lines")


def _pitch(frame: np.ndarray) -> float:
    """F0 of a 40 ms frame by autocorrelation (75–400 Hz); 0 if unvoiced."""
    frame = frame - frame.mean()
    if np.sqrt((frame ** 2).mean()) < 0.01:
        return 0.0
    ac = np.correlate(frame, frame, "full")[len(frame) - 1:]
    lo, hi = SR // 400, SR // 75
    k = lo + int(np.argmax(ac[lo:hi]))
    return SR / k if ac[k] > 0.3 * ac[0] else 0.0


def cmd_prosody(a):
    from pilot_dub_pairs import load
    frames = json.loads(a.frames.read_text(encoding="utf-8"))
    out = {}
    for i in a.ids.read_text().split():
        sub, k = i.split("-")
        x = load(str(a.iwslt / "x" / f"{sub}.{int(k) + 1}.wav"))
        segs = frames[i]["segments"]
        rms = []
        rows = []
        for s in segs:
            y = x[int(s["start"] * SR): int(s["end"] * SR)]
            rms.append(float(np.sqrt((y ** 2).mean()) + 1e-9))
            hop, win = 160, 640
            f0 = [_pitch(y[j: j + win]) for j in range(0, max(0, len(y) - win), hop)]
            voiced = [(n, f) for n, f in enumerate(f0) if f > 0]
            tail = [f for n, f in voiced if n * hop / SR >= s["dur"] - 0.5]
            body = [f for n, f in voiced if n * hop / SR < s["dur"] - 0.5]
            rise = (np.median(tail) / np.median(body)) if tail and body else 1.0
            rows.append({"final_pitch_ratio": round(float(rise), 2)})
        mean = float(np.mean(rms))
        for r, v in zip(rows, rms):
            r["loudness_db"] = round(20 * np.log10(v / mean), 1)
            flags = []
            if r["final_pitch_ratio"] >= 1.15:
                flags.append("final rise (question?)")
            if r["loudness_db"] >= 3:
                flags.append("emphasis")
            r["flags"] = flags
        out[i] = rows
    a.out.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"prosody for {len(out)} lines")


def cmd_views(a):
    asr = json.loads(a.asr.read_text(encoding="utf-8"))
    jobs, seen = [], set()

    def add(key, text, scale=1.0):
        if text.strip() and key not in seen:
            seen.add(key)
            jobs.append({"key": key, "text": text, "scale": scale})
    for i, x in asr.items():
        add(f"{i}|whole", x["whole"])
        add(f"{i}|short", x["whole"], 0.7)
        add(f"{i}|long", x["whole"], 1.4)
        for k, s in enumerate(x["segments"]):
            add(f"{i}|seg{k + 1}", s)
        words = sorted({w.strip(".,;:!?–\"„“") for w in x["whole"].split()}, key=len, reverse=True)
        for w in [w for w in words if len(w) >= 6][:6]:
            add(f"{i}|gloss|{w}", w)
    a.out.write_text("".join(json.dumps(j, ensure_ascii=False) + "\n" for j in jobs), encoding="utf-8")
    print(f"{len(jobs)} MT view jobs")


def cmd_sheet(a):
    asr = json.loads(a.asr.read_text(encoding="utf-8"))
    pro = json.loads(a.prosody.read_text(encoding="utf-8"))
    frames = json.loads(a.frames.read_text(encoding="utf-8"))
    mt = {}
    for l in a.mt.read_text(encoding="utf-8").splitlines():
        if l.strip():
            r = json.loads(l)
            mt[r["key"]] = r["text"]
    for i in a.ids.read_text().split():
        segs = frames[i]["segments"]
        print(f"=== {i}  ({len(segs)} segments)")
        print(f"  whole: {mt.get(i + '|whole', '')}\n  short: {mt.get(i + '|short', '')}\n  long : {mt.get(i + '|long', '')}")
        for k, s in enumerate(segs):
            p = pro[i][k]
            fl = (" [" + ", ".join(p["flags"]) + "]") if p["flags"] else ""
            print(f"  [{k + 1}] {s['dur']:.2f}s{fl}: {mt.get(f'{i}|seg{k + 1}', '')}")
        gl = [f"{key.split('|')[2][:2]}…→{v}" for key, v in mt.items() if key.startswith(i + "|gloss|")]
        print(f"  glosses: {'; '.join(v.split('→')[1] for v in gl)}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("asr")
    for k in ("iwslt", "models", "frames", "ids", "out"):
        p.add_argument("--" + k, type=Path, required=True)
    p = sp.add_parser("prosody")
    for k in ("iwslt", "frames", "ids", "out"):
        p.add_argument("--" + k, type=Path, required=True)
    p = sp.add_parser("views")
    for k in ("asr", "out"):
        p.add_argument("--" + k, type=Path, required=True)
    p = sp.add_parser("sheet")
    for k in ("asr", "prosody", "mt", "frames", "ids"):
        p.add_argument("--" + k, type=Path, required=True)
    a = ap.parse_args()
    {"asr": cmd_asr, "prosody": cmd_prosody, "views": cmd_views, "sheet": cmd_sheet}[a.cmd](a)


if __name__ == "__main__":
    main()
