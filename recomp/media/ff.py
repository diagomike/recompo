"""ffmpeg/ffprobe: locating them, probing files, and running ffmpeg with progress and cancel.

Probing follows recomposer_v2's ``media/probe.py``: the streams decide what a file is, never its
extension, and cover art is not video.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from ..envelope import RecompError

MEDIA_EXTS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v", ".mpg", ".mpeg", ".ts", ".wmv", ".flv",
              ".mp3", ".wav", ".m4a", ".flac", ".ogg", ".opus", ".aac", ".wma"}
SUB_EXTS = {".srt", ".vtt", ".ass", ".ssa", ".json3"}
CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


def ffmpeg_bin() -> str:
    return os.environ.get("RECOMP_FFMPEG") or shutil.which("ffmpeg") or _missing("ffmpeg")


def ffprobe_bin() -> str:
    return os.environ.get("RECOMP_FFPROBE") or shutil.which("ffprobe") or _missing("ffprobe")


def _missing(name: str) -> str:
    raise RecompError("E_TOOL", f"{name} not found on PATH", hint="winget install --id Gyan.FFmpeg -e")


@dataclass
class Stream:
    index: int
    codec_type: str
    codec_name: str
    attached_pic: bool = False
    sample_rate: int | None = None
    channels: int | None = None
    channel_layout: str = ""
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    language: str = ""
    title: str = ""


@dataclass
class MediaInfo:
    path: Path
    duration: float | None
    container: str
    size: int
    bit_rate: int | None
    tags: dict = field(default_factory=dict)
    streams: list[Stream] = field(default_factory=list)
    chapters: list[dict] = field(default_factory=list)

    @property
    def video(self) -> list[Stream]:
        return [s for s in self.streams if s.codec_type == "video" and not s.attached_pic]

    @property
    def audio(self) -> list[Stream]:
        return [s for s in self.streams if s.codec_type == "audio"]

    @property
    def subtitles(self) -> list[Stream]:
        return [s for s in self.streams if s.codec_type == "subtitle"]

    @property
    def kind(self) -> str:
        return "video" if self.video else "audio"

    def to_dict(self) -> dict:
        v = self.video[0] if self.video else None
        a = self.audio[0] if self.audio else None
        return {
            "kind": self.kind, "container": self.container, "duration": self.duration, "size": self.size,
            "bit_rate": self.bit_rate,
            "video": {"codec": v.codec_name, "width": v.width, "height": v.height, "fps": v.fps} if v else None,
            "audio": {"codec": a.codec_name, "channels": a.channels, "layout": a.channel_layout,
                      "sample_rate": a.sample_rate, "language": a.language} if a else None,
            "audio_streams": len(self.audio),
            "subtitle_streams": [{"index": s.index, "codec": s.codec_name, "language": s.language,
                                  "title": s.title} for s in self.subtitles],
            "embedded_chapters": len(self.chapters),
            "tags": {k: v for k, v in self.tags.items() if k.lower() in ("title", "artist", "date", "comment", "year")},
        }


def _num(value, cast=float):
    try:
        return cast(value)
    except (TypeError, ValueError):
        return None


def _fps(rate: str | None) -> float | None:
    if not rate or "/" not in rate:
        return _num(rate)
    n, d = rate.split("/", 1)
    n, d = _num(n), _num(d)
    return round(n / d, 3) if n and d else None


def probe(path: str | Path, timeout: int = 60) -> MediaInfo:
    path = Path(path)
    if not path.exists():
        raise RecompError("E_NOT_FOUND", f"no such file: {path}")
    cmd = [ffprobe_bin(), "-v", "error", "-print_format", "json", "-show_format", "-show_streams",
           "-show_chapters", str(path)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, encoding="utf-8",
                           errors="replace", creationflags=CREATE_NO_WINDOW)
    except subprocess.TimeoutExpired as exc:
        raise RecompError("E_TOOL", f"ffprobe timed out on {path.name}") from exc
    if r.returncode != 0:
        raise RecompError("E_TOOL", f"ffprobe could not read {path.name}: {r.stderr.strip()[:300]}")
    data = json.loads(r.stdout or "{}")
    fmt = data.get("format") or {}
    streams = []
    for raw in data.get("streams") or []:
        tags = raw.get("tags") or {}
        streams.append(Stream(
            index=int(raw.get("index", 0)), codec_type=raw.get("codec_type", "?"),
            codec_name=raw.get("codec_name", "?"),
            attached_pic=bool((raw.get("disposition") or {}).get("attached_pic")),
            sample_rate=_num(raw.get("sample_rate"), int), channels=_num(raw.get("channels"), int),
            channel_layout=raw.get("channel_layout", "") or "",
            width=_num(raw.get("width"), int), height=_num(raw.get("height"), int),
            fps=_fps(raw.get("avg_frame_rate") or raw.get("r_frame_rate")),
            language=str(tags.get("language", "")).lower(), title=str(tags.get("title", ""))))
    duration = _num(fmt.get("duration"))
    if duration is None:
        cands = [_num(s.get("duration")) for s in data.get("streams") or []]
        cands = [c for c in cands if c]
        duration = max(cands) if cands else None
    chapters = [{"start": _num(c.get("start_time")), "end": _num(c.get("end_time")),
                 "title": (c.get("tags") or {}).get("title", "")} for c in data.get("chapters") or []]
    return MediaInfo(path=path, duration=round(duration, 3) if duration else None,
                     container=fmt.get("format_name", "?"), size=path.stat().st_size,
                     bit_rate=_num(fmt.get("bit_rate"), int), tags=fmt.get("tags") or {}, streams=streams,
                     chapters=chapters)


_TIME = re.compile(r"out_time_(?:us|ms)=(\d+)")


class Cancelled(Exception):
    pass


def run(args: list[str], duration: float | None = None, progress: Callable[[float, str], None] | None = None,
        cancelled: Callable[[], bool] | None = None, timeout: float | None = None,
        capture_stdout: bool = False) -> subprocess.CompletedProcess:
    """Run ffmpeg with ``-progress``; report fraction done; kill on cancel or timeout."""
    cmd = [ffmpeg_bin(), "-hide_banner", "-nostdin", "-y", "-progress", "pipe:2", "-stats_period", "1"] + args
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE if capture_stdout else subprocess.DEVNULL,
                            stderr=subprocess.PIPE, creationflags=CREATE_NO_WINDOW)
    tail: list[str] = []
    start = time.time()
    last = 0.0
    assert proc.stderr is not None
    chunks: list[bytes] = []
    reader = None
    if capture_stdout and proc.stdout is not None:
        import threading

        def _drain(stream=proc.stdout):
            for block in iter(lambda: stream.read(65536), b""):
                chunks.append(block)

        reader = threading.Thread(target=_drain, daemon=True)
        reader.start()
    for raw in iter(proc.stderr.readline, b""):
        line = raw.decode("utf-8", "replace").rstrip()
        if line and not line.startswith(("frame=", "fps=", "stream_", "bitrate=", "total_size=", "out_time",
                                         "dup_frames", "drop_frames", "speed=", "progress=")):
            tail.append(line)
            tail = tail[-30:]
        m = _TIME.match(line)
        if m and duration and progress:
            secs = int(m.group(1)) / 1e6
            frac = max(0.0, min(1.0, secs / duration))
            if frac - last >= 0.01:
                last = frac
                progress(frac, f"{secs:.0f}/{duration:.0f}s")
        if cancelled and cancelled():
            proc.kill()
            raise Cancelled()
        if timeout and time.time() - start > timeout:
            proc.kill()
            raise RecompError("E_TOOL", f"ffmpeg timed out after {timeout:.0f}s")
    code = proc.wait()
    if reader is not None:
        reader.join(timeout=30)
    out = b"".join(chunks)
    if code != 0:
        raise RecompError("E_TOOL", "ffmpeg failed: " + " | ".join(tail[-6:])[:800],
                          data={"cmd": " ".join(cmd)[:2000]})
    return subprocess.CompletedProcess(cmd, code, out, "\n".join(tail))


def run_simple(args: list[str], timeout: float = 600) -> str:
    """ffmpeg for short tasks where we want stderr text (filters that print to the log)."""
    cmd = [ffmpeg_bin(), "-hide_banner", "-nostdin", "-y"] + args
    r = subprocess.run(cmd, capture_output=True, timeout=timeout, creationflags=CREATE_NO_WINDOW)
    text = r.stderr.decode("utf-8", "replace")
    if r.returncode != 0:
        raise RecompError("E_TOOL", "ffmpeg failed: " + text.strip()[-600:])
    return text
