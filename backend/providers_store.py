"""Phase 27 / F — runtime-editable provider settings (DB-first, env fallback).

The Phase 25 provider registry (``backend/providers.py``) hardcoded base URLs,
default models, and the list of selectable model ids; API keys could only be
configured via ``.env``. Phase 27 moves those knobs into the ``provider_settings``
SQLite table so power users can:

  * Paste an API key from the frontend without touching disk.
  * Point a provider at a self-hosted / proxy base URL.
  * Maintain a custom roster of model ids that their account has access to.
  * Record the result of the last connectivity test (for the UI badge).

Precedence — evaluated top-down, first non-empty wins:

  1. explicit call-site argument (e.g. ``engine_model`` passed to a route),
  2. DB row in ``provider_settings``,
  3. environment variable (legacy Phase 25 deployments keep working),
  4. hardcoded ``ProviderSpec`` default.

This module never raises; callers always check for ``None``.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable, Optional

from db import fetchone, execute


@dataclass
class ProviderSettings:
    id: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    default_model: Optional[str] = None
    extra_models: list[str] = field(default_factory=list)
    enabled: bool = True
    last_tested_at: Optional[str] = None
    last_test_ok: Optional[bool] = None
    last_test_note: Optional[str] = None
    updated_at: Optional[str] = None


_EMPTY = ProviderSettings(id="")


def _row_to_settings(row: Any) -> ProviderSettings:
    extras_raw = (row["extra_models_json"] if "extra_models_json" in row.keys() else None) or "[]"
    try:
        extras = json.loads(extras_raw)
        if not isinstance(extras, list):
            extras = []
    except Exception:
        extras = []
    return ProviderSettings(
        id=str(row["id"]),
        api_key=row["api_key"] or None,
        base_url=row["base_url"] or None,
        default_model=row["default_model"] or None,
        extra_models=[str(m).strip() for m in extras if str(m).strip()],
        enabled=bool(row["enabled"]) if row["enabled"] is not None else True,
        last_tested_at=row["last_tested_at"] or None,
        last_test_ok=None if row["last_test_ok"] is None else bool(row["last_test_ok"]),
        last_test_note=row["last_test_note"] or None,
        updated_at=row["updated_at"] or None,
    )


def get_settings(provider_id: str) -> ProviderSettings:
    if not provider_id:
        return _EMPTY
    try:
        row = fetchone(
            "SELECT * FROM provider_settings WHERE id = ?",
            (provider_id,),
        )
    except Exception:
        return ProviderSettings(id=provider_id)
    if not row:
        return ProviderSettings(id=provider_id)
    return _row_to_settings(row)


def upsert_settings(
    provider_id: str,
    *,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    default_model: Optional[str] = None,
    extra_models: Optional[Iterable[str]] = None,
    enabled: Optional[bool] = None,
    clear_api_key: bool = False,
) -> ProviderSettings:
    """Idempotent upsert with partial-update semantics.

    ``None`` means "leave as-is" (nothing is cleared). To explicitly wipe the
    stored API key, pass ``clear_api_key=True``. Empty-string values coerce to
    ``NULL`` so the env / default fallback path can re-engage.
    """
    if not provider_id:
        raise ValueError("provider_id is required")
    current = get_settings(provider_id)

    def _clean(val: Optional[str]) -> Optional[str]:
        if val is None:
            return None
        s = str(val).strip()
        return s or ""  # empty string → reset column to NULL below

    new_api_key = None if clear_api_key else (_clean(api_key) if api_key is not None else current.api_key)
    if new_api_key == "":
        new_api_key = None
    new_base_url = _clean(base_url) if base_url is not None else current.base_url
    if new_base_url == "":
        new_base_url = None
    new_default_model = _clean(default_model) if default_model is not None else current.default_model
    if new_default_model == "":
        new_default_model = None
    if extra_models is None:
        new_extras = current.extra_models
    else:
        seen: list[str] = []
        for m in extra_models:
            s = str(m).strip()
            if s and s not in seen:
                seen.append(s)
        new_extras = seen
    new_enabled = current.enabled if enabled is None else bool(enabled)

    now = datetime.utcnow().isoformat() + "Z"
    execute(
        """
        INSERT INTO provider_settings(
            id, api_key, base_url, default_model, extra_models_json,
            enabled, last_tested_at, last_test_ok, last_test_note, updated_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            api_key=excluded.api_key,
            base_url=excluded.base_url,
            default_model=excluded.default_model,
            extra_models_json=excluded.extra_models_json,
            enabled=excluded.enabled,
            updated_at=excluded.updated_at
        """,
        (
            provider_id,
            new_api_key,
            new_base_url,
            new_default_model,
            json.dumps(new_extras, ensure_ascii=False),
            1 if new_enabled else 0,
            current.last_tested_at,
            None if current.last_test_ok is None else (1 if current.last_test_ok else 0),
            current.last_test_note,
            now,
        ),
    )
    return get_settings(provider_id)


def record_test_result(
    provider_id: str,
    *,
    ok: bool,
    note: str = "",
) -> ProviderSettings:
    """Store the outcome of ``POST /api/providers/{id}/test`` for UI display."""
    if not provider_id:
        raise ValueError("provider_id is required")
    current = get_settings(provider_id)
    now = datetime.utcnow().isoformat() + "Z"
    execute(
        """
        INSERT INTO provider_settings(
            id, api_key, base_url, default_model, extra_models_json,
            enabled, last_tested_at, last_test_ok, last_test_note, updated_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            last_tested_at=excluded.last_tested_at,
            last_test_ok=excluded.last_test_ok,
            last_test_note=excluded.last_test_note,
            updated_at=excluded.updated_at
        """,
        (
            provider_id,
            current.api_key,
            current.base_url,
            current.default_model,
            json.dumps(current.extra_models, ensure_ascii=False),
            1 if current.enabled else 0,
            now,
            1 if ok else 0,
            (note or "").strip()[:500],
            now,
        ),
    )
    return get_settings(provider_id)


def delete_settings(provider_id: str) -> None:
    if not provider_id:
        return
    execute("DELETE FROM provider_settings WHERE id = ?", (provider_id,))


def mask_api_key(key: Optional[str]) -> str:
    """Return a UI-safe preview like ``sk-****4f2a``. Never return the raw key."""
    if not key:
        return ""
    s = str(key)
    if len(s) <= 8:
        return "*" * len(s)
    return f"{s[:4]}****{s[-4:]}"


def resolve_api_key(provider_id: str, env_name: str) -> tuple[Optional[str], str]:
    """Return ``(api_key, source)`` where source is ``db`` / ``env`` / ``none``."""
    settings = get_settings(provider_id)
    if settings.api_key:
        return settings.api_key, "db"
    env_val = os.getenv(env_name)
    if env_val and env_val.strip():
        return env_val.strip(), "env"
    return None, "none"


def resolve_base_url(
    provider_id: str, env_name: str, fallback: str
) -> tuple[str, str]:
    settings = get_settings(provider_id)
    if settings.base_url:
        return settings.base_url, "db"
    env_val = os.getenv(env_name)
    if env_val and env_val.strip():
        return env_val.strip(), "env"
    return fallback, "default"


def resolve_default_model(
    provider_id: str, env_name: str, fallback: str
) -> tuple[str, str]:
    settings = get_settings(provider_id)
    if settings.default_model:
        return settings.default_model, "db"
    env_val = os.getenv(env_name)
    if env_val and env_val.strip():
        return env_val.strip(), "env"
    return fallback, "default"
