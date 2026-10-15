"""Speech recognition, run under the *worker python* (faster-whisper or a Hugging Face CTC model).

Standalone on purpose: it imports nothing from ``recomp`` so it runs in any environment that has
faster-whisper (and optionally transformers). Progress is printed as JSON lines on stdout.

    python asr.py --wav audio16k.wav --out result.json [--model REPO_OR_PATH] [--language en]
                  [--ranges 10-70,300-360] [--threads 0] [--compute-type int8] [--engine whisper|ctc]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import wave

import numpy as np

SR = 16000


def say(**kw):
    sys.stdout.write(json.dumps(kw, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def load_wav(path: str, start: float = 0.0, end: float | None = None) -> np.ndarray:
    with wave.open(path, "rb") as w:
        sr = w.getframerate()
        n = w.getnframes()
        a = int(start * sr)
        b = n if end is None else min(n, int(end * sr))
        w.setpos(max(0, min(a, n)))
        raw = w.readframes(max(0, b - a))
    if sr != SR:
        raise SystemExit(f"expected {SR} Hz audio, got {sr}")
    return np.frombuffer(raw, dtype="<i2").astype("float32") / 32768.0


def run_whisper(args, audio_parts):
    from faster_whisper import WhisperModel

    t0 = time.time()
    model = WhisperModel(args.model, device="cpu", compute_type=args.compute_type,
                         cpu_threads=args.threads or 0, num_workers=1)
    say(message=f"model loaded in {time.time() - t0:.1f}s")
    total = sum(len(a) for _, a in audio_parts) / SR or 1.0
    done = 0.0
    segments = []
    info_lang = None
    for offset, audio in audio_parts:
        segs, info = model.transcribe(
            audio, language=args.language or None, word_timestamps=True, vad_filter=not args.no_vad,
            vad_parameters={"min_silence_duration_ms": 500}, beam_size=args.beam, condition_on_previous_text=False,
            temperature=0.0)
        info_lang = info_lang or info.language
        for s in segs:
            words = [{"start": round(w.start + offset, 3), "end": round(w.end + offset, 3),
                      "text": w.word.strip(), "prob": round(w.probability, 3)} for w in (s.words or []) if w.word.strip()]
            segments.append({"start": round(s.start + offset, 3), "end": round(s.end + offset, 3),
                             "text": s.text.strip(), "words": words,
                             "conf": round(float(np.exp(s.avg_logprob)), 3) if s.avg_logprob is not None else None})
            say(progress=round(min(0.999, (done + s.end) / total), 4), message=f"{s.end + offset:.0f}s")
        done += len(audio) / SR
    return segments, info_lang


def run_ctc(args, audio_parts):
    """Character CTC model (e.g. badrex/Ethio-ASR-amharic): text per 20-second chunk with word times."""
    import torch
    from transformers import AutoModelForCTC, AutoProcessor

    proc = AutoProcessor.from_pretrained(args.model)
    model = AutoModelForCTC.from_pretrained(args.model).eval()
    torch.set_num_threads(max(1, args.threads or os.cpu_count() or 4))
    segments = []
    total = sum(len(a) for _, a in audio_parts) / SR or 1.0
    done = 0.0
    chunk = 20 * SR
    for offset, audio in audio_parts:
        for i in range(0, len(audio), chunk):
            piece = audio[i:i + chunk]
            if len(piece) < SR // 4:
                continue
            inputs = proc(piece, sampling_rate=SR, return_tensors="pt")
            with torch.no_grad():
                logits = model(**inputs).logits[0]
            ids = logits.argmax(-1).tolist()
            text = proc.decode(ids).strip()
            frame_s = len(piece) / SR / max(1, len(ids))
            start = offset + i / SR
            if text:
                words = []
                # word boundaries from the token stream: a word spans its first to last non-blank frame
                vocab = proc.tokenizer.convert_ids_to_tokens(ids)
                blank = proc.tokenizer.pad_token
                delim = getattr(proc.tokenizer, "word_delimiter_token", "|")
                cur, cur_a, cur_b = "", None, None
                prev = None
                for f, tok in enumerate(vocab):
                    if tok == prev:
                        cur_b = f
                        continue
                    prev = tok
                    if tok == blank:
                        continue
                    if tok == delim:
                        if cur:
                            words.append({"start": round(start + cur_a * frame_s, 3),
                                          "end": round(start + (cur_b + 1) * frame_s, 3), "text": cur})
                        cur, cur_a = "", None
                        continue
                    if cur_a is None:
                        cur_a = f
                    cur_b = f
                    cur += tok
                if cur:
                    words.append({"start": round(start + cur_a * frame_s, 3),
                                  "end": round(start + (cur_b + 1) * frame_s, 3), "text": cur})
                segments.append({"start": round(start, 3), "end": round(start + len(piece) / SR, 3),
                                  "text": text, "words": words})
            say(progress=round(min(0.999, (done + (i + len(piece)) / SR) / total), 4))
        done += len(audio) / SR
    return segments, args.language


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--wav", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--model", default="mobiuslabsgmbh/faster-whisper-large-v3-turbo")
    p.add_argument("--engine", default="whisper", choices=["whisper", "ctc"])
    p.add_argument("--language", default=None)
    p.add_argument("--ranges", default="")
    p.add_argument("--threads", type=int, default=0)
    p.add_argument("--compute-type", default="int8")
    p.add_argument("--beam", type=int, default=1)
    p.add_argument("--no-vad", action="store_true")
    args = p.parse_args()
    parts = []
    if args.ranges:
        for r in args.ranges.split(","):
            a, b = (float(x) for x in r.split("-"))
            parts.append((a, load_wav(args.wav, a, b)))
    else:
        parts.append((0.0, load_wav(args.wav)))
    t0 = time.time()
    segments, lang = (run_ctc if args.engine == "ctc" else run_whisper)(args, parts)
    audio_s = sum(len(a) for _, a in parts) / SR
    result = {"segments": segments, "language": lang, "model": args.model, "engine": args.engine,
              "audio_s": round(audio_s, 1), "elapsed_s": round(time.time() - t0, 1),
              "ranges": [[o, o + len(a) / SR] for o, a in parts]}
    tmp = args.out + ".part"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False)
    os.replace(tmp, args.out)
    say(progress=1.0, message="done", segments=len(segments), elapsed_s=result["elapsed_s"])


if __name__ == "__main__":
    main()
