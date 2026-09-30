"""Database access."""

import os
import sqlite3
from pathlib import Path

# Set BAR_DB_PATH to move the database (the add-on uses /data/bar.db, which survives updates).
_DEFAULT_DB = Path(__file__).resolve().parent.parent / "bar.db"
DB_PATH = Path(os.getenv("BAR_DB_PATH") or _DEFAULT_DB)


# Schema
# ingredient is a tree via parent_id; a requirement is met by anything in its subtree.
# Garnishes are plain text on recipe, so a missing garnish never blocks a drink.

SCHEMA = """
CREATE TABLE IF NOT EXISTS ingredient (
    id              TEXT PRIMARY KEY,       -- slug, e.g. 'sweet-vermouth'
    name            TEXT NOT NULL,          -- display name, 'Sweet Vermouth'
    parent_id       TEXT REFERENCES ingredient(id),
    assumed_on_hand INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS ingredient_alias (
    alias         TEXT PRIMARY KEY,         -- lowercase fragment, 'carpano'
    ingredient_id TEXT NOT NULL REFERENCES ingredient(id)
);

CREATE TABLE IF NOT EXISTS bottle (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    barcode       TEXT,                     -- null when hand-entered
    product_name  TEXT NOT NULL,            -- what the label says
    ingredient_id TEXT NOT NULL REFERENCES ingredient(id),
    added_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS recipe (
    id           TEXT PRIMARY KEY,          -- slug, e.g. 'negroni'
    name         TEXT NOT NULL,
    glass        TEXT,                      -- 'rocks', 'coupe', 'collins'
    method       TEXT,                      -- 'stirred', 'shaken', 'built'
    garnish      TEXT,                      -- free text, never a requirement
    instructions TEXT,                      -- one-line summary
    steps        TEXT,                      -- numbered walkthrough, one step per line
    source       TEXT NOT NULL DEFAULT 'curated',
    source_ref   TEXT,                      -- id in the source dataset
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    kind         TEXT NOT NULL DEFAULT 'cocktail',   -- 'cocktail' | 'shot'
    rank         INTEGER NOT NULL DEFAULT 3000,      -- lower = more common
    hidden       INTEGER NOT NULL DEFAULT 0,
    edited       INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS recipe_ingredient (
    recipe_id     TEXT NOT NULL REFERENCES recipe(id) ON DELETE CASCADE,
    position      INTEGER NOT NULL,         -- display order within the recipe
    ingredient_id TEXT NOT NULL REFERENCES ingredient(id),
    amount        TEXT,                     -- free text
    optional      INTEGER NOT NULL DEFAULT 0,
    note          TEXT,                     -- 'rinse', or the source's wording
    PRIMARY KEY (recipe_id, position)
);

CREATE TABLE IF NOT EXISTS barcode_product (
    barcode       TEXT PRIMARY KEY,         -- normalised (UPC-A widened to EAN-13)
    product_name  TEXT,                     -- NULL = asked everyone, nobody knew
    brand         TEXT,
    source        TEXT NOT NULL,            -- openfoodfacts | upcitemdb | manual | none
    ingredient_id TEXT REFERENCES ingredient(id),  -- the category YOU confirmed
    looked_up_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE INDEX IF NOT EXISTS idx_bottle_barcode     ON bottle(barcode);
CREATE INDEX IF NOT EXISTS idx_ingredient_parent ON ingredient(parent_id);
CREATE INDEX IF NOT EXISTS idx_bottle_ingredient ON bottle(ingredient_id);
CREATE INDEX IF NOT EXISTS idx_ri_recipe        ON recipe_ingredient(recipe_id);
CREATE INDEX IF NOT EXISTS idx_ri_ingredient    ON recipe_ingredient(ingredient_id);
"""


def connect() -> sqlite3.Connection:
    """Open a connection with the settings we always want."""
    # check_same_thread=False: FastAPI may run the dependency and the endpoint on different threads.
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    # Rows behave like dicts: row["name"].
    conn.row_factory = sqlite3.Row
    # SQLite ignores foreign keys unless enabled.
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# Migration
# CREATE TABLE IF NOT EXISTS won't add new columns, so add them here.

def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    """The column names currently on a table."""
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


def migrate(conn: sqlite3.Connection) -> None:
    """Bring an existing database up to the current schema."""
    if "assumed_on_hand" not in _columns(conn, "ingredient"):
        with conn:
            conn.execute(
                "ALTER TABLE ingredient "
                "ADD COLUMN assumed_on_hand INTEGER NOT NULL DEFAULT 0"
            )
    # Added for the iPad recipe view; seed_recipes() fills it on startup.
    if "steps" not in _columns(conn, "recipe"):
        with conn:
            conn.execute("ALTER TABLE recipe ADD COLUMN steps TEXT")
    # Added with the recipe library and the phone editor.
    for column, ddl in (
        ("kind",   "kind TEXT NOT NULL DEFAULT 'cocktail'"),
        ("rank",   "rank INTEGER NOT NULL DEFAULT 3000"),
        ("hidden", "hidden INTEGER NOT NULL DEFAULT 0"),
        ("edited", "edited INTEGER NOT NULL DEFAULT 0"),
    ):
        if column not in _columns(conn, "recipe"):
            with conn:
                conn.execute(f"ALTER TABLE recipe ADD COLUMN {ddl}")


def init_db() -> None:
    """Create tables, then migrate."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = connect()
    with conn:
        conn.executescript(SCHEMA)
    migrate(conn)
    conn.close()


def get_db():
    """FastAPI dependency."""
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()
