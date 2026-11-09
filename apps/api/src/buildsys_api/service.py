"""Core learning and idempotent-event services for the hackathon MVP."""
from __future__ import annotations
import sqlite3
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
    """Persists reusable rules and applies them to independently built domains."""
    def __init__(self, database_path: str = ":memory:") -> None:
        if database_path != ":memory:":
            Path(database_path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(database_path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self) -> None:
        self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS knowledge_items (
                rule_id TEXT PRIMARY KEY, pattern TEXT NOT NULL, action TEXT NOT NULL,
                source_system TEXT NOT NULL, validated INTEGER NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS built_systems (
                system_name TEXT PRIMARY KEY, inherited_rule_id TEXT, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS events (
                system_name TEXT NOT NULL, request_id TEXT NOT NULL, payload TEXT NOT NULL,
                created_at TEXT NOT NULL, PRIMARY KEY (system_name, request_id));
        """)
        self.connection.commit()

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    def learn_from_duplicate(self, source_system: str = "orders") -> KnowledgeItem:
        item = KnowledgeItem(
            rule_id="idempotency-by-request-id-v1",
            pattern="same request_id received more than once for one system",
            action="persist exactly one event per system_name and request_id",
            source_system=source_system, validated=True, created_at=self._now())
        self.connection.execute("""INSERT OR REPLACE INTO knowledge_items
            (rule_id, pattern, action, source_system, validated, created_at)
            VALUES (?, ?, ?, ?, ?, ?)""", tuple(asdict(item).values()))
        self.connection.commit()
        return item

    def build_system(self, system_name: str) -> dict[str, Any]:
        row = self.connection.execute(
            "SELECT rule_id FROM knowledge_items WHERE validated = 1 ORDER BY created_at DESC LIMIT 1").fetchone()
        inherited_rule_id = row["rule_id"] if row else None
        self.connection.execute(
            "INSERT OR REPLACE INTO built_systems (system_name, inherited_rule_id, created_at) VALUES (?, ?, ?)",
            (system_name, inherited_rule_id, self._now()))
        self.connection.commit()
        return {"system_name": system_name, "inherited_rule_id": inherited_rule_id}

    def receive_event(self, system_name: str, request_id: str, payload: str) -> tuple[dict[str, Any], bool]:
        if not request_id:
            raise ValueError("request_id is required")
        exists = self.connection.execute(
            "SELECT 1 FROM events WHERE system_name = ? AND request_id = ?", (system_name, request_id)).fetchone()
        if exists:
            return ({"system_name": system_name, "request_id": request_id, "status": "duplicate_ignored"}, False)
        self.connection.execute(
            "INSERT INTO events (system_name, request_id, payload, created_at) VALUES (?, ?, ?, ?)",
            (system_name, request_id, payload, self._now()))
        self.connection.commit()
        return ({"system_name": system_name, "request_id": request_id, "status": "accepted"}, True)

    def knowledge(self) -> list[dict[str, Any]]:
        rows = self.connection.execute("SELECT * FROM knowledge_items ORDER BY created_at").fetchall()
        return [dict(row) | {"validated": bool(row["validated"])} for row in rows]

    def event_count(self, system_name: str) -> int:
        return self.connection.execute("SELECT COUNT(*) FROM events WHERE system_name = ?", (system_name,)).fetchone()[0]
