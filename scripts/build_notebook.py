"""Write notebooks/recomp_worker.ipynb: a remote GPU worker for Kaggle, Colab or local Jupyter.

The notebook embeds the standalone worker scripts (ASR, diarisation, separation, MMS-TTS, the folder
protocol), so it needs no clone of this repository.

    python scripts/build_notebook.py
"""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "recomp" / "workers" / "scripts"
EMBED = ["remote_worker.py", "asr.py", "diarize.py", "separate.py", "tts_mms.py", "selftest.py"]


def md(text: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": text.strip().splitlines(keepends=True)}


def code(text: str) -> dict:
    return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
            "source": text.strip().splitlines(keepends=True)}


def build() -> dict:
    cells = [
        md("""
# Recomposer remote worker

Runs the studio's heavy jobs (speech recognition, speaker detection, separation, MMS voices) on this
machine's GPU. The studio and this notebook share one folder: the studio writes job folders into it, this
notebook serves them and writes results back.

1. In the studio: `recomp config set worker.remote_folder <that folder as your PC sees it>` (for example the
   Google Drive for Desktop path `G:\\My Drive\\RecompRemote`).
2. Here: set `FOLDER` to the same folder as this machine sees it, run every cell, and leave the last one running.
3. In the studio: `recomp transcript asr S3 --on remote` (or `speaker diarize S3 --on remote`).

Speaker detection needs a Hugging Face token with access to `pyannote/speaker-diarization-community-1`:
type it into `HF_TOKEN` yourself. **Never save or share this notebook with the token filled in.**
"""),
        code("""
# Settings
FOLDER = "/content/drive/MyDrive/RecompRemote"   # Colab + Drive; on Kaggle e.g. "/kaggle/working/RecompRemote"
MOUNT_DRIVE = True                                # Colab only
HF_TOKEN = ""                                     # only for speaker detection; type it here, never commit it
"""),
        code("""
import os, sys, subprocess
if MOUNT_DRIVE:
    try:
        from google.colab import drive
        drive.mount("/content/drive")
    except ImportError:
        print("not on Colab: skipping the Drive mount")
if HF_TOKEN:
    os.environ["HF_TOKEN"] = HF_TOKEN
os.makedirs(FOLDER, exist_ok=True)
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "faster-whisper", "pyannote.audio", "transformers",
                "audio-separator[gpu]", "soundfile"], check=False)
"""),
    ]
    files = {name: (SCRIPTS / name).read_text(encoding="utf-8") for name in EMBED}
    cells.append(code("SCRIPTS = " + json.dumps(files) + """
os.makedirs("/tmp/recomp_scripts", exist_ok=True)
for name, text in SCRIPTS.items():
    open(f"/tmp/recomp_scripts/{name}", "w", encoding="utf-8").write(text)
print("wrote", len(SCRIPTS), "worker scripts")
"""))
    cells.append(code("""
# Serve jobs until you stop this cell. GPU is used automatically where the libraries support it.
!python /tmp/recomp_scripts/remote_worker.py --folder "$FOLDER"
"""))
    return {"cells": cells, "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                                         "language_info": {"name": "python"}}, "nbformat": 4, "nbformat_minor": 5}


def main() -> None:
    out = REPO / "notebooks" / "recomp_worker.ipynb"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(build(), indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
