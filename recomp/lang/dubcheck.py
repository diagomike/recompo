"""Round-trip intelligibility of a dub: transcribe the dub track and compare it with the text voiced.

Whisper (WER) for languages it handles well; Ethio-ASR (character CTC, CER) for Amharic. The score
says whether a listener could follow the dub, not whether the translation is good.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

from ..media import ff

CTC_MODELS = {"am": "badrex/Ethio-ASR-amharic"}
WHISPER_OK = {"en", "fr", "es", "de", "it", "pt", "sw", "ar", "so", "nl", "ru", "tr", "hi"}
LIMIT = 0.35


def _norm_words(text: str) -> list[str]:
    text = unicodedata.normalize("NFC", text.lower())
    text = re.sub(r"[^\w\s']", " ", text)
    return [w for w in text.split() if w]


def _chars(text: str) -> list[str]:
    return [c for c in unicodedata.normalize("NFC", text) if c.isalnum()]


def edit_rate(ref: list[str], hyp: list[str]) -> float:
    if not ref:
        return 0.0 if not hyp else 1.0
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, start=1):
        cur = [i] + [0] * len(hyp)
        for j, h in enumerate(hyp, start=1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (r != h))
        prev = cur
    return round(prev[-1] / len(ref), 3)


def check(folder: Path, plan: dict, log=print) -> dict | None:
    dub = plan.get("dub")
    lang = (plan.get("lang") or "")[:2]
    text = plan.get("_dub_text") or ""
    if not dub or not text:
        return None
    if lang in CTC_MODELS:
        engine, model, metric = "ctc", CTC_MODELS[lang], "CER"
    elif lang in WHISPER_OK:
        from ..core import config
        engine, model, metric = "whisper", config.get("worker.asr_model"), "WER"
    else:
        return {"check": "dub intelligibility", "ok": True, "detail": f"no recogniser for {lang}; listen to it"}
    wav = folder / "dub16k.wav"
    ff.run_simple(["-i", dub["file"], "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(wav)], timeout=300)
    out = folder / "dub_asr.json"
    from ..workers.worker_env import run_script
    run_script("asr", ["--wav", str(wav), "--out", str(out), "--model", model, "--engine", engine, "--language", lang])
    hyp = " ".join(s["text"] for s in json.loads(out.read_text(encoding="utf-8"))["segments"])
    if metric == "CER":
        rate = edit_rate(_chars(text), _chars(hyp))
    else:
        rate = edit_rate(_norm_words(text), _norm_words(hyp))
    wav.unlink(missing_ok=True)
    (folder / "dub_roundtrip.txt").write_text(f"VOICED:\n{text}\n\nHEARD ({model}):\n{hyp}\n\n{metric} = {rate}\n",
                                              encoding="utf-8")
    log(f"dub round trip {metric} {rate}")
    return {"check": "dub intelligibility", "ok": rate <= LIMIT, "detail": f"{metric} {rate:.2f} via {model.split('/')[-1]}",
            "rate": rate, "metric": metric}
