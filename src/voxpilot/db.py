from __future__ import annotations

import asyncio
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable


SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS kv (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    async def init(self) -> None:
        await asyncio.to_thread(self._init_sync)

    def _init_sync(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    async def set(self, key: str, value: Any) -> None:
        await asyncio.to_thread(self._set_sync, key, value)

    def _set_sync(self, key: str, value: Any) -> None:
        now = datetime.now(UTC).isoformat()
        encoded = json.dumps(value, ensure_ascii=False)
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO kv(key,value,updated_at) VALUES(?,?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
                (key, encoded, now),
            )

    async def set_many(self, values: dict[str, Any]) -> None:
        await asyncio.to_thread(self._set_many_sync, values)

    def _set_many_sync(self, values: dict[str, Any]) -> None:
        if not values:
            return
        now = datetime.now(UTC).isoformat()
        rows = [(key, json.dumps(value, ensure_ascii=False), now) for key, value in values.items()]
        with self._connect() as conn:
            conn.executemany(
                "INSERT INTO kv(key,value,updated_at) VALUES(?,?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
                rows,
            )

    async def get(self, key: str, default: Any = None) -> Any:
        return await asyncio.to_thread(self._get_sync, key, default)

    def _get_sync(self, key: str, default: Any = None) -> Any:
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
        return default if row is None else json.loads(row["value"])

    async def get_many(self, keys: Iterable[str]) -> dict[str, Any]:
        return await asyncio.to_thread(self._get_many_sync, list(keys))

    def _get_many_sync(self, keys: list[str]) -> dict[str, Any]:
        items = list(dict.fromkeys(keys))
        if not items:
            return {}
        marks = ",".join("?" for _ in items)
        with self._connect() as conn:
            rows = conn.execute(f"SELECT key,value FROM kv WHERE key IN ({marks})", items).fetchall()
        return {str(row["key"]): json.loads(row["value"]) for row in rows}

    async def event(self, kind: str, payload: dict[str, Any]) -> None:
        await asyncio.to_thread(self._event_sync, kind, payload)

    def _event_sync(self, kind: str, payload: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO events(kind,payload,created_at) VALUES(?,?,?)",
                (kind, json.dumps(payload, ensure_ascii=False), datetime.now(UTC).isoformat()),
            )
