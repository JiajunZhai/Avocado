"""Phase 23 / B4 — Partial failure protocol for multi-region quick_copy."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import main


# --------------------------------------------------------------------------- #
# fixtures
# --------------------------------------------------------------------------- #

def _write_workspace(project_id: str, data: dict) -> Path:
    """Phase 26/E — seed both the legacy JSON and the SQLite projects table."""
    ws_dir = Path(main.__file__).parent / "data" / "workspaces"
    ws_dir.mkdir(parents=True, exist_ok=True)
    path = ws_dir / f"{project_id}.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    from projects_api import save_project

    save_project(dict(data))
    return path


def _load_workspace(project_id: str) -> dict:
    from projects_api import load_project

    record = load_project(project_id)
    if record is not None:
        return record
    path = Path(main.__file__).parent / "data" / "workspaces" / f"{project_id}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


class _FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self, scripted):
        self._scripted = scripted
        self.call_count = 0

    def create(self, *args, **kwargs):  # noqa: ANN001
        idx = self.call_count
        self.call_count += 1
        if idx >= len(self._scripted):
            raise RuntimeError("unexpected extra LLM call")
        result = self._scripted[idx]
        if isinstance(result, Exception):
            raise result
        return _FakeResponse(json.dumps(result))


class _FakeChat:
    def __init__(self, scripted):
        self.completions = _FakeCompletions(scripted)


class _FakeClient:
    def __init__(self, scripted):
        self.chat = _FakeChat(scripted)


def _good_copy_payload() -> dict:
    return {
        "ad_copy_matrix": {
            "default_locale": "en",
            "locales": ["en"],
            "variants": {
                "en": {
                    "primary_texts": ["a", "b", "c", "d", "e"],
                    "headlines": ["🔥 h1", "🔥 h2", "🔥 h3", "🔥 h4", "🔥 h5", "🔥 h6", "🔥 h7", "🔥 h8", "🔥 h9", "🔥 h10"],
                    "hashtags": [f"#tag{i}" for i in range(20)],
                }
            },
        }
    }


# --------------------------------------------------------------------------- #
# tests
# --------------------------------------------------------------------------- #

def test_quick_copy_one_region_fails_but_others_succeed(client, monkeypatch):
    scripted = [_good_copy_payload(), RuntimeError("upstream boom"), _good_copy_payload()]
    monkeypatch.setattr(main, "cloud_client", _FakeClient(scripted))
    monkeypatch.setattr(
        main,
        "retrieve_context_with_evidence",
        lambda *a, **k: ("ctx", [], []),
    )
    project_id = "b4-fixture-partial"
    ws_path = _write_workspace(
        project_id,
        {
            "id": project_id,
            "name": "B4 Fixture",
            "game_info": {"core_usp": "Demo"},
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
                "region_ids": ["region_us_prime", "region_jp_advanced", "region_kr"],
                "platform_id": "platform_applovin_unity",
                "angle_id": "angle_fail_trap_pro",
                "output_mode": "cn",
                "quantity": 10,
                "locales": ["en"],
            },
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["partial_failure"] is True
        rs = body["ad_copy_matrix"]["regions_status"]
        assert rs["region_us_prime"] == "ok"
        assert rs["region_jp_advanced"] == "failed"
        assert rs["region_kr"] == "ok"
        # Failure message surfaces (truncated)
        errs = body["ad_copy_matrix"]["regions_error"]
        assert "upstream" in errs.get("region_jp_advanced", "").lower()
        # The two successful regions still contribute variants.
        locales_out = body["ad_copy_matrix"]["locales"]
        assert any(k.startswith("region_us_prime:") for k in locales_out)
        assert any(k.startswith("region_kr:") for k in locales_out)
        # history entry flagged as fallback
        saved = _load_workspace(project_id)
        entry = saved["history_log"][-1]
        assert entry["draft_status"] == "fallback"
    finally:
        try:
            ws_path.unlink()
        except Exception:
            pass


def test_quick_copy_all_ok_sets_partial_failure_false(client, monkeypatch):
    scripted = [_good_copy_payload()]
    monkeypatch.setattr(main, "cloud_client", _FakeClient(scripted))
    monkeypatch.setattr(
        main,
        "retrieve_context_with_evidence",
        lambda *a, **k: ("ctx", [], []),
    )
    project_id = "b4-fixture-ok"
    ws_path = _write_workspace(
        project_id,
        {
            "id": project_id,
            "name": "B4 OK",
            "game_info": {"core_usp": "Demo"},
            "history_log": [],
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
                "quantity": 10,
                "locales": ["en"],
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["partial_failure"] is False
        assert body["ad_copy_matrix"]["regions_status"]["region_us_prime"] == "ok"
    finally:
        try:
            ws_path.unlink()
        except Exception:
            pass


def test_retry_region_merges_successful_payload_back(client, monkeypatch):
    # First: 2 regions where region_jp_advanced fails, region_us_prime succeeds.
    first = [_good_copy_payload(), RuntimeError("jp down")]
    monkeypatch.setattr(main, "cloud_client", _FakeClient(first))
    monkeypatch.setattr(
        main,
        "retrieve_context_with_evidence",
        lambda *a, **k: ("ctx", [], []),
    )
    project_id = "b4-fixture-retry"
    ws_path = _write_workspace(
        project_id,
        {
            "id": project_id,
            "name": "Retry Fixture",
            "game_info": {"core_usp": "Demo"},
            "history_log": [],
        },
    )
    try:
        resp = client.post(
            "/api/quick-copy",
            json={
                "project_id": project_id,
                "region_id": "region_us_prime",
                "region_ids": ["region_us_prime", "region_jp_advanced"],
                "platform_id": "platform_applovin_unity",
                "angle_id": "angle_fail_trap_pro",
                "quantity": 10,
                "locales": ["en"],
            },
        )
        assert resp.status_code == 200
        first_body = resp.json()
        assert first_body["partial_failure"] is True
        script_id = first_body["script_id"]

        # Second call: retry JP, this time succeeds.
        monkeypatch.setattr(main, "cloud_client", _FakeClient([_good_copy_payload()]))
        retry_resp = client.post(
            "/api/quick-copy/retry-region",
            json={
                "project_id": project_id,
                "script_id": script_id,
                "region_id": "region_jp_advanced",
            },
        )
        assert retry_resp.status_code == 200, retry_resp.text
        retry_body = retry_resp.json()
        rs = retry_body["ad_copy_matrix"]["regions_status"]
        assert rs["region_jp_advanced"] == "ok"
        assert rs["region_us_prime"] == "ok"
        assert retry_body["partial_failure"] is False
        # history entry updated in place
        saved = _load_workspace(project_id)
        entry = [e for e in saved["history_log"] if e.get("id") == script_id][0]
        assert entry["ad_copy_matrix"]["regions_status"]["region_jp_advanced"] == "ok"
        assert entry["partial_failure"] is False
    finally:
        try:
            ws_path.unlink()
        except Exception:
            pass


def test_retry_region_rejects_non_copy_scripts(client, monkeypatch):
    project_id = "b4-fixture-reject"
    ws_path = _write_workspace(
        project_id,
        {
            "id": project_id,
            "name": "Reject Fixture",
            "game_info": {"core_usp": "Demo"},
            "history_log": [
                {
                    "id": "SOP-XYZ",
                    "timestamp": "2025-01-01T00:00:00Z",
                    "output_kind": "sop",
                    "recipe": {
                        "region": "region_us_prime",
                        "platform": "platform_applovin_unity",
                        "angle": "angle_fail_trap_pro",
                    },
                    "ad_copy_matrix": {},
                }
            ],
        },
    )
    try:
        resp = client.post(
            "/api/quick-copy/retry-region",
            json={
                "project_id": project_id,
                "script_id": "SOP-XYZ",
                "region_id": "region_jp_advanced",
            },
        )
        assert resp.status_code == 400
    finally:
        try:
            ws_path.unlink()
        except Exception:
            pass
