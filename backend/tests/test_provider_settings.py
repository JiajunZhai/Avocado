"""Phase 27 / F — user-editable provider settings (API key + base URL +
custom model list), DB-backed, with env fallback preserved.
"""
from __future__ import annotations

import os

import pytest

import providers
import providers_store


@pytest.fixture(autouse=True)
def _cleanup_deepseek_overrides():
    """Isolate the deepseek row between tests so assertions are deterministic."""
    providers_store.delete_settings("deepseek")
    providers.invalidate_client_cache("deepseek")
    yield
    providers_store.delete_settings("deepseek")
    providers.invalidate_client_cache("deepseek")


def test_get_settings_returns_empty_row_by_default():
    s = providers_store.get_settings("deepseek")
    assert s.id == "deepseek"
    assert s.api_key is None
    assert s.base_url is None
    assert s.default_model is None
    assert s.extra_models == []


def test_upsert_persists_api_key_and_overrides_env(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "env-key-xyz")
    # Without a DB override, env wins.
    key, source = providers_store.resolve_api_key("deepseek", "DEEPSEEK_API_KEY")
    assert key == "env-key-xyz"
    assert source == "env"

    providers_store.upsert_settings("deepseek", api_key="sk-db-secret-1234abcd")
    key, source = providers_store.resolve_api_key("deepseek", "DEEPSEEK_API_KEY")
    assert key == "sk-db-secret-1234abcd"
    assert source == "db"


def test_upsert_partial_update_preserves_untouched_columns():
    providers_store.upsert_settings(
        "deepseek",
        api_key="sk-original",
        base_url="https://custom.example.com/v1",
        default_model="deepseek-chat",
        extra_models=["deepseek-v3.1", "deepseek-coder"],
    )
    # Partial update — only base_url. The other fields must survive.
    providers_store.upsert_settings("deepseek", base_url="https://rotated.example.com/v1")
    s = providers_store.get_settings("deepseek")
    assert s.api_key == "sk-original"
    assert s.base_url == "https://rotated.example.com/v1"
    assert s.default_model == "deepseek-chat"
    assert s.extra_models == ["deepseek-v3.1", "deepseek-coder"]


def test_clear_api_key_wipes_db_row_and_restores_env_fallback(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "env-fallback")
    providers_store.upsert_settings("deepseek", api_key="sk-db")
    assert providers_store.resolve_api_key("deepseek", "DEEPSEEK_API_KEY") == (
        "sk-db",
        "db",
    )

    providers_store.upsert_settings("deepseek", clear_api_key=True)
    key, source = providers_store.resolve_api_key("deepseek", "DEEPSEEK_API_KEY")
    assert key == "env-fallback"
    assert source == "env"


def test_mask_api_key_never_returns_full_secret():
    assert providers_store.mask_api_key(None) == ""
    assert providers_store.mask_api_key("short") == "*****"
    assert providers_store.mask_api_key("sk-abcdef1234567890") == "sk-a****7890"


def test_list_providers_reflects_db_state_without_leaking_key():
    providers_store.upsert_settings(
        "deepseek",
        api_key="sk-db-super-secret-value",
        extra_models=["my-finetune-v1"],
    )
    entries = providers.list_providers()
    deepseek = next(p for p in entries if p["id"] == "deepseek")
    assert deepseek["has_api_key"] is True
    assert deepseek["api_key_source"] == "db"
    assert "api_key" not in deepseek  # never raw
    assert "super-secret-value" not in deepseek["api_key_mask"]
    assert deepseek["api_key_mask"].startswith("sk-d")
    assert "my-finetune-v1" in deepseek["model_choices"]
    assert deepseek["extra_models"] == ["my-finetune-v1"]


def test_default_provider_id_picks_db_provider_even_without_env(monkeypatch):
    for spec in providers.PROVIDERS:
        monkeypatch.delenv(spec.api_key_env, raising=False)
    # No env keys → default should be deepseek (hardcoded tail).
    assert providers.default_provider_id() == "deepseek"

    providers_store.upsert_settings("siliconflow", api_key="sk-sf-token")
    try:
        assert providers.default_provider_id() == "siliconflow"
    finally:
        providers_store.delete_settings("siliconflow")
        providers.invalidate_client_cache("siliconflow")


def test_put_settings_route_rejects_unknown_provider(client):
    r = client.put(
        "/api/providers/settings/does-not-exist",
        json={"api_key": "sk-xxx"},
    )
    assert r.status_code == 404


