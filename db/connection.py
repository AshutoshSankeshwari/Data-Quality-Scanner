"""
db/connection.py
SQLite database connection management using Python's built-in sqlite3.
Handles automatic schema initialization, WAL mode, and foreign keys.
"""
from __future__ import annotations
import sqlite3
from pathlib import Path
from typing import Optional

DEFAULT_DB_PATH = Path(__file__).parent.parent / "data" / "scanner.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def get_db_path(custom_path: Optional[str | Path] = None) -> Path:
    """Return resolved Path to the SQLite database file."""
    if custom_path is not None:
        return Path(custom_path)
    return DEFAULT_DB_PATH


def get_connection(db_path: Optional[str | Path] = None) -> sqlite3.Connection:
    """
    Open and return a sqlite3.Connection with Row factory, WAL mode,
    and foreign key constraints enabled.
    Auto-initializes schema on first connection if tables do not exist.
    """
    path = get_db_path(db_path)
    
    # Handle in-memory database
    if str(path) == ":memory:":
        conn = sqlite3.connect(":memory:")
    else:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path))

    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    if str(path) != ":memory:":
        conn.execute("PRAGMA journal_mode = WAL;")

    # Ensure schema exists
    _ensure_schema(conn)
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """Apply schema.sql if tables are not yet created, and apply safe migrations."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='scans';"
    )
    if cursor.fetchone()[0] == 0:
        if SCHEMA_PATH.exists():
            schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
            conn.executescript(schema_sql)
            conn.commit()
    else:
        # Non-destructive backward-compatible migration:
        # Check whether scans.affected_rows already exists before attempting to add it
        cursor.execute("PRAGMA table_info(scans);")
        existing_cols = {row["name"] for row in cursor.fetchall()}
        if "affected_rows" not in existing_cols:
            conn.execute("ALTER TABLE scans ADD COLUMN affected_rows INTEGER;")
            conn.commit()

