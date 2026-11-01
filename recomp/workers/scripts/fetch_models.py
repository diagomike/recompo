"""Download Hugging Face models into the worker's cache once, so the dub then runs offline (NLLB, M2M-100, MMS voices).

    python fetch_models.py --repos facebook/nllb-200-distilled-600M,facebook/mms-tts-orm
"""

from __future__ import annotations

import argparse
import json
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repos", required=True)
    a = ap.parse_args()
    from huggingface_hub import snapshot_download

    repos = [r for r in a.repos.split(",") if r]
    done = []
    for k, r in enumerate(repos):
        try:
            snapshot_download(r)
            done.append({"repo": r, "ok": True})
        except Exception as exc:  # noqa: BLE001 — report each repo, keep going
            done.append({"repo": r, "ok": False, "error": f"{type(exc).__name__}: {exc}"[:300]})
        sys.stdout.write(json.dumps({"progress": round((k + 1) / len(repos), 3), "message": r}) + "\n")
        sys.stdout.flush()
    print(json.dumps({"fetched": done}))


if __name__ == "__main__":
    main()
