"""Phase 23 / B2 — Pre-flight cost / token estimator.

This module produces a cheap but monotonic estimate of the tokens a
generation request will cost, along with a CNY price estimate based on
env-configurable DeepSeek pricing. It is intentionally not exact — its
only contract is that scaling the drivers (quantity / locales / regions)
scales the estimate monotonically, so the UI can use it as a decision aid.

Pricing knobs (DeepSeek defaults; override per-provider once Phase 25
lands):

* ``DEEPSEEK_PRICE_INPUT_CNY_PER_1K``  (default ``0.001``)
* ``DEEPSEEK_PRICE_OUTPUT_CNY_PER_1K`` (default ``0.002``)
"""
from __future__ import annotations

import os
from typing import Any

EstimateKind = str  # "generate_full" | "generate_draft" | "quick_copy" | "refresh_copy"


_BASE_PROMPT_TOKENS = {
    # Rough budget of the system prompt + factor JSONs + RAG context blob.
    "generate_full": 4200,
    "generate_draft": 2100,
    "quick_copy": 2400,
    "refresh_copy": 2700,  # slightly higher: existing script context injected
}

# Per-locale headline cost (including primary_texts / hashtags overhead).
_COPY_TOKENS_PER_HEADLINE = 22
_COPY_TOKENS_PER_LOCALE_OVERHEAD = 180

# Director stage baseline (shots + matrix + review metadata).
_DIRECTOR_COMPLETION_TOKENS = 3200
# Draft stage baseline (3-5 concept cards).
_DRAFT_COMPLETION_TOKENS = 900


def _price_per_1k(kind: str, default: float) -> float:
    raw = os.getenv(f"DEEPSEEK_PRICE_{kind}_CNY_PER_1K")
    if not raw:
        return default
    try:
        return max(0.0, float(raw))
    except ValueError:
        return default


def _input_price(provider_id: str | None = None) -> float:
    if provider_id:
        try:
            from providers import get_price_per_1k

            prompt_cny, _ = get_price_per_1k(provider_id)
            return max(0.0, float(prompt_cny))
        except Exception:
            pass
    return _price_per_1k("INPUT", 0.001)


def _output_price(provider_id: str | None = None) -> float:
    if provider_id:
        try:
            from providers import get_price_per_1k

            _, completion_cny = get_price_per_1k(provider_id)
            return max(0.0, float(completion_cny))
        except Exception:
            pass
    return _price_per_1k("OUTPUT", 0.002)


def _coerce_int(value: Any, *, default: int, minimum: int = 0, maximum: int | None = None) -> int:
    try:
        i = int(value)
    except (TypeError, ValueError):
        return default
    if i < minimum:
        return minimum
    if maximum is not None and i > maximum:
        return maximum
    return i


def _coerce_list_len(value: Any, *, default: int = 1, maximum: int = 16) -> int:
    if isinstance(value, (list, tuple, set)):
        length = len(value)
    elif value is None:
        length = 0
    else:
        length = 1
    if length <= 0:
        length = default
    return min(length, maximum)


def estimate_tokens(kind: EstimateKind, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return a dict with ``prompt_tokens`` / ``completion_tokens`` / ``total`` / ``price_cny``.

    ``params`` shape depends on ``kind``:

    * ``generate_full`` / ``generate_draft`` — no required fields.
    * ``quick_copy`` — ``quantity`` (int, default 20), ``locales`` (list), ``region_ids`` (list).
    * ``refresh_copy`` — ``quantity`` (int, default 20), ``locales`` (list).
    """
    params = params or {}
    kind = (kind or "").strip() or "generate_full"
    base = _BASE_PROMPT_TOKENS.get(kind, _BASE_PROMPT_TOKENS["generate_full"])
    prompt_tokens = base
    completion_tokens = _DIRECTOR_COMPLETION_TOKENS

    if kind == "generate_draft":
        completion_tokens = _DRAFT_COMPLETION_TOKENS
    elif kind in {"quick_copy", "refresh_copy"}:
        quantity = _coerce_int(params.get("quantity"), default=20, minimum=5, maximum=200)
        locale_count = _coerce_list_len(params.get("locales"), default=1, maximum=12)
        region_count = _coerce_list_len(params.get("region_ids"), default=1, maximum=8) if kind == "quick_copy" else 1
        combined = locale_count * region_count
        # quick_copy multiplies the whole prompt per-region because each region is a separate LLM call.
        if kind == "quick_copy":
            prompt_tokens = base * region_count + 120 * (region_count - 1)
        completion_tokens = (
            _COPY_TOKENS_PER_LOCALE_OVERHEAD * max(1, combined)
            + _COPY_TOKENS_PER_HEADLINE * quantity * max(1, combined)
        )
    elif kind == "generate_full":
        # director + optional draft stage when mode==auto
        mode = str(params.get("mode") or "auto").lower()
        if mode in {"auto", "draft"}:
            prompt_tokens += _BASE_PROMPT_TOKENS["generate_draft"]
            completion_tokens += _DRAFT_COMPLETION_TOKENS

    compliance_suggest = bool(params.get("compliance_suggest"))
    if compliance_suggest:
        # Extra LLM call to rewrite hits — conservative flat budget.
        prompt_tokens += 600
        completion_tokens += 500

    total = int(prompt_tokens + completion_tokens)
    provider_id = None
    raw_provider = params.get("engine_provider")
    if raw_provider:
        provider_id = str(raw_provider).strip().lower() or None
    prompt_price_1k = _input_price(provider_id)
    completion_price_1k = _output_price(provider_id)
    price_cny = round(
        (prompt_tokens / 1000.0) * prompt_price_1k
        + (completion_tokens / 1000.0) * completion_price_1k,
        4,
    )
    return {
        "kind": kind,
        "prompt_tokens": int(prompt_tokens),
        "completion_tokens": int(completion_tokens),
        "total_tokens": total,
        "price_cny": price_cny,
        "input_price_per_1k": prompt_price_1k,
        "output_price_per_1k": completion_price_1k,
        "provider_id": provider_id or "deepseek",
    }


def estimate_with_budget(kind: EstimateKind, params: dict[str, Any] | None, summary: dict) -> dict[str, Any]:
    """Merge :func:`estimate_tokens` with the live budget snapshot from usage_tracker."""
    est = estimate_tokens(kind, params)
    budget = int(summary.get("tokens_budget_today") or 0)
    used = int(summary.get("tokens_used_today") or 0)
    remaining = int(summary.get("tokens_remaining_today_estimate") or max(0, budget - used))
    after_used = used + est["total_tokens"]
    after_remaining = max(0, budget - after_used)
    pct_of_budget = (
        round(est["total_tokens"] / budget * 100.0, 2) if budget > 0 else 0.0
    )
    warn_level: str
    if budget <= 0:
        warn_level = "ok"
    elif remaining <= 0 or after_remaining <= 0:
        warn_level = "block"
    elif after_remaining / budget < 0.10:
        warn_level = "critical"
    elif after_remaining / budget < 0.25:
        warn_level = "warn"
    else:
        warn_level = "ok"
    return {
        **est,
        "budget": {
            "tokens_budget_today": budget,
            "tokens_used_today": used,
            "tokens_remaining_today": remaining,
            "projected_used_after": after_used,
            "projected_remaining_after": after_remaining,
            "percentage_of_daily_budget": pct_of_budget,
            "warn_level": warn_level,
        },
    }


__all__ = ["estimate_tokens", "estimate_with_budget"]
