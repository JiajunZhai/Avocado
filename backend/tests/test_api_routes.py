import main
from ollama_client import LocalLLMResult

def _base_generate_payload(engine: str = "cloud"):
    """Valid body for POST /api/generate (matches workspace + insight JSON ids in repo fixtures)."""
    return {
        "project_id": "e7ad471c-f8c8-49fa-b0f4-88c127833688",
        "region_id": "region_us_prime",
        "platform_id": "platform_applovin_unity",
        "angle_id": "angle_fail_trap_pro",
        "engine": engine,
    }

def _valid_script_result():
    return {
        "hook_score": 80,
        "hook_reasoning": "ok",
        "clarity_score": 81,
        "clarity_reasoning": "ok",
        "conversion_score": 82,
        "conversion_reasoning": "ok",
        "bgm_direction": "bgm",
        "editing_rhythm": "rhythm",
        "script": [
            {
                "time": "0s",
                "visual": "v",
                "visual_meaning": "画面中文",
                "audio_content": "a",
                "audio_meaning": "am",
                "text_content": "t",
                "text_meaning": "tm",
                "direction_note": "导演提示",
                "sfx_transition_note": "音效提示",
            }
        ],
        "psychology_insight": "insight",
        "cultural_notes": ["note"],
        "competitor_trend": "trend"
    }

def test_api_generate_local_success(client, monkeypatch):
    monkeypatch.setattr(main, "retrieve_context", lambda *_args, **_kwargs: ("ctx", ["src1"]))
    monkeypatch.setattr(
        "ollama_client.generate_with_local_llm",
        lambda **_kwargs: LocalLLMResult(_valid_script_result(), 1200)
    )

    response = client.post("/api/generate", json=_base_generate_payload(engine="local"))
    assert response.status_code == 200
    data = response.json()
    assert data["hook_score"] == 80
    assert data["citations"] == ["src1"]
    assert data.get("markdown_path")
    assert data["markdown_path"].startswith("@OUT/")
    assert data["markdown_path"].endswith(".md")

def test_api_generate_local_parse_failure(client, monkeypatch):
    monkeypatch.setattr(main, "retrieve_context", lambda *_args, **_kwargs: ("", []))
    monkeypatch.setattr(
        "ollama_client.generate_with_local_llm",
        lambda **_kwargs: LocalLLMResult(
            {
                "success": False,
                "error_code": "LOCAL_JSON_PARSE_FAILED",
                "error_message": "Local model output is not valid JSON.",
                "raw_excerpt": "not-json",
            },
            None,
        )
    )

    response = client.post("/api/generate", json=_base_generate_payload(engine="local"))
    assert response.status_code == 502
    detail = response.json()["detail"]
    assert detail["error_code"] == "LOCAL_JSON_PARSE_FAILED"

def test_api_generate_local_schema_mismatch(client, monkeypatch):
    monkeypatch.setattr(main, "retrieve_context", lambda *_args, **_kwargs: ("", []))
    monkeypatch.setattr(
        "ollama_client.generate_with_local_llm",
        lambda **_kwargs: LocalLLMResult({"hook_score": 1}, None)
    )

    response = client.post("/api/generate", json=_base_generate_payload(engine="local"))
    assert response.status_code == 502
    detail = response.json()["detail"]
    assert detail["error_code"] == "LOCAL_SCHEMA_MISMATCH"

def test_api_generate_cloud_fallback_when_no_key(client, monkeypatch):
    monkeypatch.setattr(main, "retrieve_context", lambda *_args, **_kwargs: ("", []))
    monkeypatch.setattr(main, "cloud_client", None)
    response = client.post("/api/generate", json=_base_generate_payload(engine="cloud"))
    assert response.status_code == 200
    data = response.json()
    assert data["hook_score"] == 95
    assert data.get("markdown_path", "").startswith("@OUT/")

def test_api_extract_url_success(client, monkeypatch):
    monkeypatch.setattr(main, "fetch_playstore_data", lambda _url: {"success": True, "title": "GameA"})
    monkeypatch.setattr("scraper.extract_usp_via_llm_with_usage", lambda *_args: ("USP A", None, False))
    monkeypatch.setattr(main, "cloud_client", None)
    response = client.post("/api/extract-url", json={"url": "https://x", "engine": "cloud"})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["extracted_usp"] == "USP A"

def test_api_extract_url_failure(client, monkeypatch):
    monkeypatch.setattr(main, "fetch_playstore_data", lambda _url: {"success": False, "error": "boom"})
    response = client.post("/api/extract-url", json={"url": "https://x", "engine": "cloud"})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert data["error"] == "boom"

def test_api_export_pdf_success(client, monkeypatch):
    monkeypatch.setattr(main, "generate_pdf_report", lambda _data: "ZmFrZV9wZGY=")
    response = client.post("/api/export/pdf", json={"data": _valid_script_result()})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["pdf_base64"] == "ZmFrZV9wZGY="

def test_api_export_pdf_rejects_error_placeholder(client):
    bad_data = _valid_script_result()
    bad_data["hook_reasoning"] = "Ollama parsing failure"
    response = client.post("/api/export/pdf", json={"data": bad_data})
    assert response.status_code == 400

def test_api_export_pdf_handles_exception(client, monkeypatch):
    monkeypatch.setattr(main, "generate_pdf_report", lambda _data: (_ for _ in ()).throw(Exception("pdf fail")))
    response = client.post("/api/export/pdf", json={"data": _valid_script_result()})
    assert response.status_code == 500

def test_api_ingest_oracle_invalid_empty(client, monkeypatch):
    monkeypatch.setattr(main, "distill_and_store", lambda *_args, **_kwargs: {"success": False, "error": "invalid input"})
    payload = {
        "raw_text": "",
        "source_url": "",
        "year_quarter": "2024-Q1"
    }
    response = client.post("/api/refinery/ingest", json=payload)
    data = response.json()
    assert data["success"] is False
