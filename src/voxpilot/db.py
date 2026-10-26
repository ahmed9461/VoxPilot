from __future__ import annotations

import asyncio
import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Iterable, TypeVar

T = TypeVar("T")

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
UPSERT = (
    "INSERT INTO kv(key,value,updated_at) VALUES(?,?,?) "
    "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at"
)


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    async def init(self) -> None:
        await asyncio.to_thread(self._init_sync)

    def _init_sync(self) -> None:
        with closing(self._connect()) as conn, conn:
            conn.executescript(SCHEMA)

    @staticmethod
    def _write(conn: sqlite3.Connection, values: dict[str, Any]) -> None:
        stamp = datetime.now(UTC).isoformat()
        conn.executemany(UPSERT, [
            (key, json.dumps(value, ensure_ascii=False), stamp)
            for key, value in values.items()
        ])

    @staticmethod
    def _read(conn: sqlite3.Connection, keys: Iterable[str]) -> dict[str, Any]:
        items = list(dict.fromkeys(keys))
        if not items:
            return {}
        marks = ",".join("?" for _ in items)
        rows = conn.execute(f"SELECT key,value FROM kv WHERE key IN ({marks})", items).fetchall()
        return {str(row["key"]): json.loads(row["value"]) for row in rows}

    async def set(self, key: str, value: Any) -> None:
        await self.set_many({key: value})

    async def set_many(self, values: dict[str, Any]) -> None:
        await asyncio.to_thread(self._set_many_sync, values)

    def _set_many_sync(self, values: dict[str, Any]) -> None:
        with closing(self._connect()) as conn, conn:
            self._write(conn, values)

    async def get(self, key: str, default: Any = None) -> Any:
        return (await self.get_many([key])).get(key, default)

    async def get_many(self, keys: Iterable[str]) -> dict[str, Any]:
        return await asyncio.to_thread(self._get_many_sync, list(keys))

    def _get_many_sync(self, keys: list[str]) -> dict[str, Any]:
        with closing(self._connect()) as conn:
            return self._read(conn, keys)

    async def transaction(
        self,
        keys: Iterable[str],
        transform: Callable[[dict[str, Any]], tuple[dict[str, Any], T]],
    ) -> T:
        """Atomic read/modify/write, including across Database instances.

        transform is synchronous and must not perform I/O or mutate its input
        outside this call. An exception rolls back the complete operation.
        """
        return await asyncio.to_thread(self._transaction_sync, list(keys), transform)

    def _transaction_sync(self, keys: list[str], transform: Callable) -> Any:
        with closing(self._connect()) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            updates, result = transform(self._read(conn, keys))
            self._write(conn, updates)
            return result

    async def event(self, kind: str, payload: dict[str, Any]) -> None:
        await asyncio.to_thread(self._event_sync, kind, payload)

    def _event_sync(self, kind: str, payload: dict[str, Any]) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "INSERT INTO events(kind,payload,created_at) VALUES(?,?,?)",
                (kind, json.dumps(payload, ensure_ascii=False), datetime.now(UTC).isoformat()),
            )
