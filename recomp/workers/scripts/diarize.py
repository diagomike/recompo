"""Who speaks when: pyannote speaker-diarization-community-1, run under the worker python.

Standalone (imports nothing from recomp). Writes turns, exclusive turns (one speaker at a time),
seconds per speaker and each speaker's centroid embedding (for matching people across sources).

    python diarize.py --wav audio16k.wav --out diarize.json [--speakers N | --min N --max M]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import wave
from pathlib import Path

import numpy as np


def say(**kw):
    sys.stdout.write(json.dumps(kw) + "\n")
    sys.stdout.flush()


def token() -> str | None:
    if os.environ.get("HF_TOKEN"):
        return os.environ["HF_TOKEN"]
    try:
        from huggingface_hub import get_token
        t = get_token()
        if t:
            return t
    except Exception:  # noqa: BLE001
        pass
    p = Path.home() / ".cache" / "huggingface" / "token"  # the user's own `hf auth login`
    return p.read_text(encoding="utf-8").strip() if p.exists() else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wav", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--speakers", type=int, default=0)
    ap.add_argument("--min", type=int, default=0)
    ap.add_argument("--max", type=int, default=0)
    ap.add_argument("--pipeline", default="pyannote/speaker-diarization-community-1")
    a = ap.parse_args()
    os.environ["PYANNOTE_METRICS_ENABLED"] = "false"
    import torch
    from pyannote.audio import Pipeline

    t0 = time.time()
    pipe = Pipeline.from_pretrained(a.pipeline, token=token())
    if pipe is None:
        raise SystemExit("could not load the diarization pipeline (gated model: accept its terms and log in once)")
    torch.set_num_threads(max(1, (os.cpu_count() or 4) - 2))
    say(message=f"pipeline loaded in {time.time() - t0:.1f}s")
    with wave.open(a.wav, "rb") as w:
        sr = w.getframerate()
        x = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype("float32") / 32768.0
    kw = {}
    if a.speakers:
        kw["num_speakers"] = a.speakers
    else:
        if a.min:
            kw["min_speakers"] = a.min
        if a.max:
            kw["max_speakers"] = a.max

    def hook(step_name, step_artifact, file=None, total=None, completed=None):
        if total:
            say(progress=round(min(0.99, completed / total), 3), message=step_name)

    try:
        res = pipe({"waveform": torch.from_numpy(x[None, :].copy()), "sample_rate": sr}, hook=hook, **kw)
    except TypeError:
        res = pipe({"waveform": torch.from_numpy(x[None, :].copy()), "sample_rate": sr}, **kw)
    ann = getattr(res, "speaker_diarization", res)
    excl = getattr(res, "exclusive_speaker_diarization", None)
    turns = [{"start": round(t.start, 3), "end": round(t.end, 3), "speaker": s} for t, _, s in ann.itertracks(yield_label=True)]
    ex = [{"start": round(t.start, 3), "end": round(t.end, 3), "speaker": s} for t, _, s in excl.itertracks(yield_label=True)] \
        if excl is not None else turns
    labels = list(ann.labels())
    embs = getattr(res, "speaker_embeddings", None)
    centroids = {lab: [round(float(v), 6) for v in embs[i]] for i, lab in enumerate(labels)} \
        if embs is not None and len(embs) == len(labels) else {}
    seconds = {lab: round(sum(t["end"] - t["start"] for t in ex if t["speaker"] == lab), 1) for lab in labels}
    doc = {"pipeline": a.pipeline, "turns": turns, "exclusive": ex, "labels": labels, "centroids": centroids,
           "seconds": seconds, "elapsed_s": round(time.time() - t0, 1), "audio_s": round(len(x) / sr, 1)}
    tmp = a.out + ".part"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f)
    os.replace(tmp, a.out)
    say(progress=1.0, message="done", speakers=len(labels))


if __name__ == "__main__":
    main()
