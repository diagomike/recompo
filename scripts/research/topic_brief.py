"""Topic brief prototype for the P17 research wing: "what did the creators I follow say about <topic>?".

    .venv\\Scripts\\python.exe scripts/research/topic_brief.py --config docs/research/P17-follow/ai-models.json \\
        --out docs/research/P17-follow/ai-models

For each followed creator in the config it reads the listed episodes' transcripts from where the creator publishes
them (no YouTube per-video requests):
  * `vtt`      a podcast feed's <podcast:transcript> WebVTT file (The Diary of a CEO)
  * `lex`      a lexfridman.com transcript page (speaker, timestamp, text)
  * `asr`      a word-timed ASR JSON made locally from the podcast feed's audio (recomp/workers/scripts/asr.py)
  * `project`  the primary transcript of a source in a Recomposer project (C:\\Recomposer\\projects\\<p>, ref S3)
It ranks ~45-90 s passages by how many of the topic's terms they use, and writes `brief.md` and `candidates.json`:
the reading list the agent turns into cuts. Ranking is only a shortlist; the agent reads and chooses.
Also saves the topic's current news headlines (Google News RSS search) as context.
"""
from __future__ import annotations

import argparse
import gzip
import html
import json
import math
import re
import sqlite3
import urllib.parse
import urllib.request
from pathlib import Path

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130 Safari/537.36"


def fetch(url: str, cache: Path) -> str:
    name = re.sub(r"[^\w.-]+", "_", url.split("://", 1)[-1])[:150]
    p = cache / name
    if p.exists():
        return p.read_text(encoding="utf-8")
    if (cache / (name + ".gz")).exists():
        with gzip.open(cache / (name + ".gz"), "rt", encoding="utf-8") as f:
            return f.read()
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        txt = r.read().decode("utf-8", errors="replace")
    p.write_text(txt, encoding="utf-8")
    return txt


def clock(t: float) -> str:
    t = int(t)
    return f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}"


def secs(ts: str) -> float:
    parts = [float(x) for x in ts.replace(",", ".").split(":")]
    while len(parts) < 3:
        parts.insert(0, 0.0)
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


def load_vtt(txt: str) -> list[dict]:
    segs = []
    for block in re.split(r"\n\s*\n", txt):
        m = re.search(r"(\d[\d:.,]+)\s*-->\s*(\d[\d:.,]+)", block)
        if not m:
            continue
        body = block[m.end():].strip()
        body = re.sub(r"<[^>]+>", "", body).replace("\n", " ")
        if body:
            segs.append({"start": secs(m.group(1)), "end": secs(m.group(2)), "text": html.unescape(body)})
    return segs


def load_lex(txt: str) -> list[dict]:
    segs = []
    for m in re.finditer(r'<span class="ts-name">(.*?)</span>.*?\((\d\d:\d\d:\d\d)\).*?<span class="ts-text">(.*?)</span>',
                         txt, re.S):
        segs.append({"start": secs(m.group(2)), "speaker": html.unescape(m.group(1)).strip(),
                     "text": html.unescape(re.sub(r"<[^>]+>", "", m.group(3))).strip()})
    for i, s in enumerate(segs):
        s["end"] = segs[i + 1]["start"] if i + 1 < len(segs) else s["start"] + 30
    vid = re.search(r"youtube\.com/watch\?v=([\w-]{11})", txt)
    if vid:
        for s in segs:
            s["video"] = vid.group(1)
    return segs


def load_asr(path: Path) -> list[dict]:
    path = Path(path)
    raw = gzip.open(path, "rt", encoding="utf-8").read() if path.suffix == ".gz" else path.read_text(encoding="utf-8")
    d = json.loads(raw)
    segs = d.get("segments", d)
    return [{"start": s["start"], "end": s["end"], "text": s["text"].strip()} for s in segs]


def load_project(project: str, ref: str) -> list[dict]:
    db = sqlite3.connect(Path(project) / "recomp.db")
    rows = db.execute('SELECT g.start, g."end", g.text, COALESCE(p.name, g.speaker) FROM segment g '
                      "JOIN transcript t ON t.id=g.transcript_id JOIN source s ON s.id=t.source_id "
                      "LEFT JOIN person p ON p.id=g.person_id WHERE s.ref=? AND t.is_primary=1 ORDER BY g.start",
                      (ref,)).fetchall()
    return [{"start": a, "end": b, "text": t, "speaker": sp} for a, b, t, sp in rows]


