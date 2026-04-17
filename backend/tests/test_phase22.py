"""Phase 22 — Learning loop primitives.

Covers:
- Compliance negative list injection into director/copy prompts.
- History schema v2 fields written by quick_copy (and reliably written,
  not silently swallowed as was the case pre-Phase 22).
- POST /api/history/decision winner/loser feedback endpoint.
"""
import json
import os
from pathlib import Path

import pytest

import main
from prompts import (
    _render_avoid_terms_block,
    render_copy_prompt,
    render_director_prompt,
)


def test_avoid_terms_block_dedupes_and_caps():
    terms = ["Free", "free", "  ", "Unlimited", "FREE", "Hack"]
    out = _render_avoid_terms_block(terms)
    assert "Free" in out
    assert "Unlimited" in out
    assert "Hack" in out
    # Case-insensitive dedupe: only one copy of "free"
    assert out.lower().count('"free"') == 1


def test_avoid_terms_block_empty_returns_empty_string():
    assert _render_avoid_terms_block(None) == ""
    assert _render_avoid_terms_block([]) == ""
    assert _render_avoid_terms_block(["", "   "]) == ""


def test_render_director_prompt_includes_avoid_terms():
    prompt = render_director_prompt(
        game_context="Title: Demo\nCore Gameplay: merge",
        culture_context={"name": "North America"},
        platform_rules={"name": "AppLovin", "specs": []},
        creative_logic={"name": "Fail Trap", "logic_steps": ["step1"]},
        avoid_terms=["Free Gift", "Unlimited"],
    )
    assert "COMPLIANCE NEGATIVE LIST" in prompt
    assert '"Free Gift"' in prompt
    assert '"Unlimited"' in prompt


def test_render_copy_prompt_includes_avoid_terms():
    prompt = render_copy_prompt(
        game_context="Title: Demo",
        culture_context={"name": "Japan"},
        platform_rules={"name": "TikTok", "specs": []},
        creative_logic={"name": "ASMR", "logic_steps": []},
        quantity=10,
        tones=[],
        locales=["en"],
        avoid_terms=["Guaranteed"],
    )
    assert "COMPLIANCE NEGATIVE LIST" in prompt
    assert '"Guaranteed"' in prompt


def test_render_director_prompt_no_avoid_block_when_empty():
    prompt = render_director_prompt(
        game_context="Title: Demo",
        culture_context={"name": "N/A"},
        platform_rules={"name": "X", "specs": []},
        creative_logic={"name": "Y", "logic_steps": []},
    )
    assert "COMPLIANCE NEGATIVE LIST" not in prompt


def test_collect_avoid_terms_from_history():
    project = {
        "history_log": [
            {
                "timestamp": "2025-01-01T00:00:00Z",
                "compliance": {"hits": [{"term": "Free Gift"}, {"term": "Unlimited"}]},
            },
            {
                "timestamp": "2025-01-02T00:00:00Z",
                "compliance": {"hits": [{"term": "Free Gift"}, {"term": "Hack"}]},
            },
        ]
    }
    terms = main._collect_avoid_terms(project, limit_records=5, limit_terms=10)
    assert "Free Gift" in terms
    assert "Unlimited" in terms
    assert "Hack" in terms
    # Dedupe
    assert terms.count("Free Gift") == 1


def test_factor_version_stable_and_differs_on_change():
    a = main._compute_factor_version({"a": 1}, {"b": 2}, {"c": 3})
    b = main._compute_factor_version({"a": 1}, {"b": 2}, {"c": 3})
    c = main._compute_factor_version({"a": 1}, {"b": 2}, {"c": 4})
    assert a == b
    assert a != c
    assert len(a) == 12


def test_extract_rag_rule_ids_from_evidence():
    ev = [
        {"id": "rule_1", "match_score": 0.9},
        {"source": "src_2"},
        {"rule_id": "rule_3"},
        {"id": "rule_1"},  # duplicate
    ]
    ids = main._extract_rag_rule_ids(ev)
    assert ids[:3] == ["rule_1", "src_2", "rule_3"]
    assert len(ids) == 3


def test_extract_rag_rule_ids_falls_back_to_citations():
    ids = main._extract_rag_rule_ids(evidence=None, citations=["c_1", "c_2", "c_1"])
    assert ids == ["c_1", "c_2"]


