"""Link ingest with yt-dlp mocked (no network): pick lists, partial metadata, captions, sections."""

import json
import shutil
import subprocess

import pytest

from recomp.envelope import RecompError
from recomp.ingest import links
from tests.media import OUT, fixtures

pytestmark = pytest.mark.e2e

CHANNEL = {"_type": "playlist", "title": "Chan - Videos", "channel": "Chan", "entries": [
    {"id": "AAAAAAAAAAA", "title": "Consciousness one", "duration": 3600, "view_count": 10, "url": "https://www.youtube.com/watch?v=AAAAAAAAAAA"},
    {"id": "BBBBBBBBBBB", "title": "Free will two", "duration": 1800, "view_count": 5, "url": "https://www.youtube.com/watch?v=BBBBBBBBBBB"},
    {"id": "CCCCCCCCCCC", "title": "Consciousness three", "duration": 40, "view_count": 7, "url": "https://www.youtube.com/watch?v=CCCCCCCCCCC"},
]}
VIDEO = {"id": "CCCCCCCCCCC", "title": "Consciousness three", "channel": "Chan", "duration": 40, "upload_date": "20260901",
         "webpage_url": "https://www.youtube.com/watch?v=CCCCCCCCCCC", "extractor_key": "Youtube",
         "chapters": [{"start_time": 0, "end_time": 11, "title": "Intro"}, {"start_time": 11, "end_time": 40, "title": "Heroes"}],
         "subtitles": {}, "automatic_captions": {"en-orig": [], "en": [], "fr": []}, "language": "en"}


def json3_from_srt():
    events = []
    for t, text in fixtures()["sentences"]:
        segs = [{"utf8": w if i == 0 else " " + w, "tOffsetMs": i * 250} for i, w in enumerate(text.split())]
        events.append({"tStartMs": int(t * 1000), "dDurationMs": 4000, "segs": segs})
    return json.dumps({"events": events})


@pytest.fixture
def lproj(proj, monkeypatch):
    monkeypatch.setenv("RECOMP_JOBS", "inline")

    def fake_extract(url, flat=False, limit=None):
        return CHANNEL if "@" in url else VIDEO

    def fake_captions(project, src, lang, log=print):
        p = project.dir("sources", src["ref"]) / "captions.en-orig.json3"
        p.write_text(json3_from_srt(), encoding="utf-8")
        return p

    monkeypatch.setattr(links, "extract", fake_extract)
    monkeypatch.setattr(links, "fetch_captions", fake_captions)
    return proj


def test_pick_list_then_add(lproj, OK):
    pl = OK("source.add", {"target": "https://www.youtube.com/@Chan/videos", "match": "conscious"}, lproj)
    assert [e["n"] for e in pl["entries"]] == [1, 3]
    assert OK("source.list", {}, lproj) == []  # listing adds nothing
    add = OK("source.add", {"pick": ["3"]}, lproj)
    a = add["added"][0]
    assert a["ref"] == "S1" and a["creator_chapters"] == 2
    tr = OK("transcript.list", {"ref": "S1"}, lproj)
    assert tr[0]["origin"] == "platform" and tr[0]["words"] is True
    seeded = OK("chapter.seed", {"ref": "S1"}, lproj)
    assert [c["title"] for c in seeded] == ["Intro", "Heroes"]
    s = OK("source.show", {"ref": "S1"}, lproj)
    assert s["rights"]["owner"] == "Chan" and s["platform"] == "youtube"
    again = OK("source.add", {"target": "https://youtu.be/CCCCCCCCCCC"}, lproj)
    assert again["skipped"][0]["ref"] == "S1"


def test_blocked_metadata_falls_back_to_list(lproj, OK, monkeypatch):
    OK("source.add", {"target": "https://www.youtube.com/@Chan/videos"}, lproj)

    def blocked(url, flat=False, limit=None):
        raise RecompError("E_EXTERNAL", "the site asks to confirm this is not a bot")

    monkeypatch.setattr(links, "extract", blocked)
    env = OK("source.add", {"pick": ["1", "2"]}, lproj)
    assert [a["ref"] for a in env["added"]] == ["S1", "S2"]
    st = OK("source.status", {}, lproj)
    assert st[0]["status"]["probe"] == "metadata-partial"
    monkeypatch.setattr(links, "extract", lambda url, flat=False, limit=None: dict(VIDEO, id="AAAAAAAAAAA"))
    r = OK("source.refresh", {"ref": "S1"}, lproj)
    assert r["creator_chapters"] == 2 and r["job"]


def test_caption_language_choice():
    meta = {"captions": {"manual": ["fr"], "auto": ["en-orig", "en", "de"]}}
    assert links.pick_caption_lang(meta, "en") == ("en-orig", True)
    assert links.pick_caption_lang(meta, "fr") == ("fr", False)
    assert links.pick_caption_lang({"captions": {"manual": [], "auto": []}}, "en") == (None, True)


def test_classify_errors():
    assert links.classify_error(Exception("HTTP Error 429: Too Many Requests")).code == "E_EXTERNAL"
    assert "ask the user" in links.classify_error(Exception("Sign in to confirm you're not a bot")).hint
    assert links.classify_error(Exception("Video unavailable")).code == "E_NOT_FOUND"


def test_render_fetches_only_sections(lproj, OK, monkeypatch):
    OK("source.add", {"target": "https://youtu.be/CCCCCCCCCCC"}, lproj)
    calls = []

    def fake_section(project, item, prof, log=print):
        # Stand in for yt-dlp: cut the fixture clip at [in-1.5, out+1.5] like a section download would.
        a = max(0.0, item["in"] - 1.5)
        b = item["out"] + 1.5
        out = project.dir("sources", item["source"], "sections") / f"{a:.2f}_{b:.2f}.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{a}", "-i", str(OUT / "clip.mp4"), "-t", f"{b - a}",
                        "-c:v", "libx264", "-c:a", "aac", str(out)], check=True)
        calls.append((a, b))
        item["in"] = round(item["in"] - a, 3)
        item["out"] = round(item["in"] + item["dur"], 3)
        item["video"] = {"width": 320, "height": 180}
        item["audio"] = {"channels": 2}
        item["fingerprint"] = f"section:{a}:{b}"
        return str(out)

    monkeypatch.setattr(links, "ensure_section", fake_section)
    OK("cut.add", {"ref": "S1", "from": "12", "to": "17", "snap": "none", "why": "w"}, lproj)
    OK("journey.new", {"title": "Link journey", "cuts": ["C1"]}, lproj)
    res = OK("export.run", {"journey": "J1", "profiles": ["landscape"]}, lproj)
    x = OK("export.show", {"ref": res["exports"][0]["export"]}, lproj)
    assert x["status"] == "done", x["problems"]
    assert calls == [(10.5, 18.5)]
    assert "Chan" in x["description"]
