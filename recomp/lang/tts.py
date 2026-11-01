"""Text-to-speech backends: edge (Microsoft neural voices over the network), sapi (Windows, offline),
mms (Meta MMS-TTS VITS models under the worker python, e.g. Afaan Oromo), and a test stub.

Every backend writes a 48 kHz mono WAV and returns its duration.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path

from ..core import config
from ..envelope import RecompError
from ..media import ff

SAPI_VOICES = {"en": "Microsoft Zira Desktop", "fr": "Microsoft Hortense Desktop"}


# MMS-TTS (offline VITS voices, facebook/mms-tts-<ISO 639-3>) for the languages the dub most often goes into.
MMS_ISO3 = {"am": "amh", "om": "orm", "ti": "tir", "so": "som", "sw": "swh", "en": "eng", "fr": "fra", "es": "spa",
            "de": "deu", "pt": "por", "it": "ita", "nl": "nld", "ar": "ara", "ha": "hau", "yo": "yor", "ig": "ibo",
            "zu": "zul", "rw": "kin", "lg": "lug", "ru": "rus", "uk": "ukr", "tr": "tur", "hi": "hin", "vi": "vie",
            "id": "ind", "fa": "fas", "pl": "pol", "ro": "ron", "el": "ell", "he": "heb"}


def is_online(online: bool | None = None) -> bool:
    """Network voices (edge) are used only when the dub is allowed online (`dub.online`, default off)."""
    return bool(config.get("dub.online", False)) if online is None else bool(online)


def voice_for(lang: str, voice: str | None = None, online: bool | None = None) -> tuple[str, str]:
    """(backend, voice) for a language. Offline (the default): a configured MMS voice, else MMS-TTS for the
    language. Online: the configured edge neural voice first. An explicit ``voice`` wins (edge ones need online)."""
    on = is_online(online)
    if voice:
        if voice.startswith("mms:"):
            return "mms", voice[4:]
        if voice.startswith("sapi:"):
            return "sapi", voice[5:]
        if voice == "stub":
            return "stub", "stub"
        if not on:
            raise RecompError("E_OFFLINE", f"{voice} is an online (edge) voice and the dub is offline",
                              hint="Use an MMS voice (mms:facebook/mms-tts-<iso3>), or allow online voices: "
                                   "`recomp dub settings --at studio --online true`")
        return "edge", voice
    if os.environ.get("RECOMP_TTS") == "stub":
        return "stub", "stub"
    tts = config.get("tts") or {}
    if on and lang in (tts.get("voices") or {}):
        return "edge", tts["voices"][lang]
    if lang in (tts.get("mms") or {}):
        return "mms", tts["mms"][lang]
    if lang in MMS_ISO3:
        return "mms", f"facebook/mms-tts-{MMS_ISO3[lang]}"
    if lang in SAPI_VOICES and os.name == "nt":
        return "sapi", SAPI_VOICES[lang]
    if not on and lang in (tts.get("voices") or {}):
        raise RecompError("E_OFFLINE", f"no offline voice for {lang!r} (its configured voice is online)",
                          hint=f"`recomp config set tts.mms.{lang} facebook/mms-tts-<iso3>`, or allow online voices: "
                               "`recomp dub settings --at studio --online true`")
    raise RecompError("E_NOT_FOUND", f"no voice configured for {lang!r}",
                      hint=f"`recomp config set tts.mms.{lang} facebook/mms-tts-<iso3>` (offline) or "
                           f"`recomp config set tts.voices.{lang} <edge voice>` (online)")


def _to_wav48(src: Path, dest: Path) -> float:
    ff.run_simple(["-i", str(src), "-ac", "1", "-ar", "48000", "-c:a", "pcm_s16le", str(dest)], timeout=120)
    return ff.probe(dest).duration or 0.0


def synth(text: str, lang: str, dest: Path, voice: str | None = None, rate_pct: int = 0, online: bool | None = None) -> float:
    backend, v = voice_for(lang, voice, online)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if backend == "edge":
        import edge_tts
        tmp = dest.with_suffix(".mp3")
        rate = f"{rate_pct:+d}%"

        async def go():
            await edge_tts.Communicate(text, v, rate=rate).save(str(tmp))

        last = None
        for _ in range(3):
            try:
                asyncio.run(go())
                if tmp.exists() and tmp.stat().st_size > 500:
                    break
            except Exception as exc:  # noqa: BLE001
                last = exc
        else:
            raise RecompError("E_NETWORK", f"edge-tts failed for {v}: {last}",
                              hint="edge-tts needs speech.platform.bing.com (and edge-tts >= 7.3.1)")
        dur = _to_wav48(tmp, dest)
        tmp.unlink(missing_ok=True)
        return dur
    if backend == "sapi":
        tmp = dest.with_suffix(".sapi.wav")
        safe = text.replace('"', "'")
        rate = max(-10, min(10, round(rate_pct / 10)))
        ps = ("Add-Type -AssemblyName System.Speech;$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
              f"try {{ $s.SelectVoice('{v}') }} catch {{}};$s.Rate={rate};$s.SetOutputToWaveFile('{tmp}');"
              f"$s.Speak(\"{safe}\");$s.Dispose()")
        subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, timeout=120)
        if not tmp.exists():
            raise RecompError("E_TOOL", "Windows speech synthesis failed")
        dur = _to_wav48(tmp, dest)
        tmp.unlink(missing_ok=True)
        return dur
    if backend == "mms":
        from ..workers.worker_env import run_script
        tmp = dest.with_suffix(".mms.wav")
        run_script("tts_mms", ["--model", v, "--text", text, "--out", str(tmp)],
                   allow_download=bool(config.get("tts.allow_download")))
        dur = _to_wav48(tmp, dest)
        tmp.unlink(missing_ok=True)
        return dur
    # stub: a tone whose length follows the text (tests, offline dry runs)
    secs = max(0.4, len(text) / 15.0) / (1 + rate_pct / 100)
    ff.run_simple(["-f", "lavfi", "-i", f"sine=f=520:d={secs:.3f}:sample_rate=48000", "-ac", "1", "-c:a", "pcm_s16le",
                   str(dest)], timeout=60)
    return secs


def synth_batch(items: list[tuple[str, Path]], lang: str, voice: str | None = None, online: bool | None = None) -> None:
    """Voice many lines at once (MMS loads its model once); other backends fall back to one call per line."""
    backend, v = voice_for(lang, voice, online)
    todo = [(t, p) for t, p in items if not p.exists()]
    if not todo:
        return
    if backend != "mms":
        for t, p in todo:
            synth(t, lang, p, voice=voice, online=online)
        return
    import json
    import tempfile
    from ..workers.worker_env import run_script
    with tempfile.TemporaryDirectory() as tmpd:
        jobs = [{"text": t, "out": str(Path(tmpd) / f"{k}.wav")} for k, (t, _) in enumerate(todo)]
        jf = Path(tmpd) / "batch.json"
        jf.write_text(json.dumps(jobs, ensure_ascii=False), encoding="utf-8")
        run_script("tts_mms", ["--model", v, "--batch", str(jf)], allow_download=bool(config.get("tts.allow_download")))
        for j, (_, p) in zip(jobs, todo):
            p.parent.mkdir(parents=True, exist_ok=True)
            _to_wav48(Path(j["out"]), p)


def edge_voices(lang: str) -> list[dict]:
    import edge_tts

    async def go():
        return await edge_tts.list_voices()

    try:
        allv = asyncio.run(go())
    except Exception as exc:  # noqa: BLE001
        raise RecompError("E_NETWORK", f"could not list edge voices: {exc}") from exc
    return [{"voice": v["ShortName"], "gender": v.get("Gender"), "locale": v.get("Locale")}
            for v in allv if v["Locale"].lower().startswith(lang.lower() + "-")]
