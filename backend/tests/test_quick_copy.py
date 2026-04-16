import main


def test_api_quick_copy_cloud_fallback_no_key(client, monkeypatch):
    monkeypatch.setattr(main, "cloud_client", None)
    # keep RAG deterministic
    monkeypatch.setattr(
        main,
        "retrieve_context_with_evidence",
        lambda *_args, **_kwargs: ("ctx", ["src1"], [{"rule": "r1", "match_score": 0.8}]),
    )
    payload = {
        "project_id": "e7ad471c-f8c8-49fa-b0f4-88c127833688",
        "region_id": "region_us_prime",
        "platform_id": "platform_applovin_unity",
        "angle_id": "angle_fail_trap_pro",
        "engine": "cloud",
        "output_mode": "cn",
        "quantity": 20,
        "tones": ["humor", "benefit"],
        "locales": ["en", "ja"],
    }
    resp = client.post("/api/quick-copy", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["script_id"].startswith("COPY-")
    assert data["project_id"] == payload["project_id"]
    assert data.get("markdown_path", "").startswith("@OUT/")
    acm = data["ad_copy_matrix"]
    assert acm["default_locale"] in acm["locales"]
    assert "variants" in acm
    assert "regions" in acm and payload["region_id"] in acm["regions"]
    assert f"{payload['region_id']}:en" in acm["variants"]
    assert len(acm["variants"][f"{payload['region_id']}:en"]["primary_texts"]) >= 5
    assert len(acm["variants"][f"{payload['region_id']}:en"]["headlines"]) == 20
    assert len(acm["variants"][f"{payload['region_id']}:en"]["hashtags"]) >= 20
    assert isinstance(data.get("ad_copy_tiles", []), list)
    assert isinstance(data.get("compliance", {}), dict)


def test_api_quick_copy_multi_region_merges_variants(client, monkeypatch):
    monkeypatch.setattr(main, "cloud_client", None)
    monkeypatch.setattr(
        main,
        "retrieve_context_with_evidence",
        lambda *_args, **_kwargs: ("ctx", ["src1"], [{"rule": "r1", "match_score": 0.8}]),
    )
    payload = {
        "project_id": "e7ad471c-f8c8-49fa-b0f4-88c127833688",
        "region_id": "region_us_prime",
        "region_ids": ["region_us_prime", "region_jp_advanced"],
        "platform_id": "platform_applovin_unity",
        "angle_id": "angle_fail_trap_pro",
        "engine": "cloud",
        "output_mode": "cn",
        "quantity": 20,
        "tones": [],
        "locales": ["en"],
    }
    resp = client.post("/api/quick-copy", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    acm = data["ad_copy_matrix"]
    assert set(acm.get("regions") or []) >= {"region_us_prime", "region_jp_advanced"}
    assert "variants" in acm
    assert "region_us_prime:en" in acm["variants"]
    assert "region_jp_advanced:en" in acm["variants"]


def test_api_quick_copy_refresh_missing_history(client):
    payload = {
        "project_id": "e7ad471c-f8c8-49fa-b0f4-88c127833688",
        "base_script_id": "SOP-NOT-EXIST",
        "engine": "cloud",
        "output_mode": "cn",
        "quantity": 20,
        "tones": [],
        "locales": ["en"],
    }
    resp = client.post("/api/quick-copy/refresh", json=payload)
    # It may be 404 (script_id not found) or 400 (no history) depending on fixture workspace
    assert resp.status_code in (400, 404)

