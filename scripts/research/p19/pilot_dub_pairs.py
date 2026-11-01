"""P19 pilot: what professional dubs do with the source's timing, measured on dual-audio media.

For each title (original audio, dubbed audio, optionally subtitles in both languages) this:

E1  finds the offset between the two audio tracks (envelope cross-correlation) and how much of the shared music and
    effects cancels when one track is subtracted from the other (a cheap way to isolate the dub voice);
E2  transcribes both tracks with word timings (Silero VAD + NeMo Parakeet TDT v3 through sherpa-onnx, CPU) and
    measures the human dub's isochrony: speech overlap, pause compliance, per-utterance duration ratio, speaking rates;
E3  compares the dubbed-language subtitles with what the dub actually says (word edit rate) — the subtitle→dub gap
    that a model would have to learn — with the original-language subtitle vs its ASR as the ASR-error control;
E4  tests the no-training budget model (timing.budget): source run duration × target rate × speaker tempo, against the
    syllables the dub actually spoke in that time, next to the isometric (character count) estimate;
E5  tests a no-training prosodic alignment: given the dub's own words and the source's pause structure, a dynamic
    programme places the breaks by speaking-rate match; scored against where the dubber really paused.

Usage (one title):
    python scripts/research/p19/pilot_dub_pairs.py --src en.wav --dub es.wav --src-lang en --dub-lang es \
        [--src-srt en.srt --dub-srt es.srt] --models DIR --out result.json
Batch: --list titles.tsv (columns: id, src_audio, dub_audio, src_lang, dub_lang, src_srt, dub_srt; '-' for none).
MKV: extract tracks first, e.g. ffmpeg -i film.mkv -map 0:a:0 en.wav -map 0:a:1 es.wav (see README).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import timing as T  # noqa: E402

SR = 16000


# ---- audio ------------------------------------------------------------------------------------------------------

def load(path: str) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768


def envelope(x: np.ndarray, hop: int = 160) -> np.ndarray:
    n = len(x) // hop
    return np.sqrt((x[: n * hop].reshape(n, hop) ** 2).mean(1) + 1e-10)


def track_offset(a: np.ndarray, b: np.ndarray, max_s: float = 5.0) -> tuple[float, float]:
    """Offset of b against a in seconds (positive: b is late) and the peak correlation of their log envelopes."""
    ea, eb = np.log(envelope(a)), np.log(envelope(b))
    n = min(len(ea), len(eb))
    ea, eb = ea[:n] - ea[:n].mean(), eb[:n] - eb[:n].mean()
    lag_max = int(max_s * 100)
    best, best_lag = -1.0, 0
    for lag in range(-lag_max, lag_max + 1):
        x = ea[max(0, -lag): n - max(0, lag)]
        y = eb[max(0, lag): n - max(0, -lag)]
        c = float(np.dot(x, y) / (np.linalg.norm(x) * np.linalg.norm(y) + 1e-9))
        if c > best:
            best, best_lag = c, lag
    return best_lag / 100, best


def fine_offset(a: np.ndarray, b: np.ndarray, coarse: float, search: float = 0.06) -> tuple[float, float]:
    """Sample-accurate offset near ``coarse`` from the waveform cross-correlation (FFT) of the whole overlap."""
    k0 = int(round(coarse * SR))
    w = int(search * SR)
    n = min(len(a), len(b)) - abs(k0) - w
    if n < SR:
        return coarse, 0.0
    x = a[max(0, -k0): max(0, -k0) + n]
    y = b[max(0, k0): max(0, k0) + n + w] if k0 >= 0 else b[: n + w]
    size = 1 << int(np.ceil(np.log2(len(x) + len(y))))
    c = np.fft.irfft(np.fft.rfft(y, size) * np.conj(np.fft.rfft(x, size)), size)
    lags = np.concatenate([c[: w + 1], c[-w:]])
    idx = np.concatenate([np.arange(0, w + 1), np.arange(-w, 0)])
    j = int(np.argmax(np.abs(lags)))
    peak = float(np.abs(lags[j]) / (np.linalg.norm(x) * np.linalg.norm(y[: len(x)]) + 1e-9))
    return float(k0 + idx[j]) / SR, round(peak, 3)


def cancellation(a: np.ndarray, b: np.ndarray, offset: float, quiet: list[tuple[float, float]], taps: int = 64) -> dict:
    """Subtract the aligned, gain-matched original from the dub; energy kept in stretches where neither voice speaks
    (music and effects) vs overall. Low 'kept' = the mixes share their M&E and the voice can be isolated by subtraction."""
    k = int(round(offset * SR))
    if k > 0:
        b = b[k:]
    elif k < 0:
        a = a[-k:]
    n = min(len(a), len(b))
    a, b = a[:n], b[:n]
    g = float(np.dot(a, b) / (np.dot(a, a) + 1e-9))
    mask = np.zeros(n, bool)
    for s, e in quiet:
        mask[int(s * SR): int(e * SR)] = True
    if mask.sum() < SR * 0.5:
        return {"gain": round(g, 3), "quiet_s": round(mask.sum() / SR, 2), "kept_db_gain": None, "kept_db_fir": None}
    d = b - g * a
    kept_g = 10 * np.log10((d[mask] ** 2).mean() / ((b[mask] ** 2).mean() + 1e-12) + 1e-12)
    # A short filter fitted on the quiet stretches (least squares) absorbs EQ and small timing differences in the mixes.
    idx = np.flatnonzero(mask)
    idx = idx[(idx >= taps) & (idx < n - taps)][:: 4]
    half = taps // 2
    A = np.stack([a[idx + k] for k in range(-half, half)], 1)
    h, *_ = np.linalg.lstsq(A, b[idx], rcond=None)
    est = np.convolve(a, h[::-1], mode="same")
    d2 = b - est
    kept_f = 10 * np.log10((d2[mask] ** 2).mean() / ((b[mask] ** 2).mean() + 1e-12) + 1e-12)
    speech = ~mask
    voice_left = 10 * np.log10((d2[speech] ** 2).mean() / ((b[speech] ** 2).mean() + 1e-12) + 1e-12)
    return {"gain": round(g, 3), "quiet_s": round(mask.sum() / SR, 2), "kept_db_gain": round(float(kept_g), 1),
            "kept_db_fir": round(float(kept_f), 1), "speech_kept_db_fir": round(float(voice_left), 1)}


# ---- speech: VAD + ASR with word timings ---------------------------------------------------------------------

class Recogniser:
    def __init__(self, models: Path):
        import sherpa_onnx as so
        m = models / "sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8"
        self.asr = so.OfflineRecognizer.from_transducer(
            encoder=str(m / "encoder.int8.onnx"), decoder=str(m / "decoder.int8.onnx"), joiner=str(m / "joiner.int8.onnx"),
            tokens=str(m / "tokens.txt"), num_threads=4, model_type="nemo_transducer")
        cfg = so.VadModelConfig()
        cfg.silero_vad.model = str(models / "silero_vad.onnx")
        cfg.silero_vad.min_silence_duration = 0.2
        cfg.silero_vad.min_speech_duration = 0.15
        cfg.silero_vad.max_speech_duration = 20
        cfg.sample_rate = SR
        self.vad_cfg = cfg
        self.so = so

    def vad(self, x: np.ndarray) -> list[tuple[float, float]]:
        v = self.so.VoiceActivityDetector(self.vad_cfg, buffer_size_in_seconds=max(30, len(x) / SR + 5))
        w = self.vad_cfg.silero_vad.window_size
        out = []
        for i in range(0, len(x) - w + 1, w):
            v.accept_waveform(x[i: i + w])
            while not v.empty():
                out.append((v.front.start / SR, (v.front.start + len(v.front.samples)) / SR))
                v.pop()
        v.flush()
        while not v.empty():
            out.append((v.front.start / SR, (v.front.start + len(v.front.samples)) / SR))
            v.pop()
        return out

    def words(self, x: np.ndarray, spans: list[tuple[float, float]]) -> list[dict]:
        out = []
        for s, e in spans:
            a, b = max(0, int((s - 0.15) * SR)), min(len(x), int((e + 0.15) * SR))
            st = self.asr.create_stream()
            st.accept_waveform(SR, x[a:b])
            self.asr.decode_stream(st)
            r = st.result
            toks, ts = list(r.tokens), list(r.timestamps)
            durs = list(getattr(r, "durations", []) or [])
            cur = None
            for k, (tok, t) in enumerate(zip(toks, ts)):
                t0 = a / SR + t
                t1 = t0 + (durs[k] if k < len(durs) and durs[k] > 0 else 0.08)
                if (tok.startswith((" ", "▁")) and tok.strip(" ▁")) or cur is None:
                    if cur:
                        out.append(cur)
                    cur = {"text": tok.strip(" ▁"), "start": t0, "end": t1}
                else:
                    cur["text"] += tok
                    cur["end"] = t1
            if cur:
                out.append(cur)
        for w in out:
            w["start"], w["end"] = round(w["start"], 3), round(max(w["end"], w["start"] + 0.04), 3)
        return [w for w in out if w["text"].strip()]


# ---- text -------------------------------------------------------------------------------------------------------

def norm_words(text: str) -> list[str]:
    text = unicodedata.normalize("NFC", text.lower())
    return [w for w in re.sub(r"[^\w\s']", " ", text).split() if w]


def edit_rate(ref: list[str], hyp: list[str]) -> float:
    if not ref:
        return 0.0 if not hyp else 1.0
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        cur = [i] + [0] * len(hyp)
        for j, h in enumerate(hyp, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (r != h))
        prev = cur
    return round(prev[-1] / len(ref), 3)


def srt_cues(path: str) -> list[dict]:
    txt = Path(path).read_text(encoding="utf-8-sig", errors="replace")
    out = []
    for block in re.split(r"\n\s*\n", txt.strip()):
        m = re.search(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)", block)
        if not m:
            continue
        g = [int(v) for v in m.groups()]
        s = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000
        e = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000
        text = " ".join(block[m.end():].split())
        out.append({"start": s, "end": e, "text": re.sub(r"<[^>]+>", "", text)})
    return out


# ---- pairing ----------------------------------------------------------------------------------------------------

def utterances(rs: list[dict], gap: float = 0.5) -> list[dict]:
    """Merge runs into utterances (gaps < ``gap``): the unit at which source and dub lines are paired."""
    out = []
    for r in rs:
        if out and r["start"] - out[-1]["end"] < gap:
            out[-1]["end"] = r["end"]
            out[-1]["runs"].append(r)
        else:
            out.append({"start": r["start"], "end": r["end"], "runs": [r]})
    return out


def pair(src_u: list[dict], dub_u: list[dict], slack: float = 0.3) -> list[tuple[dict, list[dict]]]:
    """Aligned blocks: connected groups of source and dub utterances that overlap in time (±``slack``). Each block is
    returned as (merged source utterance, [dub utterances]); blocks missing either side are dropped."""
    items = [("s", i, u) for i, u in enumerate(src_u)] + [("d", i, u) for i, u in enumerate(dub_u)]
    items.sort(key=lambda x: x[2]["start"])
    blocks, cur, end = [], [], -1e9
    for it in items:
        if cur and it[2]["start"] > end + slack:
            blocks.append(cur)
            cur, end = [], -1e9
        cur.append(it)
        end = max(end, it[2]["end"])
    if cur:
        blocks.append(cur)
    out = []
    for b in blocks:
        ss = [u for k, _, u in b if k == "s"]
        ds = [u for k, _, u in b if k == "d"]
        if ss and ds:
            merged = {"start": ss[0]["start"], "end": ss[-1]["end"], "runs": [r for u in ss for r in u["runs"]]}
            out.append((merged, ds))
    return out


# ---- E5: no-training prosodic alignment ------------------------------------------------------------------------

def place_breaks(words: list[str], lang: str, src_runs: list[dict], tempo: float = 1.0) -> list[int]:
    """Split ``words`` into len(src_runs) contiguous phrases so each phrase's estimated speaking time matches its
    source run (squared log-ratio cost) with a bonus for breaking after punctuation. Returns break indices (the word
    index after which each phrase ends, excluding the last)."""
    k, n = len(src_runs), len(words)
    if k <= 1 or n < k:
        return []
    syl = [T.syllables(w, lang) for w in words]
    cum = np.concatenate([[0.0], np.cumsum(syl)])
    rate = T.rate(lang) * tempo
    durs = [max(0.15, r["dur"]) for r in src_runs]
    INF = 1e18
    cost = np.full((k + 1, n + 1), INF)
    back = np.zeros((k + 1, n + 1), int)
    cost[0, 0] = 0.0
    for p in range(1, k + 1):
        for j in range(p, n - (k - p) + 1):
            bonus = -0.35 if re.search(r"[,.;:!?…]$", words[j - 1]) and p < k else 0.0
            for i in range(p - 1, j):
                if cost[p - 1, i] >= INF:
                    continue
                est = max(0.1, (cum[j] - cum[i]) / rate)
                c = cost[p - 1, i] + np.log(est / durs[p - 1]) ** 2 + bonus
                if c < cost[p, j]:
                    cost[p, j], back[p, j] = c, i
    cuts, j = [], n
    for p in range(k, 0, -1):
        i = back[p, j]
        if p > 1:
            cuts.append(i)
        j = i
    return sorted(c - 1 for c in cuts)


def true_breaks(words: list[dict], k: int) -> list[int]:
    """The dubber's own k−1 longest pauses inside an utterance, as word indices (the word before each pause)."""
    gaps = sorted(((words[i + 1]["start"] - words[i]["end"], i) for i in range(len(words) - 1)), reverse=True)
    return sorted(i for _, i in gaps[: k - 1])


