"""Keep RAG tests on TF-IDF so CI does not download embedding models.

Phase 26/E — also redirect the SQLite backbone to a per-session temp file so
tests never mutate the developer's local `backend/data/app.sqlite3`.
"""
import os
import tempfile
from pathlib import Path

import pytest

os.environ.setdefault("RAG_RETRIEVAL", "tfidf")
# Force per-run DB before `main` (and thus `db.py`) is imported.
_TMP_DB_DIR = Path(tempfile.mkdtemp(prefix="adcreative_test_db_"))
os.environ["DB_PATH"] = str(_TMP_DB_DIR / "app.sqlite3")

from fastapi.testclient import TestClient  # noqa: E402  (env must be set first)

import main  # noqa: E402


@pytest.fixture()
def client():
    with TestClient(main.app) as c:
        yield c