def passages(segs: list[dict], min_s: float = 45, max_s: float = 90) -> list[dict]:
    out = []
    for i in range(len(segs)):
        j = i
        while j + 1 < len(segs) and segs[j]["end"] - segs[i]["start"] < min_s and \
                segs[j + 1]["end"] - segs[i]["start"] <= max_s:
            j += 1
        out.append({"start": segs[i]["start"], "end": segs[j]["end"],
                    "text": " ".join(s["text"] for s in segs[i:j + 1]),
                    "speakers": sorted({s.get("speaker") for s in segs[i:j + 1] if s.get("speaker")})})
    return out


def score(text: str, terms: list[str]) -> tuple[float, list[str]]:
    low = text.lower()
    found, sc = [], 0.0
    for t in terms:
        n = len(re.findall(r"\b" + re.escape(t.lower()) + r"\b", low))
        if n:
            found.append(t)
            sc += 1 + math.log(n)
    return sc, found


def top(ps: list[dict], terms: list[str], k: int) -> list[dict]:
    scored = []
    for p in ps:
        s, f = score(p["text"], terms)
        if s > 0:
            scored.append({**p, "score": round(s, 2), "terms": f})
    out = []
    for p in sorted(scored, key=lambda x: -x["score"]):
        if all(p["end"] <= q["start"] or p["start"] >= q["end"] for q in out):
            out.append(p)
        if len(out) >= k:
            break
    return sorted(out, key=lambda x: x["start"])


def news(query: str, cache: Path, n: int = 10) -> list[dict]:
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
        {"q": f"{query} when:7d", "hl": "en-US", "gl": "US", "ceid": "US:en"})
    txt = fetch(url, cache)
    out = []
    for it in re.findall(r"<item>(.*?)</item>", txt, re.S)[:n]:
        out.append({"title": html.unescape(re.search(r"<title>(.*?)</title>", it, re.S).group(1)),
                    "date": (re.search(r"<pubDate>(.*?)</pubDate>", it) or [None, ""])[1][:16]})
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--k", type=int, default=4)
    a = ap.parse_args()
    cfg = json.loads(Path(a.config).read_text(encoding="utf-8"))
    out = Path(a.out)
    cache = out / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    terms = cfg["terms"]
    result = {"topic": cfg["topic"], "news": news(cfg["news_query"], cache), "creators": []}
    for cr in cfg["creators"]:
        entry = {"name": cr["name"], "episodes": []}
        for ep in cr["episodes"]:
            kind = ep["kind"]
            if kind == "vtt":
                segs = load_vtt(fetch(ep["url"], cache))
            elif kind == "lex":
                segs = load_lex(fetch(ep["url"], cache))
            elif kind == "asr":
                if not Path(ep["path"]).exists():
                    entry["episodes"].append({**ep, "missing": True})
                    continue
                segs = load_asr(Path(ep["path"]))
            else:
                segs = load_project(ep["project"], ep["ref"])
            picks = top(passages(segs), terms, a.k)
            entry["episodes"].append({**ep, "segments": len(segs), "length": clock(segs[-1]["end"]) if segs else "",
                                      "candidates": picks})
        result["creators"].append(entry)
    (out / "candidates.json").write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
    lines = [f"# Topic brief: {cfg['topic']}", "", f"Terms: {', '.join(terms)}", "", "## In the news this week", ""]
    lines += [f"- {n['title']} ({n['date']})" for n in result["news"]]
    for cr in result["creators"]:
        lines += ["", f"## {cr['name']}"]
        for ep in cr["episodes"]:
            lines += ["", f"### {ep['title']}" + (" (transcript not ready)" if ep.get("missing") else
                                                     f" · {ep['length']} · {ep['kind']}")]
            for c in ep.get("candidates", []):
                link = f" [▶](https://youtu.be/{ep['video']}?t={int(c['start'])})" if ep.get("video") else ""
                who = f" ({', '.join(c['speakers'])})" if c["speakers"] else ""
                lines.append(f"- **{clock(c['start'])}–{clock(c['end'])}**{who} score {c['score']} "
                             f"[{', '.join(c['terms'])}]{link}: {c['text'][:400]}…")
    (out / "brief.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out / 'brief.md'}")


if __name__ == "__main__":
    main()
