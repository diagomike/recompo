# P17 research: watching creators, finding trends, cutting, and running channels

**Date:** 2026-10-15 · **For:** the P17 plan (docs/PLAN.md §6) · Live checks were run from this machine; everything else is
from the sources listed at the end.

## What works without keys (verified here)

| Need | Mechanism | Verified |
|---|---|---|
| New uploads of a YouTube channel | `https://www.youtube.com/feeds/videos.xml?channel_id=UC…` (latest 15) | 200, 15 entries (Alex O'Connor) |
| … without Shorts / only Shorts | `playlist_id=UULF…` / `UUSH…` (the channel id with `UC` swapped; undocumented) | 200, 15 entries |
| A podcast's RSS feed by name | iTunes Search API `itunes.apple.com/search?media=podcast&term=…` → `feedUrl` (no key) | The Diary of a CEO → `rss2.flightcast.com/…` |
| Where viewers rewatch inside a video | yt-dlp's `heatmap` field ("Most replayed"): 100 points, value 0–1 | S3 (Anil Seth): peaks at 20:30, 7:10, 19:28, 14:21, 1:28:07 |
| Recent videos on a topic, views per day | yt-dlp on a YouTube search URL (existing `trends search`) | M2 |

Notes:
- RSS feeds had intermittent 404s in December 2025 and the `UULF/UUSH` prefixes are undocumented: fall back to
  yt-dlp's flat channel listing (already used by `source add <channel>`) when a feed fails.
- The heatmap is missing for new or low-traffic videos and some Shorts; it is a signal, not a requirement.
- The heatmap's peaks line up with the moments the agent chose by reading the transcript in M2 (S3's C3 at 14:42
  sits on the 14:21 peak's slope), which makes it a strong, free second opinion for `cut suggest`.

## Official APIs and their limits

- **YouTube Data API v3** (your key, 10,000 units/day by default): `videos.list` and `playlistItems.list` cost
  1 unit (50 videos per call: cheap view counts), `search.list` costs 100. `videos.list chart=mostPopular` still
  works, but since 21 July 2025 it reflects trending music, movies and gaming charts rather than the old
  Trending page, which YouTube retired in favour of category charts (YouTube Charts: music, podcasts, trailers).
- **Google Trends**: the public RSS feed `trends.google.com/trending/rss?geo=US` (top ~20 daily searches per
  country, undocumented); the official Trends API is an application-gated alpha (July 2025); `pytrends` is
  archived and its trending-search calls return 404.
- **Podcast Index API**: free key + secret; `episodes/byfeedurl` and `recent/episodes`. Only needed if plain RSS
  parsing falls short.
- **TikTok**: no official trend API for commercial users (the Research API is for vetted academics and non-profits).
  Creative Center shows trending hashtags (27 countries) and videos (a few countries) publicly; third-party
  scrapers depend on its internal endpoints, which change. yt-dlp reads public TikTok videos and (since 2024)
  user pages; results vary over time.
- **Instagram**: public reels often need a logged-in session for yt-dlp; we do not use cookies unless you set them.
- **Uploading** (out of scope for P17; you upload): YouTube API uploads from unaudited projects are locked
  private; TikTok's Content Posting API posts privately until the app passes an audit (max 5 users/day before);
  Instagram publishing needs a Business/Creator account linked to a Facebook Page, an app review, and the video
  on a public URL. All three are possible later behind your own accounts and audits.

## Formats

- YouTube Shorts: up to 3 minutes for square or vertical videos (since 15 October 2024).
- TikTok: up to 10 minutes; Instagram Reels: 3 minutes in Meta's current guidance (sources disagree: check
  at posting time). Our `shorts` profile (1080×1920) fits all three.

## Rights and monetisation

- YouTube's July 2025 update renamed "repetitious" to **inauthentic content** (mass-produced, template-like) and left
  the **reused content** policy unchanged: clips, compilations, commentary and reactions are reviewed for
  meaningful added value. Journeys (sections, quote cards, translations, dubbing, cross-source arguments) are the
  kind of transformation that policy looks for; plain re-uploads are not.
