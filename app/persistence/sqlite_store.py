"""SQLite 溯源存储（标准库实现，无额外服务依赖）。"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone


class SQLiteTraceStore:
    def __init__(self, db_path: str) -> None:
        directory = os.path.dirname(db_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        self.db_path = db_path
        self._init_table()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_table(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS traces (
                    trace_id   TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    status     TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    payload    TEXT NOT NULL
                )
                """
            )

    def save(self, trace_id: str, response: dict) -> None:
        payload = json.dumps(response, ensure_ascii=False)
        confidence = float(response.get("confidence", {}).get("score", 0.0))
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO traces (trace_id, created_at, status, confidence, payload)"
                " VALUES (?, ?, ?, ?, ?)",
                (
                    trace_id,
                    datetime.now(timezone.utc).isoformat(),
                    response.get("status", ""),
                    confidence,
                    payload,
                ),
            )

    def get(self, trace_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM traces WHERE trace_id = ?", (trace_id,)
            ).fetchone()
        if row is None:
            return None
        return json.loads(row[0])
