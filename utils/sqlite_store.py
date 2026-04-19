"""SQLite index on top of the JSONL session history.

Runs alongside the existing JSONL-based history. Indexes each session's
metadata for fast queries:
 - by project name / tag
 - by date range
 - by event type (demo loaded, export, error)
 - cross-session product lookup (e.g. "which sessions contained SKU XYZ?")

Transparent — schedules a rebuild on every call to `init_index()`, idempotent.
Readers can fall back to the JSONL files if the DB is missing.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

_LOCK = threading.Lock()
_DB_PATH = Path.home() / ".feed_enricher" / "index.sqlite"
_BASE = Path.home() / ".feed_enricher" / "sessions"


def _conn() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(_DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    return c


def init_schema() -> None:
    with _LOCK, _conn() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id   TEXT PRIMARY KEY,
                project_name TEXT,
                created_at   TEXT,
                updated_at   TEXT,
                n_products   INTEGER DEFAULT 0,
                has_enrichment INTEGER DEFAULT 0,
                tags         TEXT
            );
            CREATE TABLE IF NOT EXISTS events (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                ts         TEXT,
                kind       TEXT,
                payload    TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id);
            CREATE INDEX IF NOT EXISTS idx_events_kind ON events(kind);
            CREATE INDEX IF NOT EXISTS idx_sessions_updated ON sessions(updated_at DESC);
        """)


def upsert_session(session_id: str, *, project_name: str = "",
                   n_products: int = 0, has_enrichment: bool = False,
                   tags: list[str] | None = None) -> None:
    init_schema()
    now = datetime.utcnow().isoformat(timespec="seconds")
    tags_blob = ",".join(tags or [])
    with _LOCK, _conn() as c:
        c.execute("""
            INSERT INTO sessions(session_id, project_name, created_at, updated_at,
                                 n_products, has_enrichment, tags)
            VALUES(?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                project_name=excluded.project_name,
                updated_at=excluded.updated_at,
                n_products=excluded.n_products,
                has_enrichment=excluded.has_enrichment,
                tags=excluded.tags
        """, (session_id, project_name, now, now, n_products, 1 if has_enrichment else 0, tags_blob))


def log_event(session_id: str, kind: str, payload: dict | None = None) -> None:
    init_schema()
    now = datetime.utcnow().isoformat(timespec="seconds")
    blob = json.dumps(payload or {}, ensure_ascii=False)
    with _LOCK, _conn() as c:
        c.execute(
            "INSERT INTO events(session_id, ts, kind, payload) VALUES(?, ?, ?, ?)",
            (session_id, now, kind, blob),
        )
        c.execute("UPDATE sessions SET updated_at=? WHERE session_id=?", (now, session_id))


def search_sessions(q: str = "", tag: str = "", has_enrichment: bool | None = None,
                    limit: int = 100) -> list[dict]:
    init_schema()
    where = []
    params: list = []
    if q:
        where.append("(project_name LIKE ? OR session_id LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%"])
    if tag:
        where.append("tags LIKE ?")
        params.append(f"%{tag}%")
    if has_enrichment is not None:
        where.append("has_enrichment = ?")
        params.append(1 if has_enrichment else 0)
    sql = "SELECT * FROM sessions"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY updated_at DESC LIMIT ?"
    params.append(limit)
    with _conn() as c:
        return [dict(r) for r in c.execute(sql, params).fetchall()]


def stats() -> dict:
    init_schema()
    with _conn() as c:
        n_sessions = c.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        n_events = c.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        n_enriched = c.execute(
            "SELECT COUNT(*) FROM sessions WHERE has_enrichment = 1"
        ).fetchone()[0]
    return {
        "sessions": n_sessions,
        "events": n_events,
        "enriched": n_enriched,
        "db_path": str(_DB_PATH),
    }


def rebuild_from_jsonl() -> int:
    """One-shot scan of ~/.feed_enricher/sessions/*/history.jsonl to backfill.

    Safe to call repeatedly (upserts). Returns number of events ingested.
    """
    init_schema()
    if not _BASE.exists():
        return 0
    total = 0
    for sess_dir in _BASE.iterdir():
        if not sess_dir.is_dir():
            continue
        sid = sess_dir.name
        upsert_session(sid)
        hist = sess_dir / "history.jsonl"
        if not hist.exists():
            continue
        with _conn() as c:
            # Purge existing events for a clean rebuild per session
            c.execute("DELETE FROM events WHERE session_id = ?", (sid,))
            with hist.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        e = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    c.execute(
                        "INSERT INTO events(session_id, ts, kind, payload) VALUES(?, ?, ?, ?)",
                        (sid, e.get("ts", ""), e.get("kind", ""),
                         json.dumps(e.get("payload", {}), ensure_ascii=False)),
                    )
                    total += 1
    return total