- **Clipping programs** are now a market: creators fund campaigns that pay clippers per 1,000 views (Whop Content
  Rewards: about $0.20–$6, typically $1–$4). A campaign listing is the clearest sign a show authorises clips.
  Big shows (Lex Fridman: "Lex Clips"; The Diary of a CEO) run official clip channels; without a campaign or
  written permission, treat their clips as unauthorised. A third-party "Diary of a CEO (Pay To Clip)" listing
  exists but its authorisation is unconfirmed.
- Preaching and sermon channels often welcome sharing but licences vary; record each watch's rights note
  (authorised / program / unknown) and show it in the posting queue. This is not legal advice.

## Sources

- YouTube RSS: [WP RSS Aggregator](https://www.wprssaggregator.com/youtube-rss-feed/),
  [Privacy Guides thread](https://discuss.privacyguides.net/t/how-to-create-a-rss-feed-for-any-youtube-channel/35169),
  [zenn.dev guide](https://zenn.dev/banboobloom/articles/2026010200001), [HN: YouTube, your RSS feeds are broken](https://hn.nuxt.dev/item/48030964)
- YouTube Data API: [quota costs](https://developers.google.com/youtube/v3/determine_quota_cost),
  [getting started](https://developers.google.com/youtube/v3/getting-started),
  [videos implementation (mostPopular)](https://developers.google.com/youtube/v3/guides/implementation/videos?hl=en),
  [revision history](https://developers.google.com/youtube/v3/revision_history?hl=de),
  [videos.insert private lock](https://developers.google.cn/youtube/v3/docs/videos?hl=en)
- Trending page retirement: [TechCrunch](https://techcrunch.com/2025/07/10/youtube-is-getting-rid-of-its-trending-page-and-trending-now-list),
  [9to5Google](https://9to5google.com/2025/07/10/youtube-trending-page-removal/), [PPC Land](https://ppc.land/youtube-closes-trending-page-after-a-decade-of-operation/)
- Google Trends: [Trends API alpha](https://developers.google.com/search/blog/2025/07/trends-api),
  [Search Engine Journal](https://www.searchenginejournal.com/google-trends-api-alpha-mueller-confirms-small-pilot-group/554078/),
  [ScrapeBadger: Google Trends in 2026](https://scrapebadger.com/blog/does-google-trends-have-an-api-what-to-use-in-2026)
- Podcasts: [labnol: podcast feed lookup](https://labnol.org/podcast), [podcast-index-api](https://cdn.jsdelivr.net/npm/podcast-index-api@2.0.0/README.md)
- TikTok: [Research API](https://developers.tiktok.com/products/research-api/), [TokConnect guide](https://tokconnect.com/guides/tiktok-research-api/),
  [Creative Center scrapers (Apify)](https://apify.com/symphonic_mullite/tiktok-creative-center-trends),
  [Content Posting API](https://developers.tiktok.com/doc/content-posting-api-reference-direct-post), [yt-dlp-TTUser (archived)](https://github.com/bashonly/yt-dlp-TTUser)
- Instagram: [Content publishing](https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/content-publishing)
- Heatmap: [yt-dlp heatmap commit (mirror)](https://bytes.keithhacks.cyou/etc/yt-dlp/commit/5caf30dbc34f10b0be60676fece635b5c59f0d72),
  [youtube-heatmap](https://github.com/WillianAgostini/youtube-heatmap)
- Shorts length: [Tubefilter](https://www.tubefilter.com/?p=182474), [Gigazine](https://gigazine.net/gsc_news/en/20241004-youtube-short-video-length-3-minutes)
- Policy: [YouTube Help: channel monetization policies](https://support.google.com/youtube/answer/1311392),
  [PPC Land: inauthentic content](https://ppc.land/youtube-clarifies-inauthentic-content-policy-changes/)
- Clipping: [Whop Content Rewards docs](https://docs.whop.com/memberships-and-access/third-party-apps/content-rewards),
  [OpenClip: Whop clipping rates](https://openclip.app/guides/whop-clipping-guide), [Digiday: WTF is clipping](https://digiday.com/media/wtf-is-clipping-the-low-lift-creator-strategy-grabbing-advertisers-attention/),
  [Lex Clips announcement](https://x.com/lexfridman/status/1196133567308476417), [Diary of a CEO (Pay To Clip) listing](https://whop.com/clipper-school/clipper-school/)
