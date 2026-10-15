"""Vocals / background split with audio-separator (BS-RoFormer), under the worker python.

    python separate.py --input body.wav --outdir DIR --models MODEL_DIR [--model model_bs_roformer_ep_317_sdr_12.9755.ckpt]
Writes DIR/vocals.flac and DIR/background.flac.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--models", required=True)
    ap.add_argument("--model", default="model_bs_roformer_ep_317_sdr_12.9755.ckpt")
    a = ap.parse_args()
    from audio_separator.separator import Separator

    out = Path(a.outdir)
    tmp = out / "_sep"
    tmp.mkdir(parents=True, exist_ok=True)
    s = Separator(output_format="FLAC", model_file_dir=a.models, output_dir=str(tmp),
                  mdxc_params={"segment_size": 256, "override_model_segment_size": False, "batch_size": 1,
                               "overlap": 2, "pitch_shift": 0})
    s.load_model(a.model)
    files = [Path(f) if os.path.isabs(f) else tmp / f for f in s.separate(a.input)]
    vocals = next(f for f in files if "(vocals)" in f.name.lower())
    other = next(f for f in files if f != vocals)
    shutil.move(str(vocals), out / "vocals.flac")
    shutil.move(str(other), out / "background.flac")
    shutil.rmtree(tmp, ignore_errors=True)
    sys.stdout.write(json.dumps({"progress": 1.0, "message": "separated"}) + "\n")


if __name__ == "__main__":
    main()
