import sqlite3
import os
from contextlib import contextmanager
from pathlib import Path
from config import Config

import tempfile

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS files (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    filename TEXT NOT NULL,
    gst_type TEXT NOT NULL,
    period TEXT,
    status TEXT DEFAULT 'processing',
    error TEXT,
    uploaded_at TEXT NOT NULL,
    is_active INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_files_user_id ON files(user_id);
CREATE INDEX IF NOT EXISTS idx_files_period ON files(period);

CREATE TABLE IF NOT EXISTS extracted_data (
    file_id TEXT PRIMARY KEY,
    data_json TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS analytics (
    file_id TEXT PRIMARY KEY,
    data_json TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS reconciliations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT DEFAULT 'default_user',
    period TEXT NOT NULL,
    data_json TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(user_id, period)
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT DEFAULT 'default_user',
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    sources_json TEXT,
    timestamp TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chat_user ON chat_messages(user_id);
"""

def get_db_path(override_path=None):
    path = override_path or os.getenv("DATABASE_PATH") or Config.DATABASE_PATH
    if Config.IS_VERCEL:
        if not path or path.startswith("/app") or not path.startswith(tempfile.gettempdir()):
            path = str(Path(tempfile.gettempdir()) / "gst_data" / "gst_intelligence.db")
    return path

@contextmanager
def get_db_connection(db_path=None):
    path = get_db_path(db_path)
    try:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        path = str(Path(tempfile.gettempdir()) / "gst_data" / "gst_intelligence.db")
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    
    # Use DELETE rollback mode on Vercel Serverless to prevent orphaned -shm/-wal locks across cold/warm starts
    journal_mode = "DELETE" if Config.IS_VERCEL else "WAL"
    conn.execute(f"PRAGMA journal_mode = {journal_mode};")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA busy_timeout = 5000;")

    # Ensure tables exist if this is a fresh database
    table_check = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users';").fetchone()
    if not table_check:
        conn.executescript(_SCHEMA_SQL)
        conn.commit()

    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db(db_path=None):
    """Initialize database tables, indexes, and constraints."""
    with get_db_connection(db_path) as conn:
        conn.executescript(_SCHEMA_SQL)
