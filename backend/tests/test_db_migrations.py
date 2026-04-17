"""Phase 26 / E1 — migrations + schema sanity."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest


def _fresh_db(monkeypatch):
    import db as _db

    tmp = Path(tempfile.mkdtemp(prefix="adcreative_mig_")) / "app.sqlite3"
    monkeypatch.setenv("DB_PATH", str(tmp))
    _db.reset_for_tests()
    # Reset the cached connection in teardown so subsequent tests fall back
    # to the conftest-provided DB (which already carries seeded fixtures).
    monkeypatch.setattr(
        _db,
        "_conn",
        None,
        raising=False,
    )

    def _cleanup():
        _db.reset_for_tests()

    monkeypatch.setattr(_db, "__test_cleanup__", _cleanup, raising=False)
    return tmp


@pytest.fixture(autouse=True)
def _reset_after(monkeypatch):
    yield
    import db as _db

    _db.reset_for_tests()


def test_run_migrations_creates_core_tables(monkeypatch):
    _fresh_db(monkeypatch)
    from db import get_conn

    conn = get_conn()
    rows = {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','view')"
        ).fetchall()
    }
    for expected in (
        "schema_version",
        "projects",
        "history_log",
        "factors",
        "compliance_rules",
        "knowledge_docs",
        "knowledge_vectors",
    ):
        assert expected in rows, f"missing table: {expected}"
    # FTS5 should be available in a modern SQLite build.
    assert "knowledge_fts" in rows


def test_run_migrations_is_idempotent(monkeypatch):
    _fresh_db(monkeypatch)
    from db import get_conn, run_migrations

    before = get_conn().execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
    run_migrations(get_conn())
    run_migrations(get_conn())
    after = get_conn().execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
    assert before == after


def test_history_log_foreign_key_cascades(monkeypatch):
    _fresh_db(monkeypatch)
    from db import execute

    execute(
        "INSERT INTO projects(id, name, game_info_json, market_targets_json, created_at, updated_at) VALUES(?,?,?,?,?,?)",
        ("proj1", "test", "{}", "[]", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),
    )
    execute(
        """
        INSERT INTO history_log(id, project_id, created_at, payload_json)
        VALUES(?, ?, ?, '{}')
        """,
        ("h1", "proj1", "2026-01-01T00:00:00Z"),
    )
    execute("DELETE FROM projects WHERE id = 'proj1'")
    row = execute("SELECT COUNT(*) FROM history_log WHERE project_id='proj1'").fetchone()
    assert row[0] == 0
