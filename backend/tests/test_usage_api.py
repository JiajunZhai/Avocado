import json

import usage_tracker


def test_usage_summary_endpoint(client):
    response = client.get("/api/usage/summary")
    assert response.status_code == 200
    data = response.json()
    assert "tokens_budget_today" in data
    assert "tokens_used_today" in data
    assert "tokens_from_provider_today" in data
    assert "tokens_from_estimate_today" in data
    assert "script_generations_today" in data
    assert "avg_tokens_per_script_today" in data
    assert "last_script_tokens" in data
    assert "billing_quality" in data
    assert "tokens_remaining_today_estimate" in data
    assert "oracle_retrievals_today" in data
    assert "oracle_ingests_today" in data
    assert "token_note" in data


def test_usage_tracker_resets_on_date_change(tmp_path, monkeypatch):
    monkeypatch.setattr(usage_tracker, "_STATE_PATH", tmp_path / "u.json")
    (tmp_path / "u.json").write_text(
        json.dumps(
            {
                "utc_date": "1999-01-01",
                "tokens_used_total": 999,
                "tokens_from_provider_total": 100,
                "tokens_from_estimate_total": 899,
                "oracle_retrievals": 5,
                "oracle_ingests": 2,
            }
        ),
        encoding="utf-8",
    )
    s = usage_tracker.get_summary()
    assert s["oracle_retrievals_today"] == 0
    assert s["tokens_used_today_estimate"] == 0


def test_usage_tracker_script_stats_are_derived(tmp_path, monkeypatch):
    monkeypatch.setattr(usage_tracker, "_STATE_PATH", tmp_path / "u.json")
    usage_tracker.record_generate_success("cloud", measured_tokens=4000)
    usage_tracker.record_generate_success("local", measured_tokens=None)
    s = usage_tracker.get_summary()
    assert s["script_generations_today"] == 2
    assert s["last_script_tokens"] > 0
    assert s["avg_tokens_per_script_today"] > 0
