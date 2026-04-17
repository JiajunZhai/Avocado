import json as _json

import main


def _payload(engine: str = "cloud"):
    return {
        "project_id": "e7ad471c-f8c8-49fa-b0f4-88c127833688",
        "region_id": "region_us_prime",
        "platform_id": "platform_applovin_unity",
        "angle_id": "angle_fail_trap_pro",
        "engine": engine,
        "mode": "director",
    }


def _valid_full_script_result():
    return {
        "hook_score": 82,
        "hook_reasoning": "ok",
        "clarity_score": 83,
        "clarity_reasoning": "ok",
        "conversion_score": 84,
        "conversion_reasoning": "ok",
        "bgm_direction": "bgm",
        "editing_rhythm": "rhythm",
        "script": [
            {
                "time": f"{i}s",
                "visual": f"shot {i}",
                "visual_meaning": "画面中文",
                "audio_content": "a",
                "audio_meaning": "am",
                "text_content": "t",
                "text_meaning": "tm",
                "direction_note": "导演提示",
                "sfx_transition_note": "音效提示",
            }
            for i in range(5)
        ],
        "psychology_insight": "insight",
        "cultural_notes": ["note"],
        "competitor_trend": "trend",
    }


def _fake_cloud(content: str):
    class _Msg:
        def __init__(self, c): self.content = c

    class _Choice:
        def __init__(self, c): self.message = _Msg(c)

    class _Resp:
        def __init__(self, c): self.choices = [_Choice(c)]

    class _Cloud:
        class chat:  # noqa: N801
            class completions:
                @staticmethod
                def create(**_kwargs):
                    return _Resp(content)

    return _Cloud()


def test_e2e_extract_generate_export_flow(client, monkeypatch):
    monkeypatch.setattr(
        main,
        "fetch_playstore_data",
        lambda _url: {"success": True, "title": "Capybara Bomb!"},
    )
    monkeypatch.setattr(
        "scraper.extract_usp_via_llm_with_usage",
        lambda *_args, **_kwargs: ("USP BLOCK", None, False),
    )
    monkeypatch.setattr(main, "cloud_client", None)  # force rule-based fallback path
    extract_resp = client.post(
        "/api/extract-url",
        json={"url": "https://play.google.com/store/apps/details?id=com.zestplay.capybara.defense"},
    )
    assert extract_resp.status_code == 200
    assert extract_resp.json()["success"] is True

    # Generation uses the cloud engine with a mocked DeepSeek client. The former
    # "mock" silent fallback was removed, so either the real cloud path succeeds
    # or the API returns 502.
    monkeypatch.setattr(main, "retrieve_context", lambda *_args, **_kwargs: ("", []))
    monkeypatch.setattr(main, "retrieve_context_with_evidence", lambda *_args, **_kwargs: ("", [], []))
    monkeypatch.setattr(main, "cloud_client", _fake_cloud(_json.dumps(_valid_full_script_result())))

    generate_resp = client.post("/api/generate", json=_payload())
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

    monkeypatch.setattr(
        main,
        "retrieve_context",
        lambda *_args, **_kwargs: ("[Market Context from Vector Intelligence]", ["example-source"]),
    )
    monkeypatch.setattr(
        main,
        "retrieve_context_with_evidence",
        lambda *_args, **_kwargs: (
            "[Market Context from Vector Intelligence]",
            ["example-source"],
            [{"rule": "r1"}],
        ),
    )
    monkeypatch.setattr(main, "cloud_client", _fake_cloud(_json.dumps(_valid_full_script_result())))
    generate_resp = client.post("/api/generate", json=_payload())
    assert generate_resp.status_code == 200
    assert "citations" in generate_resp.json()


def test_e2e_cloud_generation_failure_is_observable(client, monkeypatch):
    """When the cloud director call raises, /api/generate must surface CLOUD_SYNTHESIS_FAILED."""
    monkeypatch.setattr(main, "retrieve_context", lambda *_args, **_kwargs: ("", []))
    monkeypatch.setattr(main, "retrieve_context_with_evidence", lambda *_args, **_kwargs: ("", [], []))

    class _Boom:
        class chat:  # noqa: N801
            class completions:
                @staticmethod
                def create(**_kwargs):
                    raise RuntimeError("cloud down")

    monkeypatch.setattr(main, "cloud_client", _Boom())
    response = client.post("/api/generate", json=_payload())
    assert response.status_code == 502
    detail = response.json()["detail"]
    assert detail["error_code"] == "CLOUD_SYNTHESIS_FAILED"
    assert "cloud down" in detail["error_message"]
