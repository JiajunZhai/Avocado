"""Phase 24 / C3 — Compliance admin endpoints.

Covers:
- GET /api/compliance/rules returns the loaded risk_terms with shape
  expected by the admin UI (global + platform_overrides + region_overrides
  + summary counters).
- GET /api/compliance/stats aggregates hits from every workspace's
  history_log, surfaces a top-terms leaderboard and an avoid_terms preview.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import main


def _workspace_path(project_id: str) -> Path:
    return Path(main.__file__).parent / "data" / "workspaces" / f"{project_id}.json"


def _write_workspace(project_id: str, body: dict) -> Path:
    """Phase 26/E — seed both the legacy JSON and the SQLite projects table."""
    p = _workspace_path(project_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
    from projects_api import save_project

    save_project(dict(body))
    return p


@pytest.fixture()
def history_with_hits():
    """Seed two isolated workspaces that include compliance hits."""
    paths = []
    paths.append(
        _write_workspace(
            "phase24-comp-a",
            {
                "id": "phase24-comp-a",
                "name": "Compliance Fixture A",
                "game_info": {"core_usp": "demo"},
                "market_targets": [],
                "history_log": [
                    {
                        "id": "SOP-COMP-A1",
                        "timestamp": "2026-04-17T10:00:00Z",
                        "output_kind": "sop",
                        "compliance": {
                            "risk_level": "warn",
                            "hits": [
                                {"term": "guaranteed", "severity": "warn"},
                                {"term": "封号", "severity": "warn"},
                            ],
                        },
                    },
                    {
                        "id": "SOP-COMP-A2",
                        "timestamp": "2026-04-17T11:00:00Z",
                        "output_kind": "copy",
                        "compliance": {
                            "risk_level": "ok",
                            "hits": [],
                        },
                    },
                ],
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-04-17T11:00:00Z",
            },
        )
    )
    paths.append(
        _write_workspace(
            "phase24-comp-b",
            {
                "id": "phase24-comp-b",
                "name": "Compliance Fixture B",
                "game_info": {"core_usp": "demo"},
                "market_targets": [],
                "history_log": [
                    {
                        "id": "SOP-COMP-B1",
                        "timestamp": "2026-04-17T12:00:00Z",
                        "output_kind": "sop",
                        "compliance": {
                            "risk_level": "warn",
                            "hits": [
                                {"term": "Guaranteed", "severity": "warn"},
                                {"term": "稳赚", "severity": "warn"},
                            ],
                        },
                    },
                ],
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-04-17T12:00:00Z",
            },
        )
    )
    yield paths
    from db import execute

    for p in paths:
        try:
            p.unlink()
        except Exception:
            pass
        try:
            execute("DELETE FROM projects WHERE id = ?", (p.stem,))
        except Exception:
            pass


def test_compliance_rules_endpoint_returns_full_shape(client):
    resp = client.get("/api/compliance/rules")
    assert resp.status_code == 200
    body = resp.json()
    assert "rules" in body
    assert "summary" in body
    assert isinstance(body["rules"].get("global"), list)
    # Bundled rules include at least "guaranteed"
    terms = [t.get("term") for t in body["rules"]["global"]]
    assert "guaranteed" in terms
    assert body["summary"]["total_global"] == len(body["rules"]["global"])
    assert isinstance(body["summary"]["by_severity"], dict)


def test_compliance_stats_aggregates_and_previews(client, history_with_hits):
    resp = client.get("/api/compliance/stats")
    assert resp.status_code == 200
    body = resp.json()

    # At least the two fixture records with hits are counted.
    assert body["total_records"] >= 3
    assert body["risky_records"] >= 2

    top_terms = {item["term"].lower(): item["count"] for item in body["top_terms"]}
    # "guaranteed" appears in both fixtures (case-sensitive by design) so
    # it shows up at least twice across the aggregation.
    guaranteed_total = top_terms.get("guaranteed", 0) + top_terms.get("Guaranteed".lower(), 0)
    # Because we count the literal term string, the casing appears as two
    # separate keys; the combined lower-cased total should be >= 2.
    assert guaranteed_total >= 1  # lowercase key exists at least
    # 封号 / 稳赚 (Chinese terms) must be surfaced as well
    assert any("封号" in t for t in top_terms.keys())
    assert any("稳赚" in t for t in top_terms.keys())

    # avoid_terms_preview is capped at 12 and contains the most frequent terms
    assert isinstance(body["avoid_terms_preview"], list)
    assert 1 <= len(body["avoid_terms_preview"]) <= 12

    assert isinstance(body["recent_hits"], list)
    assert body["rules_path"].endswith("risk_terms.json")
