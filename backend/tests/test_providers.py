"""Phase 25 / D1 — Provider registry tests."""
from __future__ import annotations

import importlib

import providers


def test_list_providers_has_expected_ids():
    ids = [p["id"] for p in providers.list_providers()]
    assert ids == ["deepseek", "siliconflow", "bailian", "openrouter", "zen"]


def test_list_providers_shape():
    for entry in providers.list_providers():
        assert "label" in entry
        assert "available" in entry
        assert "default_model" in entry
        assert "resolved_model" in entry
        assert "supports_json_mode" in entry
        assert "base_url" in entry
        assert "model_choices" in entry
        assert "price" in entry
        assert "prompt_cny_per_1k" in entry["price"]
        assert "completion_cny_per_1k" in entry["price"]
        assert isinstance(entry["model_choices"], list)
        # No secrets ever leaked.
        assert "api_key" not in entry
        assert "key" not in entry


def test_resolve_model_precedence(monkeypatch):
    monkeypatch.setenv("SILICONFLOW_MODEL", "Qwen/Qwen2.5-72B-Instruct")
    assert (
        providers.resolve_model("siliconflow", None)
        == "Qwen/Qwen2.5-72B-Instruct"
    )
    assert (
        providers.resolve_model("siliconflow", "custom-model")
        == "custom-model"
    )


def test_resolve_model_falls_back_to_default(monkeypatch):
    monkeypatch.delenv("BAILIAN_MODEL", raising=False)
    assert providers.resolve_model("bailian", None) == "qwen-plus"


def test_resolve_model_unknown_provider_defaults_to_deepseek(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)
    assert providers.resolve_model("no-such", None) == "deepseek-chat"


def test_is_json_mode_supported():
    for pid in ("deepseek", "siliconflow", "bailian", "openrouter", "zen"):
        assert providers.is_json_mode_supported(pid) is True


def test_get_price_per_1k_override(monkeypatch):
    monkeypatch.setenv("OPENROUTER_PRICE_PROMPT_CNY_PER_1K", "0.01")
    monkeypatch.setenv("OPENROUTER_PRICE_COMPLETION_CNY_PER_1K", "0.02")
    prompt, completion = providers.get_price_per_1k("openrouter")
    assert prompt == 0.01
    assert completion == 0.02


def test_get_price_per_1k_defaults(monkeypatch):
    monkeypatch.delenv("BAILIAN_PRICE_PROMPT_CNY_PER_1K", raising=False)
    monkeypatch.delenv("BAILIAN_PRICE_COMPLETION_CNY_PER_1K", raising=False)
    prompt, completion = providers.get_price_per_1k("bailian")
    assert prompt == 0.0008
    assert completion == 0.002


def test_get_client_returns_none_without_key(monkeypatch):
    monkeypatch.delenv("SILICONFLOW_API_KEY", raising=False)
    # Bust cache in case another test populated it.
    providers._CLIENT_CACHE.pop("siliconflow", None)
    assert providers.get_client("siliconflow") is None


def test_get_client_caches_instance(monkeypatch):
    monkeypatch.setenv("BAILIAN_API_KEY", "sk-test")
    providers._CLIENT_CACHE.pop("bailian", None)
    c1 = providers.get_client("bailian")
    c2 = providers.get_client("bailian")
    assert c1 is not None
    assert c1 is c2


def test_default_provider_id_prefers_configured(monkeypatch):
    # Clear all keys, then set only one.
    for spec in providers.PROVIDERS:
        monkeypatch.delenv(spec.api_key_env, raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    # Reimport not needed — default_provider_id reads env live.
    assert providers.default_provider_id() == "openrouter"


def test_default_provider_id_fallback(monkeypatch):
    for spec in providers.PROVIDERS:
        monkeypatch.delenv(spec.api_key_env, raising=False)
    assert providers.default_provider_id() == "deepseek"


def test_zen_marked_deferred():
    for entry in providers.list_providers():
        if entry["id"] == "zen":
            assert entry["note"] == "deferred"
            break
    else:
        raise AssertionError("zen provider not listed")


def test_module_reimport_safe():
    # Sanity: re-importing should not blow up (registry has no init side effects).
    importlib.reload(providers)
    assert hasattr(providers, "PROVIDERS")
