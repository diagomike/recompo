"""Hub storage (SQLite). Users, sessions, recipes with versions, votes, comments, follows, post links."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS user (
    id TEXT PRIMARY KEY, handle TEXT UNIQUE NOT NULL, display TEXT NOT NULL DEFAULT '', bio TEXT NOT NULL DEFAULT '',
    pw_salt TEXT NOT NULL, pw_hash TEXT NOT NULL, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS session (token TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES user(id) ON DELETE CASCADE,
    created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS recipe (
    id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES user(id) ON DELETE CASCADE, title TEXT NOT NULL,
    intent TEXT NOT NULL DEFAULT '', description TEXT NOT NULL DEFAULT '', visibility TEXT NOT NULL DEFAULT 'public',
    tags TEXT NOT NULL DEFAULT '[]', languages TEXT NOT NULL DEFAULT '[]', version INTEGER NOT NULL DEFAULT 1,
    hash TEXT, forked_from TEXT, duration REAL, slots INTEGER, thumbnail TEXT, created REAL NOT NULL, updated REAL NOT NULL);
CREATE INDEX IF NOT EXISTS recipe_owner ON recipe(owner_id);
CREATE TABLE IF NOT EXISTS recipe_version (recipe_id TEXT NOT NULL REFERENCES recipe(id) ON DELETE CASCADE,
    n INTEGER NOT NULL, hash TEXT, body TEXT NOT NULL, created REAL NOT NULL, PRIMARY KEY (recipe_id, n));
CREATE TABLE IF NOT EXISTS recipe_source (recipe_id TEXT NOT NULL REFERENCES recipe(id) ON DELETE CASCADE,
    key TEXT NOT NULL, title TEXT NOT NULL DEFAULT '', creator TEXT NOT NULL DEFAULT '', platform TEXT, url TEXT,
    duration REAL, PRIMARY KEY (recipe_id, key));
CREATE INDEX IF NOT EXISTS recipe_source_key ON recipe_source(key);
CREATE TABLE IF NOT EXISTS moment (recipe_id TEXT NOT NULL REFERENCES recipe(id) ON DELETE CASCADE, key TEXT NOT NULL,
    t_in REAL NOT NULL, t_out REAL NOT NULL);
CREATE INDEX IF NOT EXISTS moment_key ON moment(key);
CREATE TABLE IF NOT EXISTS vote (user_id TEXT NOT NULL REFERENCES user(id) ON DELETE CASCADE,
    recipe_id TEXT NOT NULL REFERENCES recipe(id) ON DELETE CASCADE, value INTEGER NOT NULL, created REAL NOT NULL,
    PRIMARY KEY (user_id, recipe_id));
CREATE TABLE IF NOT EXISTS comment (id TEXT PRIMARY KEY, recipe_id TEXT NOT NULL REFERENCES recipe(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES user(id) ON DELETE CASCADE, parent_id TEXT, body TEXT NOT NULL,
    created REAL NOT NULL, edited REAL, deleted INTEGER NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS comment_recipe ON comment(recipe_id, created);
CREATE TABLE IF NOT EXISTS follow (follower_id TEXT NOT NULL REFERENCES user(id) ON DELETE CASCADE,
    followee_id TEXT NOT NULL REFERENCES user(id) ON DELETE CASCADE, created REAL NOT NULL, PRIMARY KEY (follower_id, followee_id));
CREATE TABLE IF NOT EXISTS post_link (id TEXT PRIMARY KEY, recipe_id TEXT NOT NULL REFERENCES recipe(id) ON DELETE CASCADE,
    url TEXT NOT NULL, platform TEXT, lang TEXT, user_id TEXT NOT NULL, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS report (id TEXT PRIMARY KEY, recipe_id TEXT, comment_id TEXT, user_id TEXT NOT NULL,
    reason TEXT NOT NULL, created REAL NOT NULL);
"""


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)
    return conn
