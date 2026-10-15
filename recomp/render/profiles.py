"""Export profiles: format and treatment, kept separate from a journey's content.

A profile decides how a journey is rendered (aspect, size, reframe, caption style, whether
overlays and music play, loudness, endcard, dub mode); the journey decides what plays.
"""

from __future__ import annotations

import copy

BASE: dict = {
    "width": 1920, "height": 1080, "fps": 30,
    "reframe": "fit-pad",            # fit-blur | fit-pad | crop-center | crop-x
    "captions": "burn",              # burn | sidecar | off
    "caption_style": "clean",        # clean | karaoke | quote
    "caption_max_chars": None,       # characters per caption row (None: by format and script)
    "caption_max_lines": 2,          # rows per caption screen; longer lines become more screens
    "caption_scale": 1.0,            # caption font size factor
    "caption_margin": None,          # distance from the bottom as a fraction of the height (None: by format)
    "caption_lang": {},              # per-language overrides: {"am": {"max_chars": 24, "scale": 0.9}}
    "overlays": True,
    "lower_thirds": True,
    "music": True,
    "endcard": True,
    "endcard_seconds": 3.5,
    "title_card": True,
    "loudness": -14.0,
    "true_peak": -1.0,
    "video_codec": "libx264", "preset": "medium", "crf": 20,
    "audio_bitrate": "192k",
    "dub_mode": "voiceover",         # voiceover | replace
    "multitrack": False,
}

SEEDS: dict[str, dict] = {
    "shorts": {"width": 1080, "height": 1920, "reframe": "fit-blur", "caption_style": "karaoke",
               "description": "Vertical 9:16 for Shorts/Reels/TikTok: blurred-fill reframe, word-highlight captions"},
    "landscape": {"width": 1920, "height": 1080, "reframe": "fit-pad", "caption_style": "clean",
                  "description": "16:9 for YouTube: clean captions, lower thirds, endcard"},
    "square": {"width": 1080, "height": 1080, "reframe": "fit-blur", "caption_style": "clean",
               "description": "1:1 for feeds"},
    "clip": {"width": 1920, "height": 1080, "reframe": "fit-pad", "caption_style": "clean", "title_card": False,
             "endcard_seconds": 2.5, "description": "Single-cut export at 1080p"},
    "preview": {"width": 854, "height": 480, "preset": "ultrafast", "crf": 30, "audio_bitrate": "96k",
                "endcard_seconds": 2.0, "description": "Fast low-resolution check (keeps the source aspect class)"},
}


def resolve(settings: dict) -> dict:
    out = copy.deepcopy(BASE)
    out.update(settings or {})
    return out


def seed_profiles(project) -> list[str]:
    db = project.db
    made = []
    with db.op("profile.seed", "machine") as tx:
        for name, settings in SEEDS.items():
            if db.one("SELECT 1 FROM profile WHERE name=?", (name,)):
                continue
            tx.insert("profile", {"name": name, "settings": resolve(settings)}, log=False)
            made.append(name)
    return made
