"""Phase 23 / B2 — cost estimator tests.

The estimator's contract is loose: we only guarantee monotonicity and
shape. These tests pin the promises without locking in a specific curve.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import main
from cost_estimator import estimate_tokens, estimate_with_budget


# --------------------------------------------------------------------------- #
# estimate_tokens
# --------------------------------------------------------------------------- #

def test_estimate_returns_expected_shape():
    out = estimate_tokens("generate_full", {})
    assert set(out.keys()) >= {
        "kind",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "price_cny",
    }
    assert out["total_tokens"] == out["prompt_tokens"] + out["completion_tokens"]
    assert out["price_cny"] >= 0


def test_quick_copy_scales_with_quantity():
    small = estimate_tokens("quick_copy", {"quantity": 10, "locales": ["en"]})
    big = estimate_tokens("quick_copy", {"quantity": 40, "locales": ["en"]})
    # Doubling quantity at least doubles completion tokens.
    assert big["completion_tokens"] > small["completion_tokens"]
    assert big["total_tokens"] > small["total_tokens"]


def test_quick_copy_scales_with_locales_and_regions():
    single = estimate_tokens(
        "quick_copy",
        {"quantity": 20, "locales": ["en"], "region_ids": ["region_na_advanced"]},
    )
    multi = estimate_tokens(
        "quick_copy",
        {
            "quantity": 20,
            "locales": ["en", "ja", "ko"],
            "region_ids": ["region_na_advanced", "region_jp_advanced"],
        },
    )
    assert multi["total_tokens"] > single["total_tokens"] * 2


def test_refresh_copy_higher_prompt_than_draft():
    draft = estimate_tokens("generate_draft", {})
    refresh = estimate_tokens("refresh_copy", {"quantity": 20, "locales": ["en"]})
    assert refresh["prompt_tokens"] > draft["prompt_tokens"]


def test_unknown_kind_falls_back_to_generate_full():
    # Should not raise; should pick the baseline shape.
    out = estimate_tokens("ghost_mode", {})
    assert out["total_tokens"] > 0


def test_compliance_suggest_adds_overhead():
    without = estimate_tokens("generate_full", {})
    with_ = estimate_tokens("generate_full", {"compliance_suggest": True})
    assert with_["total_tokens"] > without["total_tokens"]


# --------------------------------------------------------------------------- #
# estimate_with_budget
# --------------------------------------------------------------------------- #

def test_estimate_with_budget_marks_warn_levels():
    summary = {
        "tokens_budget_today": 10_000,
        "tokens_used_today": 0,
        "tokens_remaining_today_estimate": 10_000,
    }
    low = estimate_with_budget("generate_draft", {}, summary)
    assert low["budget"]["warn_level"] in {"ok", "warn"}

    summary_hot = {
        "tokens_budget_today": 10_000,
        "tokens_used_today": 9_500,
        "tokens_remaining_today_estimate": 500,
    }
    hot = estimate_with_budget("generate_full", {}, summary_hot)
    assert hot["budget"]["warn_level"] in {"critical", "block"}


def test_estimate_with_budget_handles_zero_budget():
    summary = {
        "tokens_budget_today": 0,
        "tokens_used_today": 0,
        "tokens_remaining_today_estimate": 0,
    }
    out = estimate_with_budget("generate_full", {}, summary)
    assert out["budget"]["warn_level"] == "ok"
    assert out["budget"]["percentage_of_daily_budget"] == 0.0


# --------------------------------------------------------------------------- #
# /api/estimate route
# --------------------------------------------------------------------------- #

def test_api_estimate_happy_path():
    client = TestClient(main.app)
    resp = client.post(
        "/api/estimate",
        json={"kind": "quick_copy", "quantity": 20, "locales": ["en", "ja"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["kind"] == "quick_copy"
    assert body["total_tokens"] > 0
    assert "budget" in body
    assert body["budget"]["warn_level"] in {"ok", "warn", "critical", "block"}


def test_api_estimate_defaults_kind_when_missing():
    client = TestClient(main.app)
    resp = client.post("/api/estimate", json={})
    assert resp.status_code == 200
    assert resp.json()["kind"] in {"generate_full", "generate_draft", "quick_copy", "refresh_copy"}
