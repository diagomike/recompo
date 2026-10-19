"""Topics in the air and what followed creators said about them (P17b).

News sources are prompts, never a scoreboard (D-22): Google News RSS, Google Trends' daily RSS, Wikipedia's
most-viewed articles and the Hacker News front page, all keyless. A topic's **brief** ranks 45–90 s passages from
the creators' episodes by the topic's terms: a shortlist for the agent to read and choose from.
"""

from __future__ import annotations

import html
import math
import re
import time
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from urllib.parse import urlencode

from . import net

GN = "https://news.google.com/rss"
GN_PARAMS = {"hl": "en-US", "gl": "US", "ceid": "US:en"}
SECTIONS = ("top", "world", "nation", "business", "technology", "science", "health", "entertainment", "sports")
STOP = set("""a about above after again against all also am an and any are as at be because been before being below
between both but by can could did do does doing down during each few for from further had has have having he her here
hers him his how i if in into is it its itself just me more most my new no nor not now of off on once only or other our
out over own same says said she should so some such than that the their them then there these they this those through to
too under until up very was we were what when where which while who whom why will with would you your yet via amid after
over vs report reports news live update updates first last year years week day days time make makes made get gets
how why what new latest big more most just still themselves itself across soon warns warn says say could might may
set sets plans plan takes take gives give goes going back way ways look looks here's there's it's that's
never ever always better best good great bad worse worst really someone something anything everything nothing people
thing things want wants need needs know knows think thinks behind inside major minor much many little lot lots whole
own each every another other others own while""".split())


def _date(value: str) -> str | None:
    try:
        return parsedate_to_datetime(value).strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return None


def parse_news(xml_text: str, limit: int = 20) -> list[dict]:
    root = ET.fromstring(xml_text.encode("utf-8"))
    out = []
    for it in root.iter("item"):
        title = html.unescape((it.findtext("title") or "").strip())
        src = it.find("source")
        source = (src.text or "").strip() if src is not None and src.text else ""
        if source and title.endswith(" - " + source):
            title = title[: -len(" - " + source)]
        out.append({"title": title, "source": source, "date": _date(it.findtext("pubDate") or ""),
                    "link": (it.findtext("link") or "").strip()})
        if len(out) >= limit:
            break
    return out


def news(section: str = "top", query: str | None = None, limit: int = 15) -> list[dict]:
    if query:
        url = f"{GN}/search?" + urlencode({"q": f"{query} when:7d", **GN_PARAMS})
    elif section == "top":
        url = f"{GN}?" + urlencode(GN_PARAMS)
    else:
        url = f"{GN}/headlines/section/topic/{section.upper()}?" + urlencode(GN_PARAMS)
    return [{**n, "from": "news"} for n in parse_news(net.get_text(url, timeout=20), limit)]


def google_trends(geo: str = "US", limit: int = 10) -> list[dict]:
    root = ET.fromstring(net.get_text(f"https://trends.google.com/trending/rss?geo={geo}", timeout=20).encode("utf-8"))
    ns = {"ht": "https://trends.google.com/trending/rss"}
    out = []
    for it in root.iter("item"):
        heads = [html.unescape(n.findtext("ht:news_item_title", default="", namespaces=ns)) for n in it.findall("ht:news_item", ns)]
        out.append({"title": (it.findtext("title") or "").strip(), "source": "Google Trends", "from": "trends",
                    "date": _date(it.findtext("pubDate") or ""), "traffic": it.findtext("ht:approx_traffic", namespaces=ns),
                    "context": heads[:2], "link": ""})
        if len(out) >= limit:
            break
    return out


