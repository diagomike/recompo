"""Cut small test fixtures for P17 from the raw responses saved during the research (docs/research/P17-follow/raw).

    .venv\\Scripts\\python.exe scripts/research/make_p17_fixtures.py

Feeds keep their channel header and a few items (DOAC: items that carry a published transcript first); listings
keep a few entries; the Lex page keeps its table of contents, video embed and the first transcript lines.
"""
from __future__ import annotations

import gzip
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "docs" / "research" / "P17-follow" / "raw"
OUT = ROOT / "tests" / "fixtures" / "p17"


def read(name: str) -> str:
    p = RAW / name
    if p.suffix == ".gz":
        with gzip.open(p, "rt", encoding="utf-8") as f:
            return f.read()
    return p.read_text(encoding="utf-8")


def trim_feed(text: str, n: int, prefer: str | None = None) -> str:
    head = text[:text.index("<item")]
    items = re.findall(r"<item>.*?</item>|<item .*?</item>", text, re.S)
    if prefer:
        items = [i for i in items if prefer in i][:2] + [i for i in items if prefer not in i]
    return head + "\n".join(items[:n]) + "\n</channel>\n</rss>\n"


def trim_listing(name: str, n: int) -> dict:
    d = json.loads(read(name))
    d["entries"] = [{k: v for k, v in e.items() if k != "thumbnails"} for e in d.get("entries", []) if e][:n]
    return {k: v for k, v in d.items() if k in ("title", "channel", "channel_id", "uploader_id", "webpage_url", "_type", "entries")}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "feed-within-reason.xml").write_text(trim_feed(read("feed-within-reason.xml.gz"), 4), encoding="utf-8")
    (OUT / "feed-lex.xml").write_text(trim_feed(read("feed-lex.xml.gz"), 3), encoding="utf-8")
    (OUT / "feed-doac.xml").write_text(trim_feed(read("feed-doac.xml.gz"), 3, prefer="podcast:transcript"), encoding="utf-8")
    page = read("lex-transcript-scull.html.gz")
    segs = [m.start() for m in re.finditer(r'<div class="ts-segment">', page)]
    cut = segs[40] if len(segs) > 40 else len(page)
    (OUT / "lex-transcript.html").write_text(page[:cut] + "\n</div></body></html>\n", encoding="utf-8")
    vtt = read("doac-transcript-sample.vtt.gz")
    blocks = re.split(r"\n\s*\n", vtt)
    (OUT / "doac.vtt").write_text("\n\n".join(blocks[:80]) + "\n", encoding="utf-8")
    (OUT / "itunes-within-reason.json").write_text(read("itunes-within-reason.json"), encoding="utf-8")
    for src, dst, n in (("yt-search-channels-philosophy.json.gz", "yt-search-channels.json", 5),
                        ("yt-listing-alex-latest.json.gz", "yt-listing-alex.json", 8),
                        ("yt-search-person-alex.json", "yt-search-person-alex.json", 15),
                        ("yt-channelsearch-alex-ai.json.gz", "yt-channelsearch-alex-ai.json", 6)):
        (OUT / dst).write_text(json.dumps(trim_listing(src, n), ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "yt-rss-500.html").write_text(read("yt-rss-alex.xml"), encoding="utf-8")
    for p in sorted(OUT.iterdir()):
        print(f"{p.name:32} {p.stat().st_size // 1024:5} kB")


if __name__ == "__main__":
    main()
