"""Centralized knowledge base paths + legacy migration helpers."""

from __future__ import annotations

import os
import shutil
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parent
DATA_DIR = BACKEND_DIR / "data"
KNOWLEDGE_DIR = DATA_DIR / "knowledge"

# Atomic strategy factors (regions/platforms/angles)
FACTORS_DIR = Path(os.getenv("FACTORS_DIR", str(KNOWLEDGE_DIR / "factors")))
LEGACY_FACTORS_DIR = DATA_DIR / "insights"

# Vector knowledge store
VECTOR_STORE_DIR = Path(os.getenv("VECTOR_STORE_DIR", str(KNOWLEDGE_DIR / "vector_store")))
VECTOR_DB_PATH = Path(os.getenv("VECTOR_DB_PATH", str(VECTOR_STORE_DIR / "local_storage.json")))
LEGACY_VECTOR_DB_PATH = BACKEND_DIR / "chroma_db" / "local_storage.json"


def _copy_tree_if_missing(src: Path, dst: Path) -> None:
    if not src.exists() or not src.is_dir():
        return
    if dst.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst)


def _copy_file_if_missing(src: Path, dst: Path) -> None:
    if not src.exists() or not src.is_file():
        return
    if dst.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def ensure_knowledge_layout() -> None:
    """
    Ensure the unified layout exists and migrate from legacy directories when needed.
    - factors: backend/data/insights -> backend/data/knowledge/factors
    - vector db: backend/chroma_db/local_storage.json -> backend/data/knowledge/vector_store/local_storage.json
    """
    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    FACTORS_DIR.mkdir(parents=True, exist_ok=True)
    VECTOR_STORE_DIR.mkdir(parents=True, exist_ok=True)
    _copy_tree_if_missing(LEGACY_FACTORS_DIR, FACTORS_DIR)
    _copy_file_if_missing(LEGACY_VECTOR_DB_PATH, VECTOR_DB_PATH)

