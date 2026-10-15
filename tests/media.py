"""Shared access to generated fixture media."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from scripts.make_fixtures import OUT, colour_for_second, make  # noqa: F401

_info = None


def fixtures() -> dict:
    global _info
    if _info is None:
        if not shutil.which("ffmpeg"):
            pytest.skip("ffmpeg not available")
        _info = make()
    return _info


def copy_clip(dest_dir: Path, name: str = "clip.mp4", with_srt: bool = True, srt: str = "clip.srt") -> Path:
    fixtures()
    dest_dir.mkdir(parents=True, exist_ok=True)
    dst = dest_dir / name
    shutil.copy(OUT / name, dst)
    if with_srt:
        shutil.copy(OUT / srt, dst.with_suffix(".srt"))
    return dst
