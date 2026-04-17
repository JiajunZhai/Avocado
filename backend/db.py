"""Phase 26 / E — SQLite backbone for projects, history, factors, compliance,
knowledge docs + FTS5 + vector BLOBs.

Design notes:
    - The JSON tree under ``backend/data`` stays authoritative for git-tracked
      seeds (factors, compliance rules, knowledge corpus). At boot we compute a
      per-file SHA1 fingerprint and UPSERT into SQLite only when the fingerprint
      changed — idempotent, network-free, and preserves hand-edited seeds.
    - Projects / history / distilled-at-runtime knowledge docs are owned by the
      DB (no git footprint). Legacy ``workspaces/*.json`` are migrated on first
      boot so the Phase 25 behaviour keeps working.
    - Everything in this file is intentionally dependency-free: we only rely on
      stdlib ``sqlite3``. Vector stuff lives on top of BLOB columns.
"""

from __future__ import annotations

import os
import sqlite3
import threading
from pathlib import Path
from typing import Any, Iterable, Optional


BACKEND_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = BACKEND_DIR / "data" / "app.sqlite3"


def _db_path() -> Path:
    p = os.getenv("DB_PATH")
    if p:
        return Path(p).expanduser().resolve()
    return DEFAULT_DB_PATH


_connect_lock = threading.Lock()
_fts5_available: Optional[bool] = None


def _check_fts5(conn: sqlite3.Connection) -> bool:
    try:
        conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS __fts5_probe USING fts5(x)")
        conn.execute("DROP TABLE IF EXISTS __fts5_probe")
        return True
    except sqlite3.OperationalError:
        return False


def fts5_available() -> bool:
    global _fts5_available
    if _fts5_available is not None:
        return _fts5_available
    tmp = sqlite3.connect(":memory:")
    try:
        _fts5_available = _check_fts5(tmp)
    finally:
        tmp.close()
    return _fts5_available


def connect(db_path: Optional[Path | str] = None) -> sqlite3.Connection:
    """Return a configured SQLite connection.

    Notes:
        * ``check_same_thread=False`` — FastAPI uses a small worker pool; we
          guard writes at the call-site where needed.
        * ``row_factory=sqlite3.Row`` — every helper returns dict-like rows.
    """
    path = Path(db_path) if db_path else _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
    conn.row_factory = sqlite3.Row
    # WAL + FK + sensible sync for local SSD workloads.
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    except sqlite3.OperationalError:
        # In-memory or shared-cache DBs may reject WAL; ignore.
        pass
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


# ---------------------------------------------------------------------------
# Migrations
# ---------------------------------------------------------------------------

MIGRATIONS: list[tuple[int, str]] = [
    (
        1,
        """
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            game_info_json TEXT NOT NULL DEFAULT '{}',
            market_targets_json TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS history_log (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            kind TEXT,
            region_id TEXT,
            platform_id TEXT,
            angle_id TEXT,
            script_id TEXT,
            decision TEXT,
            decision_at TEXT,
            provider TEXT,
            model TEXT,
            schema_version INTEGER DEFAULT 3,
            engine TEXT,
            output_mode TEXT,
            markdown_path TEXT,
            parent_script_id TEXT,
            factor_version TEXT,
            draft_status TEXT,
            payload_json TEXT NOT NULL DEFAULT '{}',
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_history_project_ts
            ON history_log(project_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_history_kind ON history_log(kind);
        CREATE INDEX IF NOT EXISTS idx_history_region ON history_log(region_id);
        CREATE INDEX IF NOT EXISTS idx_history_platform ON history_log(platform_id);
        CREATE INDEX IF NOT EXISTS idx_history_angle ON history_log(angle_id);
        CREATE INDEX IF NOT EXISTS idx_history_decision ON history_log(decision);

        CREATE TABLE IF NOT EXISTS factors (
            id TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            short_name TEXT,
            name TEXT,
            data_json TEXT NOT NULL,
            file_fingerprint TEXT,
            enabled INTEGER NOT NULL DEFAULT 1,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_factors_type ON factors(type, enabled);

        CREATE TABLE IF NOT EXISTS compliance_rules (
            id TEXT PRIMARY KEY,
            scope TEXT NOT NULL,
            region_id TEXT,
            platform_id TEXT,
            term TEXT NOT NULL,
            severity TEXT NOT NULL DEFAULT 'warn',
            note TEXT,
            data_json TEXT NOT NULL DEFAULT '{}',
            file_fingerprint TEXT,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_compliance_scope
            ON compliance_rules(scope, platform_id, region_id);

        CREATE TABLE IF NOT EXISTS knowledge_docs (
            id TEXT PRIMARY KEY,
            doc_text TEXT NOT NULL,
            source TEXT,
            region TEXT,
            year_quarter TEXT,
            category TEXT,
            meta_json TEXT NOT NULL DEFAULT '{}',
            fingerprint TEXT,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_knowledge_region ON knowledge_docs(region);

        CREATE TABLE IF NOT EXISTS knowledge_vectors (
            doc_id TEXT PRIMARY KEY,
            model_id TEXT NOT NULL,
            fingerprint TEXT,
            dim INTEGER,
            vec BLOB,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(doc_id) REFERENCES knowledge_docs(id) ON DELETE CASCADE
        );
        """,
    ),
    # Migration 2 creates FTS5 on top of knowledge_docs only when available.
    # Kept as a no-op body here so the version record lands either way; the
    # actual DDL is dispatched in run_migrations() so we can gracefully
    # degrade to LIKE on old SQLite builds.
    (2, ""),
    # Phase 27 / F — user-editable provider settings. Hardcoded model lists
    # and env-only API keys were too rigid: power users need to swap keys /
    # point at a self-hosted base URL / maintain a custom model roster
    # without touching .env. Secrets are stored locally (single-user app);
    # never return them over /api/providers.
    (
        3,
        """
        CREATE TABLE IF NOT EXISTS provider_settings (
            id TEXT PRIMARY KEY,
            api_key TEXT,
            base_url TEXT,
            default_model TEXT,
            extra_models_json TEXT NOT NULL DEFAULT '[]',
            enabled INTEGER NOT NULL DEFAULT 1,
            last_tested_at TEXT,
            last_test_ok INTEGER,
            last_test_note TEXT,
            updated_at TEXT NOT NULL
        );
        """,
    ),
    (
        4,
        """
        ALTER TABLE projects ADD COLUMN archived_at TEXT;
        ALTER TABLE projects ADD COLUMN user_preference_notes TEXT;
        """
    ),
    (
        5,
        """
        CREATE TABLE IF NOT EXISTS pending_evolutions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            factor_id TEXT NOT NULL,
            field TEXT NOT NULL,
            proposed_value TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """
    ),
]


