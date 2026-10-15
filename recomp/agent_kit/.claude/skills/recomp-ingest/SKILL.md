---
name: recomp-ingest
description: Bring media into a Recomposer project — local files and folders, subtitles, YouTube/social links, channels and playlists — and get a usable transcript (sidecar subtitles, platform captions, or local ASR), including the YouTube caption/429 ladder.
---

# Ingesting sources

## Local media
- `recomp source add "D:\Recomp\Video\The.Dark.Knight*.mp4"` (a file, a folder or a glob). Files are
  referenced in place, never copied. A same-named `.srt` / `.vtt` / `.ass` next to the file is imported
  automatically; embedded subtitle streams too.
- Ingest queues jobs: probe, 16 kHz audio, shots, waveform peaks. `recomp source status` shows each stage.
- Moved a file? `recomp source relink S1 "E:\new\path.mp4"` (checked by fingerprint).

## Links (YouTube and anything yt-dlp reads)
- One video: `recomp source add https://youtu.be/ID`.
- Channel or playlist: `recomp source add https://www.youtube.com/@Channel/videos --limit 30` returns a
  **pick list** without adding anything. Add the ones you want: `recomp source add --pick 1,4,7` or
  `--match "consciousness"` / `--since 90d`.
- Links take metadata and creator chapters first (`recomp chapter seed S2`), then captions, then
  audio only if ASR is needed. **Video is fetched only for the ranges a journey uses** (exports do this).

## Transcripts: which one?
| Situation | Command |
|---|---|
| Sidecar or downloaded subtitle file | `recomp transcript import S1 file.srt` |
| Link with captions | `recomp transcript fetch-captions S2` (manual subs > `en-orig` auto captions) |
| No usable captions | `recomp transcript asr S3 [--lang en]` (local faster-whisper, word timings) |
| Unsure whether subtitles are in sync | `recomp transcript sync-check S1` → `--fix` applies the offset |

Subtitle files from the web are often offset by a release; always run `sync-check` once on
movies. ASR on CPU takes roughly 0.3–0.7× real time for whisper-turbo; start it, then chapter
whatever is already readable.

## YouTube refusing (HTTP 429, "confirm you're not a bot")
1. The fetchers already back off and retry. If a verb still fails with `E_EXTERNAL`, wait a few minutes.
2. Fallback: `recomp transcript asr S2` downloads audio only (~1 MB/min) and transcribes locally.
3. Using browser cookies is the **user's** decision; never configure it yourself. Ask them.
