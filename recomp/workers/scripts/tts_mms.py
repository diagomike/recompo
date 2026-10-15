"""MMS-TTS (VITS) synthesis under the worker python: `python tts_mms.py --model facebook/mms-tts-orm --text … --out x.wav`."""

from __future__ import annotations

import argparse
import json
import sys
import wave

import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--text", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    import torch
    from transformers import AutoTokenizer, VitsModel

    tok = AutoTokenizer.from_pretrained(a.model)
    model = VitsModel.from_pretrained(a.model).eval()
    with torch.no_grad():
        wav = model(**tok(a.text, return_tensors="pt")).waveform[0].numpy()
    sr = model.config.sampling_rate
    pcm = (np.clip(wav, -1, 1) * 32767).astype("<i2")
    with wave.open(a.out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    sys.stdout.write(json.dumps({"progress": 1.0, "seconds": round(len(pcm) / sr, 2)}) + "\n")


if __name__ == "__main__":
    main()