def _apply_sql_script(conn: sqlite3.Connection, sql: str) -> None:
    if not sql.strip():
        return
    conn.executescript(sql)


def _current_version(conn: sqlite3.Connection) -> int:
    try:
        row = conn.execute(
            "SELECT MAX(version) AS v FROM schema_version"
        ).fetchone()
        if row and row["v"] is not None:
            return int(row["v"])
    except sqlite3.OperationalError:
        pass
    return 0


def _create_fts5_if_possible(conn: sqlite3.Connection) -> None:
    if not _check_fts5(conn):
        return
    conn.executescript(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5(
            doc_id UNINDEXED,
            region,
            doc_text,
            tokenize = 'unicode61 remove_diacritics 2'
        );
        """
    )


def run_migrations(conn: Optional[sqlite3.Connection] = None) -> sqlite3.Connection:
    """Run pending migrations; safe to call on every boot."""
    owned = conn is None
    conn = conn or connect()
    try:
        from datetime import datetime

        current = _current_version(conn)
        for version, sql in MIGRATIONS:
            if version <= current:
                continue
            _apply_sql_script(conn, sql)
            if version == 2:
                _create_fts5_if_possible(conn)
            conn.execute(
                "INSERT OR IGNORE INTO schema_version(version, applied_at) VALUES(?, ?)",
                (version, datetime.utcnow().isoformat() + "Z"),
            )
        return conn
    except Exception:
        if owned:
            conn.close()
        raise


# ---------------------------------------------------------------------------
# Singleton accessor for app runtime
# ---------------------------------------------------------------------------

_conn: Optional[sqlite3.Connection] = None


def get_conn() -> sqlite3.Connection:
    """Return the shared migrated connection (created on first use)."""
    global _conn
    with _connect_lock:
        if _conn is None:
            _conn = connect()
            run_migrations(_conn)
        return _conn


def reset_for_tests() -> None:
    """Force re-initialisation on the next ``get_conn()`` call.

    Tests that override ``DB_PATH`` should call this between runs so the cached
    connection does not keep pointing at the previous temp file.
    """
    global _conn, _fts5_available
    with _connect_lock:
        if _conn is not None:
            try:
                _conn.close()
            except Exception:
                pass
        _conn = None
        _fts5_available = None


def has_fts_table(conn: Optional[sqlite3.Connection] = None) -> bool:
    conn = conn or get_conn()
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table','view') AND name='knowledge_fts'"
    ).fetchone()
    return row is not None


# ---------------------------------------------------------------------------
# Low-level helpers used across factors/compliance/knowledge stores
# ---------------------------------------------------------------------------


def execute(sql: str, params: Iterable[Any] | None = None) -> sqlite3.Cursor:
    return get_conn().execute(sql, list(params or []))


def executemany(sql: str, seq: Iterable[Iterable[Any]]) -> sqlite3.Cursor:
    return get_conn().executemany(sql, list(seq))


def fetchone(sql: str, params: Iterable[Any] | None = None) -> Optional[sqlite3.Row]:
    return execute(sql, params).fetchone()


def fetchall(sql: str, params: Iterable[Any] | None = None) -> list[sqlite3.Row]:
    return list(execute(sql, params).fetchall())
