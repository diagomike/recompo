"""P20: sample Friends scenes (EmoryNLP character-mining transcripts) for the nuance-transfer benchmark.

Random set R: scenes from seasons 1-3 with 14-32 utterances, seeded, read as whole scenes so every nuance item
in them is annotated (realistic density). Output: data/scenes_R.json with line ids S{season}E{ep}c{scene}-L{n}.
Usage: python sample_scenes.py <emorynlp json dir> <out json> [n_scenes] [seed]
"""
import json, random, sys
from pathlib import Path

src, out = Path(sys.argv[1]), Path(sys.argv[2])
n, seed = int(sys.argv[3]) if len(sys.argv) > 3 else 8, int(sys.argv[4]) if len(sys.argv) > 4 else 20
pool = []
for s in (1, 2, 3):
    d = json.loads((src / f"friends_season_{s:02d}.json").read_text())
    for ep in d["episodes"]:
        for sc in ep["scenes"]:
            us = [u for u in sc["utterances"] if u["transcript"].strip()]
            if 14 <= len(us) <= 32:
                pool.append((sc["scene_id"], us))
random.Random(seed).shuffle(pool)
picked = sorted(pool[:n], key=lambda x: x[0])
scenes = []
for sid, us in picked:
    key = f"S{int(sid[1:3])}E{int(sid.split('_')[1][1:])}c{int(sid.split('_')[2][1:])}"
    scenes.append({"scene": key, "source_id": sid, "lines": [
        {"id": f"{key}-L{i + 1}", "speaker": (u["speakers"] or ["?"])[0].split()[0], "text": u["transcript"].strip(),
         "note": u.get("transcript_with_note")} for i, u in enumerate(us)]})
out.write_text(json.dumps(scenes, indent=1, ensure_ascii=False))
print(len(pool), "candidate scenes;", sum(len(s["lines"]) for s in scenes), "lines in", [s["scene"] for s in scenes])
