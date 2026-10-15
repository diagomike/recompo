"""Openverse audio search (CC-licensed and public-domain audio from Freesound, Jamendo, ccMixter, …).

No key is needed at low request rates. Every result carries its licence, so credits can be generated
exactly (title, author, source, licence: the TASL attribution rule).
"""

from __future__ import annotations

import httpx

from ..envelope import RecompError

API = "https://api.openverse.org/v1/audio/"
UA = {"User-Agent": "Recomposer/0.1 (+local studio; music search)"}


def licence_name(code: str, version: str | None) -> str:
    code = (code or "").lower()
    if code == "cc0":
        return "CC0 1.0"
    if code == "pdm":
        return "Public Domain Mark 1.0"
    return f"CC {code.upper()} {version or ''}".strip()


def commercial_ok(code: str) -> bool:
    return "nc" not in (code or "").lower().split("-")


def adaptable(code: str) -> bool:
    """Synchronising music to video is an adaptation under CC, so ND licences can't be used as beds."""
    return "nd" not in (code or "").lower().split("-")


SAFE = ("cc0", "by", "pdm")
RANK = {"cc0": 0, "pdm": 0, "by": 1, "by-sa": 2}


def search(query: str, licence: str = "safe", page_size: int = 20, min_s: float | None = None,
           max_s: float | None = None, category: str | None = "music") -> list[dict]:
    """licence: safe (CC0, CC BY, public domain) · commercial (adds BY-SA) · any (includes NC/ND, flagged)."""
    params = {"q": query, "page_size": min(50, max(1, page_size)), "mature": "false"}
    if licence == "safe":
        params["license"] = ",".join(SAFE)
    elif licence == "commercial":
        params["license_type"] = "commercial,modification"
    if category:
        params["category"] = category
    if min_s or max_s:
        params["length"] = "long" if (min_s or 0) >= 600 else ("medium" if (min_s or 0) >= 240 else "")
        if not params["length"]:
            params.pop("length")
    try:
        r = httpx.get(API, params=params, headers=UA, timeout=25)
    except httpx.HTTPError as exc:
        raise RecompError("E_NETWORK", f"Openverse unreachable: {exc}", hint="Check the connection; try again.") from exc
    if r.status_code == 429:
        raise RecompError("E_EXTERNAL", "Openverse rate limit (429)", hint="Wait a minute and search again.")
    if r.status_code != 200:
        raise RecompError("E_EXTERNAL", f"Openverse answered {r.status_code}")
    out = []
    for x in r.json().get("results", []):
        dur = (x.get("duration") or 0) / 1000.0
        if min_s and dur and dur < min_s:
            continue
        if max_s and dur and dur > max_s:
            continue
        lic = licence_name(x.get("license"), x.get("license_version"))
        out.append({
            "provider": "openverse", "id": x["id"], "title": x.get("title") or "untitled",
            "artist": x.get("creator") or "", "licence": lic, "licence_code": x.get("license"),
            "licence_url": x.get("license_url") or "", "commercial_ok": commercial_ok(x.get("license")),
            "usable_as_bed": adaptable(x.get("license")),
            "note": ("share-alike: the video must carry the same licence" if "sa" in (x.get("license") or "").split("-")
                     else "no derivatives: cannot be laid under video" if not adaptable(x.get("license"))
                     else "non-commercial only" if not commercial_ok(x.get("license")) else ""),
            "duration": round(dur, 1) if dur else None, "source": x.get("source") or x.get("provider"),
            "url": x.get("url"), "page_url": x.get("foreign_landing_url") or "",
            "tags": [t.get("name") for t in (x.get("tags") or [])][:8], "filetype": x.get("filetype"),
            "attribution": x.get("attribution") or "",
        })
    out.sort(key=lambda r: RANK.get(r["licence_code"], 5))
    return out


def detail(audio_id: str) -> dict:
    r = httpx.get(API + audio_id + "/", headers=UA, timeout=25)
    if r.status_code != 200:
        raise RecompError("E_NOT_FOUND", f"Openverse audio {audio_id} not found ({r.status_code})")
    x = r.json()
    dur = (x.get("duration") or 0) / 1000.0
    return {"provider": "openverse", "id": x["id"], "title": x.get("title") or "untitled", "artist": x.get("creator") or "",
            "licence": licence_name(x.get("license"), x.get("license_version")), "licence_code": x.get("license"),
            "licence_url": x.get("license_url") or "", "duration": round(dur, 1) if dur else None, "url": x.get("url"),
            "page_url": x.get("foreign_landing_url") or "", "source": x.get("source"),
            "attribution": x.get("attribution") or "", "filetype": x.get("filetype")}


def download(url: str, dest) -> int:
    try:
        with httpx.stream("GET", url, headers=UA, timeout=60, follow_redirects=True) as r:
            if r.status_code != 200:
                raise RecompError("E_EXTERNAL", f"download failed: HTTP {r.status_code}")
            n = 0
            with open(dest, "wb") as f:
                for chunk in r.iter_bytes(65536):
                    f.write(chunk)
                    n += len(chunk)
            return n
    except httpx.HTTPError as exc:
        raise RecompError("E_NETWORK", f"download failed: {exc}") from exc
