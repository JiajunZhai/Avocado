"""Phase 26 / E3 — factor seeder + read API."""
from __future__ import annotations

import json

import pytest


def test_seed_from_filesystem_is_idempotent():
    from factors_store import seed_from_filesystem, stats

    first = seed_from_filesystem()
    assert first["total"] >= 1
    second = seed_from_filesystem()
    # Second pass sees identical fingerprints and should skip everything.
    assert second["inserted"] == 0
    assert second["updated"] == 0
    counts = stats()
    assert counts.get("angle", 0) >= 1
    assert counts.get("region", 0) >= 1
    assert counts.get("platform", 0) >= 1


def test_read_insight_returns_dict_or_empty():
    from factors_store import list_by_type, read_insight

    regions = list_by_type("region")
    assert regions, "expected at least one region factor seeded"
    sample_id = regions[0]["id"]
    data = read_insight(sample_id)
    assert isinstance(data, dict)
    assert data
    assert read_insight("nonexistent_factor_xyz") == {}
    assert read_insight(None) == {}
