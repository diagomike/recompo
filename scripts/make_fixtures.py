"""Generate deterministic test media (never committed).

* ``clip.mp4``: 40 s, 320×180, 10 fps; the frame colour encodes the source second
  (see :func:`colour_for_second`), so render tests can check source-time mapping by sampling a pixel.
  Audio: offline Windows SAPI speech placed at known times (tones elsewhere).
* ``clip51.mp4``: same picture, 5.1 audio with the speech on the centre channel.
* ``clip.srt``: cues at the exact placement times; ``clip_offset.srt``: the same, 1.5 s late.

    python scripts/make_fixtures.py [out_dir]
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "tests" / "fixtures" / "generated"
DURATION = 40
SENTENCES = [
    (2.0, "Why do we fall, Bruce?"),
    (7.0, "So we can learn to pick ourselves up."),
    (12.0, "You either die a hero, or you live long enough to see yourself become the villain."),
    (19.0, "Some men just want to watch the world burn."),
    (24.0, "It's not who I am underneath, but what I do that defines me."),
    (30.0, "The night is darkest just before the dawn."),
    (35.0, "Why so serious?"),
]
VERSION = 3


def colour_for_second(s: int) -> tuple[int, int, int]:
    return ((s * 37 + 40) % 216 + 20, (s * 91 + 80) % 216 + 20, (s * 53 + 120) % 216 + 20)


def _ff(args: list[str]) -> None:
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], check=True)


def _sapi(text: str, dest: Path, voice: str = "Microsoft Zira Desktop") -> bool:
    if os.name != "nt":
        return False
    ps = ("Add-Type -AssemblyName System.Speech;"
          "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
          f"try {{ $s.SelectVoice('{voice}') }} catch {{}};"
          "$s.Rate=0;"
          f"$s.SetOutputToWaveFile('{dest}');"
          f"$s.Speak(\"{text.replace(chr(34), '')}\");$s.Dispose()")
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True)
    return r.returncode == 0 and dest.exists() and dest.stat().st_size > 1000


def make(out: Path = OUT) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    stamp = out / "fixtures.json"
    if stamp.exists():
        info = json.loads(stamp.read_text(encoding="utf-8"))
        if info.get("version") == VERSION and all((out / f).exists() for f in info["files"]):
            return info
    tmp = out / f"_tmp_{os.getpid()}"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir()
    # Picture: colour changes every whole second.
    expr_r = "mod(floor(T)*37+40\\,216)+20"
    expr_g = "mod(floor(T)*91+80\\,216)+20"
    expr_b = "mod(floor(T)*53+120\\,216)+20"
    _ff(["-f", "lavfi", "-i", f"color=c=black:s=320x180:r=10:d={DURATION}",
         "-vf", f"geq=r='{expr_r}':g='{expr_g}':b='{expr_b}',format=yuv420p",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "12", "-g", "10", str(tmp / "video.mp4")])
    # Speech at known offsets.
    inputs, filters, speech = [], [], True
    for i, (t, text) in enumerate(SENTENCES):
        wav = tmp / f"s{i}.wav"
        if not _sapi(text, wav):
            speech = False
            _ff(["-f", "lavfi", "-i", f"sine=f={300 + 40 * i}:d=2", "-ar", "22050", str(wav)])
        inputs += ["-i", str(wav)]
        filters.append(f"[{i}:a]aresample=48000,adelay={int(t * 1000)}|{int(t * 1000)}[a{i}]")
    mix = "".join(f"[a{i}]" for i in range(len(SENTENCES)))
    filters.append(f"{mix}amix=inputs={len(SENTENCES)}:normalize=0,apad=whole_dur={DURATION},"
                   f"atrim=0:{DURATION}[mono]")
    _ff([*inputs, "-filter_complex", ";".join(filters), "-map", "[mono]", "-ac", "1", "-ar", "48000",
         str(tmp / "speech.wav")])
    _ff(["-i", str(tmp / "video.mp4"), "-i", str(tmp / "speech.wav"), "-map", "0:v", "-map", "1:a",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-ac", "2", "-shortest", str(out / "clip.mp4")])
    _ff(["-i", str(tmp / "video.mp4"), "-i", str(tmp / "speech.wav"),
         "-f", "lavfi", "-i", f"sine=f=110:d={DURATION}:sample_rate=48000",
         "-filter_complex",
         "[1:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=mono[c];"
         "[2:a]volume=0.25,aformat=sample_fmts=fltp:channel_layouts=mono,asplit=5[m1][m2][m3][m4][m5];"
         "[m1][m2][c][m3][m4][m5]join=inputs=6:channel_layout=5.1:"
         "map=0.0-FL|1.0-FR|2.0-FC|3.0-LFE|4.0-BL|5.0-BR[a]",
         "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-shortest",
         str(out / "clip51.mp4")])

    def srt(offset: float) -> str:
        lines = []
        for i, (t, text) in enumerate(SENTENCES, start=1):
            a, b = t + offset, t + offset + min(4.5, 0.35 + 0.075 * len(text))
            lines += [str(i), f"{_tc(a)} --> {_tc(b)}", text, ""]
        return "\n".join(lines)

    (out / "clip.srt").write_text(srt(0.0), encoding="utf-8")
    (out / "clip_offset.srt").write_text(srt(1.5), encoding="utf-8")
    shutil.copy(out / "clip.srt", out / "clip51.srt")
    shutil.rmtree(tmp, ignore_errors=True)
    info = {"version": VERSION, "speech": speech, "duration": DURATION, "sentences": SENTENCES,
            "files": ["clip.mp4", "clip51.mp4", "clip.srt", "clip_offset.srt", "clip51.srt"]}
    stamp.write_text(json.dumps(info, indent=1), encoding="utf-8")
    return info


def _tc(s: float) -> str:
    ms = int(round(s * 1000))
    h, rem = divmod(ms, 3600000)
    m, rem = divmod(rem, 60000)
    sec, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"


if __name__ == "__main__":
    print(json.dumps(make(Path(sys.argv[1]) if len(sys.argv) > 1 else OUT), indent=1))
