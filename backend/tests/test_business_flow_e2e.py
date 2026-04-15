import main
from ollama_client import LocalLLMResult


def _payload(engine: str = "cloud"):
    return {
        "project_id": "e7ad471c-f8c8-49fa-b0f4-88c127833688",
        "region_id": "region_us_prime",
        "platform_id": "platform_applovin_unity",
        "angle_id": "angle_fail_trap_pro",
        "engine": engine,
    }


def test_e2e_extract_generate_export_flow(client, monkeypatch):
    monkeypatch.setattr(
        main,
        "fetch_playstore_data",
        lambda _url: {"success": True, "title": "Capybara Bomb!"},
    )
    monkeypatch.setattr(main, "extract_usp_via_llm_with_usage", lambda *_args: ("USP BLOCK", None, False))
    extract_resp = client.post(
        "/api/extract-url",
        json={"url": "https://play.google.com/store/apps/details?id=com.zestplay.capybara.defense", "engine": "cloud"},
    )
    assert extract_resp.status_code == 200
    assert extract_resp.json()["success"] is True

    monkeypatch.setattr(main, "retrieve_context", lambda *_args, **_kwargs: ("", []))
    monkeypatch.setattr(main, "cloud_client", None)
    generate_resp = client.post("/api/generate", json=_payload(engine="cloud"))
    assert generate_resp.status_code == 200
    generated = generate_resp.json()
    assert isinstance(generated.get("script"), list) and len(generated["script"]) > 0

    monkeypatch.setattr(main, "generate_pdf_report", lambda _data: "ZmFrZV9wZGY=")
    export_resp = client.post("/api/export/pdf", json={"data": generated})
    assert export_resp.status_code == 200
    assert export_resp.json()["success"] is True


def test_e2e_oracle_ingest_then_generate_contains_citations(client, monkeypatch):
    monkeypatch.setattr(
        main,
        "distill_and_store",
        lambda *_args, **_kwargs: {"success": True, "extracted_count": 2, "error": ""},
    )
    ingest_resp = client.post(
        "/api/refinery/ingest",
        json={"raw_text": "report text", "source_url": "https://example.com", "year_quarter": "2026-Q2"},
    )
    assert ingest_resp.status_code == 200
    assert ingest_resp.json()["success"] is True

    monkeypatch.setattr(main, "retrieve_context", lambda *_args, **_kwargs: ("[Market Context from Vector Intelligence]", ["example-source"]))
    monkeypatch.setattr(main, "cloud_client", None)
    generate_resp = client.post("/api/generate", json=_payload(engine="cloud"))
    assert generate_resp.status_code == 200
    assert "citations" in generate_resp.json()


def test_e2e_local_generation_failure_is_observable(client, monkeypatch):
    monkeypatch.setattr(main, "retrieve_context", lambda *_args, **_kwargs: ("", []))
    monkeypatch.setattr(
        "ollama_client.generate_with_local_llm",
        lambda **_kwargs: LocalLLMResult(
            {
                "success": False,
                "error_code": "LOCAL_REQUEST_FAILED",
                "error_message": "Local Ollama request failed.",
                "raw_excerpt": "",
            },
            None,
        ),
    )
    response = client.post("/api/generate", json=_payload(engine="local"))
    assert response.status_code == 502
    detail = response.json()["detail"]
    assert detail["error_code"] == "LOCAL_REQUEST_FAILED"
