"""P19 corpus inventory: what a folder of dual-audio movies holds, before any heavy processing.

For every video file (mkv, mp4, avi, m4v, ts) it reads the streams with ffprobe and records:
- audio tracks: language tag, codec, channels, title (e.g. "Hindi Dub", "Commentary"), duration;
- subtitle tracks: language, **text vs bitmap** (PGS/VobSub need OCR first), forced/SDH flags, title;
- external subtitles next to the file (name.lang.srt);
- which title is a usable pair: ≥ 2 audio languages, and a text subtitle in at least one of them.

It writes `inventory.json` (every stream) and `titles.tsv` (one line per usable pair, the input of
pilot_dub_pairs.py once the tracks are extracted) and prints totals per language pair. Read-only: nothing is
extracted or changed.

    python scripts/research/p19/inventory.py "D:\\Movies" --out inventory_dir [--source-lang en]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

VIDEO = {".mkv", ".mp4", ".avi", ".m4v", ".ts", ".mov", ".webm"}
BITMAP = {"hdmv_pgs_subtitle", "dvd_subtitle", "dvb_subtitle", "xsub"}
SKIP_AUDIO = re.compile(r"comment|descri|audio desc|\bad\b", re.I)
ISO2 = {"eng": "en", "spa": "es", "fre": "fr", "fra": "fr", "ger": "de", "deu": "de", "ita": "it", "por": "pt",
        "hin": "hi", "tam": "ta", "tel": "te", "amh": "am", "orm": "om", "som": "so", "swa": "sw", "tir": "ti",
        "ara": "ar", "rus": "ru", "jpn": "ja", "kor": "ko", "chi": "zh", "zho": "zh", "tur": "tr", "per": "fa",
        "fas": "fa", "urd": "ur", "ben": "bn", "mar": "mr", "pol": "pl", "ukr": "uk", "dut": "nl", "nld": "nl"}


def lang2(tag: str | None) -> str:
    t = (tag or "und").lower()
    return ISO2.get(t, t[:2] if len(t) == 2 else t)


def probe(path: Path) -> dict | None:
    r = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(path)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        return None
    return json.loads(r.stdout or "{}")


def external_subs(path: Path) -> list[dict]:
    out = []
    for p in path.parent.glob(path.stem + "*"):
        if p.suffix.lower() in (".srt", ".ass", ".vtt", ".sub", ".idx", ".sup") and p != path:
            m = re.search(r"\.([a-z]{2,3})(?:\.(?:forced|sdh|cc))?\.\w+$", p.name, re.I)
            out.append({"file": str(p), "lang": lang2(m.group(1)) if m else "und",
                        "bitmap": p.suffix.lower() in (".sub", ".idx", ".sup")})
    return out


def describe(path: Path) -> dict:
    info = probe(path)
    if info is None:
        return {"file": str(path), "error": "ffprobe failed"}
    dur = float((info.get("format") or {}).get("duration") or 0)
    audio, subs = [], []
    for s in info.get("streams", []):
        tags = {k.lower(): v for k, v in (s.get("tags") or {}).items()}
        title = tags.get("title", "")
        disp = s.get("disposition") or {}
        if s.get("codec_type") == "audio":
            audio.append({"index": s["index"], "lang": lang2(tags.get("language")), "codec": s.get("codec_name"),
                          "channels": s.get("channels"), "title": title,
                          "skip": bool(SKIP_AUDIO.search(title)) or bool(disp.get("visual_impaired"))})
        elif s.get("codec_type") == "subtitle":
            subs.append({"index": s["index"], "lang": lang2(tags.get("language")), "codec": s.get("codec_name"),
                         "bitmap": s.get("codec_name") in BITMAP, "forced": bool(disp.get("forced")),
                         "sdh": bool(disp.get("hearing_impaired")) or "sdh" in title.lower(), "title": title})
    return {"file": str(path), "duration_s": round(dur, 1), "audio": audio, "subtitles": subs,
            "external_subtitles": external_subs(path)}


def pairs(d: dict, source_lang: str | None) -> list[dict]:
    langs = []
    for a in d.get("audio", []):
        if not a["skip"] and a["lang"] not in langs:
            langs.append(a["lang"])
    if len(langs) < 2:
        return []
    src = source_lang if source_lang in langs else langs[0]
    text_subs = {s["lang"] for s in d.get("subtitles", []) if not s["bitmap"] and not s["forced"]} | \
                {s["lang"] for s in d.get("external_subtitles", []) if not s["bitmap"]}
    any_subs = text_subs | {s["lang"] for s in d.get("subtitles", []) if s["bitmap"]}
    out = []
    for dub in langs:
        if dub == src:
            continue
        out.append({"src": src, "dub": dub, "src_text_sub": src in text_subs, "dub_text_sub": dub in text_subs,
                    "dub_any_sub": dub in any_subs, "und_tags": "und" in (src, dub)})
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--source-lang", default=None, help="Original language when tags say so (e.g. en)")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in a.root.rglob("*") if p.suffix.lower() in VIDEO)
    if a.limit:
        files = files[: a.limit]
    items, tsv = [], []
    by_pair, hours = Counter(), Counter()
    for k, f in enumerate(files, 1):
        d = describe(f)
        d["pairs"] = pairs(d, a.source_lang)
        items.append(d)
        for p in d["pairs"]:
            key = f"{p['src']}->{p['dub']}"
            by_pair[key] += 1
            hours[key] += d["duration_s"] / 3600
            if p["dub_text_sub"]:
                by_pair[key + " (dub-lang text subs)"] += 1
            tsv.append("\t".join([f.stem, str(f), p["src"], p["dub"], str(p["src_text_sub"]), str(p["dub_text_sub"])]))
        if k % 50 == 0:
            print(f"[inventory] {k}/{len(files)}", file=sys.stderr)
    (a.out / "inventory.json").write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
    (a.out / "titles.tsv").write_text("# id\tfile\tsrc_lang\tdub_lang\tsrc_text_sub\tdub_text_sub\n" + "\n".join(tsv) + "\n",
                                      encoding="utf-8")
    summary = {"files": len(files), "with_pairs": sum(1 for d in items if d.get("pairs")),
               "errors": sum(1 for d in items if d.get("error")),
               "bitmap_only_subs": sum(1 for d in items if d.get("subtitles") and all(s["bitmap"] for s in d["subtitles"])
                                       and not d.get("external_subtitles")),
               "pairs": dict(by_pair.most_common()), "hours": {k: round(v, 1) for k, v in hours.most_common()}}
    (a.out / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