def test_put_settings_route_persists_and_reflects_in_catalog(client, monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    try:
        r = client.put(
            "/api/providers/settings/openrouter",
            json={
                "api_key": "sk-or-frontend-provided",
                "base_url": "https://openrouter.example.com/v1",
                "default_model": "anthropic/claude-3.5-sonnet",
                "extra_models": ["openai/gpt-4o-mini", "anthropic/claude-3.5-sonnet"],
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["success"] is True
        assert body["provider"]["has_api_key"] is True
        assert body["provider"]["api_key_source"] == "db"
        assert body["provider"]["base_url_source"] == "db"
        assert body["provider"]["default_model_source"] == "db"
        assert "openai/gpt-4o-mini" in body["provider"]["model_choices"]
        # A follow-up GET must observe the same state (no request-scoped cache).
        catalog = client.get("/api/providers").json()
        entry = next(p for p in catalog["providers"] if p["id"] == "openrouter")
        assert entry["has_api_key"] is True
        assert entry["base_url"] == "https://openrouter.example.com/v1"
    finally:
        providers_store.delete_settings("openrouter")
        providers.invalidate_client_cache("openrouter")


def test_delete_settings_route_resets_overrides(client, monkeypatch):
    monkeypatch.delenv("BAILIAN_API_KEY", raising=False)
    monkeypatch.delenv("BAILIAN_MODEL", raising=False)
    monkeypatch.delenv("BAILIAN_BASE_URL", raising=False)
    try:
        client.put(
            "/api/providers/settings/bailian",
            json={"api_key": "sk-bl-test", "default_model": "qwen-max"},
        )
        before = client.get("/api/providers").json()
        bl = next(p for p in before["providers"] if p["id"] == "bailian")
        assert bl["has_api_key"] is True

        r = client.delete("/api/providers/settings/bailian")
        assert r.status_code == 200

        after = client.get("/api/providers").json()
        bl2 = next(p for p in after["providers"] if p["id"] == "bailian")
        assert bl2["has_api_key"] is False
        assert bl2["api_key_source"] == "none"
        assert bl2["default_model_source"] == "default"
    finally:
        providers_store.delete_settings("bailian")
        providers.invalidate_client_cache("bailian")


def test_test_route_without_key_returns_failure_note(client, monkeypatch):
    monkeypatch.delenv("ZEN_API_KEY", raising=False)
    r = client.post("/api/providers/zen/test")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    # The failure note is persisted on the row for later inspection.
    catalog = client.get("/api/providers").json()
    zen = next(p for p in catalog["providers"] if p["id"] == "zen")
    assert zen["last_test_ok"] is False
    assert "no api key" in (zen["last_test_note"] or "")


def test_fetch_models_route_requires_api_key(client, monkeypatch):
    for spec in providers.PROVIDERS:
        monkeypatch.delenv(spec.api_key_env, raising=False)
    r = client.post("/api/providers/siliconflow/fetch-models")
    assert r.status_code == 400


def test_normalize_chat_model_ids_filters_non_chat_and_dated():
    """F7 — raw /v1/models dumps (esp. Bailian) mix chat + embedding + image +
    ASR/TTS + dated snapshots. The normalizer must keep only chat ids and
    collapse dated variants onto their base.
    """
    from main import _normalize_chat_model_ids

    raw = [
        "deepseek-chat",
        "deepseek-chat-2026-03-15",  # dated snapshot → drop (base kept)
        "deepseek-reasoner",
        "qwen3-omni-plus",
        "qwen3-omni-plus-2025-08-15",  # dated → drop
        "qwen3-omni-plus-2026-03-15",  # dated → drop
        "text-embedding-v3",  # embedding → drop
        "bge-large-zh",  # embedding family → drop
        "qwen3-asr-flash",  # ASR → drop
        "qwen3-tts-vd",  # TTS → drop
        "qwen-image",  # image → drop
        "wan2.7-image-pro",  # image → drop
        "cosyvoice-v1",  # speech → drop
        "MiniMax/speech-2.8-turbo",  # speech → drop
        "gte-rerank-v2",  # rerank → drop
        "qwen-vl-max",  # vision → drop (contains -vl-)
    ]
    out = _normalize_chat_model_ids(raw)
    assert "deepseek-chat" in out
    assert "deepseek-reasoner" in out
    assert "qwen3-omni-plus" in out
    # All dated snapshots whose base survived must be gone.
    assert "deepseek-chat-2026-03-15" not in out
    assert "qwen3-omni-plus-2025-08-15" not in out
    assert "qwen3-omni-plus-2026-03-15" not in out
    # All non-chat categories gone.
    for bad in (
        "text-embedding-v3",
        "bge-large-zh",
        "qwen3-asr-flash",
        "qwen3-tts-vd",
        "qwen-image",
        "wan2.7-image-pro",
        "cosyvoice-v1",
        "MiniMax/speech-2.8-turbo",
        "gte-rerank-v2",
        "qwen-vl-max",
    ):
        assert bad not in out, f"{bad} should have been filtered"
    # Kept list is deduped and non-empty.
    assert len(out) == len(set(out))
    assert len(out) >= 3


def test_normalize_keeps_dated_variant_when_base_missing():
    """If a provider only returns versioned ids (e.g. `gpt-4o-2024-08-06`)
    without a bare `gpt-4o`, the normalizer must keep the dated one so the
    model remains reachable.
    """
    from main import _normalize_chat_model_ids

    out = _normalize_chat_model_ids(["gpt-4o-2024-08-06", "claude-3-5-sonnet-2024-10-22"])
    assert out == ["gpt-4o-2024-08-06", "claude-3-5-sonnet-2024-10-22"]
