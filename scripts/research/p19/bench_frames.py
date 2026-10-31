"""Timing frames for the P19 bench: the German speaker's speech segments (pauses ≥ 0.3 s) in each IWSLT test
recording, from Silero VAD, with a Parakeet transcript to confirm the recording matches its line.

    python scripts/research/p19/bench_frames.py --iwslt IWSLT_DIR --models MODELS_DIR --out frames.json
"""
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from pilot_dub_pairs import Recogniser, load, SR  # noqa: E402
import timing as T  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--iwslt", type=Path, required=True)
ap.add_argument("--models", type=Path, required=True)
ap.add_argument("--out", type=Path, required=True)
a = ap.parse_args()
rec = Recogniser(a.models)
rec.vad_cfg.silero_vad.min_silence_duration = 0.3
rec.vad_cfg.silero_vad.min_speech_duration = 0.1
out = {}
for subset in ("subset1", "subset2"):
    de = (a.iwslt / "data/test" / f"{subset}.de").read_text(encoding="utf-8").splitlines()
    for k, line in enumerate(de):
        wav = a.iwslt / "x" / f"{subset}.{k + 1}.wav"
        if not wav.exists():
            continue
        x = load(str(wav))
        spans = rec.vad(x)
        words = rec.words(x, spans)
        heard = " ".join(w["text"] for w in words)
        segs = [{"start": round(s, 3), "end": round(e, 3), "dur": round(e - s, 3)} for s, e in spans]
        for i, s in enumerate(segs):
            s["pause_after"] = round(segs[i + 1]["start"] - s["end"], 3) if i + 1 < len(segs) else None
        out[f"{subset}-{k}"] = {"de": line, "heard": heard, "segments": segs,
                                "match": T.syllables(heard, "de") / max(1, T.syllables(line.replace("[pause]", ""), "de"))}
        print(f"{subset}-{k} segs={len(segs)} pauses_in_text={line.count('[pause]')} match={out[f'{subset}-{k}']['match']:.2f}", file=sys.stderr)
a.out.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
