"""Event sink — where structured Loom call records get persisted.

`EventSink` is a Protocol so future backends (Postgres, ClickHouse,
S3+Parquet) can drop in without touching the handler or the queries.
`SQLiteSink` is the bundled implementation — zero infra, stdlib only,
fine for moderate volumes.

The sink owns the schema. Queries that the dashboard runs live in
`loom.observability.queries` and accept the sink as their interface.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Iterable, Protocol


class EventSink(Protocol):
    """Minimum surface every event sink must expose."""

    def write(self, event: dict[str, Any]) -> None: ...

    def fetch(
        self,
        *,
        sql: str,
        params: tuple[Any, ...] = (),
    ) -> list[dict[str, Any]]: ...


_SCHEMA = """
CREATE TABLE IF NOT EXISTS loom_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    provider TEXT NOT NULL,
    modality TEXT NOT NULL,
    model TEXT NOT NULL,
    upstream_model TEXT,
    latency_ms REAL NOT NULL,
    input_tokens INTEGER,
    output_tokens INTEGER,
    total_tokens INTEGER,
    cost_usd REAL,
    cost_local REAL,
    cost_currency TEXT,
    ok INTEGER NOT NULL,
    cached INTEGER NOT NULL,
    deduped INTEGER NOT NULL,
    retries INTEGER NOT NULL DEFAULT 0,
    tags TEXT,
    error_type TEXT,
    error TEXT
);
CREATE INDEX IF NOT EXISTS idx_loom_events_ts ON loom_events(ts);
CREATE INDEX IF NOT EXISTS idx_loom_events_provider ON loom_events(provider);
CREATE INDEX IF NOT EXISTS idx_loom_events_model ON loom_events(model);
"""

# Columns added after the original schema shipped. On an existing on-disk
# DB the CREATE TABLE above is a no-op, so we ALTER-add anything missing.
_MIGRATIONS = (
    ("retries", "INTEGER NOT NULL DEFAULT 0"),
    ("tags", "TEXT"),
)


_INSERT_SQL = """
INSERT INTO loom_events (
    ts, provider, modality, model, upstream_model, latency_ms,
    input_tokens, output_tokens, total_tokens,
    cost_usd, cost_local, cost_currency,
    ok, cached, deduped, retries, tags, error_type, error
) VALUES (?, ?, ?, ?, ?, ?,  ?, ?, ?,  ?, ?, ?,  ?, ?, ?, ?, ?, ?, ?)
"""


_FIELDS = (
    "ts", "provider", "modality", "model", "upstream_model", "latency_ms",
    "input_tokens", "output_tokens", "total_tokens",
    "cost_usd", "cost_local", "cost_currency",
    "ok", "cached", "deduped", "retries", "tags", "error_type", "error",
)


class SQLiteSink:
    """SQLite-backed event sink.

    The sink keeps one long-lived connection guarded by a lock — SQLite
    handles serialized writes fine for this workload (every write is a
    single insert against an indexed table).

    Pass `path=":memory:"` for an in-process sink (useful in tests).
    """

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self._lock = threading.Lock()
        # `check_same_thread=False` so the same connection can serve
        # write() from a logging thread and fetch() from the Flask
        # request thread; the lock above serializes both.
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.executescript(_SCHEMA)
            existing = {
                r["name"]
                for r in self._conn.execute(
                    "PRAGMA table_info(loom_events)"
                ).fetchall()
            }
            for column, ddl in _MIGRATIONS:
                if column not in existing:
                    self._conn.execute(
                        f"ALTER TABLE loom_events ADD COLUMN {column} {ddl}"
                    )
            self._conn.commit()

    def write(self, event: dict[str, Any]) -> None:
        """Insert one event row. Missing fields default to NULL / 0."""
        tags = event.get("tags")
        row = (
            float(event.get("ts") or time.time()),
            str(event.get("provider") or ""),
            str(event.get("modality") or ""),
            str(event.get("model") or ""),
            event.get("upstream_model"),
            float(event.get("latency_ms") or 0.0),
            event.get("input_tokens"),
            event.get("output_tokens"),
            event.get("total_tokens"),
            event.get("cost_usd"),
            event.get("cost_local"),
            event.get("cost_currency"),
            1 if event.get("ok", True) else 0,
            1 if event.get("cached") else 0,
            1 if event.get("deduped") else 0,
            int(event.get("retries") or 0),
            json.dumps(tags) if tags else None,
            event.get("error_type"),
            event.get("error"),
        )
        with self._lock:
            self._conn.execute(_INSERT_SQL, row)
            self._conn.commit()

    def fetch(
        self,
        *,
        sql: str,
        params: tuple[Any, ...] = (),
    ) -> list[dict[str, Any]]:
        with self._lock:
            cur = self._conn.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # convenience for tests / housekeeping
    def count(self) -> int:
        rows = self.fetch(sql="SELECT COUNT(*) AS n FROM loom_events")
        return int(rows[0]["n"]) if rows else 0


class InMemorySink(SQLiteSink):
    """Zero-config in-process event sink — a SQLite ``:memory:`` database.

    This is the default sink every :class:`~loom.Loom` client uses to power
    ``client.analytics()``. It speaks the same SQL as :class:`SQLiteSink`, so
    all `loom.observability.queries` work against it unchanged; nothing is
    persisted beyond the client's lifetime.
    """

    def __init__(self) -> None:
        super().__init__(":memory:")
