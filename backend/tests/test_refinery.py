import pytest
import refinery

def test_distill_and_store_raises_when_api_key_missing(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    with pytest.raises(Exception, match="DeepSeek API Key missing"):
        refinery.distill_and_store(raw_text="abc", source_url="", year_quarter="2024-Q1")

def test_retrieve_context_returns_empty_on_db_error(monkeypatch):
    class BrokenCollection:
        def query(self, *args, **kwargs):
            raise RuntimeError("db down")

    monkeypatch.setattr(refinery, "collection", BrokenCollection())
    context, citations = refinery.retrieve_context("query")
    assert context == ""
    assert citations == []


def test_region_score_bonus_prefers_matching_region():
    assert refinery._region_score_bonus({"region": "Japan"}, ["Japan"]) > 0.1
    assert refinery._region_score_bonus({"region": "Global"}, ["Japan"]) >= 0.03


def test_retrieve_context_supplement_passes_to_query(monkeypatch):
    seen: dict = {}

    class SpyCollection:
        def query(self, query_texts, n_results=3, region_boost_tokens=None):
            seen["texts"] = query_texts
            seen["boost"] = region_boost_tokens
            return {"documents": [["doc1"]], "metadatas": [[{"source": "s", "year_quarter": "q"}]]}

    monkeypatch.setattr(refinery, "collection", SpyCollection())
    refinery.retrieve_context("a b", top_k=2, supplement="game merge puzzle", region_boost_tokens=["Japan"])
    assert "merge" in seen["texts"][0]
    assert seen["boost"] == ["Japan"]
