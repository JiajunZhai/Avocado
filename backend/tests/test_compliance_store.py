"""Phase 26 / E3 — compliance seeder + DB-backed ``load_risk_terms``."""
from __future__ import annotations

import pytest


def test_seed_populates_terms_and_invalidates_cache():
    import compliance
    from compliance_store import seed_from_filesystem

    result = seed_from_filesystem(force=True)
    assert result["seeded"] is True
    compliance.invalidate_cache()

    cfg = compliance.load_risk_terms()
    terms = [t.get("term") for t in (cfg.get("global") or [])]
    assert "guaranteed" in terms
    assert "封号" in terms


def test_second_seed_is_noop_without_force():
    from compliance_store import seed_from_filesystem

    seed_from_filesystem(force=True)
    second = seed_from_filesystem()
    assert second.get("seeded") is False
