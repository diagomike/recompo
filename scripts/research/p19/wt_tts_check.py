"""Independent check of the llm-loop conditions: synthesize every phrase with a real TTS voice (VITS LJSpeech via
sherpa-onnx, normal speed), trim silence, and score speech overlap against the German speakers' segments with the
*measured* audio durations instead of the text ruler. Also reports the speed-up each condition would need.

    python wt_tts_check.py --frames frames.json --results results.json --voice VOICE_DIR --out tts.json
"""
import argparse, json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent))
import bench as B  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--frames", type=Path, required=True)
ap.add_argument("--results", type=Path, required=True)
ap.add_argument("--voice", type=Path, required=True)
ap.add_argument("--out", type=Path, required=True)
a = ap.parse_args()
import sherpa_onnx as so
v = a.voice
name = next(v.glob("*.onnx")).name
if (v / "lexicon.txt").exists():  # voices with their own lexicon (no espeak frontend needed)
    vits = so.OfflineTtsVitsModelConfig(model=str(v / name), lexicon=str(v / "lexicon.txt"), tokens=str(v / "tokens.txt"))
else:
    vits = so.OfflineTtsVitsModelConfig(model=str(v / name), tokens=str(v / "tokens.txt"), data_dir=str(v / "espeak-ng-data"))
cfg = so.OfflineTtsConfig(model=so.OfflineTtsModelConfig(vits=vits, num_threads=4))
tts = so.OfflineTts(cfg)
cache = {}

def measured(text):
    t = text.strip()
    if not t:
        return 0.0
    if t not in cache:
        au = tts.generate(t, sid=0, speed=1.0)
        x = np.abs(np.array(au.samples, dtype=np.float32))
        thr = 0.02 * x.max() if x.size else 0
        idx = np.flatnonzero(x > thr)
        cache[t] = (idx[-1] - idx[0]) / au.sample_rate if idx.size else 0.0
    return cache[t]

frames = json.loads(a.frames.read_text(encoding="utf-8"))
res = json.loads(a.results.read_text(encoding="utf-8"))
conds = sorted({c for d in res["detail"].values() for c in d})
out = {}
for c in conds:
    rows, speed = [], []
    for i, d in res["detail"].items():
        if c not in d:
            continue
        item = {"id": i, "segments": frames[i]["segments"]}
        sc = B.score_item(item, d[c]["phrases"], measured)
        rows.append(sc)
        for s, t in zip(frames[i]["segments"], d[c]["phrases"]):
            m = measured(t)
            if m:
                speed.append(m / s["dur"])
    sp = np.array(speed)
    out[c] = {"n": len(rows), "speech_overlap": round(float(np.mean([r["speech_overlap"] for r in rows])), 4),
              "duration_overlap": round(float(np.mean([r["duration_overlap"] for r in rows])), 4),
              "slc_0.2": round(float(np.mean([r["slc_0.2"] for r in rows])), 4),
              "segments_needing_speedup_over_1.1x": round(float((sp > 1.1).mean()), 3),
              "median_tts_over_real": round(float(np.median(sp)), 3)}
a.out.write_text(json.dumps(out, indent=1), encoding="utf-8")
print(json.dumps(out, indent=1))
