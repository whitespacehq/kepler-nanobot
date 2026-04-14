"""SQLite storage for monitoring events.

Single DB file in the workspace directory, WAL mode for concurrent
reads (Next.js dashboard) and writes (MonitoringHook).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from loguru import logger

_SCHEMA = """\
CREATE TABLE IF NOT EXISTS iterations (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    session_key           TEXT NOT NULL,
    model                 TEXT NOT NULL,
    iteration             INTEGER NOT NULL,
    prompt_tokens         INTEGER NOT NULL DEFAULT 0,
    completion_tokens     INTEGER NOT NULL DEFAULT 0,
    cached_tokens         INTEGER NOT NULL DEFAULT 0,
    cache_creation_tokens INTEGER NOT NULL DEFAULT 0,
    stop_reason           TEXT,
    error                 TEXT,
    user_content          TEXT,
    assistant_content     TEXT,
    created_at            TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tool_calls (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    iteration_id  INTEGER NOT NULL REFERENCES iterations(id),
    session_key   TEXT NOT NULL,
    tool_name     TEXT NOT NULL,
    arguments     TEXT,
    result        TEXT,
    duration_ms   INTEGER,
    created_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS heartbeat_events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    action     TEXT NOT NULL,
    tasks      TEXT,
    result     TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_iterations_session ON iterations(session_key);
CREATE INDEX IF NOT EXISTS idx_iterations_created ON iterations(created_at);
CREATE INDEX IF NOT EXISTS idx_tool_calls_session ON tool_calls(session_key);
CREATE INDEX IF NOT EXISTS idx_tool_calls_name ON tool_calls(tool_name);
CREATE INDEX IF NOT EXISTS idx_tool_calls_created ON tool_calls(created_at);
"""

# COBBLE: Migrations for existing databases that were created before
# content capture was added.
_MIGRATIONS = [
    ("iterations", "user_content", "ALTER TABLE iterations ADD COLUMN user_content TEXT"),
    ("iterations", "assistant_content", "ALTER TABLE iterations ADD COLUMN assistant_content TEXT"),
    ("tool_calls", "result", "ALTER TABLE tool_calls ADD COLUMN result TEXT"),
]


def _migrate(conn: sqlite3.Connection) -> None:
    """Apply column migrations to existing databases."""
    for table, column, sql in _MIGRATIONS:
        try:
            conn.execute(f"SELECT {column} FROM {table} LIMIT 0")
        except sqlite3.OperationalError:
            logger.info(f"Migrating monitor DB: adding {table}.{column}")
            conn.execute(sql)
    conn.commit()


def init_db(db_path: Path) -> sqlite3.Connection:
    """Open (or create) the monitoring database and ensure the schema exists."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.executescript(_SCHEMA)
    _migrate(conn)
    conn.commit()
    return conn


def insert_iteration(
    conn: sqlite3.Connection,
    *,
    session_key: str,
    model: str,
    iteration: int,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    cached_tokens: int = 0,
    cache_creation_tokens: int = 0,
    stop_reason: str | None = None,
    error: str | None = None,
    user_content: str | None = None,
    assistant_content: str | None = None,
) -> int:
    """Insert an iteration record and return its row id."""
    cur = conn.execute(
        """INSERT INTO iterations
           (session_key, model, iteration, prompt_tokens, completion_tokens,
            cached_tokens, cache_creation_tokens, stop_reason, error,
            user_content, assistant_content)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (session_key, model, iteration, prompt_tokens, completion_tokens,
         cached_tokens, cache_creation_tokens, stop_reason, error,
         user_content, assistant_content),
    )
    conn.commit()
    return cur.lastrowid  # type: ignore[return-value]


def update_iteration_final(
    conn: sqlite3.Connection,
    *,
    iteration_id: int,
    stop_reason: str | None = None,
    error: str | None = None,
) -> None:
    """Update an iteration with its final stop_reason and error."""
    conn.execute(
        "UPDATE iterations SET stop_reason = ?, error = ? WHERE id = ?",
        (stop_reason, error, iteration_id),
    )
    conn.commit()


def insert_tool_call(
    conn: sqlite3.Connection,
    *,
    iteration_id: int,
    session_key: str,
    tool_name: str,
    arguments: str | None = None,
) -> int:
    """Insert a tool call record and return its row id."""
    cur = conn.execute(
        """INSERT INTO tool_calls (iteration_id, session_key, tool_name, arguments)
           VALUES (?, ?, ?, ?)""",
        (iteration_id, session_key, tool_name, arguments),
    )
    conn.commit()
    return cur.lastrowid  # type: ignore[return-value]


def update_tool_call_result(
    conn: sqlite3.Connection,
    *,
    tool_call_id: int,
    result: str | None = None,
) -> None:
    """Update a tool call with its execution result."""
    conn.execute(
        "UPDATE tool_calls SET result = ? WHERE id = ?",
        (result, tool_call_id),
    )
    conn.commit()


def insert_heartbeat_event(
    conn: sqlite3.Connection,
    *,
    action: str,
    tasks: str | None = None,
    result: str | None = None,
) -> int:
    """Insert a heartbeat event and return its row id."""
    cur = conn.execute(
        "INSERT INTO heartbeat_events (action, tasks, result) VALUES (?, ?, ?)",
        (action, tasks, result),
    )
    conn.commit()
    return cur.lastrowid  # type: ignore[return-value]
