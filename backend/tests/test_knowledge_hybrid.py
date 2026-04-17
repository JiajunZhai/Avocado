"""Phase 26 / E4 — knowledge store + hybrid retrieval.

Keeps the suite dependency-free (``RAG_RETRIEVAL=tfidf`` from conftest) so we
don't pull ``sentence-transformers`` in CI. The tests assert:

- Seed populated ``knowledge_docs`` from the legacy JSON corpus.
- FTS5 virtual table mirrors the corpus and answers MATCH queries.
- Reciprocal Rank Fusion merges BM25 + TF-IDF candidates deterministically.
- The reason-tag grouping appears in the composed context string.
"""
from __future__ import annotations

import pytest


def test_seeded_knowledge_has_docs_and_fts():
    from db import has_fts_table
    from refinery import collection

    assert collection.count() >= 10
    assert has_fts_table()


def test_fts5_match_returns_results_for_core_rule_vocab():
    from refinery import collection

    # These tokens appear verbatim in the seeded corpus.
    for q in ("hook", "gameplay", "satisfying"):
        bm25 = collection._bm25_topn(q, 5)
        assert bm25, f"BM25 returned no rows for query={q!r}"


def test_rrf_fuse_sums_reciprocal_ranks():
    from refinery import KnowledgeStore

    a = [("doc_a", 0.9), ("doc_b", 0.8), ("doc_c", 0.7)]
    b = [("doc_b", 0.6), ("doc_a", 0.5)]
    fused = KnowledgeStore._rrf_fuse([a, b], k=60)
    # doc_b and doc_a appear in both, doc_c only once.
    assert fused["doc_b"] > fused["doc_c"]
    assert fused["doc_a"] > fused["doc_c"]


def test_retrieve_context_returns_reason_grouped_text():
    from refinery import retrieve_context_with_evidence

    ctx, cits, ev = retrieve_context_with_evidence(
        "satisfying hook gameplay",
        top_k=3,
        supplement="first 3 seconds highlight",
        region_boost_tokens=["Global"],
    )
    assert ctx, "context should not be empty"
    assert "Market Context" in ctx
    assert isinstance(ev, list) and ev
    for item in ev:
        assert "reason_tag" in item
        assert "rule" in item


def test_knowledge_stats_endpoint(client):
    resp = client.get("/api/knowledge/stats")
    assert resp.status_code == 200
    body = resp.json()
    assert "total_rules" in body
    assert "retrieval_backend" in body
    assert isinstance(body.get("fts5"), bool)
