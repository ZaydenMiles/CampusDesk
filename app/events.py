"""The local status history, fed by Freshdesk webhooks.

Freshdesk stores the ticket; this stores the JOURNEY, one row per change,
so the tracking page can show Open -> Assigned -> In Progress -> Resolved
with a timestamp on each step. SQLite from the standard library: one file,
nothing to install.
"""
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS ticket_events (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id    INTEGER NOT NULL,
    status       TEXT,
    priority     TEXT,
    group_name   TEXT,
    agent        TEXT,
    source       TEXT NOT NULL,          -- 'portal' or 'webhook'
    received_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ticket_events_ticket_idx
    ON ticket_events (ticket_id, id);
"""


class EventStore:
    def __init__(self, path: str) -> None:
        self.path = path
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._memory = (sqlite3.connect(path, check_same_thread=False)
                        if path == ":memory:" else None)
        with self._conn() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def _conn(self):
        # A fresh connection per call keeps this safe across FastAPI's
        # worker threads. (":memory:" keeps one, or the tests lose the table.)
        conn = self._memory or sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            if conn is not self._memory:
                conn.close()

    def record(self, ticket_id: int, *, status: str | None, priority: str | None,
               group_name: str | None, agent: str | None, source: str) -> None:
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO ticket_events
                   (ticket_id, status, priority, group_name, agent, source, received_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (ticket_id, status, priority, group_name or None, agent or None,
                 source, datetime.now(timezone.utc).isoformat(timespec="seconds")),
            )

    def timeline(self, ticket_id: int) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT status, priority, group_name, agent, source, received_at
                     FROM ticket_events WHERE ticket_id = ? ORDER BY id""",
                (ticket_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def healthy(self) -> bool:
        try:
            with self._conn() as conn:
                conn.execute("SELECT 1")
            return True
        except sqlite3.Error:
            return False
