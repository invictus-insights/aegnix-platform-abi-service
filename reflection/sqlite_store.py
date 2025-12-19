# reflection/sqlite_store.py

from typing import List
from reflection.store import ReflectionStore
from reflection.models import ReflectionRecord, serialize_record, deserialize_record
from aegnix_core.storage.providers.sqlite_provider import SQLiteStorage



class SQLiteReflectionStore(ReflectionStore):
    def __init__(self, storage: SQLiteStorage):
        self._storage = storage
        self._table = "reflection_events"

        self._ensure_schema()

    def _ensure_schema(self):
        self._storage.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {self._table} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                ae_id TEXT,
                session_id TEXT,
                event_type TEXT,
                payload TEXT NOT NULL
            )
            """
        )

    def append(self, record: ReflectionRecord) -> None:
        self._storage.execute(
            f"""
            INSERT INTO {self._table}
            (ts, ae_id, session_id, event_type, payload)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                record.ts,
                record.correlation.ae_id,
                record.correlation.session_id,
                record.event_type,
                serialize_record(record)
            ),
        )
        self._storage.flush()

    def all(self) -> List[ReflectionRecord]:
        cur = self._storage.execute(
            f"""
            SELECT payload
            FROM {self._table}
            ORDER BY ts ASC
            """
        )
        rows = cur.fetchall()

        return [
            deserialize_record(row[0])
            for row in rows
        ]

