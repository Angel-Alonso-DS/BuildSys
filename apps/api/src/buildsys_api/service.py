"""Core learning and idempotent-event services for the hackathon MVP."""
from __future__ import annotations
import sqlite3
import threading
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

@dataclass(frozen=True)
class KnowledgeItem:
    rule_id: str
    pattern: str
    action: str
    source_system: str
    validated: bool
    created_at: str

class BuildSysService:
    def __init__(self, database_path: str = ":memory:") -> None:
        if database_path != ":memory:":
            Path(database_path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(database_path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS knowledge_items (
              rule_id TEXT PRIMARY KEY, pattern TEXT NOT NULL, action TEXT NOT NULL,
              source_system TEXT NOT NULL, validated INTEGER NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS built_systems (
              system_name TEXT PRIMARY KEY, inherited_rule_id TEXT, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS events (
              event_id INTEGER PRIMARY KEY AUTOINCREMENT, system_name TEXT NOT NULL,
              request_id TEXT NOT NULL, idempotency_key TEXT, payload TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE UNIQUE INDEX IF NOT EXISTS learned_event_idempotency
              ON events(system_name, idempotency_key) WHERE idempotency_key IS NOT NULL;
        """)
        self.connection.commit()

    @staticmethod
    def now() -> str:
        return datetime.now(UTC).isoformat()

    def learn_from_duplicate(self, source_system: str = "orders") -> KnowledgeItem:
        item = KnowledgeItem("idempotency-by-request-id-v1",
          "same request_id received more than once for one system",
          "persist exactly one event per system_name and request_id",
          source_system, True, self.now())
        with self.lock:
            self.connection.execute(
              "INSERT OR REPLACE INTO knowledge_items VALUES (?, ?, ?, ?, ?, ?)",
              tuple(asdict(item).values()))
            self.connection.commit()
        return item

    def build_system(self, system_name: str) -> dict[str, Any]:
        if not system_name:
            raise ValueError("system_name is required")
        with self.lock:
            row = self.connection.execute(
              "SELECT rule_id FROM knowledge_items WHERE validated = 1 ORDER BY created_at DESC LIMIT 1").fetchone()
            rule_id = row["rule_id"] if row else None
            self.connection.execute(
              "INSERT OR REPLACE INTO built_systems VALUES (?, ?, ?)", (system_name, rule_id, self.now()))
            self.connection.commit()
        return {"system_name": system_name, "inherited_rule_id": rule_id}

    def receive_event(self, system_name: str, request_id: str, payload: str) -> tuple[dict[str, Any], bool]:
        if not system_name:
            raise ValueError("system_name is required")
        if not request_id:
            raise ValueError("request_id is required")
        with self.lock:
            built = self.connection.execute(
              "SELECT inherited_rule_id FROM built_systems WHERE system_name = ?", (system_name,)).fetchone()
            key = request_id if built and built["inherited_rule_id"] else None
            cursor = self.connection.execute(
              "INSERT OR IGNORE INTO events (system_name, request_id, idempotency_key, payload, created_at) VALUES (?, ?, ?, ?, ?)",
              (system_name, request_id, key, payload, self.now()))
            self.connection.commit()
        if cursor.rowcount == 0:
            return {"system_name": system_name, "request_id": request_id, "status": "duplicate_ignored"}, False
        return {"system_name": system_name, "request_id": request_id, "status": "accepted"}, True

    def knowledge(self) -> list[dict[str, Any]]:
        with self.lock:
            rows = self.connection.execute("SELECT * FROM knowledge_items ORDER BY created_at").fetchall()
        return [dict(row) | {"validated": bool(row["validated"])} for row in rows]

    def event_count(self, system_name: str) -> int:
        with self.lock:
            return self.connection.execute(
              "SELECT COUNT(*) FROM events WHERE system_name = ?", (system_name,)).fetchone()[0]