# ---- one title --------------------------------------------------------------------------------------------------

def run_title(rec: Recogniser, t: dict) -> dict:
    src, dub = load(t["src_audio"]), load(t["dub_audio"])
    coarse, corr = track_offset(src, dub)
    off, fine_peak = fine_offset(src, dub, coarse)
    sv, dv = rec.vad(src), rec.vad(dub)
    sw, dw = rec.words(src, sv), rec.words(dub, dv)
    if off:
        for w in dw:
            w["start"], w["end"] = round(w["start"] - off, 3), round(w["end"] - off, 3)
    s_runs, d_runs = T.runs(sw), T.runs(dw)
    s_iv = [(r["start"], r["end"]) for r in s_runs]
    d_iv = [(r["start"], r["end"]) for r in d_runs]
    dur = min(len(src), len(dub)) / SR
    speech = T._merge(s_iv + d_iv)
    quiet, last = [], 0.0
    for a, b in speech:
        if a - last > 0.4:
            quiet.append((last + 0.1, a - 0.1))
        last = b
    if dur - last > 0.4:
        quiet.append((last + 0.1, dur - 0.1))
    res = {"id": t["id"], "duration_s": round(dur, 2),
           "E1_tracks": {"offset_coarse_s": coarse, "offset_s": round(off, 5), "envelope_corr": round(corr, 3),
                         "waveform_peak": fine_peak, **cancellation(src, dub, off, quiet)}}

    su, du = utterances(s_runs), utterances(d_runs)
    pairs = pair(su, du)
    tempo_src = T.tempo(s_runs, t["src_lang"])
    tempo_dub = T.tempo(d_runs, t["dub_lang"])
    dur_pairs = [(s["end"] - s["start"], d[-1]["end"] - d[0]["start"]) for s, d in pairs]
    res["E2_isochrony"] = {
        **T.report(s_iv, d_iv, dur_pairs),
        "pause_compliance_0.25": T.pause_compliance(s_iv, d_iv, 0.25),
        "pairs": len(pairs), "src_utterances": len(su), "dub_utterances": len(du),
        "dub_start_delay_s_median": round(float(np.median([d[0]["start"] - s["start"] for s, d in pairs])), 3) if pairs else None,
        "dub_end_delay_s_median": round(float(np.median([d[-1]["end"] - s["end"] for s, d in pairs])), 3) if pairs else None,
        "duration_ratio_median": round(float(np.median([b / a for a, b in dur_pairs if a > 0])), 3) if dur_pairs else None,
        "rate_src_syl_s": round(sum(T.syllables(r["text"], t["src_lang"]) for r in s_runs) / max(1e-6, sum(r["dur"] for r in s_runs)), 2),
        "rate_dub_syl_s": round(sum(T.syllables(r["text"], t["dub_lang"]) for r in d_runs) / max(1e-6, sum(r["dur"] for r in d_runs)), 2),
        "tempo_src": tempo_src, "tempo_dub": tempo_dub,
    }

    if t.get("dub_srt") and t.get("src_srt"):
        def text_in(words, a, b):
            return " ".join(w["text"] for w in words if w["end"] > a and w["start"] < b)
        d_cues, s_cues = srt_cues(t["dub_srt"]), srt_cues(t["src_srt"])
        d_sub = " ".join(c["text"] for c in d_cues)
        s_sub = " ".join(c["text"] for c in s_cues)
        lo = min(c["start"] for c in d_cues + s_cues)
        hi = max(c["end"] for c in d_cues + s_cues)
        dub_heard, src_heard = text_in(dw, lo, hi), text_in(sw, lo, hi)
        res["E3_subtitle_vs_dub"] = {
            "dub_lang_subtitle_vs_dub_asr_wer": edit_rate(norm_words(dub_heard), norm_words(d_sub)),
            "src_lang_subtitle_vs_src_asr_wer (ASR-error control)": edit_rate(norm_words(src_heard), norm_words(s_sub)),
            "dub_words_spoken": len(norm_words(dub_heard)), "dub_subtitle_words": len(norm_words(d_sub)),
            "src_words_spoken": len(norm_words(src_heard)), "src_subtitle_words": len(norm_words(s_sub)),
            "samples": [{"subtitle": c["text"], "dub_says": text_in(dw, c["start"] - 0.3, c["end"] + 0.3)} for c in d_cues[:12]],
        }

    # E4: budget model vs what the dub said in the same time (per source utterance with a paired dub)
    rows = []
    for s, d in pairs:
        s_text = " ".join(r["text"] for r in s["runs"])
        d_text = " ".join(r["text"] for x in d for r in x["runs"])
        dur_s = s["end"] - s["start"]
        b = T.budget({"dur": dur_s, "pause_after": None, "text": s_text}, t["src_lang"], t["dub_lang"], tempo_src)
        actual = T.syllables(d_text, t["dub_lang"])
        # isometric: same characters as the source → syllables of a dub with that many characters (dub's chars/syl)
        cps = max(1e-6, len(re.sub(r"\W", "", d_text)) / max(1.0, actual))
        iso = len(re.sub(r"\W", "", s_text)) / cps
        flat = dur_s * T.rate(t["dub_lang"])
        rows.append({"src": s_text, "dub": d_text, "dur_s": round(dur_s, 2), "budget": b["syllables"],
                     "flat_rate": round(flat, 1), "isometric": round(iso, 1), "actual": round(actual, 1)})
    if rows:
        def mape(key):
            return round(float(np.mean([abs(r[key] - r["actual"]) / max(1.0, r["actual"]) for r in rows])), 3)
        res["E4_budget"] = {"pairs": len(rows), "mape_tempo_budget": mape("budget"), "mape_flat_rate": mape("flat_rate"),
                            "mape_isometric_chars": mape("isometric"), "rows": rows}

    # E5: break placement (only utterance pairs where both sides have the same number of runs > 1)
    hits = tot = exact = cand = 0
    detail = []
    for s, d in pairs:
        dws = [w for x in d for r in x["runs"] for w in r["words"]]
        k = len(s["runs"])
        d_k = sum(len(x["runs"]) for x in d)
        if k < 2 or d_k != k or len(dws) < k:
            continue
        cand += 1
        pred = place_breaks([w["text"] for w in dws], t["dub_lang"], s["runs"], tempo_src)
        true = true_breaks(dws, k)
        for p_, q in zip(pred, true):
            tot += 1
            hits += abs(p_ - q) <= 1
            exact += p_ == q
        detail.append({"dub": " ".join(w["text"] for w in dws), "pred": pred, "true": true})
    res["E5_breaks"] = {"utterances_same_run_count": cand, "breaks": tot,
                        "exact": round(exact / tot, 3) if tot else None, "within_1_word": round(hits / tot, 3) if tot else None,
                        "detail": detail[:10]}
    res["transcripts"] = {"src": " ".join(w["text"] for w in sw), "dub": " ".join(w["text"] for w in dw)}
    res["words"] = {"src": sw, "dub": dw}
    return res


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", required=True, type=Path)
    ap.add_argument("--src")
    ap.add_argument("--dub")
    ap.add_argument("--src-lang", default="en")
    ap.add_argument("--dub-lang", default="es")
    ap.add_argument("--src-srt")
    ap.add_argument("--dub-srt")
    ap.add_argument("--id", default="title")
    ap.add_argument("--list", type=Path, help="TSV: id, src_audio, dub_audio, src_lang, dub_lang, src_srt, dub_srt")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    titles = []
    if a.list:
        for line in a.list.read_text(encoding="utf-8").splitlines():
            if line.strip() and not line.startswith("#"):
                c = line.split("\t")
                titles.append({"id": c[0], "src_audio": c[1], "dub_audio": c[2], "src_lang": c[3], "dub_lang": c[4],
                               "src_srt": None if c[5] == "-" else c[5], "dub_srt": None if c[6] == "-" else c[6]})
    else:
        titles.append({"id": a.id, "src_audio": a.src, "dub_audio": a.dub, "src_lang": a.src_lang, "dub_lang": a.dub_lang,
                       "src_srt": a.src_srt, "dub_srt": a.dub_srt})
    rec = Recogniser(a.models)
    results = []
    for t in titles:
        print(f"[pilot] {t['id']}", file=sys.stderr)
        results.append(run_title(rec, t))
    a.out.write_text(json.dumps(results, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    for r in results:
        brief = {k: v for k, v in r.items() if k not in ("transcripts", "words")}
        for k in ("E3_subtitle_vs_dub", "E4_budget", "E5_breaks"):
            if k in brief:
                brief[k] = {x: y for x, y in brief[k].items() if x not in ("samples", "rows", "detail")}
        print(json.dumps(brief, ensure_ascii=False, indent=1, default=float))


if __name__ == "__main__":
    main()
