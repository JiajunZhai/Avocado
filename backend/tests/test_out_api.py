import os
from pathlib import Path

from md_export import repo_root


def test_api_out_markdown_reads_file(client):
    out_dir = repo_root() / "@OUT" / "_pytest"
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / "hello.md"
    p.write_text("# Hello\n\nworld\n", encoding="utf-8")

    rel = "@OUT/_pytest/hello.md"
    resp = client.get("/api/out/markdown", params={"path": rel})
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("success") is True
    assert "Hello" in (data.get("markdown") or "")


def test_api_out_markdown_rejects_traversal(client):
    resp = client.get("/api/out/markdown", params={"path": "@OUT/../secrets.md"})
    assert resp.status_code == 400


def test_api_out_open_folder_is_localhost_gated(client):
    # Starlette testclient host is not localhost/127.0.0.1, should be forbidden by default.
    resp = client.post("/api/out/open-folder", json={"path": "@OUT/_pytest/hello.md"})
    assert resp.status_code == 403

