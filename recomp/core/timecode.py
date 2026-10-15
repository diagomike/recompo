"""Time parsing and formatting.

Accepted inputs: ``4323.4``, ``01:12:03.4``, ``12:03``, ``72m3.4s``, ``1h2m``, ``90s``,
``00:01:10,592`` (SubRip comma).
"""

from __future__ import annotations

import re

_UNITS = re.compile(r"^(?:(?P<h>\d+(?:\.\d+)?)h)?(?:(?P<m>\d+(?:\.\d+)?)m)?(?:(?P<s>\d+(?:\.\d+)?)s)?$")


class TimecodeError(ValueError):
    pass


def parse(value: str | float | int | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", ".")
    if not text:
        return None
    neg = text.startswith("-")
    if neg:
        text = text[1:]
    try:
        if ":" in text:
            parts = text.split(":")
            if len(parts) > 3:
                raise TimecodeError(f"bad time {value!r}")
            secs = 0.0
            for p in parts:
                secs = secs * 60 + float(p)
            result = secs
        else:
            try:
                result = float(text)
            except ValueError:
                m = _UNITS.match(text)
                if not m or not any(m.groupdict().values()):
                    raise TimecodeError(f"bad time {value!r}") from None
                result = (float(m["h"] or 0) * 3600 + float(m["m"] or 0) * 60 + float(m["s"] or 0))
    except ValueError as exc:
        raise TimecodeError(f"bad time {value!r}") from exc
    return -result if neg else result


def clock(seconds: float | None, decimals: int = 1) -> str:
    """``3723.45`` → ``01:02:03.5`` (always hours, fixed decimals)."""
    if seconds is None:
        return ""
    neg = seconds < 0
    s = abs(seconds)
    scale = 10 ** decimals
    total = int(s * scale + 0.5 + 1e-9)
    whole, frac = divmod(total, scale)
    h, rem = divmod(whole, 3600)
    m, sec = divmod(rem, 60)
    out = f"{h:02d}:{m:02d}:{sec:02d}"
    if decimals:
        out += "." + str(frac).rjust(decimals, "0")
    return ("-" if neg else "") + out


def srt_clock(seconds: float) -> str:
    total_ms = max(0, round(seconds * 1000))
    whole, ms = divmod(total_ms, 1000)
    h, rem = divmod(whole, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def ass_clock(seconds: float) -> str:
    total_cs = max(0, round(seconds * 100))
    whole, cs = divmod(total_cs, 100)
    h, rem = divmod(whole, 3600)
    m, s = divmod(rem, 60)
    return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"


def span(start: float, end: float) -> dict:
    return {"start": round(start, 3), "end": round(end, 3), "dur": round(end - start, 3),
            "clock": f"{clock(start)}–{clock(end)}"}
