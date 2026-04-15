"""Smoke tests for Markdown synthesis export."""

from md_export import export_markdown_after_generate, synthesis_to_markdown


def test_synthesis_to_markdown_contains_script_id():
    payload = {
        "script_id": "SOP-TEST01",
        "hook_score": 80,
        "hook_reasoning": "r1",
        "clarity_score": 81,
        "clarity_reasoning": "r2",
        "conversion_score": 82,
        "conversion_reasoning": "r3",
        "bgm_direction": "bgm",
        "editing_rhythm": "cut",
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
        "psychology_insight": "psi",
        "cultural_notes": ["n1"],
        "competitor_trend": "tr",
        "citations": ["c1"],
    }
    md = synthesis_to_markdown("Proj", {"region": "r", "platform": "p", "angle": "a"}, "mock", payload)
    assert "SOP-TEST01" in md
    assert "## 分镜脚本" in md
    assert "**画面**" in md
    assert "**画面释义（中文）**" not in md
    assert "**配音释义**" not in md
    assert "**贴纸释义**" not in md


def test_export_markdown_writes_under_out(tmp_path, monkeypatch):
    monkeypatch.setattr("md_export.repo_root", lambda: tmp_path)
    rel = export_markdown_after_generate(
        "proj-1",
        "My Game",
        {
            "region": "region_x",
            "platform": "plat_y",
            "angle": "ang_z",
            "region_name": "United States Prime",
            "platform_name": "TikTok Advanced",
            "angle_name": "Emergency Rescue",
            "region_short": "US",
            "platform_short": "TikTok",
            "angle_short": "Rescue",
        },
        "mock",
        {
            "script_id": "SOP-AB12CD",
            "hook_score": 1,
            "hook_reasoning": "x",
            "clarity_score": 1,
            "clarity_reasoning": "x",
            "conversion_score": 1,
            "conversion_reasoning": "x",
            "bgm_direction": "b",
            "editing_rhythm": "e",
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
            "psychology_insight": "p",
            "cultural_notes": [],
            "competitor_trend": "t",
            "citations": [],
        },
    )
    assert rel is not None
    assert rel.startswith("@OUT/")
    from pathlib import Path

    out_file = tmp_path.joinpath(*Path(rel).parts)
    assert out_file.is_file()
    assert out_file.read_text(encoding="utf-8").startswith("#")
    assert "CN_" in out_file.name
    assert "My_Game" in out_file.name
    assert "_US_" in out_file.name
    assert "_TikTok_" in out_file.name
    assert "_Rescue_" in out_file.name
    assert "SOP-AB12CD" in out_file.name


def test_synthesis_to_markdown_supports_english_mode():
    payload = {
        "script_id": "SOP-EN01",
        "hook_score": 80,
        "hook_reasoning": "r1",
        "clarity_score": 81,
        "clarity_reasoning": "r2",
        "conversion_score": 82,
        "conversion_reasoning": "r3",
        "bgm_direction": "bgm",
        "editing_rhythm": "cut",
        "script": [
            {
                "time": "0s",
                "visual": "show gameplay",
                "visual_meaning": "中文",
                "audio_content": "voice",
                "audio_meaning": "notes",
                "text_content": "tap now",
                "text_meaning": "说明",
                "direction_note": "dir",
                "sfx_transition_note": "sfx",
            }
        ],
        "psychology_insight": "psi",
        "cultural_notes": ["n1"],
        "competitor_trend": "tr",
        "citations": ["c1"],
    }
    md = synthesis_to_markdown("Proj", {"region": "r", "platform": "p", "angle": "a"}, "cloud", payload, "en")
    assert "# Video Script (SOP Output)" in md
    assert "## Storyboard" in md
    assert "**Visual**" in md


def test_cn_mode_localizes_non_voice_fields(monkeypatch):
    monkeypatch.setattr("md_export._translate_for_mode", lambda text, mode: f"CN:{text}" if mode == "cn" else text)
    payload = {
        "script_id": "SOP-CN01",
        "hook_score": 80,
        "hook_reasoning": "Hook reason",
        "clarity_score": 81,
        "clarity_reasoning": "Clarity reason",
        "conversion_score": 82,
        "conversion_reasoning": "Conversion reason",
        "bgm_direction": "BGM text",
        "editing_rhythm": "Rhythm text",
        "script": [
            {
                "time": "0s",
                "visual": "Visual EN",
                "visual_meaning": "Visual meaning EN",
                "audio_content": "Original voice",
                "audio_meaning": "Voice notes EN",
                "text_content": "Original sticker",
                "text_meaning": "Sticker notes EN",
                "direction_note": "Direction EN",
                "sfx_transition_note": "SFX EN",
            }
        ],
        "psychology_insight": "Psych EN",
        "cultural_notes": ["Note EN"],
        "competitor_trend": "Trend EN",
        "citations": [],
    }
    md = synthesis_to_markdown("Proj", {"region": "r", "platform": "p", "angle": "a"}, "cloud", payload, "cn")
    assert "CN:Visual meaning EN" in md
    assert "Original voice" in md
    assert "Original sticker" in md


def test_en_mode_localizes_notes_but_keeps_voice_and_text():
    payload = {
        "script_id": "SOP-EN02",
        "hook_score": 80,
        "hook_reasoning": "钩子",
        "clarity_score": 81,
        "clarity_reasoning": "清晰",
        "conversion_score": 82,
        "conversion_reasoning": "转化",
        "bgm_direction": "节奏",
        "editing_rhythm": "快切",
        "script": [
            {
                "time": "0s",
                "visual": "show gameplay",
                "visual_meaning": "中文视觉",
                "audio_content": "原始配音",
                "audio_meaning": "配音释义",
                "text_content": "原始贴纸",
                "text_meaning": "贴纸释义",
                "direction_note": "导演提示",
                "sfx_transition_note": "音效提示",
            }
        ],
        "psychology_insight": "心理洞察",
        "cultural_notes": ["文化注释"],
        "competitor_trend": "趋势",
        "citations": [],
    }
    md = synthesis_to_markdown("Proj", {"region": "r", "platform": "p", "angle": "a"}, "cloud", payload, "en")
    assert "Original" not in md  # sanity guard for this fixture
    assert "原始配音" in md
    assert "原始贴纸" in md
