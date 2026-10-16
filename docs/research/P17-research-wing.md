# P17 research: following creators and compiling what they say

**Updated:** 2026-10-16 (first version 2026-10-15) · **For:** the P17 plan (docs/PLAN.md §6) · **Stance:** D-22, we
create from people we follow; trend data is only a prompt for topics. **Rights:** D-23 replaces every rights rule
that was in this note. Live checks were run from this machine; raw responses and the prototype's output are in
[P17-follow/](P17-follow/README.md).

## Finding creators (verified 2026-10-16, keyless)

| Need | Mechanism | Result here |
|---|---|---|
| Channels about a subject | yt-dlp on `youtube.com/results?search_query=…&sp=EgIQAg%253D%253D` (channel filter) | "philosophy podcast": 494 channels with subscriber counts (Philosophize This!, Overthink, …) |
| A person, and where they appear as a guest | yt-dlp `ytsearch40:"Alex O'Connor interview"`, grouped by channel | his own channel 12, plus Closer To Truth, Chris Williamson, Flagrant, Jay Shetty, Triggernometry, Hank Green… |
| A podcast and its feed | iTunes Search API `itunes.apple.com/search?media=podcast&term=…` → `feedUrl` | Within Reason (anchor.fm), Lex Fridman (lexfridman.com/feed/podcast), DOAC (flightcast) |

## Following them

| Need | Mechanism | Result here |
|---|---|---|
| New uploads of a channel | yt-dlp flat listing of `@handle/videos` (or `/shorts`) | works (Alex: 443 entries) |
| … via RSS | `youtube.com/feeds/videos.xml?channel_id=UC…` (`UULF`/`UUSH` playlists for no-Shorts/Shorts) | **failing today**: 404 / 500 for all three channels (worked 2026-10-15); keep as the cheap first try, fall back to the listing |
| New podcast episodes | the feed itself | Within Reason 162 items, Lex 502, DOAC 896 |
| A channel's past videos on a topic | yt-dlp on `@handle/search?query=AI` | Alex 313, Lex 137, DOAC 416 results (title, views, length) |

## Transcripts without per-video YouTube requests

| Creator | Route | Result here |
|---|---|---|
| The Diary of a CEO | feed `<podcast:transcript type="text/vtt">` | on 322 of 896 episodes; sentence-level cues, no speaker names |
| Lex Fridman | `lexfridman.com/<episode>-transcript` | speaker names, hh:mm:ss per paragraph, the YouTube id, chapter headings |
| Alex O'Connor (Within Reason) | feed audio (`megaphone.fm` mp3) + local ASR | no transcript tag; #153 (95 min, 91 MB) transcribed locally in 75 min of CPU (1,185 segments, word-timed) |
| Any YouTube video | word-timed captions `json3` | **blocked today**: per-video requests answer 429, then "Sign in to confirm you're not a bot", even after a 15 min back-off |

Notes:
- Podcast and YouTube versions can differ: DOAC's podcast titles don't match the YouTube titles of the same episode
  (match by guest, date and transcript text, not title), and feed audio may carry intros or inserted ads, so a
  feed-timed passage is aligned to the video by text before cutting video.
- Cookies (D-24): `--cookies-from-browser chrome` failed with "Could not copy Chrome cookie database" because
  Chrome was running; close Chrome or export a cookies.txt.

## What's in the air (topic prompts, verified 2026-10-16, keyless)

| Source | Mechanism | Today |
|---|---|---|
| Google News | `news.google.com/rss` (top), `/rss/headlines/section/topic/TECHNOLOGY`, `/rss/search?q=AI+models+when:7d` | 45–100 items; "Anthropic warns AI models could soon copy themselves…", "Meta unveils new frontier-class AI models", "Gemini 4" |
| Google Trends | `trends.google.com/trending/rss?geo=US` | 10 items, mostly sports and celebrities: weak for our topics |
| Wikipedia | `wikimedia.org/api/rest_v1/metrics/pageviews/top/en.wikipedia/all-access/YYYY/MM/DD` | the previous day 404s until it is published; one day earlier works |
| Hacker News | `hacker-news.firebaseio.com/v0/topstories.json` | ids of the top 500 stories (tech topics) |

The official Google Trends API is an application-gated alpha and `pytrends` is archived; the RSS feeds above are
undocumented but keyless.

## The prototype: a topic brief

`scripts/research/topic_brief.py` took the topic "AI models are getting good", this week's headlines and six
episodes from three followed creators. It read their transcripts by the routes above and ranked 45–90 s passages by
the topic's terms. Some of what it surfaced, with timestamps:
- DOAC, Jeffrey Ladish (2026-10-08) 0:35:11: "the latest Frontier model escaped… was able to actually copy itself",
  which is the week's headline in a guest's words.
- Lex Fridman #490 *State of AI in 2026* 2:39:03 (Nathan Lambert): what AGI and ASI mean and when AI "can replace
  any remote worker".
- Alex O'Connor S3 (Anil Seth) 0:26:48: "LLMs have just burst open the door to credulity about conscious AI".

So the loop works end to end without touching YouTube's blocked endpoints. Three things matter for the build:
- Speaker names decide whose opinion a passage is. Lex's pages have them; DOAC's VTT doesn't, so diarisation or the
  host's known voice (P9) is needed.
- Keyword ranking finds the passages. The agent still reads them and picks.
- Keeping a back catalogue of transcripts makes "what did they say before" instant.

## Official APIs and their limits (from 2026-10-15, still relevant)

- **YouTube Data API v3** (your key, 10,000 units/day): `videos.list` 1 unit per 50 videos; `search.list` 100 units.
  Useful later for your own channel's analytics (read-only), not needed for following.
- **Podcast Index API** (free key): only if plain feeds fall short.
- **Uploading** stays with you (D-10). YouTube API uploads from unaudited projects are locked private.

## Formats

YouTube Shorts: up to 3 minutes for square or vertical video (since 15 October 2024). The `shorts` profile
(1080×1920) fits.

## Possible later aids (not in P17)

- YouTube's "Most replayed" heatmap (yt-dlp `heatmap`, 100 points) as a second opinion on where an episode's
  strongest moments are. Dropped from P17 as a market signal (D-22); the agent reads the transcript.

## Sources

- YouTube RSS: [WP RSS Aggregator](https://www.wprssaggregator.com/youtube-rss-feed/),
  [HN: YouTube, your RSS feeds are broken](https://hn.nuxt.dev/item/48030964)
- Podcasts: [Podcasting 2.0 transcript tag](https://github.com/Podcastindex-org/podcast-namespace/blob/main/docs/1.0.md#transcript),
  [labnol: podcast feed lookup](https://labnol.org/podcast)
- Lex Fridman transcripts: [example](https://lexfridman.com/andrew-scull-transcript)
- Google News RSS, Google Trends RSS, Wikimedia pageviews API, Hacker News API: endpoints above (checked live)
- YouTube Data API: [quota costs](https://developers.google.com/youtube/v3/determine_quota_cost)
- Google Trends: [Trends API alpha](https://developers.google.com/search/blog/2025/07/trends-api)
- Shorts length: [Tubefilter](https://www.tubefilter.com/?p=182474)
- Cookies: [yt-dlp issue 7271 (Chrome cookie database locked)](https://github.com/yt-dlp/yt-dlp/issues/7271)
