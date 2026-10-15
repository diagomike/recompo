"""Speaker jobs: diarisation, segment stamping, matching labels to known people."""

from __future__ import annotations

import bisect
import json

from ..speakers import people
from .jobs import JobCtx, task
from .tasks_speech import ensure_audio
from .worker_env import run_script


def stamp_segments(tx, db, source_id: str, ex_turns: list[dict]) -> int:
    """Each segment's speaker = the label talking most during it (exclusive turns)."""
    starts = [t["start"] for t in ex_turns]
    n = 0
    for tr in db.all("SELECT id FROM transcript WHERE source_id=?", (source_id,)):
        rows = db.all('SELECT id, start, "end" FROM segment WHERE transcript_id=?', (tr["id"],))
        updates = []
        for r in rows:
            k = max(0, bisect.bisect_right(starts, r["start"]) - 1)
            tally: dict[str, float] = {}
            for t in ex_turns[max(0, k - 1):]:
                if t["start"] >= r["end"]:
                    break
                ov = min(r["end"], t["end"]) - max(r["start"], t["start"])
                if ov > 0:
                    tally[t["speaker"]] = tally.get(t["speaker"], 0) + ov
            if tally:
                updates.append((max(tally, key=tally.get), r["id"]))
        tx.conn.executemany("UPDATE segment SET speaker=? WHERE id=?", updates)
        n += len(updates)
    return n


@task("diarize", lane="cpu")
def job_diarize(ctx: JobCtx):
    src = ctx.source()
    wav = ensure_audio(ctx, src)
    out = ctx.folder / "diarize.json"
    args = ["--wav", str(wav), "--out", str(out)]
    for k in ("speakers", "min", "max"):
        if ctx.params.get(k):
            args += [f"--{k}", str(ctx.params[k])]
    run_script("diarize", args, ctx)
    doc = json.loads(out.read_text(encoding="utf-8"))
    (people.emb_dir(ctx.project) / f"{src['ref']}.json").write_text(
        json.dumps({"centroids": doc["centroids"], "seconds": doc["seconds"]}), encoding="utf-8")
    db = ctx.db
    with db.op("speaker.diarize", "machine") as tx:
        tx.conn.execute("DELETE FROM speaker_turn WHERE source_id=?", (src["id"],))
        tx.conn.executemany('INSERT INTO speaker_turn(source_id, start, "end", label) VALUES(?,?,?,?)',
                            [(src["id"], t["start"], t["end"], t["speaker"]) for t in doc["exclusive"]])
        keep = {r["label"]: r for r in db.rows("speaker_label", "WHERE source_id=?", (src["id"],))}
        for lab in doc["labels"]:
            if lab in keep:
                tx.update("speaker_label", keep[lab]["id"], {"seconds": doc["seconds"].get(lab)}, log=False)
            else:
                tx.insert("speaker_label", {"source_id": src["id"], "label": lab, "seconds": doc["seconds"].get(lab)}, log=False)
        stamped = stamp_segments(tx, db, src["id"], doc["exclusive"])
        for r in db.rows("speaker_label", "WHERE source_id=? AND person_id IS NOT NULL", (src["id"],)):
            people.apply_person(tx, db, src["id"], r["label"], r["person_id"])
        matches = people.match_all(ctx.project, db, tx)
    ctx.set_status("speakers", "done")
    return {"speakers": len(doc["labels"]), "seconds": doc["seconds"], "segments": stamped, "matched": matches,
            "elapsed_s": doc["elapsed_s"]}