def _write_workspace(tmp_project_id: str, data: dict) -> Path:
    """Seed both the on-disk JSON (for legacy tests) and the Phase 26/E DB.

    Also returns the path so existing callers can still ``.unlink()`` it.
    """
    ws_dir = Path(main.__file__).parent / "data" / "workspaces"
    ws_dir.mkdir(parents=True, exist_ok=True)
    path = ws_dir / f"{tmp_project_id}.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    from projects_api import save_project

    save_project(dict(data))
    return path


def _load_workspace(project_id: str) -> dict:
    """Prefer the DB (Phase 26/E); fall back to on-disk JSON for unit tests."""
    from projects_api import load_project

    record = load_project(project_id)
    if record is not None:
        return record
    path = Path(main.__file__).parent / "data" / "workspaces" / f"{project_id}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def test_quick_copy_writes_history_schema_v2(client, monkeypatch, tmp_path):
    # Use an isolated workspace file so we do not pollute the real demo project
    monkeypatch.setattr(main, "cloud_client", None)
    monkeypatch.setattr(
        main,
        "retrieve_context_with_evidence",
        lambda *_args, **_kwargs: ("ctx", ["src1"], [{"id": "rule_X", "match_score": 0.8}]),
    )
    project_id = "phase22-fixture-qc"
    ws_path = _write_workspace(
        project_id,
        {
            "id": project_id,
            "name": "Fixture Game",
            "game_info": {"core_usp": "Demo"},
            "market_targets": [],
            "history_log": [],
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
        },
    )
    try:
        resp = client.post(
            "/api/quick-copy",
            json={
                "project_id": project_id,
                "region_id": "region_us_prime",
                "platform_id": "platform_applovin_unity",
                "angle_id": "angle_fail_trap_pro",
                "engine": "cloud",
                "output_mode": "cn",
                "quantity": 10,
                "tones": [],
                "locales": ["en"],
            },
        )
        assert resp.status_code == 200
        saved = _load_workspace(project_id)
        log = saved.get("history_log") or []
        assert log, "quick_copy must reliably append a history entry (pre-Phase 22 bug)"
        entry = log[-1]
        # Phase 25/D2 bumped schema to v3 (provider/model fields). Accept >= 2
        # so the Phase 22 regression stays future-proof.
        assert int(entry.get("schema_version") or 0) >= 2
        assert entry.get("output_kind") == "copy"
        assert entry.get("lang") == "cn"
        assert entry.get("decision") == "pending"
        assert isinstance(entry.get("rag_rule_ids"), list)
        assert entry.get("factor_version")
        assert entry.get("draft_status") == "skipped"
    finally:
        try:
            ws_path.unlink()
        except Exception:
            pass


def test_history_decision_endpoint_updates_entry(client):
    project_id = "phase22-fixture-decision"
    ws_path = _write_workspace(
        project_id,
        {
            "id": project_id,
            "name": "Decision Fixture",
            "game_info": {"core_usp": "Demo"},
            "market_targets": [],
            "history_log": [
                {
                    "id": "SOP-AAA111",
                    "timestamp": "2025-01-01T00:00:00Z",
                    "output_kind": "sop",
                    "decision": "pending",
                }
            ],
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
        },
    )
    try:
        # winner path
        resp = client.post(
            "/api/history/decision",
            json={"project_id": project_id, "script_id": "SOP-AAA111", "decision": "winner"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["decision"] == "winner"
        saved = _load_workspace(project_id)
        entry = saved["history_log"][0]
        assert entry["decision"] == "winner"
        assert entry.get("decision_at")

        # invalid decision
        resp_bad = client.post(
            "/api/history/decision",
            json={"project_id": project_id, "script_id": "SOP-AAA111", "decision": "champion"},
        )
        assert resp_bad.status_code == 400

        # unknown script
        resp_missing = client.post(
            "/api/history/decision",
            json={"project_id": project_id, "script_id": "SOP-XXX999", "decision": "loser"},
        )
        assert resp_missing.status_code == 404
    finally:
        try:
            ws_path.unlink()
        except Exception:
            pass


def test_history_decision_rejects_unknown_project(client):
    resp = client.post(
        "/api/history/decision",
        json={"project_id": "does-not-exist", "script_id": "SOP-ZZZ", "decision": "winner"},
    )
    assert resp.status_code == 404
