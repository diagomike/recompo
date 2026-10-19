"""SQLite schema. Migrations are append-only; ``PRAGMA user_version`` records how many ran.

Editorial tables carry the common columns ``id, ref, created_at, updated_at, created_by, prov``.
``prov`` maps each field to the actor who last wrote it; :mod:`recomp.core.store` uses it to
refuse lower-precedence overwrites.
"""

from __future__ import annotations

COMMON = """
    id TEXT PRIMARY KEY,
    ref TEXT UNIQUE,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    created_by TEXT NOT NULL DEFAULT 'machine',
    prov TEXT NOT NULL DEFAULT '{}'"""

MIGRATIONS: list[str] = [
    # 1 — everything the phases need, so later phases only add columns when they must.
    f"""
    CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
    CREATE TABLE refseq (kind TEXT PRIMARY KEY, next INTEGER NOT NULL);

    CREATE TABLE op (
        seq INTEGER PRIMARY KEY AUTOINCREMENT,
        id TEXT UNIQUE NOT NULL,
        time REAL NOT NULL,
        actor TEXT NOT NULL,
        verb TEXT NOT NULL,
        args TEXT NOT NULL DEFAULT '{{}}',
        summary TEXT NOT NULL DEFAULT '',
        changes TEXT NOT NULL DEFAULT '[]',
        refs TEXT NOT NULL DEFAULT '[]',
        state TEXT NOT NULL DEFAULT 'done',
        redoable INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE event (
        seq INTEGER PRIMARY KEY AUTOINCREMENT,
        time REAL NOT NULL,
        kind TEXT NOT NULL,
        payload TEXT NOT NULL DEFAULT '{{}}'
    );
    CREATE TABLE ui_state (key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at REAL NOT NULL);

    CREATE TABLE job (
        id TEXT PRIMARY KEY,
        ref TEXT UNIQUE,
        type TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'queued',
        backend TEXT NOT NULL DEFAULT 'local',
        source_id TEXT,
        target TEXT,
        params TEXT NOT NULL DEFAULT '{{}}',
        progress REAL NOT NULL DEFAULT 0,
        message TEXT NOT NULL DEFAULT '',
        result TEXT,
        error TEXT,
        depends_on TEXT NOT NULL DEFAULT '[]',
        folder TEXT,
        pid INTEGER,
        created_at REAL NOT NULL,
        started_at REAL,
        finished_at REAL,
        heartbeat REAL
    );

    CREATE TABLE source ({COMMON},
        kind TEXT NOT NULL,
        uri TEXT NOT NULL,
        path TEXT,
        platform TEXT,
        platform_id TEXT,
        title TEXT NOT NULL DEFAULT '',
        creator TEXT NOT NULL DEFAULT '',
        year INTEGER,
        language TEXT,
        duration REAL,
        size INTEGER,
        fingerprint TEXT,
        rights TEXT NOT NULL DEFAULT '{{}}',
        status TEXT NOT NULL DEFAULT '{{}}',
        meta TEXT NOT NULL DEFAULT '{{}}'
    );
    CREATE INDEX source_platform ON source(platform, platform_id);

    CREATE TABLE asset (
        id TEXT PRIMARY KEY,
        source_id TEXT NOT NULL REFERENCES source(id) ON DELETE CASCADE,
        role TEXT NOT NULL,
        path TEXT NOT NULL,
        range_start REAL,
        range_end REAL,
        info TEXT NOT NULL DEFAULT '{{}}',
        created_at REAL NOT NULL
    );

    CREATE TABLE transcript ({COMMON},
        source_id TEXT NOT NULL REFERENCES source(id) ON DELETE CASCADE,
        origin TEXT NOT NULL,
        language TEXT,
        model TEXT,
        label TEXT NOT NULL DEFAULT '',
        is_primary INTEGER NOT NULL DEFAULT 0,
        offset_s REAL NOT NULL DEFAULT 0,
        has_words INTEGER NOT NULL DEFAULT 0,
        stats TEXT NOT NULL DEFAULT '{{}}'
    );
    CREATE TABLE segment (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        transcript_id TEXT NOT NULL REFERENCES transcript(id) ON DELETE CASCADE,
        idx INTEGER NOT NULL,
        start REAL NOT NULL,
        "end" REAL NOT NULL,
        text TEXT NOT NULL,
        speaker TEXT,
        person_id TEXT,
        conf REAL,
        created_by TEXT NOT NULL DEFAULT 'machine',
        prov TEXT NOT NULL DEFAULT '{{}}',
        created_at REAL NOT NULL DEFAULT 0,
        updated_at REAL NOT NULL DEFAULT 0
    );
    CREATE INDEX segment_tr ON segment(transcript_id, idx);
    CREATE INDEX segment_time ON segment(transcript_id, start);
    CREATE VIRTUAL TABLE segment_fts USING fts5(text, content='segment', content_rowid='id',
        tokenize='unicode61 remove_diacritics 2');
    CREATE TRIGGER segment_ai AFTER INSERT ON segment BEGIN
        INSERT INTO segment_fts(rowid, text) VALUES (new.id, new.text);
    END;
    CREATE TRIGGER segment_ad AFTER DELETE ON segment BEGIN
        INSERT INTO segment_fts(segment_fts, rowid, text) VALUES ('delete', old.id, old.text);
    END;
    CREATE TRIGGER segment_au AFTER UPDATE OF text ON segment BEGIN
        INSERT INTO segment_fts(segment_fts, rowid, text) VALUES ('delete', old.id, old.text);
        INSERT INTO segment_fts(rowid, text) VALUES (new.id, new.text);
    END;
    CREATE TABLE word (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        segment_id INTEGER NOT NULL REFERENCES segment(id) ON DELETE CASCADE,
        idx INTEGER NOT NULL,
        start REAL NOT NULL,
        "end" REAL NOT NULL,
        text TEXT NOT NULL,
        prob REAL
    );
    CREATE INDEX word_seg ON word(segment_id, idx);

    CREATE TABLE shot (
        source_id TEXT NOT NULL REFERENCES source(id) ON DELETE CASCADE,
        t REAL NOT NULL,
        score REAL,
        PRIMARY KEY (source_id, t)
    );

    CREATE TABLE person ({COMMON},
        name TEXT NOT NULL,
        aliases TEXT NOT NULL DEFAULT '[]',
        note TEXT NOT NULL DEFAULT '',
        meta TEXT NOT NULL DEFAULT '{{}}'
    );
    CREATE TABLE speaker_turn (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_id TEXT NOT NULL REFERENCES source(id) ON DELETE CASCADE,
        start REAL NOT NULL,
        "end" REAL NOT NULL,
        label TEXT NOT NULL,
        person_id TEXT REFERENCES person(id) ON DELETE SET NULL,
        conf REAL
    );
    CREATE INDEX turn_src ON speaker_turn(source_id, start);
    CREATE TABLE speaker_label ({COMMON},
        source_id TEXT NOT NULL REFERENCES source(id) ON DELETE CASCADE,
        label TEXT NOT NULL,
        person_id TEXT REFERENCES person(id) ON DELETE SET NULL,
        score REAL,
        seconds REAL,
        UNIQUE (source_id, label)
    );

    CREATE TABLE chapter ({COMMON},
        source_id TEXT NOT NULL REFERENCES source(id) ON DELETE CASCADE,
        start REAL NOT NULL,
        "end" REAL NOT NULL,
        title TEXT NOT NULL DEFAULT '',
        summary TEXT NOT NULL DEFAULT '',
        tags TEXT NOT NULL DEFAULT '[]',
        method TEXT NOT NULL DEFAULT 'written'
    );
    CREATE INDEX chapter_src ON chapter(source_id, start);

    CREATE TABLE cut ({COMMON},
        source_id TEXT NOT NULL REFERENCES source(id) ON DELETE CASCADE,
        start REAL NOT NULL,
        "end" REAL NOT NULL,
        title TEXT NOT NULL DEFAULT '',
        quote TEXT NOT NULL DEFAULT '',
        why TEXT NOT NULL DEFAULT '',
        note TEXT NOT NULL DEFAULT '',
        tags TEXT NOT NULL DEFAULT '[]',
        emotions TEXT NOT NULL DEFAULT '[]',
        people TEXT NOT NULL DEFAULT '[]',
        chapter_id TEXT REFERENCES chapter(id) ON DELETE SET NULL,
        rating INTEGER,
        snap TEXT NOT NULL DEFAULT '{{}}'
    );
    CREATE INDEX cut_src ON cut(source_id, start);

    CREATE TABLE journey ({COMMON},
        title TEXT NOT NULL,
        intent TEXT NOT NULL DEFAULT '',
        description TEXT NOT NULL DEFAULT '',
        language TEXT NOT NULL DEFAULT 'en',
        status TEXT NOT NULL DEFAULT 'draft',
        settings TEXT NOT NULL DEFAULT '{{}}',
        links TEXT NOT NULL DEFAULT '{{}}'
    );
    CREATE TABLE slot ({COMMON},
        journey_id TEXT NOT NULL REFERENCES journey(id) ON DELETE CASCADE,
        pos REAL NOT NULL,
        cut_id TEXT NOT NULL REFERENCES cut(id),
        trim_in REAL,
        trim_out REAL,
        section TEXT NOT NULL DEFAULT '',
        transition TEXT NOT NULL DEFAULT '{{}}',
        settings TEXT NOT NULL DEFAULT '{{}}'
    );
    CREATE INDEX slot_j ON slot(journey_id, pos);
    CREATE TABLE overlay ({COMMON},
        journey_id TEXT NOT NULL REFERENCES journey(id) ON DELETE CASCADE,
        slot_id TEXT REFERENCES slot(id) ON DELETE CASCADE,
        kind TEXT NOT NULL,
        text TEXT NOT NULL DEFAULT '',
        style TEXT NOT NULL DEFAULT '{{}}',
        at REAL NOT NULL DEFAULT 0,
        dur REAL
    );

    CREATE TABLE music_track ({COMMON},
        provider TEXT NOT NULL,
        provider_id TEXT,
        url TEXT,
        page_url TEXT,
        file TEXT,
        title TEXT NOT NULL DEFAULT '',
        artist TEXT NOT NULL DEFAULT '',
        licence TEXT NOT NULL DEFAULT '',
        licence_url TEXT NOT NULL DEFAULT '',
        attribution TEXT NOT NULL DEFAULT '',
        duration REAL,
        meta TEXT NOT NULL DEFAULT '{{}}'
    );
    CREATE TABLE music_bed ({COMMON},
        journey_id TEXT NOT NULL REFERENCES journey(id) ON DELETE CASCADE,
        track_id TEXT NOT NULL REFERENCES music_track(id),
        at REAL NOT NULL DEFAULT 0,
        track_in REAL NOT NULL DEFAULT 0,
        dur REAL,
        gain_db REAL NOT NULL DEFAULT -16,
        duck_db REAL NOT NULL DEFAULT -10,
        fade_in REAL NOT NULL DEFAULT 1.5,
        fade_out REAL NOT NULL DEFAULT 2.5
    );

    CREATE TABLE profile ({COMMON},
        name TEXT UNIQUE NOT NULL,
        settings TEXT NOT NULL DEFAULT '{{}}'
    );
    CREATE TABLE export ({COMMON},
        journey_id TEXT REFERENCES journey(id) ON DELETE SET NULL,
        cut_id TEXT REFERENCES cut(id) ON DELETE SET NULL,
        profile TEXT NOT NULL,
        lang TEXT NOT NULL DEFAULT 'en',
        recipe_hash TEXT,
        status TEXT NOT NULL DEFAULT 'queued',
        job_id TEXT,
        folder TEXT,
        outputs TEXT NOT NULL DEFAULT '{{}}',
        checks TEXT NOT NULL DEFAULT '{{}}'
    );
    CREATE TABLE translation ({COMMON},
        lang TEXT NOT NULL,
        kind TEXT NOT NULL,
        target_id TEXT NOT NULL,
        text TEXT NOT NULL,
        method TEXT NOT NULL DEFAULT 'agent',
        UNIQUE (lang, kind, target_id)
    );
    """,
]

