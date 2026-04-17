import main


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

def test_api_generate_cloud_success(client, monkeypatch):
    """engine=cloud end-to-end: director stage returns a valid JSON script."""
    import json as _json

    monkeypatch.setattr(
        main,
        "retrieve_context_with_evidence",
        lambda *_args, **_kwargs: ("ctx", ["src1"], [{"rule": "r1", "match_score": 0.8}]),
    )

    script_json = _json.dumps(_valid_script_result())

    class _FakeMsg:
        def __init__(self, content): self.content = content

    class _FakeChoice:
        def __init__(self, content): self.message = _FakeMsg(content)

    class _FakeResponse:
        def __init__(self, content): self.choices = [_FakeChoice(content)]

    class _FakeCloud:
        class chat:  # noqa: N801
            class completions:
                @staticmethod
                def create(**_kwargs):
                    return _FakeResponse(script_json)

    monkeypatch.setattr(main, "cloud_client", _FakeCloud())
    payload = _base_generate_payload(engine="cloud")
    payload["mode"] = "director"
    response = client.post("/api/generate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["hook_score"] == 80
    assert data["citations"] == ["src1"]
    assert data.get("markdown_path")
    assert data["markdown_path"].startswith("@OUT/")
    assert data["markdown_path"].endswith(".md")
    assert "review" in data
    assert "generation_metrics" in data
    assert "ad_copy_matrix" in data
    acm = data["ad_copy_matrix"]
    assert isinstance(acm.get("primary_texts"), list) and len(acm["primary_texts"]) >= 5
    assert isinstance(acm.get("headlines"), list) and len(acm["headlines"]) >= 10
    assert isinstance(acm.get("hashtags"), list) and len(acm["hashtags"]) >= 20
    assert isinstance(acm.get("visual_stickers"), list) and len(acm["visual_stickers"]) >= 1


def test_api_generate_cloud_fails_loud_without_key(client, monkeypatch):
    """When engine=cloud but DEEPSEEK_API_KEY is absent, the request must 502 instead of
    silently falling back to a useless single-shot mock SOP."""
    monkeypatch.setattr(main, "retrieve_context_with_evidence", lambda *_args, **_kwargs: ("", [], []))
    monkeypatch.setattr(main, "cloud_client", None)
    response = client.post("/api/generate", json=_base_generate_payload(engine="cloud"))
    assert response.status_code == 502
    detail = response.json()["detail"]
    assert detail["error_code"] == "CLOUD_UNAVAILABLE"


def test_api_generate_cloud_director_failure_surfaces(client, monkeypatch):
    """If the cloud director call explodes, caller must see CLOUD_SYNTHESIS_FAILED (not a mock)."""
    monkeypatch.setattr(main, "retrieve_context_with_evidence", lambda *_args, **_kwargs: ("", [], []))

    class _Boom:
        class chat:  # noqa: N801 (matches openai shape)
            class completions:
                @staticmethod
                def create(**_kwargs):
                    raise RuntimeError("boom director")

    monkeypatch.setattr(main, "cloud_client", _Boom())
    payload = _base_generate_payload(engine="cloud")
    payload["mode"] = "director"  # skip draft so the boom is unambiguously at director stage
    response = client.post("/api/generate", json=payload)
    assert response.status_code == 502
    detail = response.json()["detail"]
    assert detail["error_code"] == "CLOUD_SYNTHESIS_FAILED"
    assert "boom director" in detail["error_message"]
    assert isinstance(detail.get("elapsed_ms"), int)


def test_api_generate_draft_mode_returns_candidates(client, monkeypatch):
    """Draft mode must reach the model; we mock the cloud client so it returns a real JSON draft set."""
    import json as _json

    draft_json = _json.dumps({
        "drafts": [
            {
                "id": "D1",
                "title": "Fast hook",
                "hook": "Start with stakes",
                "story_arc": "stakes -> payoff",
                "gameplay_bridge": "show mechanic in 2 shots",
                "risk_flags": [],
                "estimated_ctr": 81,
                "estimated_quality": 79,
            }
        ],
        "pick_recommendation": "D1",
    })

    class _FakeMsg:
        def __init__(self, content): self.content = content

    class _FakeChoice:
        def __init__(self, content): self.message = _FakeMsg(content)

    class _FakeResponse:
        def __init__(self, content): self.choices = [_FakeChoice(content)]

    class _FakeCloud:
        class chat:  # noqa: N801
            class completions:
                @staticmethod
                def create(**_kwargs):
                    return _FakeResponse(draft_json)

    monkeypatch.setattr(main, "retrieve_context_with_evidence", lambda *_args, **_kwargs: ("", [], []))
    monkeypatch.setattr(main, "cloud_client", _FakeCloud())
    payload = _base_generate_payload(engine="cloud")
    payload["mode"] = "draft"
    response = client.post("/api/generate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data.get("drafts"), list) and data["drafts"]
    assert data.get("generation_metrics", {}).get("mode") == "draft"

def test_api_extract_url_success(client, monkeypatch):
    monkeypatch.setattr(main, "fetch_playstore_data", lambda _url: {"success": True, "title": "GameA"})
    monkeypatch.setattr("scraper.extract_usp_via_llm_with_usage", lambda *_args, **_kwargs: ("USP A", None, False))
    monkeypatch.setattr(main, "cloud_client", None)
    response = client.post("/api/extract-url", json={"url": "https://x"})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["extracted_usp"] == "USP A"

def test_api_extract_url_failure(client, monkeypatch):
    monkeypatch.setattr(main, "fetch_playstore_data", lambda _url: {"success": False, "error": "boom"})
    response = client.post("/api/extract-url", json={"url": "https://x"})
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
    bad_data["hook_reasoning"] = "CLOUD_SYNTHESIS_FAILED upstream"
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
