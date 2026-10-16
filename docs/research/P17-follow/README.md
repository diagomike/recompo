# P17-follow: evidence for "follow creators, compile what they say"

**Collected:** 2026-10-16 from this machine, keyless. Summary and conclusions: [../P17-research-wing.md](../P17-research-wing.md).

## Contents
- `raw/`: the responses as received. Feeds and large listings are gzipped (`*.gz`).
  - `news-*.xml`: Google News RSS (top, technology section, search "AI models when:7d").
  - `gtrends-us.xml`: Google Trends daily RSS (US). `wiki-top-2026-10-14.json`: Wikipedia most-viewed. `hn-top.json`.
  - `itunes-*.json`: podcast search results. `feed-*.xml.gz`: the Within Reason, Lex Fridman and DOAC feeds.
  - `doac-transcript-sample.vtt`, `lex-transcript-scull.html`: one published transcript of each kind.
  - `yt-search-*.json.gz`, `yt-channelsearch-*-ai.json.gz`, `yt-listing-alex-latest.json.gz`: yt-dlp flat listings.
  - `yt-rss-*.xml`: the YouTube RSS failures (404/500) as returned.
- `ai-models.json`: the topic brief's configuration (topic, terms, creators, episodes, transcript routes).
- `ai-models/brief.md`, `ai-models/candidates.json`: the prototype's output; `ai-models/cache/` holds the fetched
  transcripts (gzipped).

## How to rerun
```
# sources (bash; UA = any desktop browser user agent)
curl -sL -A "$UA" "https://news.google.com/rss/search?q=AI+models+when:7d&hl=en-US&gl=US&ceid=US:en"
curl -sL "https://itunes.apple.com/search?media=podcast&term=Within+Reason+Alex+O%27Connor"
.venv/Scripts/python.exe -m yt_dlp --flat-playlist -J "https://www.youtube.com/results?search_query=philosophy+podcast&sp=EgIQAg%253D%253D"
.venv/Scripts/python.exe -m yt_dlp --flat-playlist -J "ytsearch40:Alex O'Connor interview"
.venv/Scripts/python.exe -m yt_dlp --flat-playlist -J "https://www.youtube.com/@CosmicSkeptic/search?query=AI"

# Within Reason #153 transcript (feed audio + local ASR, ~30 min CPU)
curl -sL -o wr153.mp3 https://traffic.megaphone.fm/APO8838750537.mp3
ffmpeg -i wr153.mp3 -ac 1 -ar 16000 wr153.wav
HF_HOME='D:\LangBridgeLocal\cache\hf' HF_HUB_OFFLINE=1 D:/LangBridgeLocal/.venv/Scripts/python.exe -I recomp/workers/scripts/asr.py --wav wr153.wav --out wr153.asr.json

# the brief (edit the asr path in ai-models.json to where wr153.asr.json is)
.venv/Scripts/python.exe scripts/research/topic_brief.py --config docs/research/P17-follow/ai-models.json --out docs/research/P17-follow/ai-models
```

## What is missing
- YouTube per-video requests (captions, heatmaps) were blocked all session (429, then the bot check). Cookies were
  allowed (D-24), but `--cookies-from-browser chrome` could not copy the cookie database: Chrome kept 10 background
  processes running after its windows closed. An exported cookies.txt is the reliable route.
- The Within Reason audio (91 MB) and its WAV were kept outside the repo (scratch folder); only the ASR JSON's passages
  appear in the brief.
- DOAC's VTT has no speaker names, so the brief can't yet say whether a passage is Steven Bartlett or the guest.
- Within Reason's podcast timing was not aligned to the YouTube upload (B_HDkqZtGOE); the build aligns by text.
