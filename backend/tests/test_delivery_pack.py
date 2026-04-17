"""Phase 24 / C4 — Delivery Pack export.

Covers:
- POST /api/export/delivery-pack happy path (produces zip with expected
  entries: README.md + payload.json always, plus script.md / ad_copy.csv
  conditionally).
- Rejects non-object `data` fields.
- Zip contents carry the CSV matrix with a locale x slot table and a JSON
  payload that round-trips the original response body.
"""
from __future__ import annotations

import base64
import io
import json
import zipfile

import pytest


def _zip_from_b64(b64: str) -> zipfile.ZipFile:
    blob = base64.b64decode(b64.encode("ascii"))
    return zipfile.ZipFile(io.BytesIO(blob), mode="r")


def test_delivery_pack_with_ad_copy_matrix(client):
    payload = {
        "data": {
            "script_id": "SOP-ABC123",
            "project_id": "fixture-proj",
            "partial_failure": False,
            "ad_copy_matrix": {
                "default_locale": "en",
                "locales": ["en", "ja"],
                "variants": {
                    "en": {
                        "headlines": ["Hit A", "Hit B"],
                        "primary_texts": ["Body A"],
                        "hashtags": ["#one", "#two"],
                    },
                    "ja": {
                        "headlines": ["ジェイA"],
                        "primary_texts": [],
                        "hashtags": [],
                    },
                },
            },
            "compliance": {"risk_level": "ok", "hits": []},
        },
        "markdown_path": None,
        "project_name": "Fixture Project",
    }
    resp = client.post("/api/export/delivery-pack", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["filename"].endswith(".zip")
    assert body["size_bytes"] > 0
    assert "README.md" in body["entries"]
    assert "payload.json" in body["entries"]
    assert "ad_copy.csv" in body["entries"]
    # script.md is absent when markdown_path cannot be resolved
    assert "script.md" not in body["entries"]

    z = _zip_from_b64(body["zip_base64"])
    names = set(z.namelist())
    assert {"README.md", "payload.json", "ad_copy.csv"}.issubset(names)
    assert "script.md" not in names

    csv_body = z.read("ad_copy.csv").decode("utf-8")
    lines = csv_body.strip().splitlines()
    assert lines[0] == "locale,slot,headline,primary_text,hashtags"
    assert any("Hit A" in l for l in lines)
    assert any("ジェイA" in l for l in lines)

    json_body = json.loads(z.read("payload.json").decode("utf-8"))
    assert json_body["script_id"] == "SOP-ABC123"
    assert json_body["ad_copy_matrix"]["locales"] == ["en", "ja"]

    readme = z.read("README.md").decode("utf-8")
    assert "SOP-ABC123" in readme
    assert "Fixture Project" in readme


def test_delivery_pack_rejects_non_object_data(client):
    resp = client.post("/api/export/delivery-pack", json={"data": ["not", "an", "object"]})
    # FastAPI's pydantic coercion currently rejects a list where a dict is
    # expected with a 422 validation error. Either response is acceptable as
    # long as it's not a 200 success.
    assert resp.status_code in (400, 422)


def test_delivery_pack_without_ad_copy_matrix(client):
    resp = client.post(
        "/api/export/delivery-pack",
        json={"data": {"script_id": "SOP-NOCOPY", "script": [{"line": 1, "body": "hello"}]}},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "ad_copy.csv" not in body["entries"]
    assert "payload.json" in body["entries"]
    z = _zip_from_b64(body["zip_base64"])
    assert "ad_copy.csv" not in z.namelist()
