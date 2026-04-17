"""Phase 25 / D1 — LLM provider registry.

All providers supported by the system are assumed to expose an OpenAI-compatible
chat-completions endpoint (the industry default at the time of writing). The
registry normalises env-var naming, base URLs, default models, whether the
provider supports `response_format={"type": "json_object"}`, and pricing for
the cost estimator.

Usage (read-only side):
    from providers import list_providers, get_provider_info
    providers = list_providers()  # for /api/providers

Usage (call path side):
    from providers import get_client, resolve_model, is_json_mode_supported
    client = get_client("deepseek")
    model = resolve_model("deepseek", None)  # None → default
    if is_json_mode_supported("deepseek"):
        ...

The registry never raises; callers always check `client is not None` before
using it. Providers with missing API keys are still listed but flagged
`available=False` so the UI can disable them.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class ProviderSpec:
    id: str
    label: str
    api_key_env: str
    base_url_env: str
    default_base_url: str
    model_env: str
    default_model: str
    supports_json_mode: bool = True
    # Optional price override envs — when absent, cost_estimator defaults apply.
    price_prompt_env: str = ""
    price_completion_env: str = ""
    default_price_prompt_cny: float = 0.001
    default_price_completion_cny: float = 0.002
    # Free-form note shown in the /api/providers response (e.g. "deferred").
    note: str = ""
    # A short list of commonly-used model ids for the UI's model dropdown.
    model_choices: tuple[str, ...] = field(default_factory=tuple)


# Provider catalog. Order here drives the UI dropdown order.
PROVIDERS: tuple[ProviderSpec, ...] = (
    ProviderSpec(
        id="deepseek",
        label="DeepSeek",
        api_key_env="DEEPSEEK_API_KEY",
        base_url_env="DEEPSEEK_BASE_URL",
        default_base_url="https://api.deepseek.com",
        model_env="DEEPSEEK_MODEL",
        default_model="deepseek-chat",
        supports_json_mode=True,
        price_prompt_env="DEEPSEEK_PRICE_PROMPT_CNY_PER_1K",
        price_completion_env="DEEPSEEK_PRICE_COMPLETION_CNY_PER_1K",
        default_price_prompt_cny=0.001,
        default_price_completion_cny=0.002,
        model_choices=("deepseek-chat", "deepseek-reasoner"),
    ),
    ProviderSpec(
        id="siliconflow",
        label="SiliconFlow (硅基流动)",
        api_key_env="SILICONFLOW_API_KEY",
        base_url_env="SILICONFLOW_BASE_URL",
        default_base_url="https://api.siliconflow.cn/v1",
        model_env="SILICONFLOW_MODEL",
        default_model="deepseek-ai/DeepSeek-V3",
        supports_json_mode=True,
        price_prompt_env="SILICONFLOW_PRICE_PROMPT_CNY_PER_1K",
        price_completion_env="SILICONFLOW_PRICE_COMPLETION_CNY_PER_1K",
        default_price_prompt_cny=0.001,
        default_price_completion_cny=0.002,
        model_choices=(
            "deepseek-ai/DeepSeek-V3",
            "Qwen/Qwen2.5-72B-Instruct",
            "meta-llama/Meta-Llama-3.1-70B-Instruct",
        ),
    ),
    ProviderSpec(
        id="bailian",
        label="Alibaba Cloud Bailian (百炼)",
        api_key_env="BAILIAN_API_KEY",
        base_url_env="BAILIAN_BASE_URL",
        default_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model_env="BAILIAN_MODEL",
        default_model="qwen-plus",
        supports_json_mode=True,
        price_prompt_env="BAILIAN_PRICE_PROMPT_CNY_PER_1K",
        price_completion_env="BAILIAN_PRICE_COMPLETION_CNY_PER_1K",
        default_price_prompt_cny=0.0008,
        default_price_completion_cny=0.002,
        model_choices=("qwen-plus", "qwen-max", "qwen-turbo"),
    ),
    ProviderSpec(
        id="openrouter",
        label="OpenRouter",
        api_key_env="OPENROUTER_API_KEY",
        base_url_env="OPENROUTER_BASE_URL",
        default_base_url="https://openrouter.ai/api/v1",
        model_env="OPENROUTER_MODEL",
        default_model="deepseek/deepseek-chat",
        supports_json_mode=True,
        price_prompt_env="OPENROUTER_PRICE_PROMPT_CNY_PER_1K",
        price_completion_env="OPENROUTER_PRICE_COMPLETION_CNY_PER_1K",
        default_price_prompt_cny=0.002,
        default_price_completion_cny=0.006,
        model_choices=(
            "deepseek/deepseek-chat",
            "anthropic/claude-3.5-sonnet",
            "openai/gpt-4o-mini",
        ),
    ),
    ProviderSpec(
        id="zen",
        label="Open Code ZEN (deferred)",
        api_key_env="ZEN_API_KEY",
        base_url_env="ZEN_BASE_URL",
        default_base_url="https://api.opencode.zen/v1",
        model_env="ZEN_MODEL",
        default_model="zen-default",
        supports_json_mode=True,
        note="deferred",
        model_choices=("zen-default",),
    ),
)


_PROVIDER_BY_ID: dict[str, ProviderSpec] = {p.id: p for p in PROVIDERS}
# Cache OpenAI client instances per provider to avoid repeated construction.
_CLIENT_CACHE: dict[str, Any] = {}


def get_provider_spec(provider_id: Optional[str]) -> ProviderSpec:
    """Return the spec for the given provider, falling back to DeepSeek."""
    pid = (provider_id or "deepseek").strip().lower() or "deepseek"
    return _PROVIDER_BY_ID.get(pid, _PROVIDER_BY_ID["deepseek"])


# ---------------------------------------------------------------------------
# Phase 27 / F — DB-first runtime overrides. ``providers_store`` imports lazily
# because ``db`` may not be ready during unit-test collection.
# ---------------------------------------------------------------------------


def _load_store():
    try:
        import providers_store  # local import to avoid import-time DB init

        return providers_store
    except Exception:
        return None


def _resolved_api_key(provider_id: str) -> tuple[Optional[str], str]:
    spec = get_provider_spec(provider_id)
    store = _load_store()
    if store is not None:
        try:
            return store.resolve_api_key(spec.id, spec.api_key_env)
        except Exception:
            pass
    env_val = os.getenv(spec.api_key_env)
    if env_val and env_val.strip():
        return env_val.strip(), "env"
    return None, "none"


def is_provider_available(provider_id: str) -> bool:
    key, _source = _resolved_api_key(provider_id)
    return bool(key)


def resolve_model(provider_id: Optional[str], model: Optional[str]) -> str:
    """Pick the model to send to the API (call-arg > DB > env > default)."""
    spec = get_provider_spec(provider_id)
    if model and str(model).strip():
        return str(model).strip()
    store = _load_store()
    if store is not None:
        try:
            resolved, _source = store.resolve_default_model(
                spec.id, spec.model_env, spec.default_model
            )
            return resolved
        except Exception:
            pass
    envv = os.getenv(spec.model_env)
    if envv and envv.strip():
        return envv.strip()
    return spec.default_model


def resolve_base_url(provider_id: Optional[str]) -> str:
    spec = get_provider_spec(provider_id)
    store = _load_store()
    if store is not None:
        try:
            resolved, _source = store.resolve_base_url(
                spec.id, spec.base_url_env, spec.default_base_url
            )
            return resolved
        except Exception:
            pass
    return os.getenv(spec.base_url_env) or spec.default_base_url


def is_json_mode_supported(provider_id: Optional[str]) -> bool:
    return get_provider_spec(provider_id).supports_json_mode


def get_price_per_1k(provider_id: Optional[str]) -> tuple[float, float]:
    """Return (prompt_price_cny_per_1k, completion_price_cny_per_1k)."""
    spec = get_provider_spec(provider_id)
    try:
        prompt_price = float(os.getenv(spec.price_prompt_env) or spec.default_price_prompt_cny)
    except (TypeError, ValueError):
        prompt_price = spec.default_price_prompt_cny
    try:
        completion_price = float(os.getenv(spec.price_completion_env) or spec.default_price_completion_cny)
    except (TypeError, ValueError):
        completion_price = spec.default_price_completion_cny
    return prompt_price, completion_price


def get_client(provider_id: Optional[str]) -> Optional[Any]:
    """Return a cached OpenAI client for the provider, or None if unavailable."""
    spec = get_provider_spec(provider_id)
    api_key, source = _resolved_api_key(spec.id)
    if not api_key:
        return None
    # Cache key includes the source marker so DB rotations invalidate the
    # cached client when the key changes.
    cache_key = f"{spec.id}:{source}:{hash(api_key) & 0xffff}:{resolve_base_url(spec.id)}"
    cached = _CLIENT_CACHE.get(cache_key)
    if cached is not None:
        return cached
    try:
        from openai import OpenAI

        client = OpenAI(
            api_key=api_key,
            base_url=resolve_base_url(spec.id),
        )
    except Exception:
        return None
    _CLIENT_CACHE[cache_key] = client
    return client


def invalidate_client_cache(provider_id: Optional[str] = None) -> None:
    """Clear the cached OpenAI clients after a settings change."""
    if not provider_id:
        _CLIENT_CACHE.clear()
        return
    prefix = f"{provider_id}:"
    for k in list(_CLIENT_CACHE.keys()):
        if k.startswith(prefix):
            _CLIENT_CACHE.pop(k, None)


def get_model_choices(provider_id: str) -> list[str]:
    """Return the merged model dropdown: hardcoded choices + user extras."""
    spec = get_provider_spec(provider_id)
    merged: list[str] = list(spec.model_choices)
    store = _load_store()
    if store is not None:
        try:
            settings = store.get_settings(spec.id)
            for m in settings.extra_models or []:
                s = str(m).strip()
                if s and s not in merged:
                    merged.append(s)
        except Exception:
            pass
    return merged


def list_providers() -> list[dict[str, Any]]:
    """Snapshot intended for /api/providers — no secrets leaked."""
    store = _load_store()
    out: list[dict[str, Any]] = []
    for spec in PROVIDERS:
        prompt_price, completion_price = get_price_per_1k(spec.id)
        api_key, key_source = _resolved_api_key(spec.id)
        base_url_source = "default"
        default_model_source = "default"
        settings_obj = None
        if store is not None:
            try:
                settings_obj = store.get_settings(spec.id)
                _, base_url_source = store.resolve_base_url(
                    spec.id, spec.base_url_env, spec.default_base_url
                )
                _, default_model_source = store.resolve_default_model(
                    spec.id, spec.model_env, spec.default_model
                )
            except Exception:
                settings_obj = None
        mask = ""
        if store is not None and api_key and key_source == "db":
            try:
                mask = store.mask_api_key(api_key)
            except Exception:
                mask = ""
        elif api_key and key_source == "env":
            mask = "env · ****"
        out.append(
            {
                "id": spec.id,
                "label": spec.label,
                "available": bool(api_key),
                "default_model": spec.default_model,
                "resolved_model": resolve_model(spec.id, None),
                "supports_json_mode": spec.supports_json_mode,
                "note": spec.note,
                "base_url": resolve_base_url(spec.id),
                "base_url_source": base_url_source,
                "model_choices": get_model_choices(spec.id),
                "extra_models": list(getattr(settings_obj, "extra_models", []) or []),
                "has_api_key": bool(api_key),
                "api_key_source": key_source,  # db | env | none
                "api_key_mask": mask,
                "default_model_source": default_model_source,
                "last_tested_at": getattr(settings_obj, "last_tested_at", None),
                "last_test_ok": getattr(settings_obj, "last_test_ok", None),
                "last_test_note": getattr(settings_obj, "last_test_note", None),
                "api_key_env": spec.api_key_env,
                "base_url_env": spec.base_url_env,
                "model_env": spec.model_env,
                "price": {
                    "prompt_cny_per_1k": prompt_price,
                    "completion_cny_per_1k": completion_price,
                },
            }
        )
    return out


def get_explicit_default_provider() -> Optional[str]:
    import os, json
    settings_file = os.path.join(os.path.dirname(__file__), "data", "app_settings.json")
    if os.path.exists(settings_file):
        try:
            with open(settings_file, "r", encoding="utf-8") as f:
                return json.load(f).get("default_provider_id")
        except Exception:
            return None
    return None

def default_provider_id() -> str:
    """Prefer explicit user override, else first provider with key, else DeepSeek."""
    explicit = get_explicit_default_provider()
    if explicit:
        key, _ = _resolved_api_key(explicit)
        if key:
            return explicit
            
    for spec in PROVIDERS:
        key, _ = _resolved_api_key(spec.id)
        if key:
            return spec.id
    return "deepseek"
