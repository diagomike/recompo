"""People across sources: speaker labels per source (from diarisation) linked to project-level persons.

Each source's labels carry a centroid embedding (pyannote's own). A person's centroid is the mean
of the labels linked to them; an unlinked label joins a person when its cosine similarity clears
the threshold (machine origin, so the user and agent can always correct it).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

THRESHOLD = 0.70


def emb_dir(project) -> Path:
    return project.dir("cache", "speakers")


def load_label_emb(project, src_ref: str, label: str) -> np.ndarray | None:
    p = emb_dir(project) / f"{src_ref}.json"
    if not p.exists():
        return None
    data = json.loads(p.read_text(encoding="utf-8"))
    v = data.get("centroids", {}).get(label)
    return np.asarray(v, dtype="float32") if v else None


def cos(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))


def person_centroid(project, db, person_id: str) -> np.ndarray | None:
    vecs = []
    for r in db.all("SELECT sl.label, s.ref FROM speaker_label sl JOIN source s ON s.id=sl.source_id WHERE sl.person_id=?",
                    (person_id,)):
        v = load_label_emb(project, r["ref"], r["label"])
        if v is not None:
            vecs.append(v / (np.linalg.norm(v) + 1e-9))
    return np.mean(vecs, axis=0) if vecs else None


def apply_person(tx, db, source_id: str, label: str, person_id: str | None) -> int:
    """Stamp segments and turns of a source's label with a person (bulk machine data)."""
    tx.conn.execute("UPDATE speaker_turn SET person_id=? WHERE source_id=? AND label=?", (person_id, source_id, label))
    cur = tx.conn.execute("UPDATE segment SET person_id=? WHERE speaker=? AND transcript_id IN "
                          "(SELECT id FROM transcript WHERE source_id=?)", (person_id, label, source_id))
    return cur.rowcount


def match_all(project, db, tx, threshold: float = THRESHOLD) -> list[dict]:
    """Link unlinked labels to the best-matching person above the threshold."""
    persons = {p["id"]: person_centroid(project, db, p["id"]) for p in db.rows("person")}
    persons = {k: v for k, v in persons.items() if v is not None}
    out = []
    for row in db.rows("speaker_label", "WHERE person_id IS NULL"):
        src = db.get("source", row["source_id"])
        v = load_label_emb(project, src["ref"], row["label"])
        if v is None or not persons:
            continue
        best = max(persons.items(), key=lambda kv: cos(v, kv[1]))
        score = cos(v, best[1])
        if score >= threshold:
            tx.update("speaker_label", row["id"], {"person_id": best[0], "score": round(score, 3)})
            n = apply_person(tx, db, row["source_id"], row["label"], best[0])
            person = db.get("person", best[0])
            out.append({"source": src["ref"], "label": row["label"], "person": person["name"], "ref": person["ref"],
                        "score": round(score, 3), "segments": n})
    return out
