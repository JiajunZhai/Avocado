"""Phase 25 / D2-D3 — /api/providers route + per-call routing integration."""
from __future__ import annotations

import json

import main


def _write_workspace(tmp_path, project_id, payload):
    """Phase 26/E — seed both the legacy JSON and the SQLite projects table."""
    import os
    from pathlib import Path

    ws_dir = Path(os.path.dirname(main.__file__)) / "data" / "workspaces"
    ws_dir.mkdir(parents=True, exist_ok=True)
    ws_path = ws_dir / f"{project_id}.json"
    ws_path.write_text(json.dumps(payload), encoding="utf-8")
    from projects_api import save_project

    save_project(dict(payload))
    return ws_path


def _load_workspace(project_id):
    from projects_api import load_project

    return load_project(project_id) or {}


def test_providers_route_returns_catalog(client):
    r = client.get("/api/providers")
    assert r.status_code == 200
    body = r.json()
    assert "default_provider_id" in body
    assert "providers" in body
    ids = [p["id"] for p in body["providers"]]
    for needed in ("deepseek", "siliconflow", "bailian", "openrouter", "zen"):
        assert needed in ids
    for p in body["providers"]:
        # No secrets leaked.
        assert "api_key" not in p
        assert "price" in p
        assert p["price"]["prompt_cny_per_1k"] >= 0
        assert p["price"]["completion_cny_per_1k"] >= 0


def test_providers_route_availability_reflects_env(client, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    monkeypatch.delenv("SILICONFLOW_API_KEY", raising=False)
    r = client.get("/api/providers")
    assert r.status_code == 200
    body = r.json()
    for p in body["providers"]:
        if p["id"] == "openrouter":
            assert p["available"] is True
        if p["id"] == "siliconflow":
            assert p["available"] is False


def test_resolve_llm_client_falls_back_to_cloud(monkeypatch):
    """If caller passes an unconfigured provider, we fall back to the legacy
    cloud_client (DeepSeek) when it is configured."""

    class FakeClient:
        pass

    fake = FakeClient()
    monkeypatch.setattr(main, "cloud_client", fake)
    monkeypatch.delenv("SILICONFLOW_API_KEY", raising=False)
    client, pid, model = main.resolve_llm_client("siliconflow", None)
    assert client is fake
    assert pid == "deepseek"
    assert isinstance(model, str) and model


def test_resolve_llm_client_none_when_no_key_anywhere(monkeypatch):
    monkeypatch.setattr(main, "cloud_client", None)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("SILICONFLOW_API_KEY", raising=False)
    client, pid, model = main.resolve_llm_client(None, None)
    assert client is None
    assert isinstance(pid, str) and pid
    assert isinstance(model, str) and model


def test_quick_copy_accepts_engine_provider_and_records_it(client, monkeypatch, tmp_path):
    """When a provider is requested but no key is set, quick_copy still runs
    (graceful skip), does not crash, and records the fallback provider in
    history schema v3."""
    monkeypatch.setattr(main, "cloud_client", None)
    monkeypatch.setattr(
        main,
        "retrieve_context_with_evidence",
        lambda *_args, **_kwargs: ("ctx", [], []),
    )
    project_id = "phase25-fixture-qc"
    ws = _write_workspace(
        tmp_path,
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
                "engine_provider": "siliconflow",
                "engine_model": "Qwen/Qwen2.5-72B-Instruct",
                "output_mode": "cn",
                "quantity": 10,
                "tones": [],
                "locales": ["en"],
            },
        )
        assert resp.status_code == 200, resp.text
        saved = _load_workspace(project_id)
        entries = saved.get("history_log") or []
        assert entries
        entry = entries[-1]
        # Schema v3 fields present.
        assert "provider" in entry
        assert "model" in entry
        # provider is a non-empty string (either 'siliconflow' or 'deepseek' fallback).
        assert isinstance(entry.get("provider"), str) and entry["provider"]
        assert isinstance(entry.get("model"), str) and entry["model"]
    finally:
        try:
            ws.unlink()
        except Exception:
            pass


def test_estimate_endpoint_accepts_engine_provider(client, monkeypatch):
    # openrouter has a higher default price, assert that price_cny increases.
    r1 = client.post("/api/estimate", json={"kind": "quick_copy", "quantity": 20, "locales": ["en"]})
    r2 = client.post(
        "/api/estimate",
        json={"kind": "quick_copy", "quantity": 20, "locales": ["en"], "engine_provider": "openrouter"},
    )
    assert r1.status_code == 200
    assert r2.status_code == 200
    b1 = r1.json()
    b2 = r2.json()
    # Tokens are identical; only the price_cny differs by provider.
    assert b1["total_tokens"] == b2["total_tokens"]
    assert b2["provider_id"] == "openrouter"
    assert b2["price_cny"] >= b1["price_cny"]
