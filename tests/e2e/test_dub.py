"""Translation and dubbing with a stub voice (tones): offline, fast."""

import subprocess

import numpy as np
import pytest

from tests.media import copy_clip

pytestmark = pytest.mark.e2e


def tone_share(video, a, b, f0=520.0):
    """Share of spectral energy near the stub voice's 520 Hz tone."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(a), "-t", str(b - a), "-i", str(video), "-map", "0:a:0",
                          "-ac", "1", "-ar", "16000", "-f", "s16le", "-"], capture_output=True).stdout
    x = np.frombuffer(raw, dtype="<i2").astype("float32") / 32768
    spec = np.abs(np.fft.rfft(x)) ** 2
    freqs = np.fft.rfftfreq(len(x), 1 / 16000)
    band = (freqs > f0 - 15) & (freqs < f0 + 15)
    return float(spec[band].sum() / (spec.sum() + 1e-12))


@pytest.fixture
def dproj(proj, tmp_path, OK, monkeypatch):
    monkeypatch.setenv("RECOMP_JOBS", "inline")
    monkeypatch.setenv("RECOMP_TTS", "stub")
    monkeypatch.setenv("RECOMP_DUB_ROUNDTRIP", "0")
    clip = copy_clip(tmp_path / "media", "clip.mp4")
    OK("source.add", {"target": str(clip), "jobs": ["audio"]}, proj)
    OK("cut.add", {"ref": "S1", "from": "11.8", "to": "17.0", "snap": "none", "why": "w"}, proj)
    OK("cut.add", {"ref": "S1", "from": "1.8", "to": "6.5", "snap": "none", "why": "w"}, proj)
    OK("journey.new", {"title": "Heroes", "cuts": ["C1", "C2"]}, proj)
    OK("overlay.add", {"target": "J1#1", "kind": "quote", "text": "Live long enough"}, proj)
    return proj


def test_template_translate_and_coverage(dproj, OK):
    t = OK("lang.translate", {"journey": "J1", "to": "fr", "template": True}, dproj)
    keys = [l["key"] for l in t["lines"]]
    assert keys[0] == "title" and any(k.startswith("seg:") for k in keys) and any(k.startswith("ovl:") for k in keys)
    assert all("max_chars" in l for l in t["lines"] if l["key"].startswith("seg:"))
    fr = {"title": "Héros", "ovl:O1": "Vivre assez longtemps"}
    for l in t["lines"]:
        if l["key"].startswith("seg:"):
            fr[l["key"]] = "FR " + l["text"]
    w = OK("lang.translate", {"journey": "J1", "to": "fr", "translations": fr}, dproj)
    assert w["coverage"] == f"{len(keys)}/{len(keys)}"
    st = OK("lang.status", {"journey": "J1"}, dproj)
    assert st["languages"]["fr"]["complete"] is True


def test_dubbed_export_language_track_and_captions(dproj, OK):
    t = OK("lang.translate", {"journey": "J1", "to": "fr", "template": True}, dproj)
    OK("lang.translate", {"journey": "J1", "to": "fr",
                          "translations": {l["key"]: "Bonjour " + l["text"] for l in t["lines"]}}, dproj)
    res = OK("export.run", {"journey": "J1", "profiles": ["landscape"], "langs": ["en", "fr"]}, dproj)
    by_lang = {e["lang"]: e["export"] for e in res["exports"]}
    en = OK("export.show", {"ref": by_lang["en"]}, dproj)
    fr = OK("export.show", {"ref": by_lang["fr"]}, dproj)
    assert en["status"] == "done" and fr["status"] == "done", fr["checks"]
    tags = {c["check"]: c["detail"] for c in fr["checks"]}
    assert tags["audio language tag"] == "fra" and "dub fit" in tags
    srt = (__import__("pathlib").Path(fr["folder"]) / "captions.srt").read_text(encoding="utf-8")
    assert "Bonjour" in srt
    ass = (__import__("pathlib").Path(fr["folder"]) / "overlay.ass").read_text(encoding="utf-8")
    assert "Vivre" not in ass and "Bonjour Live long enough" in ass  # overlay translated
    # The dub is there: the French render differs from the English one where the voice plays.
    assert tone_share(fr["video"], 0.3, 3.0) > 0.2 > tone_share(en["video"], 0.3, 3.0)


def test_untranslated_language_is_reported(dproj, OK):
    res = OK("export.run", {"journey": "J1", "profiles": ["landscape"], "langs": ["sw"]}, dproj)
    x = OK("export.show", {"ref": res["exports"][0]["export"]}, dproj)
    assert x["status"] in ("failed", "done-with-problems") or x.get("error")
