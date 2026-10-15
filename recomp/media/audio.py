"""Audio derived from a source: the 16 kHz mono WAV every speech step uses, and waveform peaks.

Surround sources are folded to mono with the centre (dialogue) channel weighted up, so ASR and
the waveform follow speech rather than the score.
"""

from __future__ import annotations

import json
import wave
from pathlib import Path

import numpy as np

from . import ff

PEAKS_PER_SECOND = 20


def mono_filter(channels: int | None, layout: str = "") -> str:
    if channels and channels >= 6:
        return "pan=mono|c0=0.6*FC+0.2*FL+0.2*FR"
    if channels == 2:
        return "pan=mono|c0=0.5*c0+0.5*c1"
    return "anull"


def extract_16k(src: Path, dest: Path, channels: int | None, layout: str = "", duration: float | None = None,
                progress=None, cancelled=None, start: float | None = None, length: float | None = None) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".part.wav")
    args = []
    if start:
        args += ["-ss", f"{start:.3f}"]
    args += ["-i", str(src)]
    if length:
        args += ["-t", f"{length:.3f}"]
    args += ["-map", "0:a:0", "-vn", "-sn", "-af", mono_filter(channels, layout) + ",aresample=16000",
             "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(tmp)]
    ff.run(args, duration=length or duration, progress=progress, cancelled=cancelled)
    tmp.replace(dest)
    return dest


def read_wav(path: Path, start: float = 0.0, end: float | None = None) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as w:
        sr = w.getframerate()
        n = w.getnframes()
        a = int(start * sr)
        b = n if end is None else min(n, int(end * sr))
        w.setpos(max(0, min(a, n)))
        raw = w.readframes(max(0, b - a))
    data = np.frombuffer(raw, dtype="<i2").astype("float32") / 32768.0
    return data, sr


def peaks_from_wav(wav: Path, out: Path, per_second: int = PEAKS_PER_SECOND) -> dict:
    """Max-abs envelope at ``per_second`` bins, stored as uint8 (0–255) plus a JSON header."""
    with wave.open(str(wav), "rb") as w:
        sr = w.getframerate()
        n = w.getnframes()
        hop = sr // per_second
        values: list[np.ndarray] = []
        block = hop * per_second * 60  # one minute per read
        carry = np.zeros(0, dtype="int16")
        read = 0
        while read < n:
            raw = w.readframes(min(block, n - read))
            read += block
            arr = np.frombuffer(raw, dtype="<i2")
            arr = np.concatenate((carry, arr)) if carry.size else arr
            usable = (arr.size // hop) * hop
            if usable:
                values.append(np.abs(arr[:usable].astype("int32")).reshape(-1, hop).max(axis=1))
            carry = arr[usable:]
        if carry.size:
            values.append(np.array([np.abs(carry.astype("int32")).max()]))
    env = np.concatenate(values) if values else np.zeros(0, dtype="int32")
    peak = int(env.max()) if env.size else 1
    scaled = np.clip(np.round(env / max(peak, 1) * 255), 0, 255).astype("uint8")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(scaled.tobytes())
    meta = {"per_second": per_second, "bins": int(scaled.size), "duration": round(n / sr, 3),
            "peak": round(peak / 32768.0, 4), "file": out.name}
    out.with_suffix(".json").write_text(json.dumps(meta), encoding="utf-8")
    return meta


def silences(wav: Path, threshold_db: float = -38.0, min_len: float = 0.35) -> list[tuple[float, float]]:
    """Quiet stretches from the 16 kHz WAV, via a 20 ms RMS envelope (no ffmpeg pass needed)."""
    with wave.open(str(wav), "rb") as w:
        sr = w.getframerate()
        n = w.getnframes()
        hop = sr // 50
        parts = []
        block = hop * 50 * 60
        while True:
            raw = w.readframes(block)
            if not raw:
                break
            arr = np.frombuffer(raw, dtype="<i2").astype("float32") / 32768.0
            usable = (arr.size // hop) * hop
            if usable:
                fr = arr[:usable].reshape(-1, hop)
                parts.append(20 * np.log10(np.sqrt((fr ** 2).mean(axis=1) + 1e-12) + 1e-9))
    if not parts:
        return []
    db = np.concatenate(parts)
    del n
    quiet = db < threshold_db
    out = []
    start = None
    for i, q in enumerate(quiet):
        if q and start is None:
            start = i
        elif not q and start is not None:
            if (i - start) * 0.02 >= min_len:
                out.append((round(start * 0.02, 3), round(i * 0.02, 3)))
            start = None
    if start is not None and (len(quiet) - start) * 0.02 >= min_len:
        out.append((round(start * 0.02, 3), round(len(quiet) * 0.02, 3)))
    return out