# The studio store (``studio.db`` in the studio home): what spans projects, i.e. the research wing (P17).
# Same store code as a project (op log, undo, precedence, events); its own append-only migrations.
STUDIO_MIGRATIONS: list[str] = [
    # 1 — P17a: follows, their inbox, and the transcript library (text only, searchable).
    f"""
    CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
    CREATE TABLE refseq (kind TEXT PRIMARY KEY, next INTEGER NOT NULL);
    CREATE TABLE op (
        seq INTEGER PRIMARY KEY AUTOINCREMENT,
        id TEXT UNIQUE NOT NULL,
        time REAL NOT NULL,
        actor TEXT NOT NULL,
        verb TEXT NOT NULL,
        args TEXT NOT NULL DEFAULT '{{}}',
        summary TEXT NOT NULL DEFAULT '',
        changes TEXT NOT NULL DEFAULT '[]',
        refs TEXT NOT NULL DEFAULT '[]',
        state TEXT NOT NULL DEFAULT 'done',
        redoable INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE event (
        seq INTEGER PRIMARY KEY AUTOINCREMENT,
        time REAL NOT NULL,
        kind TEXT NOT NULL,
        payload TEXT NOT NULL DEFAULT '{{}}'
    );
    CREATE TABLE ui_state (key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at REAL NOT NULL);

    CREATE TABLE follow ({COMMON},
        name TEXT NOT NULL,
        person TEXT NOT NULL DEFAULT '',
        projects TEXT NOT NULL DEFAULT '[]',
        feeds TEXT NOT NULL DEFAULT '{{}}',
        only_kind TEXT NOT NULL DEFAULT 'videos',
        match TEXT NOT NULL DEFAULT '',
        rights TEXT NOT NULL DEFAULT '{{}}',
        note TEXT NOT NULL DEFAULT '',
        state TEXT NOT NULL DEFAULT '{{}}'
    );
    CREATE TABLE follow_seen (
        follow_id TEXT NOT NULL REFERENCES follow(id) ON DELETE CASCADE,
        key TEXT NOT NULL,
        at REAL NOT NULL,
        PRIMARY KEY (follow_id, key)
    );
    CREATE TABLE inbox ({COMMON},
        follow_id TEXT REFERENCES follow(id) ON DELETE SET NULL,
        project TEXT NOT NULL DEFAULT '',
        key TEXT NOT NULL,
        kind TEXT NOT NULL DEFAULT 'video',
        title TEXT NOT NULL DEFAULT '',
        channel TEXT NOT NULL DEFAULT '',
        url TEXT NOT NULL DEFAULT '',
        video_id TEXT,
        published TEXT,
        duration REAL,
        route TEXT NOT NULL DEFAULT '{{}}',
        status TEXT NOT NULL DEFAULT 'new',
        taken TEXT NOT NULL DEFAULT '{{}}',
        meta TEXT NOT NULL DEFAULT '{{}}'
    );
    CREATE INDEX inbox_status ON inbox(status, project);
    CREATE UNIQUE INDEX inbox_key ON inbox(follow_id, key);

    CREATE TABLE lib_doc ({COMMON},
        follow_id TEXT REFERENCES follow(id) ON DELETE SET NULL,
        key TEXT UNIQUE NOT NULL,
        creator TEXT NOT NULL DEFAULT '',
        title TEXT NOT NULL DEFAULT '',
        published TEXT,
        url TEXT NOT NULL DEFAULT '',
        video_id TEXT,
        route TEXT NOT NULL DEFAULT '{{}}',
        language TEXT,
        stats TEXT NOT NULL DEFAULT '{{}}'
    );
    CREATE TABLE lib_seg (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        doc_id TEXT NOT NULL REFERENCES lib_doc(id) ON DELETE CASCADE,
        idx INTEGER NOT NULL,
        start REAL NOT NULL,
        "end" REAL NOT NULL,
        speaker TEXT,
        text TEXT NOT NULL
    );
    CREATE INDEX lib_seg_doc ON lib_seg(doc_id, idx);
    CREATE VIRTUAL TABLE lib_seg_fts USING fts5(text, content='lib_seg', content_rowid='id',
        tokenize='unicode61 remove_diacritics 2');
    CREATE TRIGGER lib_seg_ai AFTER INSERT ON lib_seg BEGIN
        INSERT INTO lib_seg_fts(rowid, text) VALUES (new.id, new.text);
    END;
    CREATE TRIGGER lib_seg_ad AFTER DELETE ON lib_seg BEGIN
        INSERT INTO lib_seg_fts(lib_seg_fts, rowid, text) VALUES ('delete', old.id, old.text);
    END;
    """,
    # 2 — P17b: topics (from the news or from you) and their briefs.
    f"""
    CREATE TABLE topic ({COMMON},
        title TEXT NOT NULL,
        terms TEXT NOT NULL DEFAULT '[]',
        follows TEXT NOT NULL DEFAULT '[]',
        since TEXT,
        news_query TEXT NOT NULL DEFAULT '',
        projects TEXT NOT NULL DEFAULT '[]',
        note TEXT NOT NULL DEFAULT '',
        brief TEXT NOT NULL DEFAULT '{{}}',
        state TEXT NOT NULL DEFAULT '{{}}'
    );
    """,
    # 3 — P17c: your channel and the posting queue (you upload; D-10).
    f"""
    CREATE TABLE channel ({COMMON},
        name TEXT NOT NULL,
        platform TEXT NOT NULL DEFAULT 'youtube',
        handle TEXT NOT NULL DEFAULT '',
        url TEXT NOT NULL DEFAULT '',
        placeholder INTEGER NOT NULL DEFAULT 0,
        stats TEXT NOT NULL DEFAULT '{{}}'
    );
    CREATE TABLE post ({COMMON},
        channel_id TEXT REFERENCES channel(id) ON DELETE SET NULL,
        project TEXT NOT NULL,
        export TEXT NOT NULL,
        journey TEXT,
        profile TEXT NOT NULL DEFAULT '',
        lang TEXT NOT NULL DEFAULT 'en',
        title TEXT NOT NULL DEFAULT '',
        description TEXT NOT NULL DEFAULT '',
        file TEXT NOT NULL DEFAULT '',
        at TEXT,
        status TEXT NOT NULL DEFAULT 'planned',
        url TEXT NOT NULL DEFAULT '',
        sources TEXT NOT NULL DEFAULT '[]',
        meta TEXT NOT NULL DEFAULT '{{}}'
    );
    CREATE INDEX post_status ON post(status, at);
    """,
]

