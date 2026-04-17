"""
Daily usage for quota UI: Oracle ops + LLM tokens.

When the upstream API returns ``usage.total_tokens`` (or prompt+completion), those
values are accumulated as *provider* totals. Otherwise env-based fallbacks are
used (*estimate* totals). Cloud /extract-url uses rule-based distillation — no
tokens recorded unless you add a cloud LLM path later.
"""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_LOCK = threading.Lock()
_STATE_PATH = Path(__file__).resolve().parent / "usage_counters.json"


def _today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _budget() -> int:
    return int(os.getenv("USAGE_DAILY_TOKEN_BUDGET", "500000"))


def _fresh_row() -> dict[str, Any]:
    return {
        "utc_date": _today_utc(),
        "tokens_used_total": 0,
        "tokens_from_provider_total": 0,
        "tokens_from_estimate_total": 0,
        "script_generations_total": 0,
        "script_generations_provider": 0,
        "script_generations_estimate": 0,
        "last_script_tokens": 0,
        "oracle_retrievals": 0,
        "oracle_ingests": 0,
        # Phase 25 / D2 — aggregated LLM tokens & calls per provider id.
        # Shape: {provider_id: {"tokens": int, "calls": int}}
        "by_provider": {},
    }


def _normalize_loaded(data: dict) -> dict[str, Any]:
    """Merge legacy ``tokens_used_estimate`` into new shape."""
    raw_by_provider = data.get("by_provider") or {}
    by_provider: dict[str, dict[str, int]] = {}
    if isinstance(raw_by_provider, dict):
        for k, v in raw_by_provider.items():
            if not isinstance(v, dict):
                continue
            by_provider[str(k)] = {
                "tokens": int(v.get("tokens", 0) or 0),
                "calls": int(v.get("calls", 0) or 0),
            }
    row: dict[str, Any] = {
        "utc_date": str(data.get("utc_date", _today_utc())),
        "tokens_used_total": int(data.get("tokens_used_total", 0) or 0),
        "tokens_from_provider_total": int(data.get("tokens_from_provider_total", 0) or 0),
        "tokens_from_estimate_total": int(data.get("tokens_from_estimate_total", 0) or 0),
        "script_generations_total": int(data.get("script_generations_total", 0) or 0),
        "script_generations_provider": int(data.get("script_generations_provider", 0) or 0),
        "script_generations_estimate": int(data.get("script_generations_estimate", 0) or 0),
        "last_script_tokens": int(data.get("last_script_tokens", 0) or 0),
        "oracle_retrievals": int(data.get("oracle_retrievals", 0) or 0),
        "oracle_ingests": int(data.get("oracle_ingests", 0) or 0),
        "by_provider": by_provider,
    }
    legacy = int(data.get("tokens_used_estimate", 0) or 0)
    if row["tokens_used_total"] == 0 and legacy > 0:
        row["tokens_used_total"] = legacy
        row["tokens_from_estimate_total"] = legacy
    return row


def _load() -> dict[str, int | str]:
    if not _STATE_PATH.is_file():
        return _fresh_row()
    try:
        raw = _STATE_PATH.read_text(encoding="utf-8")
        data = json.loads(raw)
        if data.get("utc_date") != _today_utc():
            return _fresh_row()
        return _normalize_loaded(data)
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return _fresh_row()


def _save(data: dict[str, int | str]) -> None:
    _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _STATE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _resolve_tokens(measured: int | None, fallback: int) -> tuple[int, str]:
    """Returns (delta, source) where source is provider / estimate / none."""
    if measured is not None and measured >= 0:
        return int(measured), "provider"
    delta = max(0, int(fallback))
    if delta > 0:
        return delta, "estimate"
    return 0, "none"


def _add_llm_tokens(
    measured: int | None,
    fallback: int,
    *,
    provider: str | None = None,
) -> tuple[int, str]:
    """Add one LLM call to token tallies. Returns (delta, source).

    Phase 25 / D2: when ``provider`` is given, the tokens + call are also
    aggregated under ``by_provider[provider]``.
    """
    delta, source = _resolve_tokens(measured, fallback)
    if delta == 0:
        return 0, "none"
    with _LOCK:
        data = _load()
        data["tokens_used_total"] = int(data["tokens_used_total"]) + int(delta)
        if source == "provider":
            data["tokens_from_provider_total"] = int(data["tokens_from_provider_total"]) + int(delta)
        else:
            data["tokens_from_estimate_total"] = int(data["tokens_from_estimate_total"]) + int(delta)
        if provider:
            pid = str(provider).strip().lower() or "unknown"
            by = data.setdefault("by_provider", {})
            if not isinstance(by, dict):
                by = {}
                data["by_provider"] = by
            row = by.setdefault(pid, {"tokens": 0, "calls": 0})
            row["tokens"] = int(row.get("tokens", 0)) + int(delta)
            row["calls"] = int(row.get("calls", 0)) + 1
        _save(data)
    return int(delta), source


