"""SQLite-schema en connectiebeheer voor de Evaluatiematrix-app.

Eén lokale database (`projects/evaluatiematrix.db`) voor alle projecten.
Documentbestanden zelf staan op schijf onder `projects/<project_id>/`.
"""
from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

from app.config import DB_PATH, ensure_dirs

SCHEMA_VERSION = 1


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def get_conn():
    ensure_dirs()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


DDL = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    naam TEXT NOT NULL,
    opdrachtgever TEXT,
    status TEXT NOT NULL DEFAULT 'actief',   -- actief | gearchiveerd
    matrix_status TEXT NOT NULL DEFAULT 'concept',  -- concept | vastgesteld
    aangemaakt_op TEXT NOT NULL,
    bijgewerkt_op TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS documenten (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    bestandsnaam TEXT NOT NULL,
    pad TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'overig',  -- offerte-aanvraag | SLA | contractvoorwaarden | PvE | overig
    status TEXT NOT NULL DEFAULT 'wachten',  -- wachten | bezig | klaar | fout
    foutmelding TEXT,
    geextraheerde_tekst TEXT,
    geupload_op TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS categorieen (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    naam TEXT NOT NULL,
    weging REAL NOT NULL DEFAULT 0,
    volgorde INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS criteria (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    categorie_id TEXT NOT NULL REFERENCES categorieen(id) ON DELETE CASCADE,
    naam TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'score',  -- score | knock-out
    schaal TEXT NOT NULL DEFAULT '0-10',
    weging REAL NOT NULL DEFAULT 0,
    bron TEXT,
    toelichting TEXT,
    volgorde INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS leveranciers (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    naam TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'nog niet gescoord',
    uitgesloten INTEGER NOT NULL DEFAULT 0,
    volgorde INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS leverancier_documenten (
    id TEXT PRIMARY KEY,
    leverancier_id TEXT NOT NULL REFERENCES leveranciers(id) ON DELETE CASCADE,
    bestandsnaam TEXT NOT NULL,
    pad TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'wachten',
    foutmelding TEXT,
    geextraheerde_tekst TEXT,
    geupload_op TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scores (
    id TEXT PRIMARY KEY,
    leverancier_id TEXT NOT NULL REFERENCES leveranciers(id) ON DELETE CASCADE,
    criterium_id TEXT NOT NULL REFERENCES criteria(id) ON DELETE CASCADE,
    score REAL,
    voldaan INTEGER,  -- voor knock-out: 1/0/NULL
    onderbouwing TEXT,
    citaat TEXT,
    vertrouwen TEXT,
    overschreven_door_gebruiker INTEGER NOT NULL DEFAULT 0,
    gebruiker_commentaar TEXT,
    nader_verifieren INTEGER NOT NULL DEFAULT 0,
    bijgewerkt_op TEXT NOT NULL,
    UNIQUE(leverancier_id, criterium_id)
);
"""


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(DDL)
        conn.execute(
            "INSERT OR IGNORE INTO meta (key, value) VALUES ('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )
