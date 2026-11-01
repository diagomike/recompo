"""All timed-rephrasal conditions in one table: the LLM-loop rounds plus the trained duration-aware NMT, scored on
the same German speaker frames with the text ruler, a real TTS voice, and chrF (as written, and normalised:
lower case, no punctuation, since the trained model's phoneme→word output has neither).

    python wt_compare_all.py --frames frames.json --iwslt IWSLT --llm cands.json --tmt cands_tmt.json \
        --ruler ruler.json --voice VOICE_DIR --out compare.json
"""
import argparse, json, re, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import bench as B  # noqa: E402
from wt_llm_loop import load_ruler, place  # noqa: E402

ap = argparse.ArgumentParser()
for k in ("frames", "iwslt", "llm", "tmt", "ruler", "voice", "out"):
    ap.add_argument("--" + k, type=Path, required=True)
a = ap.parse_args()
frames = json.loads(a.frames.read_text(encoding="utf-8"))
conds = json.loads(a.llm.read_text(encoding="utf-8"))
tmt = json.loads(a.tmt.read_text(encoding="utf-8"))
conds["TRAINED_MT"] = tmt["TRAINED_MT"]
dur, _ = load_ruler(a.ruler)
refs = {}
for sub in ("subset1", "subset2"):
    for k, line in enumerate((a.iwslt / "data/test" / f"{sub}.en").read_text(encoding="utf-8").splitlines()):
        refs[f"{sub}-{k}"] = line
ids = list(conds["R0"].keys())
items = [{"id": i, "en": refs[i], "segments": frames[i]["segments"]} for i in ids]
conds["R0+place"] = {i: place(" ".join(v).split(), [s["dur"] for s in frames[i]["segments"]], dur) for i, v in conds["R0"].items()}
conds["REF"] = {it["id"]: place(it["en"].split(), [s["dur"] for s in it["segments"]], dur) for it in items}
norm = lambda t: re.sub(r"\s+", " ", re.sub(r"[^\w\s']", " ", t.lower())).strip()  # noqa: E731
res = {}
for c, outs in conds.items():
    r = B.summary(items, outs, dur)
    r["chrF_normalised"] = B.chrf([norm(" ".join(outs[i])) for i in ids], [norm(refs[i]) for i in ids])
    res[c] = {"ruler": r}
# model's own predicted durations (frames) against the real segments
own = tmt["_model_durations_s"]
rows = [B.score_item(it, ["x"] * len(own[it["id"]]), lambda t, _d=iter([]): 0.0) for it in items[:0]]
ov = []
for it in items:
    segs, d = it["segments"], own[it["id"]]
    hyp = [(s["start"], s["start"] + x) for s, x in zip(segs, d) if x > 0]
    ref = [(s["start"], s["end"]) for s in segs]
    union = sum(b - a_ for a_, b in B._merge(ref + hyp))
    ov.append(B._inter(ref, hyp) / union if union else 0)
res["TRAINED_MT"]["model_own_durations_speech_overlap"] = round(sum(ov) / len(ov), 4)
results = {"summary": {}, "detail": {i: {c: {"phrases": conds[c][i]} for c in conds} for i in ids}}
tmp = a.out.with_suffix(".detail.json")
tmp.write_text(json.dumps(results, ensure_ascii=False), encoding="utf-8")
voice = subprocess.run([sys.executable, str(Path(__file__).parent / "wt_tts_check.py"), "--frames", str(a.frames),
                        "--results", str(tmp), "--voice", str(a.voice), "--out", str(a.out.with_suffix(".tts.json"))],
                       capture_output=True, text=True)
tts = json.loads(a.out.with_suffix(".tts.json").read_text())
for c in res:
    res[c]["voice"] = tts.get(c)
a.out.write_text(json.dumps(res, indent=1), encoding="utf-8")
for c, v in res.items():
    r, t = v["ruler"], v["voice"] or {}
    print(f"{c:12s} ruler_ov={r['speech_overlap']:.3f} voice_ov={t.get('speech_overlap', 0):.3f} "
          f"voice±20%={t.get('slc_0.2', 0):.2f} speedup>1.1={t.get('segments_needing_speedup_over_1.1x', 0):.2f} "
          f"chrF={r['chrF']:.1f} chrF_norm={r['chrF_normalised']:.1f}")
print("trained-mt own durations overlap:", res["TRAINED_MT"]["model_own_durations_speech_overlap"])
