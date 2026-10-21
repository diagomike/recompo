"""Dub lines in the original speakers' voices with OmniVoice (zero-shot voice cloning), under the worker python.

    python tts_clone.py --input lines.json [--model k2-fsa/OmniVoice] [--steps 16]
lines.json: {"language": "fr", "items": [{"text", "ref_audio", "ref_text", "max_dur", "out"}, …]}
Each line is spoken at its natural length; one that runs longer than max_dur is spoken again to fit, never faster
than MAX_SQUEEZE × (what still does not fit is left for the caller to report). Writes 24 kHz mono WAVs.
"""

from __future__ import annotations

import argparse
import json
import sys

MAX_SQUEEZE = 1.4
SR = 24000


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--model", default="k2-fsa/OmniVoice")
    ap.add_argument("--steps", type=int, default=16)
    a = ap.parse_args()
    import numpy as np
    import soundfile as sf
    import torch
    from omnivoice import OmniVoice
    try:
        from omnivoice import OmniVoiceGenerationConfig
        cfg = {"generation_config": OmniVoiceGenerationConfig(num_step=a.steps, guidance_scale=2.0)}
    except ImportError:
        cfg = {}

    job = json.load(open(a.input, encoding="utf-8"))
    items = job["items"]
    model = OmniVoice.from_pretrained(a.model, device_map="cpu", dtype=torch.float32)
    prompts: dict[str, object] = {}
    done = []
    for k, it in enumerate(items):
        key = it["ref_audio"]
        if key not in prompts:  # one voice prompt per reference, reused by every line that shares it
            prompts[key] = model.create_voice_clone_prompt(ref_audio=it["ref_audio"], ref_text=it.get("ref_text") or None)
        gen = lambda **kw: np.asarray(model.generate(text=[it["text"]], language=[job["language"]],  # noqa: E731
                                                      voice_clone_prompt=[prompts[key]], **cfg, **kw)[0], np.float32)
        wav = gen()
        natural = len(wav) / SR
        if it.get("max_dur") and natural > it["max_dur"]:
            wav = gen(duration=max(float(it["max_dur"]), natural / MAX_SQUEEZE))
        sf.write(it["out"], wav, SR)
        done.append({"out": it["out"], "natural": round(natural, 3), "dur": round(len(wav) / SR, 3)})
        sys.stdout.write(json.dumps({"progress": (k + 1) / len(items), "message": f"voiced {k + 1}/{len(items)}"}) + "\n")
        sys.stdout.flush()
    sys.stdout.write(json.dumps({"progress": 1.0, "message": f"{len(done)} lines", "lines": done}) + "\n")


if __name__ == "__main__":
    main()