def wikipedia_top(limit: int = 15, now: float | None = None) -> list[dict]:
    """Most-viewed English Wikipedia articles (yesterday's list appears a day late: try 1, then 2 days back).
    Wikimedia's robot policy wants contact details in the user agent: `research.contact` (an email or URL you choose)."""
    from ..core import config
    from ..envelope import RecompError
    contact = config.get("research.contact")
    if not contact:
        raise RecompError("E_INVALID", "Wikipedia's API asks for contact details in the user agent",
                          hint="`recomp config set research.contact <your email or a URL>` to include Wikipedia's most-viewed list.")
    ua = f"RecomposerStudio/0.1 ({contact})"
    now = now or time.time()
    last = None
    for back in (1, 2, 3):
        day = time.strftime("%Y/%m/%d", time.gmtime(now - back * 86400))
        try:
            data = net.get_json(f"https://wikimedia.org/api/rest_v1/metrics/pageviews/top/en.wikipedia/all-access/{day}",
                                user_agent=ua)
            break
        except Exception as exc:  # noqa: BLE001 — not published yet: one day earlier
            last = exc
            data = None
    if data is None:
        raise last  # type: ignore[misc]
    out = []
    for a in data["items"][0]["articles"]:
        name = a["article"]
        if ":" in name or name in ("Main_Page",):
            continue
        out.append({"title": name.replace("_", " "), "source": "Wikipedia", "from": "wikipedia", "views": a.get("views"),
                    "date": "-".join(day.split("/")), "link": f"https://en.wikipedia.org/wiki/{name}"})
        if len(out) >= limit:
            break
    return out


def hacker_news(limit: int = 15) -> list[dict]:
    data = net.get_json("https://hn.algolia.com/api/v1/search?" + urlencode({"tags": "front_page", "hitsPerPage": limit}))
    return [{"title": h.get("title") or "", "source": "Hacker News", "from": "hn", "points": h.get("points"),
             "date": (h.get("created_at") or "")[:10] or None, "link": h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID')}"}
            for h in data.get("hits") or []][:limit]


# ---- terms and passages -----------------------------------------------------------------------------

def key_terms(title: str, n: int = 4) -> list[str]:
    """The informative words of a headline or topic: acronyms and names first, then content words in order."""
    words = re.findall(r"[A-Za-z][A-Za-z0-9'\-]*", title)
    seen, scored = set(), []
    for i, w in enumerate(words):
        w = w.strip("'-")
        low = w.lower()
        if low in STOP or low in seen or (len(low) < 3 and not (w.isupper() and len(w) >= 2)):
            continue
        seen.add(low)
        if w.isupper() and len(w) >= 2:
            rank = 0  # AI, AGI, NASA
        elif w[0].isupper() and i > 0:
            rank = 1  # a name inside the headline
        elif w[0].isupper():
            rank = 2  # the first word: often a name, sometimes not
        else:
            rank = 3
        scored.append((rank, i, w))
    return [w for _, _, w in sorted(scored)[:n]]


def term_rx(term: str) -> re.Pattern:
    t = re.escape(term.lower()).replace(r"\ ", r"\s+")
    return re.compile(r"(?<![\w])" + t + r"(?![\w])", re.I)


def score(text: str, rxs: list[tuple[str, re.Pattern]]) -> tuple[float, list[str]]:
    found, sc = [], 0.0
    for term, rx in rxs:
        k = len(rx.findall(text))
        if k:
            found.append(term)
            sc += 1 + math.log(k)
    # Passages that use several of the topic's terms are worth more than one term repeated.
    return round(sc * (1 + 0.25 * max(0, len(found) - 1)), 2), found


def passages(segs: list[dict], terms: list[str], k: int = 3, min_s: float = 45, max_s: float = 90) -> list[dict]:
    """The best ``k`` non-overlapping 45–90 s windows of an episode for these terms."""
    rxs = [(t, term_rx(t)) for t in terms if t.strip()]
    cands = []
    for i in range(len(segs)):
        j = i
        while j + 1 < len(segs) and segs[j]["end"] - segs[i]["start"] < min_s and segs[j + 1]["end"] - segs[i]["start"] <= max_s:
            j += 1
        text = " ".join(s["text"] for s in segs[i:j + 1])
        sc, found = score(text, rxs)
        if sc > 0:
            cands.append({"start": segs[i]["start"], "end": segs[j]["end"], "text": text, "score": sc, "terms": found,
                          "speakers": sorted({s["speaker"] for s in segs[i:j + 1] if s.get("speaker")})})
    out: list[dict] = []
    for p in sorted(cands, key=lambda x: -x["score"]):
        if all(p["end"] <= q["start"] or p["start"] >= q["end"] for q in out):
            out.append(p)
        if len(out) >= k:
            break
    return sorted(out, key=lambda x: x["start"])


def mentions(text: str, terms: list[str]) -> int:
    return sum(1 for t in terms if term_rx(t).search(text or ""))