# Columns stored as JSON text, decoded on read.
JSON_COLS: dict[str, set[str]] = {
    "follow": {"projects", "feeds", "rights", "state", "prov"},
    "inbox": {"route", "taken", "meta", "prov"},
    "lib_doc": {"route", "stats", "prov"},
    "topic": {"terms", "follows", "projects", "brief", "state", "prov"},
    "channel": {"stats", "prov"},
    "post": {"sources", "meta", "prov"},
    "op": {"args", "changes", "refs"},
    "event": {"payload"},
    "job": {"params", "result", "depends_on"},
    "source": {"rights", "status", "meta", "prov"},
    "asset": {"info"},
    "transcript": {"stats", "prov"},
    "segment": {"prov"},
    "person": {"aliases", "meta", "prov"},
    "speaker_label": {"prov"},
    "chapter": {"tags", "prov"},
    "cut": {"tags", "emotions", "people", "snap", "prov"},
    "journey": {"settings", "links", "prov"},
    "slot": {"transition", "settings", "prov"},
    "overlay": {"style", "prov"},
    "music_track": {"meta", "prov"},
    "music_bed": {"prov"},
    "profile": {"settings", "prov"},
    "export": {"outputs", "checks", "prov"},
    "translation": {"prov"},
}

# Tables whose rows carry provenance and go through the precedence guard.
EDITORIAL = {"source", "transcript", "segment", "person", "speaker_label", "chapter", "cut",
             "journey", "slot", "overlay", "music_track", "music_bed", "profile", "export",
             "translation", "follow", "inbox", "lib_doc", "topic", "channel", "post"}

