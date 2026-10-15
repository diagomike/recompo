"""MMS-TTS (VITS) synthesis under the worker python.

    python tts_mms.py --model facebook/mms-tts-orm --text "…" --out x.wav
    python tts_mms.py --model facebook/mms-tts-orm --batch jobs.json     # [{"text": …, "out": …}, …]
"""

from __future__ import annotations

import argparse
import json
import sys
import wave

import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--text")
    ap.add_argument("--out")
    ap.add_argument("--batch")
    a = ap.parse_args()
    import torch
    from transformers import AutoTokenizer, VitsModel

    tok = AutoTokenizer.from_pretrained(a.model)
    model = VitsModel.from_pretrained(a.model).eval()
    sr = model.config.sampling_rate
    items = json.load(open(a.batch, encoding="utf-8")) if a.batch else [{"text": a.text, "out": a.out}]
    for k, it in enumerate(items):
        with torch.no_grad():
            wav = model(**tok(it["text"], return_tensors="pt")).waveform[0].numpy()
        pcm = (np.clip(wav, -1, 1) * 32767).astype("<i2")
        with wave.open(it["out"], "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sr)
            w.writeframes(pcm.tobytes())
        sys.stdout.write(json.dumps({"progress": round((k + 1) / len(items), 3)}) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
