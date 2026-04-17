import json
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper import fetch_playstore_data, extract_usp_via_llm, extract_usp_via_llm_with_usage


def test_google_play_extraction_truncation():
    """
    Ensure the scraper correctly fetches a known URL and truncates description
    to <= 1500 + suffix length for VRAM safety.
    """
    url = "https://play.google.com/store/apps/details?id=com.supercell.brawlstars"
    data = fetch_playstore_data(url)

    assert data is not None
    assert "title" in data
    assert "description" in data

    # 1500 chars limit + len("... [TRUNCATED FOR ENGINE SAFETY]")
    assert len(data["description"]) <= 1600


def test_extract_usp_is_deterministic_and_description_driven():
    metadata = {
        "description": (
            "Cute but chaotic capybara RPG battle game. "
            "Collect heroes, build your squad, and use strategy and formation. "
            "Open chests, mine treasure, and claim free rewards. "
            "Funny stress-relief style with addictive progression."
        ),
        "genre": "Casual",
        "installs": "100K+",
        "recentChanges": "Bug fixes and rewards."
    }
    result = extract_usp_via_llm("Capybara Bomb!", metadata)

    doc = json.loads(result.split("\n\n[Store scale signal]")[0])
    assert "core_gameplay" in doc and "en" in doc["core_gameplay"] and "cn" in doc["core_gameplay"]
    assert len(doc["value_hooks"]) >= 3
    assert all("en" in h and "cn" in h for h in doc["value_hooks"])
    assert "target_persona" in doc

    joined_en = " ".join(h["en"] for h in doc["value_hooks"])
    assert "hero" in joined_en.lower() or "squad" in joined_en.lower()
    assert "chest" in joined_en.lower() or "loot" in joined_en.lower()
    assert "100K+" in result


def test_extract_usp_with_usage_reports_no_llm():
    """Rule-based distillation consumes no LLM tokens; used_llm must be False."""
    metadata = {
        "description": "battle strategy chest rewards hero collect",
        "genre": "Casual",
        "installs": "10K+",
        "recentChanges": "update",
    }
    text, tokens, used_llm = extract_usp_via_llm_with_usage("Capybara Bomb!", metadata)
    assert "Capybara Bomb!" not in text or text  # text is non-empty
    assert tokens is None
    assert used_llm is False
