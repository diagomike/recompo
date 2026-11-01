---
name: recomp-export
description: Export journeys and cuts from Recomposer — profiles (shorts, landscape, square, clip), the language matrix, translation and dubbing, automated checks, credits/attribution, upload packages and re-linking posted videos.
---

# Exporting

## Profiles
`recomp profile list` · `recomp profile show shorts`. The seeded ones:
`shorts` 1080×1920 (blurred-fill reframe, karaoke captions, endcard) · `landscape` 1920×1080 ·
`square` 1080×1080 · `clip` (single cuts, source aspect) · `preview` (480p, fastest).
Make your own: `recomp profile new reel --from shorts --caption-style clean --no-music`.

## Running
```
recomp preview J1                                   # quick look first
recomp export run J1 --profiles shorts,landscape --langs en
recomp export cuts C4 C9 --profile clip
recomp export status                                # jobs, outputs, check results
```
Outputs go to `exports/<journey>/<profile>-<lang>/`: `video.mp4`, `captions.srt`, `description.txt`
(title, credits, recipe link, ready to paste), `credits.json`, `recipe.json`, `thumb.jpg`.

## Other languages
1. Translate: write the translation yourself (best) with `recomp lang translate J1 --to am --input am.json`
   (get the source lines with `recomp lang translate J1 --to am --template`), or `--engine google` for a draft.
   For dub lines timed to the speaker's frames, any language pair, use the LLM dubber (`recomp-dub` skill).
2. Dub by exporting the language: `recomp export run J1 --profiles shorts --langs am,sw,fr` voices every line
   (edge-tts neural voices; `recomp lang voices am`, audition with `recomp lang say "…" --lang am`; Oromo uses
   MMS-TTS). Voice-over ducks the original under the dub; a profile with `--dub-mode replace` puts the dub over
   the separated background instead. `--no-dub` exports subtitles only.
3. Check `recomp export show X…`: `dub fit` lists lines too long for their time. Shorten those lines
   (`lang translate --input` with just their keys) and export again; unchanged lines are cached. Short
   interjections that cannot fit keep the original voice. `dub intelligibility` re-transcribes the dub
   (CER/WER ≤ 0.35 passes).

## Checks (automatic on every export)
Duration, loudness (−14 LUFS ±1), caption timing, audio language tags, dub overflow, and for dubs a
round-trip ASR intelligibility score. `recomp export check X3` re-runs them. Report failures to the user
before calling an export done.

## Credits and sharing
Credits are generated from source and music metadata; never type them by hand. Fix a source's
rights with `recomp source rights S1 --owner "…" --notice "…"`. The user uploads videos themselves.
Afterwards, `recomp hub link-post J1 <posted url>` links the post to the recipe.
`recomp hub publish J1` shares the recipe (not the media). Ask before publishing anywhere that is not local.
