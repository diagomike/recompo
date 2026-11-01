"""P19 worktree `llm-multiround`: multi-round LLM refinement of timed lines against the real voice.

Each round: synthesize every segment with the voice (VITS LJSpeech via sherpa-onnx; durations cached on disk so every
round is measured with the same numbers), flag segments outside the band (voice / segment between --lo and --hi),
and show them with the German line and the plain translation, so the LLM revises only those — shortening overruns,
filling gaps, and putting back the plain translation's wording where padding is no longer needed.

    python wt_multiround.py sheet  --frames F --cands C --round R4 --voice V --cache cache.json [--all]
    python wt_multiround.py curve  --frames F --cands C --rounds R0+place,R1,R2,R3,R4 --voice V --cache cache.json
"""
import argparse, json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent))
import bench as B  # noqa: E402


class Voice:
    def __init__(self, vdir: Path, cache: Path):
        import sherpa_onnx as so
        kw = {"model": str(next(vdir.glob("*.onnx"))), "tokens": str(vdir / "tokens.txt")}
        if (vdir / "lexicon.txt").exists():
            kw["lexicon"] = str(vdir / "lexicon.txt")
        self.chars = "lexicon" not in kw  # MMS voices read characters: lower case, no punctuation
        vits = so.OfflineTtsVitsModelConfig(**kw)
        self.tts = so.OfflineTts(so.OfflineTtsConfig(model=so.OfflineTtsModelConfig(vits=vits, num_threads=4)))
        self.path = cache
        self.cache = json.loads(cache.read_text()) if cache.exists() else {}

    def __call__(self, text: str) -> float:
        t = text.strip()
        if not t:
            return 0.0
        if t not in self.cache:
            say = " ".join(__import__("re").sub(r"[^\w\s']", " ", t.lower()).split()) if self.chars else t
            au = self.tts.generate(say, sid=0, speed=1.0)
            x = np.abs(np.array(au.samples, dtype=np.float32))
            idx = np.flatnonzero(x > 0.02 * x.max()) if x.size else []
            self.cache[t] = round(float((idx[-1] - idx[0]) / au.sample_rate), 3) if len(idx) else 0.0
        return self.cache[t]

    def save(self):
        self.path.write_text(json.dumps(self.cache, ensure_ascii=False))


def rounds_of(cands: dict, frames: dict, names: list[str]):
    from wt_llm_loop import load_ruler, place  # noqa
    out = {}
    for n in names:
        if n == "R0+place":
            ruler, _ = load_ruler(RULER)
            out[n] = {i: place(" ".join(v).split(), [s["dur"] for s in frames[i]["segments"]], ruler)
                      for i, v in cands["R0"].items()}
        else:
            out[n] = cands[n]
    return out


RULER = None


def main():
    global RULER
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["sheet", "curve"])
    for k in ("frames", "cands", "voice", "cache"):
        ap.add_argument("--" + k, type=Path, required=True)
    ap.add_argument("--ruler", type=Path)
    ap.add_argument("--round", default="R3")
    ap.add_argument("--rounds", default="R3")
    ap.add_argument("--lo", type=float, default=0.8)
    ap.add_argument("--hi", type=float, default=1.05)
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    RULER = a.ruler
    frames = json.loads(a.frames.read_text(encoding="utf-8"))
    cands = json.loads(a.cands.read_text(encoding="utf-8"))
    v = Voice(a.voice, a.cache)
    if a.cmd == "sheet":
        cur = cands[a.round]
        n_out = 0
        for i, phrases in cur.items():
            segs = frames[i]["segments"]
            rows, flag = [], False
            for k, (s, t) in enumerate(zip(segs, phrases + [""] * len(segs))):
                r = v(t) / s["dur"] if t.strip() else 0.0
                bad = not (a.lo <= r <= a.hi) and not (not t.strip() and s["dur"] < 0.3)
                flag |= bad
                n_out += bad
                rows.append(f"  [{k + 1}] {s['dur']:.2f}s voice×{r:.2f}{' ◀' if bad else ''}: {t}")
            if flag or a.all:
                print(f"{i} | DE: {frames[i]['de'].replace(' [pause]', '')}\n  PLAIN: {' '.join(cands['R0'][i])}\n" + "\n".join(rows))
        print(f"# {n_out} segments outside {a.lo}–{a.hi}", file=sys.stderr)
    else:
        allr = rounds_of(cands, frames, a.rounds.split(","))
        ids = list(cands["R0"])
        for n, outs in allr.items():
            ratios, ov = [], []
            for i in ids:
                item = {"id": i, "segments": frames[i]["segments"]}
                ov.append(B.score_item(item, outs[i], v)["speech_overlap"])
                for s, t in zip(frames[i]["segments"], outs[i]):
                    if t.strip():
                        ratios.append(v(t) / s["dur"])
            r = np.array(ratios)
            print(json.dumps({"round": n, "voice_overlap": round(float(np.mean(ov)), 4),
                              "in_band": round(float(((r >= a.lo) & (r <= a.hi)).mean()), 3),
                              "over_1.05": round(float((r > 1.05).mean()), 3), "over_1.1": round(float((r > 1.1).mean()), 3),
                              "under_0.8": round(float((r < 0.8).mean()), 3), "median": round(float(np.median(r)), 3)}))
    v.save()


if __name__ == "__main__":
    main()
