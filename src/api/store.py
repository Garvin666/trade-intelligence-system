"""SQLite-backed state store for feedback and scoring weights."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.config import DATA_DIR

DEFAULT_WEIGHTS: dict[str, float] = {
    "forecast_growth": 0.35,
    "search_trend": 0.30,
    "competition": 0.25,
    "review_growth": 0.10,
}

_LOCK = threading.RLock()


def _db_path() -> Path:
    return Path(os.environ.get("BACKEND_STATE_DB", str(DATA_DIR / "backend_state.db")))


def _connect() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _init() -> None:
    with _LOCK, _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS scoring_weights (
                key TEXT PRIMARY KEY,
                value REAL NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                payload TEXT NOT NULL
            )
            """
        )
        conn.commit()


def get_weights() -> dict[str, float]:
    _init()
    result = dict(DEFAULT_WEIGHTS)
    with _LOCK, _connect() as conn:
        rows = conn.execute("SELECT key, value FROM scoring_weights").fetchall()
    for row in rows:
        result[row["key"]] = float(row["value"])
    return result


def update_weights(payload: dict[str, Any]) -> dict[str, float]:
    allowed = set(DEFAULT_WEIGHTS)
    updates: dict[str, float] = {}
    for key, value in payload.items():
        if key not in allowed:
            raise ValueError(f"Unsupported scoring weight: {key}")
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Weight must be numeric: {key}") from exc
        if not 0 <= number <= 1:
            raise ValueError(f"Weight must be between 0 and 1: {key}")
        updates[key] = number
    if updates and sum(updates.values()) > 1.5:
        raise ValueError("Weight sum is too large")

    _init()
    now = datetime.now(timezone.utc).isoformat()
    with _LOCK, _connect() as conn:
        for key, value in updates.items():
            conn.execute(
                """
                INSERT INTO scoring_weights (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (key, value, now),
            )
        conn.commit()
    return get_weights()


def add_feedback(payload: dict[str, Any]) -> dict[str, Any]:
    _init()
    created_at = datetime.now(timezone.utc).isoformat()
    raw = json.dumps(payload, ensure_ascii=False)
    with _LOCK, _connect() as conn:
        cursor = conn.execute(
            "INSERT INTO feedback (created_at, payload) VALUES (?, ?)",
            (created_at, raw),
        )
        conn.commit()
        feedback_id = int(cursor.lastrowid)
    return {"id": feedback_id, "created_at": created_at, **payload}


def list_feedback(limit: int = 50) -> list[dict[str, Any]]:
    _init()
    with _LOCK, _connect() as conn:
        rows = conn.execute(
            "SELECT id, created_at, payload FROM feedback ORDER BY id DESC LIMIT ?",
            (max(1, min(int(limit), 200)),),
        ).fetchall()
    result = []
    for row in rows:
        payload = json.loads(row["payload"])
        result.append({"id": row["id"], "created_at": row["created_at"], **payload})
    return result
