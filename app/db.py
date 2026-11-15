"""SQLite access: one short-lived connection per call, schema migrations via PRAGMA user_version."""

import json
import os
import sqlite3
import time
from contextlib import contextmanager

DB_PATH = os.environ.get("DB_PATH", "./data/reiseplaner.db")

# Append only. Each entry runs once, in order; never edit an entry that has shipped.
MIGRATIONS = [
    """
    CREATE TABLE users (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL UNIQUE COLLATE NOCASE,
        pw_hash TEXT NOT NULL,
        is_admin INTEGER NOT NULL DEFAULT 0,
        created_at REAL NOT NULL
    );
    CREATE TABLE sessions (
        token_hash TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        created_at REAL NOT NULL
    );
    CREATE TABLE trips (
        id INTEGER PRIMARY KEY,
        title TEXT NOT NULL,
        destination TEXT NOT NULL,
        lat REAL NOT NULL,
        lon REAL NOT NULL,
        bbox TEXT NOT NULL,              -- JSON [south, north, west, east]
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        mode TEXT NOT NULL DEFAULT 'foot',
        invite_code TEXT NOT NULL UNIQUE,
        wishes TEXT NOT NULL DEFAULT '',
        job TEXT NOT NULL DEFAULT '{"state":"idle"}',
        created_by INTEGER NOT NULL REFERENCES users(id),
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL
    );
    CREATE TABLE trip_members (
        trip_id INTEGER NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        PRIMARY KEY (trip_id, user_id)
    );
    CREATE TABLE places (
        id INTEGER PRIMARY KEY,
        trip_id INTEGER NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
        name TEXT NOT NULL,
        kind TEXT NOT NULL DEFAULT 'other',
        meals TEXT NOT NULL DEFAULT '[]',     -- JSON list of breakfast|lunch|dinner
        lat REAL NOT NULL,
        lon REAL NOT NULL,
        status TEXT NOT NULL DEFAULT 'accepted',  -- suggested|accepted|rejected
        day INTEGER,                          -- 1-based day of the trip, NULL = idea without a day
        pos INTEGER NOT NULL DEFAULT 0,
        source TEXT NOT NULL DEFAULT 'manual',    -- ai|wiki|manual
        reason TEXT NOT NULL DEFAULT '',
        note TEXT NOT NULL DEFAULT '',
        verified INTEGER NOT NULL DEFAULT 0,  -- position confirmed by OSM or Wikipedia
        osm_ref TEXT NOT NULL DEFAULT '',     -- e.g. way/123
        address TEXT NOT NULL DEFAULT '',
        opening_hours TEXT NOT NULL DEFAULT '',
        website TEXT NOT NULL DEFAULT '',
        phone TEXT NOT NULL DEFAULT '',
        wikidata TEXT NOT NULL DEFAULT '',
        wikipedia TEXT NOT NULL DEFAULT '',   -- lang:Title, from OSM
        wiki_hint TEXT NOT NULL DEFAULT '',   -- article title guessed by the AI, checked before use
        info TEXT NOT NULL DEFAULT '{}',      -- JSON: summary, history, facts, source links, image
        info_status TEXT NOT NULL DEFAULT 'none',  -- none|pending|done
        created_by INTEGER REFERENCES users(id),
        created_at REAL NOT NULL
    );
    CREATE INDEX places_trip ON places(trip_id);
    CREATE TABLE votes (
        place_id INTEGER NOT NULL REFERENCES places(id) ON DELETE CASCADE,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        PRIMARY KEY (place_id, user_id)
    );
    CREATE TABLE cache (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        created_at REAL NOT NULL
    );
    """,
    # 2: hotel as start and end of each day, per-leg preferences, undo for weather replanning
    """
    ALTER TABLE trips ADD COLUMN hotel_id INTEGER;
    ALTER TABLE trips ADD COLUMN replan TEXT NOT NULL DEFAULT '{}';
    -- how to get from this place to the next stop: auto|walk|transit; a labelled walk is a suggested stroll
    ALTER TABLE places ADD COLUMN leg_mode TEXT NOT NULL DEFAULT 'auto';
    ALTER TABLE places ADD COLUMN walk_label TEXT NOT NULL DEFAULT '';
    ALTER TABLE places ADD COLUMN walk_via TEXT NOT NULL DEFAULT '';   -- JSON [lat, lon] the stroll passes through
    """,
    # 3: timetable of a day: time spent per stop, start time per day, live progress on the day itself
    """
    ALTER TABLE places ADD COLUMN stay_min INTEGER;                      -- NULL = default for the kind of place
    ALTER TABLE trips ADD COLUMN day_starts TEXT NOT NULL DEFAULT '{}';  -- JSON {day: "HH:MM"}, missing = 09:00
    -- JSON {date, passed, left_at}: how many points of that day's route the group has left, and when it left the last
    ALTER TABLE trips ADD COLUMN live TEXT NOT NULL DEFAULT '{}';
    """,
]


def connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH, timeout=20)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    return con


def init() -> None:
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    con = connect()
    try:
        con.execute("PRAGMA journal_mode=WAL")
        version = con.execute("PRAGMA user_version").fetchone()[0]
        for i, script in enumerate(MIGRATIONS[version:], start=version + 1):
            con.executescript(script)
            con.execute(f"PRAGMA user_version={i}")
        con.commit()
    finally:
        con.close()


@contextmanager
def tx():
    """Several statements in one transaction."""
    con = connect()
    try:
        yield con
        con.commit()
    finally:
        con.close()


def q(sql: str, args: tuple = ()) -> list[dict]:
    con = connect()
    try:
        return [dict(r) for r in con.execute(sql, args).fetchall()]
    finally:
        con.close()


def one(sql: str, args: tuple = ()) -> dict | None:
    rows = q(sql, args)
    return rows[0] if rows else None


def run(sql: str, args: tuple = ()) -> int:
    """Execute a write; returns lastrowid."""
    with tx() as con:
        return con.execute(sql, args).lastrowid


def cache_get(key: str, max_age_days: float | None = None):
    row = one("SELECT value, created_at FROM cache WHERE key=?", (key,))
    if not row or (max_age_days and time.time() - row["created_at"] > max_age_days * 86400):
        return None
    return json.loads(row["value"])


def cache_set(key: str, value) -> None:
    run("INSERT OR REPLACE INTO cache (key, value, created_at) VALUES (?,?,?)",
        (key, json.dumps(value, ensure_ascii=False), time.time()))