# Bookkeeping fields written by jobs: no precedence guard, ignored when undo checks for conflicts.
UNGUARDED = {"status", "stats", "has_words", "updated_at", "outputs", "checks", "job_id", "recipe_hash", "state", "brief", "links",
             "idx", "seconds"}  # seconds: measured voice time; idx: segment order is renumbered in bulk by line splits; undo restores content, not position numbers
# links (journeys): hub ids, posted URLs and permission answers are bookkeeping, recorded by whoever publishes or posts.
# Where a status is a person's decision (a dismissed inbox item, a cancelled post), it is editorial: guarded and undone.
DECIDED_STATUS = {"inbox", "post"}


def unguarded(table: str) -> set[str]:
    return UNGUARDED - {"status"} if table in DECIDED_STATUS else UNGUARDED

# Child rows captured with a delete so undo can restore them (only op-logged children).
CHILDREN: dict[str, list[tuple[str, str]]] = {
    "journey": [("slot", "journey_id"), ("overlay", "journey_id"), ("music_bed", "journey_id")],
    "slot": [("overlay", "slot_id")],
    "source": [("chapter", "source_id"), ("cut", "source_id"), ("speaker_label", "source_id")],
    "follow": [("inbox", "follow_id")],
}

# Short-ref prefixes per table (chapters/transcripts get ``S1.c4`` / ``S1.t2`` style refs).
REF_PREFIX = {"source": "S", "cut": "C", "journey": "J", "overlay": "O", "music_track": "M",
              "music_bed": "B", "person": "P", "export": "X", "job": "job",
              "follow": "F", "inbox": "I", "lib_doc": "L", "topic": "T", "channel": "CH", "post": "Q"}
