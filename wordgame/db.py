import sqlite3

import click
from flask import current_app, g
from werkzeug.security import generate_password_hash

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('admin', 'player')),
    created_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS words (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    word     TEXT NOT NULL UNIQUE CHECK (length(word) = 5 AND word = upper(word)),
    added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- One row per word handed to a player ("the words given").
CREATE TABLE IF NOT EXISTS games (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    word_id     INTEGER NOT NULL REFERENCES words(id),
    played_on   TEXT NOT NULL,              -- YYYY-MM-DD, drives the 3-per-day rule and reports
    status      TEXT NOT NULL DEFAULT 'in_progress'
                CHECK (status IN ('in_progress', 'won', 'lost')),
    started_at  TEXT NOT NULL,
    finished_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_games_user_day ON games (user_id, played_on);
CREATE INDEX IF NOT EXISTS idx_games_day ON games (played_on);

-- Every guess the player submitted for a given word, in order, with a timestamp.
CREATE TABLE IF NOT EXISTS guesses (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id    INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    attempt_no INTEGER NOT NULL CHECK (attempt_no BETWEEN 1 AND 5),
    guess      TEXT NOT NULL,
    guessed_at TEXT NOT NULL,
    UNIQUE (game_id, attempt_no)
);
"""

STARTER_WORDS = [
    "CRANE", "PLANT", "BRICK", "SHINE", "GHOST",
    "FLAME", "OCEAN", "TIGER", "MANGO", "STORM",
    "CLOUD", "PIANO", "RIVER", "LEMON", "CHAIR",
    "BREAD", "FROST", "GRAPE", "HOUSE", "TOWER",
]


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Create tables and seed starter data. Safe to run on every start."""
    db = get_db()
    db.executescript(SCHEMA)

    # Seed words only on an empty table, so words an admin removed stay removed.
    if db.execute("SELECT COUNT(*) FROM words").fetchone()[0] == 0:
        db.executemany("INSERT INTO words (word) VALUES (?)", [(w,) for w in STARTER_WORDS])

    if db.execute("SELECT 1 FROM users WHERE role = 'admin' LIMIT 1").fetchone() is None:
        db.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, 'admin')",
            (
                current_app.config["ADMIN_USERNAME"],
                generate_password_hash(current_app.config["ADMIN_PASSWORD"]),
            ),
        )
    db.commit()


@click.command("reset-db")
def reset_db_command():
    """Drop all data and recreate the database with starter words and the admin account."""
    db = get_db()
    db.executescript(
        "DROP TABLE IF EXISTS guesses; DROP TABLE IF EXISTS games;"
        "DROP TABLE IF EXISTS words; DROP TABLE IF EXISTS users;"
    )
    init_db()
    click.echo("Database reset.")


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(reset_db_command)