def record_generate_success(
    engine: str = "cloud",
    measured_tokens: int | None = None,
    *,
    provider: str | None = None,
) -> None:
    """Successful /api/generate: Oracle retrieval + LLM tokens (measured or fallback).

    ``engine`` is kept for call-site backward compat but is always treated as the
    cloud path (DeepSeek) now that the local Ollama engine has been removed.
    Phase 25 / D2 adds ``provider`` for by_provider aggregation.
    """
    _ = engine  # kept for signature compatibility
    fb = int(os.getenv("USAGE_TOKENS_ESTIMATE_GENERATE_CLOUD", "8500"))
    delta, source = _add_llm_tokens(measured_tokens, fb, provider=provider)
    with _LOCK:
        data = _load()
        data["oracle_retrievals"] = int(data["oracle_retrievals"]) + 1
        data["script_generations_total"] = int(data["script_generations_total"]) + 1
        data["last_script_tokens"] = int(delta)
        if source == "provider":
            data["script_generations_provider"] = int(data["script_generations_provider"]) + 1
        elif source == "estimate":
            data["script_generations_estimate"] = int(data["script_generations_estimate"]) + 1
        _save(data)


def record_extract_url_success(
    engine: str = "cloud",
    measured_tokens: int | None = None,
    *,
    used_llm: bool = False,
    provider: str | None = None,
) -> None:
    """
    Successful /api/extract-url: charge tokens only when an LLM was actually used.
    Provider-reported ``measured_tokens`` are recorded as-is; rule-based fallbacks
    do not charge. ``engine`` is accepted for backward compat only.
    Phase 25 / D2 adds ``provider`` for by_provider aggregation.
    """
    _ = engine
    if not used_llm:
        return
    if measured_tokens is not None and measured_tokens >= 0:
        _add_llm_tokens(measured_tokens, 0, provider=provider)
        return
    fb = int(os.getenv("USAGE_TOKENS_ESTIMATE_EXTRACT", "2800"))
    _add_llm_tokens(measured_tokens, fb, provider=provider)


def record_oracle_ingest_success() -> None:
    with _LOCK:
        data = _load()
        data["oracle_ingests"] = int(data["oracle_ingests"]) + 1
        _save(data)


def get_summary() -> dict:
    with _LOCK:
        data = _load()
    budget = _budget()
    total = int(data["tokens_used_total"])
    prov = int(data["tokens_from_provider_total"])
    est = int(data["tokens_from_estimate_total"])
    scripts = int(data["script_generations_total"])
    avg_script = int(round(total / scripts)) if scripts > 0 else 0
    per_script_provider = int(round(prov / scripts)) if scripts > 0 else 0
    per_script_estimate = int(round(est / scripts)) if scripts > 0 else 0
    remaining = max(0, budget - total)
    if prov > 0 and est > 0:
        billing_quality = "mixed"
    elif prov > 0:
        billing_quality = "provider"
    else:
        billing_quality = "estimate_only"

    if billing_quality == "provider":
        token_note = "Token 主要来自上游 API 返回的 usage 字段（DeepSeek 等 OpenAI 兼容接口）。"
    elif billing_quality == "mixed":
        token_note = "部分请求含厂商 usage，其余为本地估算补齐。"
    else:
        token_note = "当前无可用厂商用量字段，累计为环境变量估算；接入 API usage 后将自动切换。"

    by_provider_raw = data.get("by_provider") or {}
    by_provider: dict[str, dict[str, int]] = {}
    if isinstance(by_provider_raw, dict):
        for k, v in by_provider_raw.items():
            if not isinstance(v, dict):
                continue
            by_provider[str(k)] = {
                "tokens": int(v.get("tokens", 0) or 0),
                "calls": int(v.get("calls", 0) or 0),
            }
    return {
        "reset_utc_date": data["utc_date"],
        "tokens_budget_today": budget,
        "tokens_used_today": total,
        "tokens_used_today_estimate": total,
        "tokens_from_provider_today": prov,
        "tokens_from_estimate_today": est,
        "tokens_remaining_today_estimate": remaining,
        "script_generations_today": scripts,
        "avg_tokens_per_script_today": avg_script,
        "avg_provider_tokens_per_script_today": per_script_provider,
        "avg_estimate_tokens_per_script_today": per_script_estimate,
        "last_script_tokens": int(data["last_script_tokens"]),
        "script_generations_provider_today": int(data["script_generations_provider"]),
        "script_generations_estimate_today": int(data["script_generations_estimate"]),
        "billing_quality": billing_quality,
        "token_note": token_note,
        "oracle_note": "检索 = 每次成功剧本生成时的向量检索；归档 = 成功 ingest 次数。",
        "oracle_retrievals_today": int(data["oracle_retrievals"]),
        "oracle_ingests_today": int(data["oracle_ingests"]),
        "by_provider_today": by_provider,
    }
